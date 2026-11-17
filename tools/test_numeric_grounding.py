"""Pure grounding regression: fixed synthetic sources, no network or database."""
from types import SimpleNamespace
from unittest import TestCase
from ai_features.integration import GroundedProvider
from ai_features.numeric_grounding import numeric_claims_supported


class NumericGroundingTests(TestCase):
    def supported(self, source, answer):
        return numeric_claims_supported(answer, [source])

    def test_bare_integer_anchors_vietnamese_or_comma_grouping(self):
        for answer in ("200000", "200.000", "200,000"):
            self.assertTrue(self.supported("200000", answer))

    def test_currency_grouping_is_symmetric(self):
        for source in ("Giá 200000 VND", "Giá 200.000 VND", "Giá 200,000 VND"):
            for answer in ("Giá 200000 VND", "Giá 200.000 VND", "Giá 200,000 VND"):
                self.assertTrue(self.supported(source, answer))

    def test_fabricated_price_rejected(self):
        self.assertFalse(self.supported("200000", "250.000"))
        self.assertFalse(self.supported("200000 VND", "250,000 VND"))

    def test_changed_duration_rejected(self):
        self.assertFalse(self.supported("60 phút", "90 phút"))
        self.assertFalse(self.supported("60 phút", "60 giờ"))

    def test_decimal_comma_or_dot_exact_value(self):
        self.assertTrue(self.supported("12.50", "12,5"))
        self.assertFalse(self.supported("12,5", "125"))
        self.assertFalse(self.supported("12.50", "12.51"))
        self.assertTrue(self.supported("0.125 kg", "0,125 kg"))
        self.assertFalse(self.supported("1.234 kg", "1234 kg"))
        self.assertFalse(self.supported("5 VND", ".5 VND"))
        self.assertTrue(self.supported("0.5 VND", ".5 VND"))

    def test_extra_number_rejected(self):
        self.assertFalse(self.supported("Giá 200000 VND, 60 phút", "Giá 200.000 VND, 60 phút, giảm 10%"))

    def test_multiple_sources_only_evidenced_prices_allowed(self):
        sources = ["Giá 200000 VND", "Giá 350000 VND"]
        self.assertTrue(numeric_claims_supported("200.000 VND hoặc 350,000 VND", sources))
        self.assertFalse(numeric_claims_supported("275.000 VND", sources))

    def test_dates_times_and_ranges_remain_literal(self):
        for source, answer in (("16/11/2026", "16112026"), ("16.11.2026", "16.112.026"),
                               ("09:00", "900"), ("09:00", "09:30"), ("09:00–21:00", "09:00–22:00"),
                               ("10-20", "1020"), ("1.2.3", "123"), ("1e3", "1000")):
            self.assertFalse(self.supported(source, answer), (source, answer))
        for raw in ("16/11/2026", "16.11.2026", "09:00", "09:00–21:00", "10-20", "1.2.3"):
            self.assertTrue(self.supported(raw, raw))

    def test_percentages_cannot_be_promoted_to_integers_or_prices(self):
        self.assertTrue(self.supported("12,5%", "12.50%"))
        self.assertTrue(self.supported("12.500%", "12,5%"))
        for source, answer in (("12.5%", "125%"), ("12.500%", "12500%"),
                               ("10 phút", "10%"), ("10%", "10 VND"), ("10 VND", "10%")):
            self.assertFalse(self.supported(source, answer))

    def test_ambiguous_source_is_not_silently_promoted(self):
        self.assertFalse(self.supported("1.234", "1234"))
        self.assertTrue(self.supported("1.234", "1.234"))
        self.assertFalse(self.supported("1,23,456", "123456"))
        self.assertFalse(self.supported("2000.000 VND", "2000000 VND"))
        self.assertFalse(self.supported("0.5 và 0", ".5.0"))

    def test_mixed_grouping_and_decimal_fraction(self):
        for source in ("200.000,50 VND", "200,000.50 VND"):
            self.assertTrue(self.supported(source, "200000,5 VND"))
            self.assertFalse(self.supported(source, "200000 VND"))
        self.assertFalse(self.supported("1,23.45 VND", "123.45 VND"))

    def test_negative_values_are_not_positive_values(self):
        self.assertFalse(self.supported("200000 VND", "-200.000 VND"))
        self.assertTrue(self.supported("-200000 VND", "-200,000 VND"))

    def test_long_values_are_not_rounded_into_equivalence(self):
        self.assertFalse(self.supported("1234567890123456789012345678901", "1234567890123456789012345678902"))

    def test_explicit_decimal_context_is_not_thousands(self):
        self.assertTrue(self.supported("Số thập phân: 200.125", "Số thập phân: 200,125"))
        self.assertFalse(self.supported("200125", "Số thập phân: 200.125"))
        self.assertFalse(self.supported("Số thập phân: 1.234", "1234"))

    def test_grounded_provider_accepts_equivalent_value_without_weakening_source_ids(self):
        class Provider(GroundedProvider):
            result = {}
            def structured(self, instruction, data):
                return self.result
        provider = Provider()
        sources = [SimpleNamespace(kind="service", object_id=1, name="Synthetic", text="200000 VND, 60 phút")]
        for price in ("200.000", "200,000"):
            provider.result = {"answer": price + " VND", "sources": ["service:1"]}
            self.assertIn("Nguồn:", provider.answer("synthetic", sources))
        for result in ({"answer": "200.000 VND", "sources": ["service:999"]},
                       {"answer": "200.000 VND", "sources": []},
                       {"answer": "250.000 VND", "sources": ["service:1"]},
                       {"answer": 200000, "sources": ["service:1"]}):
            provider.result = result
            self.assertEqual(provider.answer("synthetic", sources), "")
