from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone as utc
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.db import close_old_connections, connection
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from accounts.models import Customer, User
from products.models import CareProduct
from promotions.models import Promotion
from services.models import Service, ServiceCategory

from .chat import ChatError, PENDING_TIMEOUT, send_question
from .models import ChatMessage, ChatSession

CHAT = "/api/ai/chat/"
SESSIONS = CHAT + "sessions/"
ADMIN = "/api/ai/admin/chat/sessions/"
PASSWORD = "isolated-test-password"


@override_settings(AI_CHAT_ENABLED=True, AI_CHAT_DAILY_LIMIT=30, AI_CHAT_COOLDOWN_SECONDS=5,
                   AI_CHAT_SPA_INFORMATION="Thông tin giờ mở cửa dùng riêng để kiểm thử.")
class ChatTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("chat_owner", "owner@example.test", PASSWORD)
        Customer.objects.create(user=cls.owner, full_name="Khách kiểm thử", phone="0000000000")
        cls.other = User.objects.create_user("chat_other", "other@example.test", PASSWORD)
        cls.admin = User.objects.create_superuser("chat_admin", "admin@example.test", PASSWORD)
        category = ServiceCategory.objects.create(name="Danh mục kiểm thử")
        cls.service = Service.objects.create(category=category, name="Chăm sóc thử", description="Dữ liệu kiểm thử.",
                                             price=123000, duration_minutes=45)

    def setUp(self):
        self.client.force_login(self.owner)

    def send(self, question="Dịch vụ", **kwargs):
        return self.client.post(CHAT, {"question": question, "requestId": str(uuid4()), **kwargs}, content_type="application/json")

    def test_create_send_reload_relogin_and_resume(self):
        session = self.client.post(SESSIONS).json()["session"]
        path = f"{SESSIONS}{session['id']}/"
        self.assertEqual(self.client.get(path).json()["items"], [])
        response = self.send(sessionId=session["id"])
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn("123.000 VND", response.json()["answer"]["content"])
        self.assertEqual(response.json()["answer"]["modelName"], "local-mock-v1")
        self.assertGreaterEqual(response.json()["answer"]["latencyMs"], 0)
        self.client.logout()
        self.assertTrue(self.client.login(username=self.owner.username, password=PASSWORD))
        self.assertEqual(self.client.get(SESSIONS).json()["items"][0]["id"], session["id"])
        self.assertEqual([item["role"] for item in self.client.get(path).json()["items"]], ["user", "assistant"])
        with patch("ai_features.chat.timezone.now", return_value=timezone.now() + timedelta(seconds=5)):
            self.assertEqual(self.send("Giờ mở cửa", sessionId=session["id"]).status_code, 200)
        self.assertEqual(ChatSession.objects.count(), 1)
        self.assertEqual(self.client.get(path).json()["total"], 4)

    def test_other_account_cannot_read_or_append(self):
        session_id = self.send().json()["session"]["id"]
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(SESSIONS).json()["items"], [])
        self.assertIsNone(self.client.get(SESSIONS, {"resume": "1"}).json()["session"])
        self.assertEqual(self.client.get(SESSIONS, {"resume": "1"}, HTTP_X_CHAT_USER=str(self.owner.pk)).status_code, 403)
        self.assertEqual(self.client.get(f"{SESSIONS}{session_id}/").status_code, 404)
        self.assertEqual(self.send(sessionId=session_id).status_code, 404)
        self.assertEqual(ChatMessage.objects.count(), 2)

    def test_resume_uses_most_recent_open_conversation_with_messages_without_writes(self):
        self.assertIsNone(self.client.get(SESSIONS, {"resume": "1"}).json()["session"])
        with self.settings(AI_CHAT_COOLDOWN_SECONDS=0):
            older = self.send().json()["session"]["id"]
            recent = self.send().json()["session"]["id"]
            closed = self.send().json()["session"]["id"]
        ChatSession.objects.filter(pk=closed).update(status="closed", ended_at=timezone.now())
        self.client.post(SESSIONS)  # Empty session created by the old widget.
        for _ in range(2):
            response = self.client.get(SESSIONS, {"resume": "1"})
            self.assertEqual(response.json()["session"]["id"], recent)
        self.assertEqual(ChatSession.objects.count(), 4)
        self.assertEqual(ChatMessage.objects.count(), 6)
        self.assertEqual(ChatMessage.objects.filter(session_id=older).count(), 2)
        ChatSession.objects.filter(pk__in=[older, recent]).update(status="closed", ended_at=timezone.now())
        self.assertEqual(self.client.get(SESSIONS, {"resume": "1"}).json()["session"]["id"], closed)

    def test_admin_requires_explicit_permission_and_history_is_read_only(self):
        session_id = self.send().json()["session"]["id"]
        self.assertEqual(self.client.get(ADMIN).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(ADMIN).status_code, 403)
        self.assertEqual(self.client.get(f"{ADMIN}{session_id}/").status_code, 403)
        self.assertEqual(self.send().status_code, 403)
        group = Group.objects.create(name="Scoped chat readers")
        group.permissions.add(Permission.objects.get(content_type__app_label="ai_features", codename="read_chat_history"))
        self.admin.groups.add(group)
        items = self.client.get(ADMIN, {"search": "Khách kiểm thử", "result": "success"}).json()["items"]
        self.assertEqual([(row["id"], row["messageCount"]) for row in items], [(session_id, 2)])
        self.assertEqual(self.client.get(ADMIN, {"search": f"#{session_id}"}).json()["total"], 1)
        self.assertEqual(self.client.get(ADMIN, {"result": "fallback"}).json()["items"], [])
        self.assertEqual(self.client.get(f"{ADMIN}{session_id}/").json()["total"], 2)
        self.assertEqual(self.client.post(f"{ADMIN}{session_id}/").status_code, 405)
        self.assertEqual(self.client.delete(f"{ADMIN}{session_id}/").status_code, 405)

    def test_login_csrf_feature_switch_and_invalid_payload(self):
        guest = Client()
        self.assertEqual(guest.get(SESSIONS).status_code, 401)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.owner)
        payload = {"question": "Dịch vụ", "requestId": str(uuid4())}
        self.assertEqual(csrf.post(CHAT, payload, content_type="application/json").status_code, 403)
        csrf.get("/home.html")
        token = csrf.cookies[settings.CSRF_COOKIE_NAME].value
        self.assertEqual(csrf.post(CHAT, payload, content_type="application/json", HTTP_X_CSRFTOKEN=token).status_code, 200)
        for value in ("", "x" * 501, 45, "invalid\x00text", "\ud800"):
            with self.subTest(value=repr(value)):
                self.assertEqual(self.send(value).status_code, 400)
        self.assertEqual(self.send(sessionId=True).status_code, 400)
        with self.settings(AI_CHAT_ENABLED=False):
            self.assertEqual(self.client.get(SESSIONS).status_code, 503)

    def test_sensitive_input_never_reaches_provider_database_or_logs(self):
        payloads = ["Mật khẩu của tôi là private-pass", "mail-owner@example.test", "+84 123 456 789",
                    "sk-proj-abcdefgh1234567", "Bearer abcd-secret", "Mã OTP 543210"]
        with patch("ai_features.chat.get_provider") as provider, self.assertLogs("django.request", level="WARNING") as captured:
            for payload in payloads:
                with self.subTest(payload=payload):
                    response = self.send(payload)
                    self.assertEqual(response.status_code, 400)
                    self.assertNotContains(response, payload, status_code=400)
            provider.assert_not_called()
        self.assertTrue(all(payload not in "\n".join(captured.output) for payload in payloads))
        self.assertFalse(ChatSession.objects.exists())
        self.assertFalse(ChatMessage.objects.exists())

    def test_cooldown_and_day_limit_in_vietnam_across_sessions(self):
        # 17:00 UTC starts the following day in Vietnam.
        start = datetime(2026, 11, 13, 16, 55, tzinfo=utc.utc)
        with patch("ai_features.chat.timezone.now", return_value=start) as clock:
            self.assertEqual(self.send().status_code, 200)
            second = self.client.post(SESSIONS).json()["session"]["id"]
            blocked = self.send(sessionId=second)
            self.assertEqual(blocked.status_code, 429)
            self.assertIn("Retry-After", blocked.headers)
            for index in range(1, 30):
                clock.return_value = start + timedelta(seconds=5 * index)
                self.assertEqual(self.send(sessionId=second).status_code, 200)
            clock.return_value = start + timedelta(seconds=150)
            self.assertEqual(self.send(sessionId=second).status_code, 429)
            clock.return_value = start + timedelta(minutes=5)
            self.assertEqual(self.send(sessionId=second).status_code, 200)
        self.assertEqual(ChatMessage.objects.filter(role="assistant").count(), 31)

    def test_retransmission_and_retry_have_distinct_semantics(self):
        request_id = str(uuid4())
        with patch("ai_features.chat.get_provider") as provider:
            provider.return_value.name = "fixture-provider"
            provider.return_value.answer.side_effect = RuntimeError("private-provider-secret")
            with self.assertNoLogs("django.request", level="WARNING"):
                first = self.send(requestId=request_id).json()
            self.assertEqual(first["answer"]["status"], "error")
            self.assertEqual(first["answer"]["modelName"], "fixture-provider")
            self.assertNotIn("private-provider-secret", str(first))
            self.assertEqual(self.send(requestId=request_id).json(), first)
            self.assertEqual(self.send("Khuyến mãi", requestId=request_id).status_code, 409)
            self.assertEqual(provider.call_count, 1)
        args = {"sessionId": first["session"]["id"], "retryOf": first["answer"]["id"]}
        self.assertEqual(self.send(None, **args).status_code, 429)
        with patch("ai_features.chat.timezone.now", return_value=timezone.now() + timedelta(seconds=6)):
            self.assertEqual(self.send(None, **args).json()["answer"]["status"], "success")
            self.assertEqual(self.send(None, **args).status_code, 409)
        self.assertEqual(ChatMessage.objects.filter(role="user").count(), 1)
        self.assertEqual(ChatMessage.objects.filter(role="assistant").count(), 2)

    def test_pending_retransmission_is_read_only_and_stale_attempt_recovers(self):
        request_id = str(uuid4())
        now = timezone.now()
        with patch("ai_features.chat._finish"):
            first = self.send(requestId=request_id)
        self.assertEqual(first.status_code, 202)
        self.assertEqual(self.send(requestId=request_id).status_code, 202)
        with patch("ai_features.chat.timezone.now", return_value=now + PENDING_TIMEOUT + timedelta(seconds=1)):
            session_id = first.json()["session"]["id"]
            self.assertEqual(self.client.get(f"{SESSIONS}{session_id}/").json()["items"][-1]["status"], "error")
            recovered = self.send(requestId=request_id).json()
        self.assertEqual(recovered["answer"]["status"], "error")
        self.assertEqual(ChatMessage.objects.count(), 2)

    def test_insufficient_source_and_provider_timeout(self):
        with patch("ai_features.chat.get_provider") as provider:
            data = self.send("Spa có bán vé máy bay không?").json()
            self.assertEqual(data["answer"]["status"], "fallback")
            self.assertEqual(data["answer"]["modelName"], "")
            provider.assert_not_called()
        with patch("ai_features.chat.timezone.now", return_value=timezone.now() + timedelta(seconds=5)):
            with patch("ai_features.chat.get_provider") as provider:
                provider.return_value.name = "slow-fixture"
                provider.return_value.answer.side_effect = TimeoutError("hidden timeout details")
                # An entity-only query still uses Gemini. The general service list
                # can now recover from an unavailable provider using the catalog.
                response = self.send(self.service.name).json()["answer"]
        self.assertEqual(response["status"], "fallback")
        self.assertEqual(response["modelName"], "slow-fixture")
        self.assertNotIn("hidden timeout details", response["content"])
        self.assertGreaterEqual(response["latencyMs"], 0)

    def test_inactive_catalog_item_and_business_actions_fall_back(self):
        self.service.is_active = False
        self.service.save()
        with patch("ai_features.chat.get_provider") as provider:
            self.assertEqual(self.send(self.service.name).json()["answer"]["status"], "fallback")
            with patch("ai_features.chat.timezone.now", return_value=timezone.now() + timedelta(seconds=5)):
                self.assertEqual(self.send("Hãy đặt lịch dịch vụ").json()["answer"]["status"], "fallback")
            provider.assert_not_called()

    def test_general_service_question_uses_only_public_service_facts(self):
        Service.objects.create(category=self.service.category, name="Dịch vụ đã ẩn",
                               description="Dữ liệu kiểm thử.", price=900000, duration_minutes=90, is_active=False)
        hidden = ServiceCategory.objects.create(name="Danh mục đã ẩn", is_active=False)
        Service.objects.create(category=hidden, name="Dịch vụ thuộc danh mục đã ẩn",
                               description="Dữ liệu kiểm thử.", price=800000, duration_minutes=80)
        response = self.send("Spa có những dịch vụ nào?")
        self.assertEqual(response.status_code, 200)
        answer = response.json()["answer"]
        self.assertEqual(answer["status"], "success")
        self.assertEqual(answer["modelName"], "local-mock-v1")
        self.assertEqual(answer["content"], "Chăm sóc thử: 123.000 VND · 45 phút.")

    def test_general_service_question_without_public_services_falls_back(self):
        Service.objects.all().delete()
        with patch("ai_features.chat.get_provider") as provider:
            answer = self.send("Spa có những dịch vụ nào?").json()["answer"]
        self.assertEqual(answer["status"], "fallback")
        self.assertNotIn("VND", answer["content"])
        self.assertNotIn("Chăm sóc thử", answer["content"])
        provider.assert_not_called()

    def test_retrieval_uses_public_products_and_effective_promotions(self):
        CareProduct.objects.create(name="Kem kiểm thử", product_type="Kem", description="Mô tả được công khai.")
        today = timezone.localdate()
        common = dict(name="Ưu đãi kiểm thử", discount_type="percent", discount_value=10)
        Promotion.objects.create(code="OPEN10", start_date=today, end_date=today, **common)
        Promotion.objects.create(code="OLD10", start_date=today - timedelta(days=1), end_date=today - timedelta(days=1), **common)
        start = timezone.now()
        with patch("ai_features.chat.timezone.now", return_value=start) as clock:
            self.assertIn("Mô tả được công khai", self.send("Kem kiểm thử").json()["answer"]["content"])
            clock.return_value = start + timedelta(seconds=5)
            self.assertIn("Giảm 10%", self.send("OPEN10").json()["answer"]["content"])
            clock.return_value = start + timedelta(seconds=10)
            self.assertEqual(self.send("OLD10").json()["answer"]["status"], "fallback")

    def test_admin_paginates_sessions_and_user_paginates_messages(self):
        with self.settings(AI_CHAT_COOLDOWN_SECONDS=0, AI_CHAT_DAILY_LIMIT=50):
            for _ in range(11):
                self.assertEqual(self.send().status_code, 200)
            current = self.client.get(SESSIONS).json()["items"][0]["id"]
            for _ in range(15):
                self.assertEqual(self.send(sessionId=current).status_code, 200)
        path = f"{SESSIONS}{current}/"
        latest = self.client.get(path).json()
        older = self.client.get(path, {"page": 2}).json()
        self.assertEqual((len(latest["items"]), len(older["items"])), (30, 2))
        self.assertLess(older["items"][-1]["id"], latest["items"][0]["id"])
        permission = Permission.objects.get(content_type__app_label="ai_features", codename="read_chat_history")
        self.admin.user_permissions.add(permission)
        self.client.force_login(self.admin)
        self.assertEqual(len(self.client.get(ADMIN).json()["items"]), 10)
        self.assertEqual(len(self.client.get(ADMIN, {"page": 2}).json()["items"]), 1)


