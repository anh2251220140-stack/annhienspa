"""Chat request reservation, execution and persistence."""

from datetime import datetime, time, timedelta
import logging
from math import ceil
from time import monotonic, sleep

from django.conf import settings
from django.contrib.auth.models import Permission
from django.db import OperationalError, connection, transaction
from django.db.models import Q
from django.http import Http404
from django.utils import timezone

from accounts.models import User

from .catalog_answers import catalog_answer, provider_sources, unsupported_guidance
from .chat_intents import outside_catalog_scope
from .models import ChatMessage, ChatSession
from .providers import CatalogRetriever, get_provider
from .config import enabled, time_budget
from .integration import ProviderUnavailable

FALLBACK = "Chưa có đủ thông tin để trả lời. Bạn có thể liên hệ An Nhiên Spa để được hướng dẫn thêm."
UNAVAILABLE = "Trợ lý tạm thời chưa thể trả lời. Bạn có thể thử lại hoặc liên hệ An Nhiên Spa."
PENDING_TIMEOUT = timedelta(minutes=2)
logger = logging.getLogger("ai_features.fr21")


class ChatError(Exception):
    def __init__(self, message, status=400, retry_after=None):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


def can_read_history(user):
    if not (user.is_authenticated and user.is_active and user.role == User.Role.ADMIN):
        return False
    # Query actual assignments, including for superusers. No role-based implicit grant.
    return Permission.objects.filter(content_type__app_label="ai_features", content_type__model="chatsession",
                                     codename="read_chat_history").filter(Q(user=user) | Q(group__user=user)).exists()


def _retry_sqlite_lock(operation, *args):
    for attempt in range(6):
        try:
            return operation(*args)
        except OperationalError as error:
            if connection.vendor != "sqlite" or "locked" not in str(error).lower() or attempt == 5:
                raise
            sleep(0.01 * (2 ** attempt))


@transaction.atomic
def _reserve(user_id, session_id, question, retry_id, request_id):
    # One account row serializes quota checks across all of that account's sessions on MySQL.
    user = User.objects.select_for_update().filter(pk=user_id, is_active=True, role=User.Role.USER).first()
    if user is None:
        raise ChatError("Tài khoản không có quyền trò chuyện.", 403)
    sessions = ChatSession.objects.filter(user=user)
    session = sessions.filter(pk=session_id).first() if session_id else None
    if session_id and session is None:
        raise Http404

    attempts = ChatMessage.objects.filter(session__user=user, role=ChatMessage.Role.ASSISTANT)
    now = timezone.now()
    stale = attempts.filter(status=ChatMessage.Status.PENDING, created_at__lte=now - PENDING_TIMEOUT)
    previous = attempts.select_related("reply_to").filter(request_id=request_id).first()
    if previous:
        if ((session and previous.session_id != session.pk) or previous.retry_of_id != retry_id
                or (question is not None and previous.reply_to.content != question)):
            raise ChatError("Mã yêu cầu đã được dùng cho nội dung khác.", 409)
        if stale.filter(pk=previous.pk).update(status=ChatMessage.Status.ERROR, content=UNAVAILABLE):
            previous.refresh_from_db()
        return previous, False

    if session and session.status != ChatSession.Status.OPEN:
        raise ChatError("Phiên này đã kết thúc. Vui lòng mở phiên mới.", 409)
    original = None
    if retry_id:
        stale.filter(pk=retry_id, session=session).update(status=ChatMessage.Status.ERROR, content=UNAVAILABLE)
        failed = attempts.select_related("reply_to").filter(pk=retry_id, session=session).first()
        if not failed or failed.status != ChatMessage.Status.ERROR:
            raise ChatError("Phản hồi này chưa thể thử lại.", 409)
        if failed.retries.exists():
            raise ChatError("Phản hồi này đã được thử lại. Vui lòng tải lại hội thoại.", 409)
        original = failed.reply_to

    local_now = timezone.localtime(now, timezone.get_default_timezone())
    day_start = datetime.combine(local_now.date(), time.min, local_now.tzinfo)
    tomorrow = day_start + timedelta(days=1)
    daily_limit = settings.AI_CHAT_DAILY_LIMIT
    if attempts.filter(created_at__gte=day_start, created_at__lt=tomorrow).count() >= daily_limit:
        raise ChatError(f"Bạn đã dùng hết {daily_limit} lượt hôm nay (giờ Việt Nam).", 429,
                        max(1, ceil((tomorrow - now).total_seconds())))
    cooldown = settings.AI_CHAT_COOLDOWN_SECONDS
    last = attempts.order_by("-created_at", "-pk").first()
    if last and (remaining := cooldown - (now - last.created_at).total_seconds()) > 0:
        raise ChatError(f"Vui lòng chờ ít nhất {cooldown} giây giữa hai lượt hỏi.", 429, ceil(remaining))
    if attempts.filter(status=ChatMessage.Status.PENDING, created_at__gt=now - PENDING_TIMEOUT).exists():
        raise ChatError("Trợ lý đang xử lý lượt trước. Vui lòng chờ phản hồi.", 409)
    stale.update(status=ChatMessage.Status.ERROR, content=UNAVAILABLE)

    if session is None:
        session = ChatSession.objects.create(user=user, title=question[:150], started_at=now, updated_at=now)
    if original is None:
        original = ChatMessage.objects.create(session=session, role=ChatMessage.Role.USER, content=question,
                                              status=ChatMessage.Status.SUCCESS, created_at=now)
        if not session.messages.exclude(pk=original.pk).exists():
            session.title = question[:150]
    attempt = ChatMessage.objects.create(session=session, role=ChatMessage.Role.ASSISTANT, reply_to=original,
                                         request_id=request_id, retry_of_id=retry_id, status=ChatMessage.Status.PENDING,
                                         created_at=now)
    session.updated_at = now
    session.save(update_fields=["title", "updated_at"])
    return attempt, True


