"""FR-23 application integration: synthetic ORM fixtures + real SDK/mock transport.

Run only through tools/ai_tests.py, which owns temporary SQLite and blocks sockets,
the MySQL driver and PayOS. No website, real keys or external requests are used.
"""
from contextlib import contextmanager
from datetime import time
import json
from unittest.mock import patch

import httpx
from django.conf import settings
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.db import connection
from django.test import Client, TestCase, override_settings

from accounts.models import User
from appointments.models import Appointment
from reviews.models import Review, ReviewReply
from .models import AIReviewAnalysis
from .test_assistance import AssistanceTests

VALID = {"sentiment": "positive", "themes": ["Không gian"], "priority": "low",
         "summary": "Khách hài lòng với không gian giả lập.", "actions": ["Duy trì không gian yên tĩnh."]}


@override_settings(AI_PROVIDER="gemini", AI_ASSISTANCE_ENABLED=True, AI_REVIEW_EXPORT_APPROVED=True,
                   AI_GEMINI_REQUESTS_APPROVED=True, AI_GEMINI_FREE_TIER_CONFIRMED=True,
                   AI_GEMINI_FREE_TIER_ONLY=True, AI_PAID_CALLS_APPROVED=False,
                   AI_GEMINI_API_KEY="synthetic-fr23-key-not-a-secret", AI_RAG_ENABLED=False)
class ReviewGeminiIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        AssistanceTests.setUpTestData.__func__(cls)
        cls.admin.user_permissions.add(Permission.objects.get(
            content_type__app_label="ai_features", codename="change_aireviewanalysis"))

    def setUp(self):
        cache.clear()
        self.client.force_login(self.admin)
        self.requests = []
        self.path = f"/api/ai/reviews/{self.review.pk}/analyze/"
        self.assertEqual(connection.vendor, "sqlite")

    def post(self, path=None, data=None):
        return self.client.post(path or self.path, data or {}, content_type="application/json")

    @contextmanager
    def transport(self, *, output=VALID, text=None, status=200, failure=None):
        def handle(_transport, request):
            self.requests.append(request)
            self.assertEqual(request.method, "POST")
            self.assertEqual(request.url.host, "generativelanguage.googleapis.com")
            self.assertEqual(request.url.path, "/v1beta/models/gemini-3.5-flash-lite:generateContent")
            if failure:
                raise failure
            if status != 200:
                return httpx.Response(status, request=request, json={"error": {
                    "code": status, "status": {429: "RESOURCE_EXHAUSTED", 401: "UNAUTHENTICATED",
                        403: "PERMISSION_DENIED"}.get(status, "INVALID_ARGUMENT"),
                    "message": "sensitive-error-marker synthetic-fr23-key-not-a-secret"}})
            return httpx.Response(200, request=request, json={"candidates": [{"content": {
                "role": "model", "parts": [{"text": text if text is not None else json.dumps(output)}]}}]})
        mock_transport = httpx.MockTransport(lambda request: handle(None, request))

        def mock_only_send(client, request, **kwargs):
            # The runner also blocks Client.send. Replace it ONLY with a local
            # dispatcher to MockTransport, never restore the real HTTP sender.
            # Keep the adapter's pre-send deadline hook active.
            for hook in client.event_hooks.get("request", []):
                hook(request)
            return mock_transport.handle_request(request)

        with patch.object(httpx.Client, "send", mock_only_send):
            yield

    def assert_preserved(self):
        self.review.refresh_from_db()
        self.assertEqual(self.review.comment, "Không gian yên tĩnh, rất hài lòng.")
        self.assertEqual(self.review.rating, 5)
        self.assertFalse(ReviewReply.objects.exists())

    def test_post_sdk_validation_database_get_and_page_reload(self):
        with self.transport():
            response = self.post()
            self.assertEqual(response.status_code, 200)
            result = response.json()["analysis"]
            self.assertEqual(result["mode"], "ai")
            self.assertEqual(result["diagnostics"]["code"], "AI_ANALYSIS_VALIDATED")
            self.assertEqual(result["reviewId"], self.review.pk)
            self.assertEqual(AIReviewAnalysis.objects.get().summary, VALID["summary"])
            # This is SDK-serialized application input, not a mocked Provider result.
            payload = json.loads(self.requests[0].content)
            data = json.loads(payload["contents"][0]["parts"][0]["text"])
            self.assertEqual(data, {"rating": 5, "comment": self.review.comment})
            for _ in range(2):
                self.assertEqual(self.client.get("/admin-reviews.html").status_code, 200)
                restored = self.client.get(self.path).json()["analysis"]
                self.assertEqual(restored["summary"], VALID["summary"])
                self.assertEqual(restored["analyzedAt"], result["analyzedAt"])
                self.assertNotIn("diagnostics", restored)
            self.assertEqual(len(self.requests), 1)
        self.assertEqual(AIReviewAnalysis.objects.count(), 1)
        self.assert_preserved()

    def test_timeout_falls_back_without_retry(self):
        with self.transport(failure=httpx.ReadTimeout("sensitive-error-marker")), self.assertLogs("ai_features.fr23", "WARNING") as logs:
            result = self.post().json()["analysis"]
        self.assertEqual(result["mode"], "rule")
        self.assertEqual(result["diagnostics"]["code"], "PROVIDER_TIMEOUT")
        self.assertEqual(len(self.requests), 1)
        self.assertNotIn("sensitive-error-marker", str(logs.output) + json.dumps(result))
        self.assert_preserved()

    def test_quota_and_authentication_have_safe_status_codes_without_retry(self):
        for status, code in ((429, "QUOTA_EXCEEDED"), (401, "AUTHENTICATION_FAILED"),
                             (403, "AUTHENTICATION_FAILED"), (400, "PROVIDER_HTTP_ERROR")):
            cache.clear()
            with self.subTest(status=status), self.transport(status=status), self.assertLogs("ai_features.fr23", "WARNING") as logs:
                result = self.post().json()["analysis"]
                self.assertEqual(result["mode"], "rule")
                self.assertEqual(result["diagnostics"], {"code": code, "httpStatus": status, "provider": "gemini"})
                safe = str(logs.output) + json.dumps(result)
                for forbidden in ("sensitive-error-marker", "synthetic-fr23-key-not-a-secret", "headers", self.review.comment):
                    self.assertNotIn(forbidden, safe)
        self.assertEqual(len(self.requests), 4)
        self.assert_preserved()

    def test_invalid_json_uses_safe_fallback(self):
        with self.transport(text="sensitive-error-marker: not json"), self.assertLogs("ai_features.fr23", "WARNING") as logs:
            result = self.post().json()["analysis"]
        self.assertEqual(result["mode"], "rule")
        self.assertEqual(result["diagnostics"]["code"], "RESPONSE_JSON_INVALID")
        self.assertNotIn("sensitive-error-marker", str(logs.output) + json.dumps(result))
        self.assertEqual(len(self.requests), 1)

    def test_invalid_object_and_schema_never_saved_as_ai(self):
        for output in ([], {}, {**VALID, "sentiment": "unknown"}, {**VALID, "priority": "urgent"},
                       {**VALID, "themes": []}, {**VALID, "summary": "x" * 1001}):
            cache.clear()
            with self.subTest(output_type=type(output).__name__), self.transport(output=output), self.assertLogs("ai_features.fr23", "WARNING"):
                result = self.post().json()["analysis"]
                self.assertEqual(result["mode"], "rule")
                self.assertIn(result["diagnostics"]["code"], {"PROVIDER_UNAVAILABLE", "OUTPUT_VALIDATION_FAILED"})
                self.assertEqual(AIReviewAnalysis.objects.get().mode, "rule")
        self.assertEqual(len(self.requests), 6)

    def test_private_input_is_blocked_before_http(self):
        Review.objects.filter(pk=self.review.pk).update(comment="Liên hệ fixture@example.test")
        with self.transport():
            result = self.post().json()["analysis"]
        self.assertEqual(result["diagnostics"]["code"], "PRIVATE_INPUT_BLOCKED")
        self.assertEqual(result["mode"], "rule")
        self.assertEqual(self.requests, [])
        self.assertFalse(ReviewReply.objects.exists())

    def test_private_output_is_discarded_not_logged_or_saved(self):
        with self.transport(output={**VALID, "summary": "Liên hệ fixture@example.test"}), self.assertLogs("ai_features.fr23", "WARNING") as logs:
            result = self.post().json()["analysis"]
        self.assertEqual(result["diagnostics"]["code"], "PRIVATE_OUTPUT_BLOCKED")
        self.assertEqual(result["mode"], "rule")
        self.assertNotIn("fixture@example.test", str(logs.output) + json.dumps(result))
        self.assertNotIn("fixture@example.test", AIReviewAnalysis.objects.get().summary)
        self.assert_preserved()

    def test_export_not_approved_and_missing_provider_never_send_http(self):
        with self.transport(), self.settings(AI_REVIEW_EXPORT_APPROVED=False):
            result = self.post().json()["analysis"]
            self.assertEqual(result["diagnostics"]["code"], "REVIEW_EXPORT_NOT_APPROVED")
        cache.clear()
        with self.transport(), self.settings(AI_PROVIDER="mock"):
            result = self.post().json()["analysis"]
            self.assertEqual(result["diagnostics"]["code"], "PROVIDER_NOT_SELECTED")
        self.assertEqual(self.requests, [])

    def test_empty_or_whitespace_text_has_no_sentiment_or_priority_for_any_rating(self):
        with self.transport():
            for rating, comment in ((1, ""), (3, "   "), (5, "")):
                cache.clear()
                Review.objects.filter(pk=self.review.pk).update(rating=rating, comment=comment)
                result = self.post().json()["analysis"]
                self.assertEqual(result["diagnostics"]["code"], "INSUFFICIENT_TEXT")
                for item in (result, self.client.get(self.path).json()["analysis"]):
                    self.assertEqual(item["analysisState"], "insufficient_text")
                    self.assertIsNone(item["sentiment"])
                    self.assertIsNone(item["priority"])
                    self.assertEqual(item["themes"], [])
                    self.assertEqual(item["mode"], "rule")
                self.assertEqual(Review.objects.get(pk=self.review.pk).comment, comment)
        self.assertEqual(self.requests, [])
        self.assertEqual(AIReviewAnalysis.objects.count(), 1)

    def test_permissions_and_csrf_stop_before_http(self):
        with self.transport():
            self.client.logout()
            self.assertEqual(self.post().status_code, 401)
            self.client.force_login(self.owner)
            self.assertEqual(self.post().status_code, 403)
            limited = User.objects.create_user("limited_fr23", "limited@example.test", "fixture-only", role="Admin")
            self.client.force_login(limited)
            self.assertEqual(self.post().status_code, 403)
            secure = Client(enforce_csrf_checks=True)
            secure.force_login(self.admin)
            self.assertEqual(secure.post(self.path, {}, content_type="application/json").status_code, 403)
        self.assertEqual(self.requests, [])
        self.assertFalse(AIReviewAnalysis.objects.exists())

    def test_inactive_admin_and_disabled_feature_stop_before_http(self):
        with self.transport():
            with self.settings(AI_ASSISTANCE_ENABLED=False):
                self.assertEqual(self.post().status_code, 503)
            self.admin.is_active = False
            self.admin.save()
            self.assertIn(self.post().status_code, (401, 403))
        self.assertEqual(self.requests, [])
        self.assertFalse(AIReviewAnalysis.objects.exists())

    def test_unexpected_sdk_failure_has_only_fixed_diagnostics(self):
        with self.transport(failure=ValueError("sensitive-error-marker")), self.assertLogs("ai_features.fr23", "WARNING") as logs:
            result = self.post().json()["analysis"]
        self.assertEqual(result["diagnostics"], {"code": "PROVIDER_UNAVAILABLE", "provider": "gemini"})
        self.assertEqual(result["mode"], "rule")
        self.assertNotIn("sensitive-error-marker", str(logs.output) + json.dumps(result))
        self.assertEqual(len(self.requests), 1)

    def test_valid_csrf_post_and_five_second_cooldown(self):
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.admin)
        secure.get("/admin-reviews.html")
        token = secure.cookies[settings.CSRF_COOKIE_NAME].value
        with self.transport():
            self.assertEqual(secure.post(self.path, {}, content_type="application/json", HTTP_X_CSRFTOKEN=token).status_code, 200)
            retry = secure.post(self.path, {}, content_type="application/json", HTTP_X_CSRFTOKEN=token)
            self.assertEqual(retry.status_code, 429)
            self.assertEqual(retry["Retry-After"], "5")
        self.assertEqual(len(self.requests), 1)

    def test_batch_five_successes_and_six_rejected_before_http(self):
        ids = [self.review.pk]
        for hour in range(10, 14):
            original = self.appointment
            appointment = Appointment.objects.create(customer=self.customer, service=self.service,
                employee=original.employee, appointment_date=original.appointment_date,
                start_time=time(hour), end_time=time(hour + 1), status="completed")
            ids.append(Review.objects.create(appointment=appointment, customer=self.customer,
                service=self.service, rating=5, comment="Không gian giả lập yên tĩnh.").pk)
        with self.transport():
            result = self.post("/api/ai/reviews/analyze/", {"reviewIds": ids})
            self.assertEqual(result.status_code, 200)
            self.assertEqual([item["reviewId"] for item in result.json()["items"]], ids)
            self.assertTrue(all(item["mode"] == "ai" for item in result.json()["items"]))
            cache.clear()
            self.assertEqual(self.post("/api/ai/reviews/analyze/", {"reviewIds": ids + [99999]}).status_code, 400)
        self.assertEqual(len(self.requests), 5)
        self.assertEqual(AIReviewAnalysis.objects.count(), 5)
        self.assert_preserved()

    def test_existing_socket_guard_remains_active(self):
        import socket
        with socket.socket() as sock, self.assertRaises(RuntimeError):
            sock.connect(("127.0.0.1", 3311))
