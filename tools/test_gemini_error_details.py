"""Pure offline error projection tests; no Django configuration or client creation."""
import json
from unittest import TestCase
import httpx
from tools.gemini_live import safe_error_details, safe_google_error


class GeminiErrorDetailsTests(TestCase):
    def test_error_info_keeps_only_allowed_reason_domain_service(self):
        result = safe_error_details([{"@type": "type.googleapis.com/google.rpc.ErrorInfo",
            "reason": "API_KEY_SERVICE_BLOCKED", "domain": "googleapis.com", "message": "PRIVATE",
            "metadata": {"service": "generativelanguage.googleapis.com", "consumer": "PRIVATE", "apiKey": "PRIVATE"}}])
        self.assertEqual(result, [{"type": "google.rpc.ErrorInfo", "reason": "API_KEY_SERVICE_BLOCKED",
            "domain": "googleapis.com", "service": "generativelanguage.googleapis.com"}])
        self.assertNotIn("PRIVATE", json.dumps(result))

    def test_unknown_labels_and_types_are_dropped_not_guessed(self):
        self.assertEqual(safe_error_details([
            {"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": "PRIVATE", "domain": "PRIVATE",
             "metadata": {"service": "PRIVATE"}}, {"@type": "PRIVATE", "reason": "API_KEY_INVALID"}]), [])

    def test_bad_request_only_known_field_names_no_descriptions(self):
        result = safe_error_details([{"@type": "type.googleapis.com/google.rpc.BadRequest", "fieldViolations": [
            {"field": "contents[0].parts[0].text", "description": "PRIVATE"},
            {"field": "generation_config.response_mime_type", "description": "PRIVATE"},
            {"field": "generationConfig.responseMimeType"},
            {"field": 'generationConfig.responseSchema.properties["PRIVATE"]'},
            {"field": "PRIVATE"}]}])
        self.assertEqual(result, [{"type": "google.rpc.BadRequest", "fields": [
            "contents[].parts[].text", "generationConfig.responseMimeType"]}])

    def test_bad_types_and_unhashable_values_do_not_escape(self):
        for value in (None, "PRIVATE", {}, [None, [], "PRIVATE"],
            [{"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": {}, "domain": [], "metadata": []}],
            [{"@type": "type.googleapis.com/google.rpc.BadRequest", "fieldViolations": [None, {"field": []}]}]):
            self.assertEqual(safe_error_details(value), [])

    def test_details_are_parsed_even_without_message_and_body_is_not_retained(self):
        result = safe_google_error(httpx.Response(400, json={"error": {"code": 400,
            "status": "INVALID_ARGUMENT", "details": [{"@type": "type.googleapis.com/google.rpc.BadRequest",
            "fieldViolations": [{"field": "model", "description": "PRIVATE"}]}]}}))
        self.assertEqual(result["details"], [{"type": "google.rpc.BadRequest", "fields": ["model"]}])
        self.assertNotIn("PRIVATE", json.dumps(result))

    def test_details_and_field_count_bounds(self):
        item = {"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": "API_KEY_INVALID"}
        self.assertEqual(len(safe_error_details([item] * 20)), 16)
        result = safe_error_details([{"@type": "type.googleapis.com/google.rpc.BadRequest",
            "fieldViolations": [{"field": "PRIVATE"}] * 32 + [{"field": "model"}]}])
        self.assertEqual(result, [])
