"""FR-22 endpoint + persistence regressions; run with tools/ai_tests.py only."""
import json
from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings

from accounts.models import Customer, User
from services.models import Service, ServiceCategory
from .models import AIRecommendation


@override_settings(AI_PROVIDER="gemini", AI_PERSONALIZATION_EXPORT_APPROVED=True, AI_RAG_ENABLED=False)
class RecommendationTypedApplicationTests(TestCase):
    def setUp(self):
        user=User.objects.create_user("typed_fixture","typed@example.test",password=None)
        Customer.objects.create(user=user,full_name="Khách giả lập",phone="000")
        cat=ServiceCategory.objects.create(name="Danh mục giả lập")
        self.basic=Service.objects.create(category=cat,name="Dịch vụ cơ bản",price=350000,
            duration_minutes=60,description="Làm sạch dịu nhẹ",care_group="face")
        self.deep=Service.objects.create(category=cat,name="Dịch vụ chuyên sâu",price=550000,
            duration_minutes=70,description="Cấp ẩm",care_group="face")
        self.history=[{"serviceId":self.basic.pk,"count":1,"firstUsed":"2026-11-20","lastUsed":"2026-11-20"}]
        self.client.force_login(user)

    def post(self, items, **inputs):
        cache.clear()
        with patch("ai_features.assistance.external_provider") as factory, \
             patch("ai_features.assistance.service_history",return_value=([self.basic.pk],self.history)):
            factory.return_value.structured.return_value={"items":items}
            response=self.client.post("/api/ai/recommendations/", {"skin":"Da dầu","needs":"face","budget":None,**inputs},content_type="application/json")
            factory.return_value.structured.assert_called_once()
        self.assertEqual(response.status_code,200)
        self.saved=json.loads(AIRecommendation.objects.latest("pk").reason)
        return response.json()

    def row(self, service, reason):
        return {"id":service.pk,"reason":reason}

    def test_multiple_services_keep_their_own_numeric_facts(self):
        items=[self.row(self.basic,"Giá 350.000 VND, 1 giờ; đã sử dụng một lần ngày 20/11/2026."),
               self.row(self.deep,"Giá 550 nghìn đồng, thời lượng 1 giờ 10 phút, cấp ẩm.")]
        result=self.post(items)
        self.assertEqual(result["mode"],"ai")
        self.assertEqual([r["reason"] for r in result["items"]],[r["reason"] for r in items])
        self.assertEqual(self.saved["diagnostics"],{"code":"AI_RECOMMENDATION_VALIDATED"})

    def test_swapping_another_service_price_or_minutes_falls_back_as_a_whole(self):
        for reason,check in (("Giá 550000 VND.","PRICE_OR_BUDGET_MISMATCH"),
                             ("Thời lượng 70 phút.","DURATION_MISMATCH")):
            with self.subTest(reason=reason):
                result=self.post([self.row(self.basic,reason),self.row(self.deep,"Cấp ẩm dịu nhẹ.")])
                self.assertEqual(result["mode"],"rule")
                self.assertEqual(self.saved["diagnostics"],{"code":"OUTPUT_NUMERIC_GROUNDING_FAILED",
                    "serviceId":self.basic.pk,"check":check})
                self.assertNotIn(reason,json.dumps(self.saved,ensure_ascii=False))

    def test_history_of_other_service_cannot_validate_count_or_date(self):
        for reason,check in (("Đã sử dụng 1 lần.","HISTORY_COUNT_MISMATCH"),
                             ("Đã sử dụng ngày 20/11/2026.","HISTORY_DATE_MISMATCH")):
            with self.subTest(reason=reason):
                self.assertEqual(self.post([self.row(self.deep,reason)])["mode"],"rule")
                self.assertEqual(self.saved["diagnostics"]["check"],check)

    def test_budget_is_not_a_service_price_and_null_stays_null(self):
        self.assertEqual(self.post([self.row(self.basic,"Giá 600000 VND.")],budget="600000")["mode"],"rule")
        result=self.post([self.row(self.basic,"Ngân sách 600000 VND, giá 350000 VND.")],budget="600000")
        self.assertEqual(result["mode"],"ai")
        self.assertEqual(self.post([self.row(self.basic,"Ngân sách 350000 VND.")])["mode"],"rule")
        self.assertEqual(self.saved["diagnostics"]["check"],"BUDGET_NOT_CONFIGURED")

    def test_sourced_percent_is_valid_but_effectiveness_percent_is_not(self):
        self.basic.benefits="Công thức chứa 5% niacinamide."
        self.basic.save()
        self.assertEqual(self.post([self.row(self.basic,"Công thức chứa 5% niacinamide.")])["mode"],"ai")
        for target,reason in ((self.basic,"Hiệu quả 5%."),(self.deep,"Công thức chứa 5% niacinamide.")):
            self.assertEqual(self.post([self.row(target,reason)])["mode"],"rule")
            self.assertEqual(self.saved["diagnostics"]["check"],"UNSUPPORTED_PERCENT_OR_MEASURE")

    def test_valid_large_price_does_not_disable_privacy_filter(self):
        self.basic.price=Decimal("1200000.00")
        self.basic.save()
        self.assertEqual(self.post([self.row(self.basic,"Giá 1200000.00 VND.")])["mode"],"ai")
        secret_reason="Giá 1200000.00 VND; liên hệ private@example.test."
        self.assertEqual(self.post([self.row(self.basic,secret_reason)])["mode"],"rule")
        self.assertEqual(self.saved["diagnostics"]["code"],"OUTPUT_SCHEMA_INVALID")
        self.assertNotIn("private@example.test",json.dumps(self.saved))

    def test_medical_and_guarantee_phrases_stay_rejected(self):
        for reason in ("Điều trị da, giá 350000 VND.","Cam kết hiệu quả với thời lượng 60 phút."):
            self.assertEqual(self.post([self.row(self.basic,reason)])["mode"],"rule")
            self.assertEqual(self.saved["diagnostics"]["code"],"OUTPUT_FORBIDDEN_PHRASE")

    def test_catalog_change_during_inference_discards_old_price(self):
        cache.clear()
        def answer(*args):
            Service.objects.filter(pk=self.basic.pk).update(price=400000)
            return {"items":[self.row(self.basic,"Giá 350000 VND.")]}
        with patch("ai_features.assistance.external_provider") as factory:
            factory.return_value.structured.side_effect=answer
            result=self.client.post("/api/ai/recommendations/",{"needs":"face","budget":None},content_type="application/json").json()
        self.assertEqual(result["mode"],"rule")
        self.assertEqual(json.loads(AIRecommendation.objects.latest("pk").reason)["diagnostics"]["code"],"CATALOG_CHANGED_DURING_INFERENCE")