@transaction.atomic
def _finish(attempt, status, content, model_name, latency_ms):
    updated = ChatMessage.objects.filter(pk=attempt.pk, status=ChatMessage.Status.PENDING).update(
        status=status, content=content, model_name=model_name, latency_ms=latency_ms,
    )
    if updated:
        ChatSession.objects.filter(pk=attempt.session_id).update(updated_at=timezone.now())
    attempt.refresh_from_db()


def send_question(user_id, session_id, question, retry_id, request_id):
    attempt, created = _retry_sqlite_lock(_reserve, user_id, session_id, question, retry_id, request_id)
    if not created:
        return attempt

    started = monotonic()
    model_name = ""
    question = attempt.reply_to.content
    try:
        guidance = unsupported_guidance(question)
        use_rag = enabled("AI_RAG_ENABLED")
        with time_budget():
            retriever = CatalogRetriever()
            if use_rag:
                from .rag import RAGRetriever
                retriever = RAGRetriever()
            sources = [] if guidance or outside_catalog_scope(question) else retriever.retrieve(question, limit=5)
            answer = catalog_answer(question, sources)
            if sources and not answer:
                try:
                    provider = get_provider()
                    model_name = provider.name
                    answer = provider.answer(question, provider_sources(sources))
                except (TimeoutError, ProviderUnavailable):
                    answer = catalog_answer(question, sources, recover=True)
                    if not answer:
                        raise
                    model_name = ""
                if not answer:
                    answer = catalog_answer(question, sources, recover=True)
                    if answer:
                        model_name = ""
                    else:
                        logger.warning("FR21 attempt=%s code=OUTPUT_REJECTED", attempt.pk)
            if answer and use_rag:
                from .rag import sources_current
                if not sources_current(sources):
                    logger.warning("FR21 attempt=%s code=SOURCE_CHANGED", attempt.pk)
                    answer = ""
        if isinstance(answer, str) and answer.strip():
            status, content = ChatMessage.Status.SUCCESS, answer.strip()[:2000]
        else:
            status, content = ChatMessage.Status.FALLBACK, guidance or FALLBACK
    except TimeoutError:
        logger.warning("FR21 attempt=%s code=TIMEOUT", attempt.pk)
        status, content = ChatMessage.Status.FALLBACK, UNAVAILABLE
    except ProviderUnavailable:
        logger.warning("FR21 attempt=%s code=PROVIDER_UNAVAILABLE", attempt.pk)
        status, content = ChatMessage.Status.FALLBACK, UNAVAILABLE
    except Exception:
        # Never return or log exception text, which may contain a provider payload or secret.
        status, content = ChatMessage.Status.ERROR, UNAVAILABLE
    _retry_sqlite_lock(_finish, attempt, status, content, model_name, round((monotonic() - started) * 1000))
    return attempt
