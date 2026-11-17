from concurrent.futures import ThreadPoolExecutor
from datetime import time, timedelta
import json
from pathlib import Path
from threading import Barrier
from time import perf_counter
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.db import close_old_connections, connection
from django.test import Client, TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.utils import timezone

from accounts.models import Customer, User
from appointments.models import Appointment
from employees.models import Employee, EmployeeSchedule, EmployeeService
from reviews.models import Review, ReviewReply
from services.models import Service, ServiceCategory

from .assistance import analyze_review, recommend
from .chat import send_question
from .models import AIRecommendation, AIReviewAnalysis, ChatMessage

REC = "/api/ai/recommendations/"


@override_settings(AI_ASSISTANCE_ENABLED=True, AI_RAG_ENABLED=False, AI_PROVIDER="mock")
class AssistanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("ai_owner", "ai-owner@example.test", "fixture-only-password")
        cls.customer = Customer.objects.create(user=cls.owner, full_name="Khách thử", phone="123",
            budget=300000, care_needs=json.dumps(["Dưỡng ẩm, cải thiện da khô"], ensure_ascii=False))
        cls.other = User.objects.create_user("ai_other", "ai-other@example.test", "fixture-only-password")
        Customer.objects.create(user=cls.other, full_name="Khách khác", phone="123")
        cls.admin = User.objects.create_user("ai_admin", "ai-admin@example.test", "fixture-only-password", role="Admin")
        cls.cat = ServiceCategory.objects.create(name="Danh mục thử")
        cls.service = Service.objects.create(category=cls.cat, name="Chăm sóc da", description="Dịu nhẹ", price=300000,
                                            duration_minutes=60, care_group="face")
        cls.expensive = Service.objects.create(category=cls.cat, name="Da vượt ngân sách", description="Dịu nhẹ", price=400000,
                                              duration_minutes=60, care_group="face")
        cls.off = Service.objects.create(category=cls.cat, name="Đã ẩn", description="Dịu nhẹ", price=100000,
                                        duration_minutes=60, care_group="face", is_active=False)
        cls.hair = Service.objects.create(category=cls.cat, name="Tóc", description="Nhẹ nhàng", price=200000,
                                         duration_minutes=90, care_group="hair")
        employee = Employee.objects.create(full_name="Nhân viên thử", specialty="Chăm sóc")
        EmployeeService.objects.create(employee=employee, service=cls.service)
        day = timezone.localdate() - timedelta(days=2)
        EmployeeSchedule.objects.create(employee=employee, work_date=day, start_time=time(8), end_time=time(17))
        cls.appointment = Appointment.objects.create(customer=cls.customer, service=cls.service, employee=employee,
            appointment_date=day, start_time=time(9), end_time=time(10), status="completed")
        cls.review = Review.objects.create(appointment=cls.appointment, customer=cls.customer, service=cls.service,
                                          rating=5, comment="Không gian yên tĩnh, rất hài lòng.")

    def setUp(self):
        cache.clear()
        self.client.force_login(self.owner)

    def post(self, path=REC, data=None):
        return self.client.post(path, data if data is not None else {}, content_type="application/json")

    def permit_analysis(self):
        self.admin.user_permissions.add(Permission.objects.get(content_type__app_label="ai_features",
                                                               codename="change_aireviewanalysis"))
        self.client.force_login(self.admin)

    def test_recommendation_fallback_respects_profile_and_persists(self):
        result = self.post().json()
        self.assertEqual(result["mode"], "rule")
        self.assertEqual([s["id"] for s in result["items"]], [self.service.pk])
        row = AIRecommendation.objects.get()
        self.assertEqual(row.customer_id, self.customer.pk)
        self.assertEqual(row.recommended_services, [self.service.pk])

    def test_needs_budget_duration_and_inactive_are_server_constraints(self):
        for data in ({"budget": "299999"}, {"duration": "short"}, {"needs": "body"}):
            with self.subTest(data=data):
                self.assertEqual(recommend(self.customer, data)["items"], [])
        self.assertEqual(AIRecommendation.objects.count(), 0)

    def test_manual_overrides_still_work(self):
        result = recommend(self.customer, {"needs": "hair", "duration": "medium"})
        self.assertEqual([s["id"] for s in result["items"]], [self.hair.pk])

    def test_saved_profile_newline_needs_preserve_first_valid_order(self):
        from .assistance import profile_inputs
        self.customer.care_needs = "Dữ liệu cũ không nhận diện\nChăm sóc tóc và da đầu\nThư giãn, giảm căng thẳng"
        self.customer.save()
        self.customer.refresh_from_db()
        self.assertEqual(profile_inputs(self.customer, {})["needs"], "hair")
        self.assertEqual([s["id"] for s in recommend(self.customer, {})["items"]], [self.hair.pk])
        self.customer.care_needs = "Thư giãn, giảm căng thẳng\nChăm sóc tóc và da đầu"
        self.assertEqual(profile_inputs(self.customer, {})["needs"], "relax")
        self.assertEqual(recommend(self.customer, {})["items"], [])

    def test_invalid_inputs_are_rejected_without_provider(self):
        values = [{"budget": "NaN"}, {"budget": -1}, {"needs": "bad"}, {"skin": "bad"},
                  {"duration": "bad"}, {"customerId": self.customer.pk}, {"interests": "a"*161},
                  {"interests": "email me at person@example.test"}, {"skin": []}]
        with patch("ai_features.gemini.GeminiProvider.structured") as provider:
            for data in values:
                cache.clear()
                with self.subTest(data=data):
                    self.assertEqual(self.post(data=data).status_code, 400)
            provider.assert_not_called()

    def test_login_and_role_authorization(self):
        self.client.logout()
        self.assertEqual(self.post().status_code, 401)
        self.client.force_login(self.admin)
        self.assertEqual(self.post().status_code, 403)

    def test_csrf_enforced_and_post_only(self):
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.owner)
        self.assertEqual(secure.post(REC, {}, content_type="application/json").status_code, 403)
        self.assertEqual(self.client.get(REC).status_code, 405)

    @override_settings(AI_PROVIDER="gemini", AI_PERSONALIZATION_EXPORT_APPROVED=False)
    def test_personal_data_not_exported_without_approval(self):
        with patch("ai_features.gemini.GeminiProvider.structured") as provider:
            self.assertEqual(self.post().json()["mode"], "rule")
            provider.assert_not_called()

    @override_settings(AI_PROVIDER="gemini", AI_PERSONALIZATION_EXPORT_APPROVED=True)
    def test_valid_ai_json_contains_only_verified_ids(self):
        with patch("ai_features.gemini.GeminiProvider.structured", return_value={"items": [{"id": self.service.pk, "reason": "Phù hợp với nhu cầu."}]}):
            body = self.post().json()
        self.assertEqual(body["mode"], "ai")
        self.assertEqual(body["items"][0]["id"], self.service.pk)

    @override_settings(AI_PROVIDER="gemini", AI_PERSONALIZATION_EXPORT_APPROVED=True)
    def test_bad_or_unavailable_ai_falls_back_as_a_whole(self):
        rows = [[], [{"id": 999999, "reason": "Sai"}], [{"id": self.off.pk, "reason": "Ẩn"}],
                [{"id": self.expensive.pk, "reason": "Quá giá"}], [{"id": self.hair.pk, "reason": "Sai nhu cầu"}],
                [{"id": self.service.pk, "reason": "Đúng"}]*2, [{"id": self.service.pk, "reason": ""}],
                [{"id": True, "reason": "Sai kiểu"}]]
        for rows in rows:
            with self.subTest(rows=rows), patch("ai_features.gemini.GeminiProvider.structured", return_value={"items": rows}):
                result = recommend(self.customer, {})
                self.assertEqual(result["mode"], "rule")
                self.assertEqual([s["id"] for s in result["items"]], [self.service.pk])
        with patch("ai_features.gemini.GeminiProvider.structured", side_effect=TimeoutError):
            self.assertEqual(recommend(self.customer, {})["mode"], "rule")

    @override_settings(AI_PROVIDER="gemini", AI_PERSONALIZATION_EXPORT_APPROVED=True)
    def test_visibility_rechecked_after_inference(self):
        def answer(*args):
            Service.objects.filter(pk=self.service.pk).update(is_active=False)
            return {"items": [{"id": self.service.pk, "reason": "Không được hiển thị"}]}
        with patch("ai_features.gemini.GeminiProvider.structured", side_effect=answer):
            self.assertEqual(recommend(self.customer, {})["items"], [])

    @override_settings(AI_PROVIDER="gemini", AI_PERSONALIZATION_EXPORT_APPROVED=True)
    def test_only_owner_history_and_no_identity_sent(self):
        self.customer.user_id = self.other.pk
        # Use the other customer's real persisted profile, never a supplied customer ID.
        other = self.other.customer
        with patch("ai_features.gemini.GeminiProvider.structured", return_value={"items": [{"id": self.hair.pk, "reason": "Phù hợp"}]}) as provider:
            recommend(other, {"needs": "hair"})
        sent = provider.call_args.args[1]
        self.assertEqual(sent["completedServiceIds"], [])
        self.assertNotIn("Khách thử", json.dumps(sent, ensure_ascii=False))
        self.assertNotIn("email", json.dumps(sent))

    def test_assistance_cooldown_precedes_provider(self):
        self.assertEqual(self.post().status_code, 200)
        with patch("ai_features.gemini.GeminiProvider.structured") as provider:
            self.assertEqual(self.post().status_code, 429)
            provider.assert_not_called()

    def test_existing_luxury_pages_render_with_new_controls(self):
        response = self.client.get("/services.html")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Một liệu trình, đúng với bạn")
        self.assertContains(response, "data-recommendation-form")
        self.client.force_login(self.admin)
        response = self.client.get("/admin-reviews.html")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="analysis-run"')
        self.assertContains(response, 'id="analysis-status"')
        self.assertNotContains(response, "FR-23 chưa được triển khai")

    def test_review_requires_admin_permission_and_post_csrf(self):
        path = f"/api/ai/reviews/{self.review.pk}/analyze/"
        self.assertEqual(self.post(path).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.post(path).status_code, 403)
        self.permit_analysis()
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.admin)
        self.assertEqual(secure.post(path, {}, content_type="application/json").status_code, 403)
        self.assertEqual(self.post(path).status_code, 200)

    def test_no_automatic_analysis_or_replies(self):
        self.assertFalse(AIReviewAnalysis.objects.exists())
        self.assertFalse(ReviewReply.objects.exists())
        self.review.refresh_from_db()
        self.assertEqual(self.review.comment, "Không gian yên tĩnh, rất hài lòng.")

    def test_rule_analysis_is_honest_and_read_back_is_stale_aware(self):
        self.permit_analysis()
        path = f"/api/ai/reviews/{self.review.pk}/analyze/"
        self.assertIsNone(self.client.get(path).json()["analysis"])
        data = self.post(path).json()["analysis"]
        self.assertEqual(data["mode"], "rule")
        self.assertIn("chưa phân tích", data["themes"][0])
        self.assertFalse(data["stale"])
        Review.objects.filter(pk=self.review.pk).update(comment="Nội dung thay đổi")
        self.assertTrue(self.client.get(path).json()["analysis"]["stale"])

    @override_settings(AI_PROVIDER="gemini", AI_REVIEW_EXPORT_APPROVED=True)
    def test_review_structured_output_persists_without_modifying_review(self):
        expected = {"sentiment": "positive", "themes": ["Không gian"], "summary": "Khách hài lòng với không gian.",
                    "priority": "low", "actions": ["Duy trì không gian yên tĩnh."]}
        with patch("ai_features.gemini.GeminiProvider.structured", return_value=expected) as provider:
            result = analyze_review(self.review.pk)
        self.assertEqual(result["mode"], "ai")
        self.assertEqual(result["themes"], expected["themes"])
        self.assertEqual(provider.call_args.args[1], {"rating": 5, "comment": self.review.comment})
        self.assertEqual(Review.objects.get(pk=self.review.pk).comment, self.review.comment)
        self.assertEqual(ReviewReply.objects.count(), 0)
        self.assertEqual(AIReviewAnalysis.objects.count(), 1)

    @override_settings(AI_PROVIDER="gemini", AI_REVIEW_EXPORT_APPROVED=False)
    def test_review_export_requires_explicit_approval(self):
        with patch("ai_features.gemini.GeminiProvider.structured") as provider:
            self.assertEqual(analyze_review(self.review.pk)["mode"], "rule")
            provider.assert_not_called()

    @override_settings(AI_PROVIDER="gemini", AI_REVIEW_EXPORT_APPROVED=True)
    def test_private_review_is_not_exported(self):
        Review.objects.filter(pk=self.review.pk).update(comment="Liên hệ me@example.test")
        with patch("ai_features.gemini.GeminiProvider.structured") as provider:
            self.assertEqual(analyze_review(self.review.pk)["mode"], "rule")
            provider.assert_not_called()

    @override_settings(AI_PROVIDER="gemini", AI_REVIEW_EXPORT_APPROVED=True)
    def test_invalid_review_json_and_provider_errors_use_fallback(self):
        for output in ({}, {"sentiment": "mixed"}, {"sentiment": "positive", "priority": "urgent"}):
            with patch("ai_features.gemini.GeminiProvider.structured", return_value=output):
                self.assertEqual(analyze_review(self.review.pk)["mode"], "rule")
        with patch("ai_features.gemini.GeminiProvider.structured", side_effect=TimeoutError):
            self.assertEqual(analyze_review(self.review.pk)["mode"], "rule")

    @override_settings(AI_PROVIDER="gemini", AI_REVIEW_EXPORT_APPROVED=True)
    def test_changed_review_during_inference_rejected(self):
        def changed(*args):
            Review.objects.filter(pk=self.review.pk).update(comment="Mới")
            return {}
        from .chat import ChatError
        with patch("ai_features.gemini.GeminiProvider.structured", side_effect=changed):
            with self.assertRaises(ChatError) as error:
                analyze_review(self.review.pk)
        self.assertEqual(error.exception.status, 409)
        self.assertFalse(AIReviewAnalysis.objects.exists())

    def test_batch_limit_missing_review_and_explicit_trigger(self):
        self.permit_analysis()
        path = "/api/ai/reviews/analyze/"
        self.assertEqual(self.post(path, {"reviewIds": list(range(1, 7))}).status_code, 400)
        cache.clear()
        self.assertEqual(self.post(path, {"reviewIds": [999999]}).status_code, 404)
        cache.clear()
        self.assertEqual(len(self.post(path, {"reviewIds": [self.review.pk]}).json()["items"]), 1)

    def test_saved_analysis_get_and_reload_never_invoke_provider_or_write(self):
        self.permit_analysis()
        saved = analyze_review(self.review.pk)
        saved.pop("diagnostics")  # Request diagnostics are not a persisted analysis field.
        path = f"/api/ai/reviews/{self.review.pk}/analyze/"
        with patch("ai_features.assistance.external_provider") as provider:
            with self.captureOnCommitCallbacks(execute=True):
                page = self.client.get("/admin-reviews.html")
                self.assertEqual(page.status_code, 200)
                self.assertContains(page, "Phân tích các đánh giá trong kết quả lọc (tối đa 5)")
                for _ in range(2):
                    result = self.client.get(path)
                    self.assertEqual(result.status_code, 200)
                    self.assertEqual(result.json()["analysis"], saved)
            provider.assert_not_called()
        self.assertEqual(AIReviewAnalysis.objects.count(), 1)
        self.assertEqual(ReviewReply.objects.count(), 0)

    def test_empty_analysis_get_does_not_create_or_infer(self):
        self.permit_analysis()
        with patch("ai_features.assistance.external_provider") as provider:
            response = self.client.get(f"/api/ai/reviews/{self.review.pk}/analyze/")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"analysis": None})
            provider.assert_not_called()
        self.assertFalse(AIReviewAnalysis.objects.exists())

    def test_analysis_timestamp_creation_and_reanalysis_without_new_record(self):
        first_time = timezone.now() - timedelta(hours=1)
        second_time = first_time + timedelta(minutes=10)
        with patch("django.utils.timezone.now", return_value=first_time):
            first = analyze_review(self.review.pk)
        with patch("django.utils.timezone.now", return_value=second_time):
            second = analyze_review(self.review.pk)
        self.assertEqual(first["analyzedAt"], first_time.isoformat())
        self.assertEqual(second["analyzedAt"], second_time.isoformat())
        self.assertEqual(AIReviewAnalysis.objects.get().analyzed_at, second_time)
        self.assertEqual(AIReviewAnalysis.objects.count(), 1)
        self.review.refresh_from_db()
        self.assertEqual(self.review.comment, "Không gian yên tĩnh, rất hài lòng.")

    def test_get_stale_analysis_keeps_saved_result_without_reanalysis(self):
        self.permit_analysis()
        saved = analyze_review(self.review.pk)
        Review.objects.filter(pk=self.review.pk).update(comment="Nội dung mới trong fixture")
        with patch("ai_features.assistance.external_provider") as provider:
            result = self.client.get(f"/api/ai/reviews/{self.review.pk}/analyze/").json()["analysis"]
            provider.assert_not_called()
        self.assertTrue(result["stale"])
        self.assertEqual(result["analyzedAt"], saved["analyzedAt"])
        self.assertEqual(result["summary"], saved["summary"])


@override_settings(AI_CHAT_ENABLED=True, AI_PROVIDER="mock", AI_RAG_ENABLED=False,
                   AI_CHAT_SPA_INFORMATION="Giờ mở cửa thử nghiệm: 09:00–21:00.")
class ConcurrentMockPerformanceTests(TransactionTestCase):
    @skipUnlessDBFeature("has_select_for_update")
    def test_twenty_distinct_users_mock_latency(self):
        users = [User.objects.create_user(f"perf{i}", f"perf{i}@example.test", "test-only") for i in range(20)]
        barrier = Barrier(20)
        def ask(user):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                started = perf_counter()
                answer = send_question(user.pk, None, "Giờ mở cửa", None, uuid4())
                return perf_counter()-started, answer.status
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=20) as pool:
            results = list(pool.map(ask, users))
        durations = sorted(x[0] for x in results)
        self.assertEqual(ChatMessage.objects.filter(role="assistant").count(), 20)
        self.assertTrue(all(status == "success" for _, status in results))
        # Evidence is a local orchestration baseline, not provider/MySQL/HTTP acceptance.
        print(f"MOCK_{connection.vendor.upper()}_20_USERS p95={durations[18]:.4f}s max={durations[-1]:.4f}s")
