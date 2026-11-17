"""APIError construction and response parsing only: no client/key/DB/network."""
import importlib.metadata
import json
from unittest import TestCase
from unittest.mock import patch
import httpx
from google.genai.errors import APIError, ClientError
from tools.gemini_live import safe_google_error, safe_sdk_error


def fixture(*, wrapped=True, details=True):
    body = {"code": 400, "status": "INVALID_ARGUMENT", "message": "PRIVATE-PROMPT FAKE-KEY"}
    if details:
        body["details"] = [
            {"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": "API_KEY_SERVICE_BLOCKED",
             "domain": "googleapis.com", "metadata": {"service": "generativelanguage.googleapis.com",
             "consumer": "PRIVATE-PROJECT", "key": "FAKE-KEY"}},
            {"@type": "type.googleapis.com/google.rpc.BadRequest", "fieldViolations": [
                {"field": "generation_config.max_output_tokens", "description": "PRIVATE-PROMPT"}]}]
    return {"error": body} if wrapped else body


class GeminiSDKDiagnosticsTests(TestCase):
    def setUp(self):
        self.socket_guard = patch("socket.socket.connect", side_effect=AssertionError("Offline only"))
        self.socket_guard.start()
        self.addCleanup(self.socket_guard.stop)

    def assert_private_data_removed(self, result):
        text = json.dumps(result)
        for value in ("PRIVATE-PROMPT", "FAKE-KEY", "PRIVATE-PROJECT", "consumer", "description"):
            self.assertNotIn(value, text)

    def test_sdk234_stores_entire_nested_response_and_extracts_properties(self):
        self.assertEqual(importlib.metadata.version("google-genai"), "2.34.0")
        body = fixture()
        error = ClientError(400, body)
        self.assertIs(error.details, body)
        self.assertIsInstance(error.details, dict)
        self.assertEqual(error.code, 400)
        self.assertEqual(error.status, "INVALID_ARGUMENT")
        self.assertEqual(error.message, body["error"]["message"])
        # Verify SDK formatting would expose the raw JSON; never use str(error) in output.
        self.assertIsNot(error.details, body["error"]["details"])

    def test_nested_and_flat_http_and_sdk_diagnostics_are_identical(self):
        results = []
        for wrapped in (True, False):
            body = fixture(wrapped=wrapped)
            results.append(safe_google_error(httpx.Response(400, json=body)))
            results.append(safe_sdk_error(ClientError(400, body)))
        for result in results:
            self.assertEqual(result, results[0])
            self.assertEqual(result["google_error_code"], 400)
            self.assertEqual(result["google_error_status"], "INVALID_ARGUMENT")
            self.assertEqual(len(result["details"]), 2)
            self.assert_private_data_removed(result)

    def test_raise_for_response_preserves_wrapped_json_without_http_call(self):
        response = httpx.Response(400, json=fixture())
        with self.assertRaises(ClientError) as caught:
            APIError.raise_for_response(response)
        self.assertEqual(set(caught.exception.details), {"error"})
        self.assertEqual(safe_sdk_error(caught.exception)["details"][0]["reason"], "API_KEY_SERVICE_BLOCKED")

    def test_error_info_and_bad_request_are_read_from_normalized_error_details_only(self):
        result = safe_sdk_error(ClientError(400, fixture()))
        self.assertEqual(result["details"], [
            {"type": "google.rpc.ErrorInfo", "reason": "API_KEY_SERVICE_BLOCKED", "domain": "googleapis.com",
             "service": "generativelanguage.googleapis.com"},
            {"type": "google.rpc.BadRequest", "fields": ["generationConfig.maxOutputTokens"]}])
        self.assert_private_data_removed(result)
        # A raw list of RPC detail objects is NOT a whole API error response.
        raw_list = fixture()["error"]["details"]
        self.assertEqual(safe_sdk_error(ClientError(400, raw_list))["details"], [])

    def test_no_details_is_honestly_empty_not_a_fabricated_cause(self):
        for wrapped in (True, False):
            result = safe_sdk_error(ClientError(400, fixture(wrapped=wrapped, details=False)))
            self.assertEqual(result["details"], [])
            self.assertEqual(result["google_error_status"], "INVALID_ARGUMENT")
            self.assert_private_data_removed(result)

    def test_singleton_list_matches_sdk_unwrapping(self):
        body = fixture()
        error = ClientError(400, [body])
        self.assertIs(error.details, body)
        self.assertEqual(safe_google_error(httpx.Response(400, json=[body])), safe_sdk_error(error))

    def test_malformed_and_oversized_http_or_sdk_payloads_are_safe(self):
        for text in ("PRIVATE-PROMPT not json", '{"error":', "FAKE-KEY" * 3000):
            result = safe_google_error(httpx.Response(400, text=text))
            self.assertEqual(result["http_status"], 400)
            self.assertEqual(result["details"], [])
            self.assert_private_data_removed(result)
        for body in (None, "PRIVATE-PROMPT", {"error": {"message": "FAKE-KEY" * 3000}}):
            result = safe_sdk_error(ClientError(400, body))
            self.assertEqual(result["details"], [])
            self.assert_private_data_removed(result)

    def test_sdk_http_code_does_not_replace_google_body_code(self):
        body = {"error": {"code": 403, "status": "PERMISSION_DENIED"}}
        result = safe_sdk_error(ClientError(400, body))
        self.assertEqual(result["http_status"], 400)
        self.assertEqual(result["google_error_code"], 403)

    def test_sdk_properties_used_only_as_fallback_and_unknown_exception_ignored(self):
        error = ClientError(400, {"status": "INVALID_ARGUMENT", "message": "PRIVATE-PROMPT"})
        self.assertEqual(safe_sdk_error(error)["google_error_code"], 400)
        self.assertIsNone(safe_sdk_error(ValueError("PRIVATE-PROMPT")))

    def test_nested_payload_takes_precedence_over_unrelated_top_level_fields(self):
        body = fixture()
        body.update(code=403, status="PERMISSION_DENIED", details=[{"private": "FAKE-KEY"}])
        result = safe_google_error(httpx.Response(400, json=body))
        self.assertEqual(result["google_error_code"], 400)
        self.assertEqual(result["google_error_status"], "INVALID_ARGUMENT")
        self.assertEqual(len(result["details"]), 2)
        self.assert_private_data_removed(result)
