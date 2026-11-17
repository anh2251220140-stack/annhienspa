"""Message projection only; fake exceptions, no clients or external connections."""
import json
from unittest import TestCase
from unittest.mock import patch
import httpx
from google.genai.errors import ClientError
from tools.gemini_live import safe_google_message, safe_google_error, safe_sdk_error


class GeminiSafeMessageTests(TestCase):
    def setUp(self):
        guard = patch("socket.socket.connect", side_effect=AssertionError("Offline only"))
        guard.start()
        self.addCleanup(guard.stop)

    def project(self, message, *, wrapped=True):
        payload = {"code": 400, "status": "INVALID_ARGUMENT", "message": message}
        if wrapped:
            payload = {"error": payload}
        http_result = safe_google_error(httpx.Response(400, json=payload))
        sdk_result = safe_sdk_error(ClientError(400, payload))
        self.assertEqual(http_result, sdk_result)
        return http_result["google_error_message_safe"]

    def test_unknown_json_field_retains_public_field_and_technical_type_only(self):
        message = ('Invalid JSON payload received. Unknown name "top_p" at \'generation_config\': '
                   'Cannot find field. FAKE-KEY prompt=PRIVATE-PROMPT email=person@example.test')
        result = self.project(message)
        self.assertIn("INVALID_JSON_PAYLOAD", result)
        self.assertIn("UNKNOWN_JSON_FIELD", result)
        self.assertIn("generationConfig.topP", result)
        for secret in ("FAKE-KEY", "PRIVATE-PROMPT", "person@example.test", "email=", "prompt="):
            self.assertNotIn(secret, result)

    def test_nested_json_paths_and_indices_are_normalized_without_values(self):
        result = self.project("Invalid argument: GenerateContentRequest.contents[0].parts[1].text is invalid: PRIVATE")
        self.assertIn("contents[].parts[].text", result)
        self.assertNotIn("PRIVATE", result)
        self.assertNotIn("[0]", result)

    def test_flat_message_retains_unsupported_parameter(self):
        result = self.project("response_mime_type is not supported for this operation. PRIVATE", wrapped=False)
        self.assertIn("UNSUPPORTED_PARAMETER", result)
        self.assertIn("generationConfig.responseMimeType", result)
        self.assertNotIn("PRIVATE", result)

    def test_range_missing_field_and_api_key_errors_use_fixed_labels(self):
        for message, label in (
            ("Unable to submit request because maxOutputTokens has a supported range of 1 to 2. PRIVATE", "VALUE_OUT_OF_RANGE"),
            ("contents is not specified. PRIVATE", "MISSING_REQUIRED_FIELD"),
            ("API key not valid. Please pass a valid API key. FAKE-KEY", "INVALID_API_KEY"),
            ("The model does not support this feature. PRIVATE", "UNSUPPORTED_REQUEST_FEATURE")):
            with self.subTest(label=label):
                result = self.project(message)
                self.assertIn(label, result)
                self.assertNotIn("PRIVATE", result)
                self.assertNotIn("FAKE-KEY", result)

    def test_unknown_and_non_string_messages_only_return_error_type(self):
        for message in (None, "", [], {}, "PRIVATE-PROMPT x-goog-api-key: FAKE-KEY", "Thông tin cá nhân riêng tư"):
            with self.subTest(message_type=type(message).__name__):
                result = self.project(message)
                self.assertEqual(result, "INVALID_ARGUMENT: source message withheld (unrecognised or unavailable).")

    def test_missing_message_still_has_typed_safe_field(self):
        result = safe_google_error(httpx.Response(400, json={"error": {"code": 400, "status": "INVALID_ARGUMENT"}}))
        self.assertEqual(result["google_error_message_safe"],
                         "INVALID_ARGUMENT: source message withheld (unrecognised or unavailable).")

    def test_sdk_message_is_used_as_fallback_when_payload_message_absent(self):
        error = ClientError(400, {"error": {"status": "INVALID_ARGUMENT"}})
        error.message = "contents is not specified. PRIVATE"
        result = safe_sdk_error(error)
        self.assertIn("MISSING_REQUIRED_FIELD", result["google_error_message_safe"])
        self.assertNotIn("PRIVATE", json.dumps(result))

    def test_key_headers_urls_and_unknown_schema_properties_are_not_copied(self):
        message = ('Invalid JSON payload received: generationConfig.responseSchema.properties["PRIVATE-NAME"] '
                   'Authorization: Bearer FAKE-KEY; https://private.example.test/?key=FAKE-KEY; 0901234567')
        result = self.project(message)
        for private in ("PRIVATE-NAME", "Authorization", "Bearer", "FAKE-KEY", "private.example.test", "0901234567"):
            self.assertNotIn(private, result)

    def test_malformed_oversized_payloads_have_safe_field_and_no_source(self):
        for response in (httpx.Response(400, text="PRIVATE not json"),
                         httpx.Response(400, json={"error": {"message": "PRIVATE" * 4000}})):
            result = safe_google_error(response)
            self.assertIn("google_error_message_safe", result)
            self.assertNotIn("PRIVATE", json.dumps(result))
        self.assertNotIn("PRIVATE", safe_google_message("Invalid argument: " + "PRIVATE" * 2000, "INVALID_ARGUMENT"))

    def test_untrusted_error_type_never_passes_through(self):
        for kind in ("PRIVATE", {}, None):
            self.assertTrue(safe_google_message("unrecognised", kind).startswith("HTTP_ERROR:"))
        self.assertEqual(safe_google_message("\ud800", "INVALID_ARGUMENT"),
                         "INVALID_ARGUMENT: source message withheld (unrecognised or unavailable).")
