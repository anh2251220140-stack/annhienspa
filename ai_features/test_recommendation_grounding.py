"""FR-22 grounding matrix; synthetic facts only, no network/database."""
from decimal import Decimal
from types import SimpleNamespace
from unittest import TestCase

from .recommendation_grounding import check_recommendation_numbers


def service(pk=2, name="Dịch vụ cơ bản", price="350000.00", minutes=60, **fields):
    return SimpleNamespace(pk=pk, name=name, price=Decimal(price), duration_minutes=minutes,
        **{k:fields.get(k, "") for k in ("description", "benefits", "suitable", "steps", "note")})


class RecommendationNumberTests(TestCase):
    def setUp(self):
        self.basic = service()
        self.deep = service(6, "Dịch vụ chuyên sâu", "550000.00", 70)
        self.history = [{"serviceId":2,"count":1,"firstUsed":"2026-10-15","lastUsed":"2026-11-20"},
                        {"serviceId":6,"count":3,"firstUsed":"2026-09-10","lastUsed":"2026-11-19"}]

    def check(self, text, *, target=None, budget=None, history=None):
        return check_recommendation_numbers(text,target or self.basic,budget,
            self.history if history is None else history,[self.basic,self.deep])

    def test_money_format_matrix(self):
        amounts = ["350000", "350000.00", "350000,00", "350.000", "350,000",
                   "350.000,00", "350,000.00", "350 000", "350\u00a0000", "350\u202f000"]
        for amount in amounts:
            for label in ("Giá", "giá là", "Chi phí", "Đơn giá"):
                for unit in ("VND", "VNĐ", "đ", "đồng", "₫"):
                    with self.subTest(amount=amount,label=label,unit=unit):
                        self.assertIsNone(self.check(f"{label} {amount} {unit}.").code)

    def test_bare_price_requires_price_context(self):
        self.assertIsNone(self.check("Giá 350.000, phù hợp nhu cầu.").code)
        self.assertIsNotNone(self.check("Gợi ý 350000.").code)

    def test_exact_money_scales(self):
        for value in ("350 nghìn đồng", "350 ngàn", "350k", "0,35 triệu đồng", "ba trăm năm mươi nghìn đồng"):
            with self.subTest(value=value):
                self.assertIsNone(self.check(f"Giá {value}.").code)
        for value in ("35 nghìn", "350 triệu", "0,350001 triệu đồng"):
            self.assertIsNotNone(self.check(f"Giá {value}.").code)

    def test_large_and_fractional_source_prices_without_float_rounding(self):
        for price, text in (("1200000.00","Giá 1.200.000 VND."),("350000.50","Giá 350.000,50 VND.")):
            self.basic.price=Decimal(price)
            self.assertIsNone(self.check(text).code)
        self.basic.price=Decimal("350000.50")
        self.assertIsNotNone(self.check("Giá 350000 VND.").code)
        self.assertIsNotNone(self.check("Giá 350000.5000000000000000000001 VND.").code)

    def test_bad_currency_values_and_grouping(self):
        for value in ("-350000", "350.001", "350,001", "1,23.45", "35,00,00", "3500.000", "3.5e5", "NaN", "Infinity"):
            text=f"Giá {value} VND."
            with self.subTest(value=value):
                # Non-numeric special values must not evade the numeric guard.
                self.assertIsNotNone(self.check(text).code)

    def test_duration_formats_exact_equivalence(self):
        for text in ("60 phút", "60phút", "60 min", "60p", "1 giờ", "1h", "một giờ", "sáu mươi phút"):
            self.assertIsNone(self.check(f"Thời lượng {text}.").code, text)
        for text in ("70 phút", "1 giờ 10 phút", "1h10p", "một giờ mười phút"):
            self.assertIsNone(self.check(f"Thời lượng {text}.",target=self.deep).code, text)
        self.deep.duration_minutes=90
        for text in ("1,5 giờ", "1.5 giờ", "1 giờ 30 phút"):
            self.assertIsNone(self.check(text,target=self.deep).code,text)

    def test_wrong_duration_and_unit_cannot_borrow_price_or_history(self):
        for text in ("Thời lượng 70 phút.", "60 giờ", "1 phút", "350000 phút", "1,01 giờ", "1 giờ 60 phút"):
            self.assertIsNotNone(self.check(text).code,text)

    def test_money_and_budget_have_distinct_roles(self):
        self.assertIsNone(self.check("Ngân sách 600.000 VND; giá 350.000 VND.",budget="600000").code)
        self.assertIsNotNone(self.check("Giá 600.000 VND.",budget="600000").code)
        self.assertIsNotNone(self.check("Ngân sách 350000 VND.").code)
        self.assertIsNotNone(self.check("Ngân sách 500000 VND.",budget="600000").code)

    def test_service_price_and_minutes_are_not_pooled(self):
        for text in ("Giá 550000 VND.", "Thời lượng 70 phút.", "Đã sử dụng 3 lần."):
            self.assertIsNotNone(self.check(text).code,text)

    def test_explicit_named_comparisons_are_scoped(self):
        text="Dịch vụ chuyên sâu giá 550000 VND, thời lượng 70 phút; Dịch vụ cơ bản giá 350000 VND, 60 phút."
        self.assertIsNone(self.check(text).code)
        self.assertIsNotNone(self.check(text.replace("70 phút","60 phút")).code)
        self.assertIsNotNone(self.check(text.replace("550000","350000")).code)

    def test_visits_belong_to_the_named_service(self):
        for text in ("Đã sử dụng 1 lần.", "Đã sử dụng một lượt."):
            self.assertIsNone(self.check(text).code,text)
        self.assertIsNone(self.check("Dịch vụ chuyên sâu đã sử dụng ba lần.").code)
        self.assertIsNotNone(self.check("Đã sử dụng ba lần.").code)
        self.assertIsNotNone(self.check("Đã sử dụng một lần.",history=[]).code)
        self.assertIsNotNone(self.check("Chưa sử dụng, 0 lần.",history=[]).code)

    def test_history_count_does_not_become_price_or_percent(self):
        for text in ("Giá 1 VND.", "Hiệu quả 1%.", "Thời lượng 1 phút."):
            self.assertIsNotNone(self.check(text).code)

    def test_same_dates_in_iso_vietnamese_and_natural_format(self):
        for day in ("2026-11-20", "20/11/2026", "20-11-2026", "20.11.2026", "ngày 20 tháng 11 năm 2026"):
            self.assertIsNone(self.check(f"Lần gần nhất vào {day}.").code,day)
        self.assertIsNone(self.check("Đã dùng vào năm 2026.").code)

    def test_wrong_dates_and_cross_service_history_rejected(self):
        for text in ("Lần gần nhất 19/11/2026.", "Lần đầu tiên 20/11/2026.", "Đã dùng 31/02/2026.","Đã dùng năm 2025."):
            self.assertIsNotNone(self.check(text).code,text)
        self.assertIsNone(self.check("Dịch vụ chuyên sâu lần gần nhất 19/11/2026.").code)
        self.assertIsNotNone(self.check("Dịch vụ chuyên sâu lần gần nhất 20/11/2026.").code)

    def test_percent_only_when_sourced_for_this_service(self):
        self.basic.benefits="Công thức chứa 5% niacinamide."
        for text in ("Công thức chứa 5% niacinamide.","Có 5,0 phần trăm niacinamide."):
            self.assertIsNone(self.check(text).code,text)
        for text in ("Hiệu quả tăng 5%.","Công thức chứa 50% niacinamide."):
            self.assertIsNotNone(self.check(text).code,text)
        self.assertIsNotNone(self.check("Công thức chứa 5% niacinamide.",target=self.deep).code)

    def test_percent_is_not_inferred_from_price_minutes_or_counts(self):
        for text in ("Hiệu quả 60%.","Giảm 350000%.","Giảm 1%."):
            self.assertIsNotNone(self.check(text).code)

    def test_sourced_measurements_and_identifiers(self):
        self.basic.description="Sử dụng 5 ml serum vitamin B5."
        self.assertIsNone(self.check("Sử dụng 5 ml serum vitamin B5.").code)
        self.assertIsNotNone(self.check("Sử dụng 5 kg serum.").code)
        self.assertIsNotNone(self.check("Sử dụng 50 ml serum.").code)
        self.assertIsNotNone(self.check("Sử dụng vitamin B12.").code)

    def test_validated_numbers_mask_only_for_privacy_check(self):
        self.basic.price=Decimal("1200000.00")
        check=self.check("Giá 1200000.00 VND; liên hệ test@example.test.")
        self.assertIsNone(check.code)
        self.assertNotIn("1200000",check.privacy_text)
        self.assertIn("test@example.test",check.privacy_text)

    def test_unknown_bare_numbers_fail_closed(self):
        for text in ("Kết quả 99.","09:00", "3.5e5 VND", "350000 và 60"):
            self.assertIsNotNone(self.check(text).code,text)

    def test_id11_numeric_claims_replay(self):
        text="Dịch vụ cơ bản (350000.00 VND, 60 phút), đã sử dụng 1 lần gần nhất vào ngày 2026-11-20."
        self.assertIsNone(self.check(text).code)

    def test_id12_13_14_inputs_with_only_valid_simulated_claims(self):
        for target,text in ((self.deep,"Giá 550.000 VND, thời lượng 1 giờ 10 phút."),
                            (self.basic,"Giá 350.000 VND, đã dùng 1 lần ngày 20/11/2026.")):
            self.assertIsNone(self.check(text,target=target).code)
        # These are simulations, not recovered responses from IDs 12–14.

    def test_diagnostics_never_contain_raw_text(self):
        reason="Không có nguồn cho 999999 VND; private-example."
        result=self.check(reason)
        self.assertIsNotNone(result.code)
        self.assertEqual(result.privacy_text,"")
        self.assertNotIn(reason,repr(result))

    def test_natural_vietnamese_prepositions_are_not_quantity_claims(self):
        for text in ("Đã biết dịch vụ từ lần trước.", "Có thể trao đổi từ buổi trước.", "Làm sạch và chăm sóc dịu nhẹ.",
                     "Sau lần trải nghiệm trước, có thể trao đổi thêm."):
            self.assertIsNone(self.check(text).code,text)
        self.assertIsNotNone(self.check("Đã sử dụng sáu lần.").code)

    def test_correct_number_with_wrong_semantic_role_is_rejected(self):
        for text in ("Giá 20/11/2026.","Giá 60 phút.","Thời lượng 350000 VND."):
            self.assertEqual(self.check(text).code,"NUMERIC_ROLE_MISMATCH",text)

    def test_count_and_duration_grouping_do_not_hide_a_thousand_fold_error(self):
        self.assertIsNotNone(self.check("Đã dùng 1.000 lần.").code)
        self.assertIsNotNone(self.check("Thời lượng 60.000 phút.").code)
        self.assertIsNone(self.check("Thời lượng 60,00 phút.").code)
        self.history[0]["count"]=1000
        self.assertIsNone(self.check("Đã dùng 1.000 lần.").code)

    def test_unique_qualified_service_alias_can_ground_comparison_history(self):
        self.basic.name="Chăm sóc da mặt cơ bản"
        self.deep.name="Chăm sóc da mặt chuyên sâu cấp ẩm"
        text="Bạn đã trải nghiệm dịch vụ cơ bản một lần gần nhất vào ngày 20/11/2026."
        self.assertIsNone(self.check(text,target=self.deep).code)
        self.assertIsNotNone(self.check(text.replace("một lần","ba lần"),target=self.deep).code)

    def test_generic_words_cannot_turn_ingredient_percent_into_effectiveness(self):
        self.basic.benefits="Giúp chăm sóc da với 5% niacinamide."
        self.assertIsNotNone(self.check("Giúp tăng hiệu quả 5%.").code)
        self.assertIsNone(self.check("Có 5% niacinamide.").code)

    def test_deterministic_value_sweep_accepts_only_the_correct_typed_fact(self):
        for amount in ("0", "1", "5", "350", "350000", "550000", "1200000", "9999999999.99"):
            self.basic.price=Decimal(amount)
            self.assertIsNone(self.check(f"Giá {amount} VND.").code)
            with self.subTest(amount=amount):
                self.assertIsNotNone(self.check(f"Giá {Decimal(amount)+1} VND.").code)
        for minutes in (1,5,60,70,90,180):
            self.basic.duration_minutes=minutes
            self.assertIsNone(self.check(f"Thời lượng {minutes} phút.").code)
            self.assertIsNotNone(self.check(f"Thời lượng {minutes+1} phút.").code)
        for count in (1,2,5,1000):
            self.history[0]["count"]=count
            self.assertIsNone(self.check(f"Đã sử dụng {count} lần.").code)
            self.assertIsNotNone(self.check(f"Đã sử dụng {count+1} lần.").code)

    def test_unambiguous_compound_vietnamese_currency(self):
        self.basic.price=Decimal("1200000")
        for text in ("Giá 1 triệu 200 nghìn đồng.","Giá một triệu hai trăm nghìn đồng.","Giá 1 triệu 200k."):
            self.assertIsNone(self.check(text).code,text)
        self.assertIsNotNone(self.check("Giá 1 triệu 300 nghìn đồng.").code)

    def test_history_entity_can_follow_a_quantity_when_explicit(self):
        self.basic.name="Chăm sóc da mặt cơ bản"
        self.deep.name="Chăm sóc da mặt chuyên sâu cấp ẩm"
        self.assertIsNone(self.check("Bạn từng trải nghiệm một lần dịch vụ cơ bản ngày 20/11/2026.",target=self.deep).code)
        self.assertIsNotNone(self.check("Bạn từng trải nghiệm ba lần dịch vụ cơ bản.",target=self.deep).code)

    def test_same_names_use_the_selected_id_without_borrowing_another_price(self):
        self.basic.name=self.deep.name="Tên dịch vụ trùng nhau"
        self.assertIsNone(self.check("Tên dịch vụ trùng nhau giá 550000 VND.",target=self.deep).code)
        self.assertIsNotNone(self.check("Tên dịch vụ trùng nhau giá 550000 VND.",target=self.basic).code)

    def test_duplicate_signs_or_decimal_marks_are_not_valid_amounts(self):
        self.basic.price=Decimal("0")
        for text in ("Giá ++0 VND.","Giá 0..00 VND.","Giá --0 VND."):
            self.assertEqual(self.check(text).code,"MALFORMED_NUMBER")

    def test_currency_symbols_without_a_price_prefix(self):
        for unit in ("VND","VNĐ","đ","đồng","₫"):
            self.assertIsNone(self.check(f"Liệu trình (350.000 {unit}) phù hợp nhu cầu.").code,unit)

    def test_natural_hour_synonyms_and_halves_preserve_exact_values(self):
        self.assertIsNone(self.check("Thời lượng một tiếng.").code)
        self.assertIsNotNone(self.check("Thời lượng hai tiếng.").code)
        self.basic.duration_minutes=90
        for text in ("một giờ rưỡi", "một tiếng rưỡi", "1 tiếng 30 phút"):
            self.assertIsNone(self.check(f"Thời lượng {text}.").code,text)
        self.basic.duration_minutes=30
        self.assertIsNone(self.check("Thời lượng nửa tiếng.").code)
        self.assertIsNotNone(self.check("Đã sử dụng một lần rưỡi.").code)
