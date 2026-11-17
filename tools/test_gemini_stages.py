"""Stage-only FR-21 diagnostics with fake SDK responses. No live CLI or DB."""
from contextlib import ExitStack, redirect_stdout
from io import StringIO
import json
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import PropertyMock, patch
import httpx
from tools import gemini_live as live


class GeminiStageTests(TestCase):
    @classmethod
    def setUpClass(cls):
        live.configure(generation_only=True)

    def run_case(self, *, text=None, empty=False, status=200, transport_error=None, setup_error=False, envelope=None):
        requests = []
        def transport(_transport, request):
            requests.append(request)
            if transport_error:
                raise transport_error
            if status != 200:
                return httpx.Response(status, request=request, json={"error": {"code": status,
                    "status": "INVALID_ARGUMENT", "message": "PRIVATE-RESPONSE"}})
            body = {"candidates": []} if empty else {"candidates": [{"content": {"role": "model",
                "parts": [{"text": text}]}}]}
            if envelope is not None:
                body = envelope
            return httpx.Response(200, request=request, json=body)
        output = StringIO()
        with ExitStack() as stack:
            stack.enter_context(patch("socket.socket.connect", side_effect=AssertionError("Real network forbidden")))
            stack.enter_context(patch.object(live.sys.stdin, "isatty", return_value=True))
            stack.enter_context(patch("builtins.input", return_value=live.CONFIRMATION))
            stack.enter_context(patch("tools.openai_test.hidden_input", return_value="FAKE-KEY"))
            stack.enter_context(patch.object(live, "configure"))
            stack.enter_context(patch.object(httpx.HTTPTransport, "handle_request", transport))
            if setup_error:
                stack.enter_context(patch("google.genai.Client", side_effect=ValueError("PRIVATE-RESPONSE")))
            with redirect_stdout(output):
                report = live.generate_only("fr21")
        self.assertLessEqual(len(requests), 1)
        self.assertTrue(all(code in live.STAGE_CODES for code in report["stage_codes"]))
        for private in ("FAKE-KEY", "PRIVATE-RESPONSE", "PRIVATE-ANSWER", "PRIVATE-PROMPT"):
            self.assertNotIn(private, json.dumps(report) + output.getvalue())
        self.assertNotIn("Reply exactly", output.getvalue())
        return report, requests

    def assert_failure(self, code, **kwargs):
        report, requests = self.run_case(**kwargs)
        self.assertEqual(report["status"], "FALLBACK")
        self.assertFalse(report["result"]["grounded_response_validated"])
        self.assertIn(code, report["stage_codes"])
        self.assertNotIn("ANSWER_VALIDATED", report["stage_codes"])
        return report, requests

    def test_before_http_is_not_mistaken_for_received_response(self):
        report, requests = self.assert_failure("REQUEST_NOT_SENT", setup_error=True)
        self.assertEqual(requests, [])
        self.assertEqual(report["http_requests"], 0)
        self.assertNotIn("HTTP_RESPONSE_RECEIVED", report["stage_codes"])

    def test_dispatched_but_no_response(self):
        report, requests = self.assert_failure("HTTP_RESPONSE_NOT_RECEIVED",
            transport_error=httpx.ReadTimeout("PRIVATE-RESPONSE"))
        self.assertEqual(len(requests), 1)
        self.assertNotIn("HTTP_RESPONSE_RECEIVED", report["stage_codes"])

    def test_non200_is_distinct_from_json_and_grounding_errors(self):
        report, _ = self.assert_failure("HTTP_RESPONSE_NOT_OK", status=400)
        self.assertIn("HTTP_RESPONSE_RECEIVED", report["stage_codes"])
        self.assertNotIn("JSON_PARSE_FAILED", report["stage_codes"])

    def test_http200_empty_response_text(self):
        report, _ = self.assert_failure("RESPONSE_TEXT_EMPTY", empty=True)
        self.assertIn("HTTP_RESPONSE_OK", report["stage_codes"])
        self.assertEqual(report["diagnostics"], [])

    def test_http200_sdk_decode_failure(self):
        from google.genai.models import Models
        original = Models.generate_content
        def fail_after_http(*args, **kwargs):
            original(*args, **kwargs)
            raise ValueError("PRIVATE-RESPONSE")
        with patch.object(Models, "generate_content", fail_after_http):
            report, _ = self.assert_failure("SDK_GENERATION_FAILED", text='{}')
        self.assertIn("HTTP_RESPONSE_OK", report["stage_codes"])
        self.assertNotIn("SDK_RESPONSE_RECEIVED", report["stage_codes"])

    def test_malformed_sdk_envelope_can_be_returned_as_empty_text(self):
        self.assert_failure("RESPONSE_TEXT_EMPTY", envelope={"candidates": "PRIVATE-RESPONSE"})

    def test_response_text_property_failure_is_identified(self):
        from google.genai import types
        with patch.object(types.GenerateContentResponse, "text", new_callable=PropertyMock,
                          side_effect=ValueError("PRIVATE-RESPONSE")):
            self.assert_failure("RESPONSE_TEXT_READ_FAILED", text='{}')

    def test_response_text_length_limit_is_unchanged(self):
        self.assert_failure("RESPONSE_TEXT_TOO_LONG", text="x" * 20001)

    def test_json_parse_failed(self):
        for text in ("PRIVATE-RESPONSE invalid json", '{"answer":NaN}'):
            with self.subTest(kind=type(text).__name__):
                report, _ = self.assert_failure("JSON_PARSE_FAILED", text=text)
                self.assertEqual(report["failure_stage_code"], "JSON_PARSE_FAILED")

    def test_json_not_object(self):
        self.assert_failure("JSON_NOT_OBJECT", text='[]')

    def test_answer_missing(self):
        self.assert_failure("ANSWER_MISSING", text=json.dumps({"sources": ["service:900001"]}))

    def test_answer_invalid(self):
        self.assert_failure("ANSWER_INVALID", text=json.dumps({"answer": None, "sources": ["service:900001"]}))

    def test_source_list_missing_or_empty(self):
        for refs in (None, [], "service:900001"):
            self.assert_failure("SOURCE_LIST_INVALID", text=json.dumps({"answer": "PRIVATE-ANSWER", "sources": refs}))

    def test_source_id_invalid(self):
        self.assert_failure("SOURCE_ID_INVALID", text=json.dumps({"answer": "PRIVATE-ANSWER", "sources": ["service:999999"]}))

    def test_numeric_grounding_failed(self):
        report, _ = self.assert_failure("NUMERIC_GROUNDING_FAILED", text=json.dumps({
            "answer": "Giá 999999 VND", "sources": ["service:900001"]}))
        self.assertIn("FINAL_ANSWER_NOT_CREATED", report["stage_codes"])
        self.assertEqual(report["failure_stage_code"], "NUMERIC_GROUNDING_FAILED")

    def test_valid_response_records_validation_without_content(self):
        report, requests = self.run_case(text=json.dumps({"answer": "Giá 200000 VND", "sources": ["service:900001"]}))
        self.assertEqual(len(requests), 1)
        self.assertEqual(report["status"], "PASS")
        self.assertIn("ANSWER_VALIDATED", report["stage_codes"])
        self.assertTrue(report["result"]["grounded_response_validated"])
        self.assertIsNone(report["failure_stage_code"])
        self.assertNotIn("200000", json.dumps(report))

    def test_equivalent_thousands_format_passes_full_generate_only_pipeline(self):
        for price in ("200.000", "200,000"):
            report, requests = self.run_case(text=json.dumps({"answer": price + " VND",
                "sources": ["service:900001"]}))
            self.assertEqual(len(requests), 1)
            self.assertEqual(report["status"], "PASS")
            self.assertTrue(report["result"]["grounded_response_validated"])
            self.assertIn("ANSWER_VALIDATED", report["stage_codes"])
            self.assertNotIn("NUMERIC_GROUNDING_FAILED", report["stage_codes"])

    def test_final_answer_build_failure_records_fixed_code(self):
        from ai_features.integration import GroundedProvider
        codes = []
        class Provider(GroundedProvider):
            def structured(self, instruction, data):
                return {"answer": "Synthetic", "sources": ["service:1"]}
            def _trace_stage(self, code):
                codes.append(code)
        source = SimpleNamespace(kind="service", object_id=1, text="Synthetic", name=["PRIVATE-ANSWER"])
        with self.assertRaises(TypeError):
            Provider().answer("PRIVATE-PROMPT", [source])
        self.assertEqual(codes, ["FINAL_ANSWER_BUILD_FAILED"])

    def test_trace_allowlist_drops_unknown_codes_and_caps_length(self):
        budget = live.Budget(1)
        budget.record_stage("PRIVATE-RESPONSE")
        self.assertEqual(budget.stage_codes, [])
        for _ in range(100):
            budget.record_stage("ANSWER_VALIDATED")
        self.assertEqual(len(budget.stage_codes), 64)
