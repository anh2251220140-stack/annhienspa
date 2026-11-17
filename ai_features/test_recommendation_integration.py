"""FR-22 authenticated application acceptance, offline SDK transport only."""
from contextlib import contextmanager
import json
from unittest.mock import patch

import httpx
from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from tools.fr22_application_test import (INPUT, POST_URL, READ_URL, acceptance_urls,
    application_check, guarded_application, seed_synthetic)
from tools.gemini_live import Budget, SafetyStop
from .models import AIRecommendation

urlpatterns = acceptance_urls()  # Acceptance-only URLConf, never installed in production.


@override_settings(ROOT_URLCONF=__name__, AI_PROVIDER="gemini", AI_PERSONALIZATION_EXPORT_APPROVED=True,
    AI_GEMINI_REQUESTS_APPROVED=True, AI_GEMINI_FREE_TIER_CONFIRMED=True, AI_GEMINI_FREE_TIER_ONLY=True,
    AI_PAID_CALLS_APPROVED=False, AI_REVIEW_EXPORT_APPROVED=False, AI_GEMINI_API_KEY="fake-fr22-application-key")
class RecommendationApplicationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = seed_synthetic()

    def setUp(self):
        cache.clear()
        self.wire = []
        self.budget = Budget(1, generation_only=True)

    @contextmanager
    def transport(self, *, status=200, text=None, output=None, error=None):
        result = output if output is not None else {"items": [{"id": self.fixture.eligible[0].pk, "reason": "Phù hợp ngân sách và nhu cầu giả lập."}]}
        def handle(request):
            self.wire.append(request)
            if error:
                raise error
            if status != 200:
                return httpx.Response(status, request=request, json={"error": {"code": status,
                    "status": "RESOURCE_EXHAUSTED" if status == 429 else "UNAUTHENTICATED",
                    "message": "sensitive-synthetic-error fake-fr22-application-key"}})
            payload = {"candidates": [{"content": {"role": "model", "parts": [{"text":
                text if text is not None else json.dumps(result)}]}}]}
            return httpx.Response(200, request=request, json=payload)
        mock = httpx.MockTransport(handle)
        def send(client, request, **kwargs):
            for hook in client.event_hooks.get("request", []):
                hook(request)
            return mock.handle_request(request)
        # Replace the offline runner's HTTP deny only with this local dispatcher;
        # sockets stay blocked, and the shared live budget still checks every send.
        with patch.object(httpx.Client, "send", send), guarded_application(self.budget):
            yield

    def test_authenticated_post_sdk_persistence_and_acceptance_get(self):
        with self.transport():
            report = application_check(self.fixture, self.budget)
        self.assertEqual(report["status"], "PASS")
        self.assertFalse(report["production_get_supported"])
        self.assertTrue(report["acceptance_get_only"])
        self.assertEqual(len(self.wire), 1)
        serialized = json.loads(self.wire[0].content)
        data = json.loads(serialized["contents"][0]["parts"][0]["text"])
        self.assertEqual({row["id"] for row in data["candidates"]}, {s.pk for s in self.fixture.eligible})
        self.assertEqual(data["completedServiceIds"], [self.fixture.eligible[0].pk])
        for forbidden in ("customerId", "email", "phone", self.fixture.customer.full_name):
            self.assertNotIn(forbidden, json.dumps(data, ensure_ascii=False))
        self.assertEqual(AIRecommendation.objects.get().customer_id, self.fixture.customer.pk)

    def assert_failed_acceptance(self, **kwargs):
        with self.transport(**kwargs), self.assertRaises(SafetyStop):
            application_check(self.fixture, self.budget)
        self.assertEqual(self.budget.wire_requests, 1)
        self.assertEqual(len(self.wire), 1)
        row = AIRecommendation.objects.get()
        self.assertEqual(json.loads(row.reason)["mode"], "rule")

    def test_quota_is_failure_not_rule_pass_and_no_retry(self):
        self.assert_failed_acceptance(status=429)

    def test_auth_error_is_failure_not_rule_pass(self):
        self.assert_failed_acceptance(status=401)

    def test_timeout_is_failure_not_rule_pass(self):
        self.assert_failed_acceptance(error=httpx.ReadTimeout("sensitive-synthetic-error"))

    def test_malformed_json_is_failure(self):
        self.assert_failed_acceptance(text="sensitive-synthetic-error not JSON")

    def test_out_of_budget_service_is_rejected_by_real_service(self):
        self.assert_failed_acceptance(output={"items": [{"id": self.fixture.excluded[0].pk, "reason": "Không hợp lệ"}]})

    def test_invented_price_in_reason_is_rejected(self):
        self.assert_failed_acceptance(output={"items": [{"id": self.fixture.eligible[0].pk, "reason": "Giá chỉ 999.000 VND."}]})

    def test_history_count_cannot_ground_an_invented_price(self):
        self.assert_failed_acceptance(output={"items": [{"id": self.fixture.eligible[0].pk, "reason": "Giá chỉ 1 VND."}]})

    def test_medical_claim_is_rejected(self):
        self.assert_failed_acceptance(output={"items": [{"id": self.fixture.eligible[0].pk, "reason": "Điều trị da chắc chắn."}]})

    def test_wrong_need_hidden_and_duration_are_rejected(self):
        for service in self.fixture.excluded[1:]:
            cache.clear()
            before = len(self.wire)
            self.budget = Budget(1, generation_only=True)
            with self.transport(output={"items": [{"id": service.pk, "reason": "Không hợp lệ"}]}):
                self.budget.reserve(INPUT)
                client = Client();client.force_login(self.fixture.owner)
                result = client.post(POST_URL, INPUT, content_type="application/json")
            self.assertEqual(result.json()["mode"], "rule")
            self.assertEqual(len(self.wire) - before, 1)

    def test_get_and_other_account_cannot_read_or_infer(self):
        with self.transport():
            application_check(self.fixture, self.budget)
            row = AIRecommendation.objects.get()
            anonymous = Client()
            self.assertEqual(anonymous.get(f"{READ_URL}{row.pk}/").status_code, 401)
            anonymous.force_login(self.fixture.other)
            self.assertEqual(anonymous.get(f"{READ_URL}{row.pk}/").status_code, 404)
        self.assertEqual(len(self.wire), 1)

    def test_csrf_and_unauthenticated_requests_stop_before_provider(self):
        with self.transport():
            client = Client()
            self.assertEqual(client.post(POST_URL, INPUT, content_type="application/json").status_code, 401)
            secure = Client(enforce_csrf_checks=True);secure.force_login(self.fixture.owner)
            self.assertEqual(secure.post(POST_URL, INPUT, content_type="application/json").status_code, 403)
        self.assertEqual(self.wire, [])

    def test_approval_and_missing_key_cannot_pass(self):
        for settings in ({"AI_PERSONALIZATION_EXPORT_APPROVED": False}, {"AI_GEMINI_API_KEY": ""}):
            cache.clear()
            with self.settings(**settings), self.transport():
                self.budget = Budget(1, generation_only=True)
                self.budget.reserve(INPUT)
                client = Client();client.force_login(self.fixture.owner)
                result = client.post(POST_URL, INPUT, content_type="application/json")
                self.assertEqual(result.json()["mode"], "rule")
        self.assertEqual(self.wire, [])

    def test_one_wire_request_limit_and_alternate_origin_are_enforced(self):
        with self.transport():
            application_check(self.fixture, self.budget)
            with self.assertRaises(SafetyStop):
                httpx.Client().post("https://api.openai.com/v1/chat/completions", json={})
        self.assertEqual(len(self.wire), 1)

    def test_mysql_and_raw_sockets_are_denied_before_connect(self):
        import MySQLdb
        import socket
        with self.transport():
            for port in (3306, 3307, 3310, 3311):
                with self.assertRaises(SafetyStop):
                    MySQLdb.connect(host="127.0.0.1", port=port)
                with socket.socket() as sock, self.assertRaises(SafetyStop):
                    sock.connect(("127.0.0.1", port))
        self.assertEqual(self.wire, [])