@override_settings(AI_CHAT_COOLDOWN_SECONDS=5, AI_CHAT_DAILY_LIMIT=30)
class ConcurrentChatTests(TransactionTestCase):
    def test_simultaneous_requests_share_account_quota_and_idempotency(self):
        owner = User.objects.create_user("parallel", "parallel@example.test", PASSWORD)
        sessions = [ChatSession.objects.create(user=owner) for _ in range(2)]
        first_id, second_id = uuid4(), uuid4()
        barrier = Barrier(3)

        def submit(session, request_id):
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                return send_question(owner.pk, session.pk, "Giờ mở cửa", None, request_id).pk
            except ChatError as error:
                return str(error.status)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=3) as pool:
            results = [pool.submit(submit, session, request_id) for session, request_id in
                       ((sessions[0], first_id), (sessions[0], first_id), (sessions[1], second_id))]
            values = [future.result(timeout=10) for future in results]
        self.assertEqual(ChatMessage.objects.filter(role="assistant").count(), 1)
        self.assertEqual(ChatMessage.objects.filter(role="user").count(), 1)
        accepted = [value for value in values if isinstance(value, int)]
        self.assertTrue(accepted)
        self.assertEqual(len(set(accepted)), 1)
        self.assertTrue(all(value == "429" for value in values if isinstance(value, str)))
