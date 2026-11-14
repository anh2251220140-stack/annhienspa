import json
from functools import wraps
from uuid import UUID

from django.conf import settings
from django.core.exceptions import RequestDataTooBig
from django.core.paginator import Paginator
from django.db.models import Case, Count, Exists, OuterRef, Q, Subquery, Value, When
from django.http import Http404, JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from accounts.models import User

from .chat import ChatError, PENDING_TIMEOUT, UNAVAILABLE, can_read_history, send_question
from .models import ChatMessage, ChatSession
from .providers import contains_private_input

SESSION_PAGE_SIZE = 10
MESSAGE_PAGE_SIZE = 30


def chat_access(*, admin=False):
    def decorate(view):
        @never_cache
        @wraps(view)
        def guarded(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                return JsonResponse({"error": "Vui lòng đăng nhập để tiếp tục."}, status=401)
            if not user.is_active or user.role != (User.Role.ADMIN if admin else User.Role.USER):
                return JsonResponse({"error": "Tài khoản không có quyền truy cập."}, status=403)
            if not settings.AI_CHAT_ENABLED:
                return JsonResponse({"error": "Trợ lý chưa được bật trên website này."}, status=503)
            # A widget left open in another tab must not display the new login's
            # data. Ownership still comes exclusively from the authenticated user.
            widget_user = request.headers.get("X-Chat-User")
            if not admin and widget_user is not None and widget_user != str(user.pk):
                return JsonResponse({"error": "Tài khoản đã thay đổi. Vui lòng tải lại trang."}, status=403)
            if admin and not can_read_history(user):
                return JsonResponse({"error": "Tài khoản chưa được cấp quyền đọc lịch sử hội thoại."}, status=403)
            try:
                return view(request, *args, **kwargs)
            except Http404:
                return JsonResponse({"error": "Không tìm thấy hội thoại."}, status=404)
            except ChatError as error:
                response = JsonResponse({"error": str(error)}, status=error.status)
                if error.retry_after is not None:
                    response["Retry-After"] = error.retry_after
                return response
        return guarded
    return decorate


def _payload(request):
    if request.content_type != "application/json":
        raise ChatError("Yêu cầu phải có định dạng JSON.", 415)
    try:
        body = request.body
    except RequestDataTooBig:
        raise ChatError("Yêu cầu quá dài.", 413) from None
    if len(body) > 8192:
        raise ChatError("Yêu cầu quá dài.", 413)
    try:
        data = json.loads(body)
    except (ValueError, UnicodeError, RecursionError):
        raise ChatError("Yêu cầu không đúng định dạng JSON.") from None
    if not isinstance(data, dict):
        raise ChatError("Yêu cầu không đúng định dạng JSON.")
    return data


def _optional_id(data, key):
    value = data.get(key)
    if value is not None and (type(value) is not int or not 0 < value < 2**63):
        raise ChatError("Mã hội thoại hoặc tin nhắn không hợp lệ.")
    return value


def _page(queryset, number, size, serialize):
    page = Paginator(queryset, size).get_page(number)
    return {"items": [serialize(item) for item in page], "page": page.number,
            "pages": page.paginator.num_pages, "total": page.paginator.count}


def _session(item, *, admin=False):
    result = {"id": item.pk, "title": item.title, "status": item.status, "startedAt": item.started_at.isoformat(),
              "updatedAt": item.updated_at.isoformat(), "endedAt": item.ended_at.isoformat() if item.ended_at else None}
    if admin:
        customer = getattr(item.user, "customer", None)
        result.update(name=customer.full_name if customer else item.user.username, username=item.user.username,
                      messageCount=item.message_count, result=item.last_result)
    return result


def _message(item):
    expired = item.status == ChatMessage.Status.PENDING and item.created_at <= timezone.now() - PENDING_TIMEOUT
    return {"id": item.pk, "role": item.role, "content": UNAVAILABLE if expired else item.content,
            "createdAt": item.created_at.isoformat(), "status": ChatMessage.Status.ERROR if expired else item.status,
            "modelName": item.model_name, "latencyMs": item.latency_ms,
            "replyTo": item.reply_to_id, "retryOf": item.retry_of_id}


def _sessions_for_admin():
    latest = ChatMessage.objects.filter(session=OuterRef("pk"), role=ChatMessage.Role.ASSISTANT).order_by("-created_at", "-pk")
    latest = latest.annotate(result=Case(
        When(status=ChatMessage.Status.PENDING, created_at__lte=timezone.now() - PENDING_TIMEOUT,
             then=Value(ChatMessage.Status.ERROR)),
        default="status",
    ))
    return ChatSession.objects.select_related("user", "user__customer").annotate(
        message_count=Count("messages"), last_result=Subquery(latest.values("result")[:1]),
    )


def _detail(request, queryset, session_id, *, admin=False):
    item = queryset.filter(pk=session_id).first()
    if item is None:
        raise Http404
    page = _page(item.messages.order_by("-created_at", "-pk"), request.GET.get("page"), MESSAGE_PAGE_SIZE, _message)
    page["items"].reverse()
    return JsonResponse({"session": _session(item, admin=admin), **page})


@chat_access()
@require_http_methods(["GET", "POST"])
def sessions(request):
    if request.method == "POST":
        item = ChatSession.objects.create(user=request.user)
        return JsonResponse({"session": _session(item)}, status=201)
    items = ChatSession.objects.filter(user=request.user).order_by("-updated_at", "-pk")
    limits = {"dailyLimit": settings.AI_CHAT_DAILY_LIMIT, "cooldown": settings.AI_CHAT_COOLDOWN_SECONDS}
    if request.GET.get("resume") == "1":
        # Skip empty sessions left by the old "new session" button. If only
        # closed conversations exist, the most recent one can still be read.
        started = items.filter(Exists(ChatMessage.objects.filter(session_id=OuterRef("pk"))))
        item = started.filter(status=ChatSession.Status.OPEN).first() or started.first()
        return JsonResponse({"session": _session(item) if item else None, **limits})
    return JsonResponse({**_page(items, request.GET.get("page"), SESSION_PAGE_SIZE, _session), **limits})


@chat_access()
@require_http_methods(["GET"])
def detail(request, session_id):
    return _detail(request, ChatSession.objects.filter(user=request.user), session_id)


@chat_access()
@require_http_methods(["POST"])
def chat(request):
    data = _payload(request)
    session_id, retry_id = _optional_id(data, "sessionId"), _optional_id(data, "retryOf")
    try:
        request_id = UUID(data["requestId"])
    except (KeyError, ValueError, TypeError, AttributeError):
        raise ChatError("Thiếu mã yêu cầu hợp lệ.") from None
    question = data.get("question")
    if retry_id:
        if not session_id or question is not None:
            raise ChatError("Cần chọn đúng phiên và phản hồi cần thử lại.")
    else:
        if not isinstance(question, str) or not 1 <= len(question.strip()) <= 500:
            raise ChatError("Nhập câu hỏi từ 1 đến 500 ký tự.")
        question = question.strip()
        if any((ord(char) < 32 and char not in "\n\r\t") or 0xD800 <= ord(char) <= 0xDFFF for char in question):
            raise ChatError("Câu hỏi chứa ký tự không hợp lệ.")
        if contains_private_input(question):
            raise ChatError("Vui lòng bỏ mật khẩu, mã xác thực và thông tin liên hệ cá nhân khỏi câu hỏi.")
    attempt = send_question(request.user.pk, session_id, question, retry_id, request_id)
    return JsonResponse({"session": _session(attempt.session), "question": _message(attempt.reply_to),
                         "answer": _message(attempt)}, status=202 if attempt.status == ChatMessage.Status.PENDING else 200)


@chat_access(admin=True)
@require_http_methods(["GET"])
def admin_sessions(request):
    items = _sessions_for_admin().exclude(last_result__isnull=True).order_by("-updated_at", "-pk")
    search = request.GET.get("search", "").strip()[:150]
    if search:
        matches = Q(user__username__icontains=search) | Q(user__customer__full_name__icontains=search)
        code = search.removeprefix("#")
        if code.isascii() and code.isdecimal() and len(code) < 19:
            matches |= Q(pk=int(code))
        items = items.filter(matches)
    status = request.GET.get("result")
    if status in ChatMessage.Status.values:
        items = items.filter(last_result=status)
    return JsonResponse(_page(items, request.GET.get("page"), SESSION_PAGE_SIZE, lambda item: _session(item, admin=True)))


@chat_access(admin=True)
@require_http_methods(["GET"])
def admin_detail(request, session_id):
    return _detail(request, _sessions_for_admin(), session_id, admin=True)
