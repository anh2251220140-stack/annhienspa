"""Official SDK + mocked SSE transport only. Never runs the live CLI."""
import json
import socket
from unittest import TestCase
from unittest.mock import patch
import httpx
from tools import gemini_studio_probe as probe


class StudioProbeTests(TestCase):
    def run_probe(self, *, status=200, chunks=("O", "K"), error=None, body=None):
        self.requests = []
        def transport(_transport, request):
            self.requests.append(request)
            if error:
                raise error
            if status != 200:
                return httpx.Response(status, request=request, json=body or {"error": {
                    "code": status, "status": "INVALID_ARGUMENT", "message":
                    "audio_transcription_config is not supported. FAKE-KEY PRIVATE-PROMPT"}})
            payload = b"".join(("data: " + json.dumps({"candidates": [{"content": {"role": "model",
                "parts": [{"text": text}]}}]}) + "\n\n").encode() for text in chunks)
            return httpx.Response(200, request=request, headers={"content-type": "text/event-stream"}, content=payload)
        with patch.object(httpx.HTTPTransport, "handle_request", transport):
            return probe.probe_once("FAKE-KEY")

    def test_200_sse_reassembles_exact_ok_and_matches_studio_json(self):
        result = self.run_probe()
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["received_exact_ok"])
        self.assertEqual(result["http_status"], 200)
        self.assertEqual(result["http_requests"], 1)
        request, = self.requests
        self.assertEqual(str(request.url), probe.URL)
        self.assertEqual(request.method, "POST")
        self.assertEqual(int(request.headers["X-Server-Timeout"]), 12)
        self.assertEqual(json.loads(request.content), probe.EXPECTED_BODY)
        self.assertEqual(request.headers.get("x-goog-api-key"), "FAKE-KEY")
        self.assertNotIn("FAKE-KEY", json.dumps(result))
        for field in ("systemInstruction", "tools"):
            self.assertNotIn(field, json.loads(request.content))
        config = json.loads(request.content)["generationConfig"]
        self.assertNotIn("responseMimeType", config)
        self.assertNotIn("maxOutputTokens", config)

    def test_400_has_safe_parameter_and_operation_and_no_retry(self):
        result = self.run_probe(status=400)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(len(self.requests), 1)
        diagnostic, = result["diagnostics"]
        self.assertEqual(diagnostic["operation"], "stream_generate_content")
        self.assertEqual(diagnostic["google_error_status"], "INVALID_ARGUMENT")
        self.assertIn("audioTranscriptionConfig", diagnostic["google_error_message_safe"])
        self.assertNotIn("FAKE-KEY", json.dumps(result))
        self.assertNotIn("PRIVATE-PROMPT", json.dumps(result))

    def test_429_and_auth_errors_do_not_retry(self):
        for status in (429, 401, 403):
            with self.subTest(status=status):
                result = self.run_probe(status=status)
                self.assertEqual(result["http_requests"], 1)
                self.assertEqual(len(self.requests), 1)
                self.assertEqual(result["status"], "FAIL")

    def test_timeout_does_not_retry_or_echo_exception(self):
        result = self.run_probe(error=httpx.ReadTimeout("FAKE-KEY PRIVATE-PROMPT"))
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(len(self.requests), 1)
        self.assertNotIn("PRIVATE-PROMPT", json.dumps(result))

    def test_unexpected_or_empty_output_is_not_reported_as_ok_or_printed(self):
        for chunks in ((), ("PRIVATE-PROMPT FAKE-KEY",), ("not OK",)):
            result = self.run_probe(chunks=chunks)
            self.assertEqual(result["status"], "FAIL")
            self.assertFalse(result["received_exact_ok"])
            self.assertNotIn("PRIVATE-PROMPT", json.dumps(result))

    def test_output_and_chunk_bounds_close_stream(self):
        for chunks in (("x" * 4097,), ("",) * 65):
            result = self.run_probe(chunks=chunks)
            self.assertEqual(result["status"], "FAIL")
            self.assertEqual(result["http_requests"], 1)

    def test_late_stream_completion_cannot_pass_total_deadline(self):
        now = [0.]
        class Stream(httpx.SyncByteStream):
            def __iter__(self):
                yield ('data: ' + json.dumps({"candidates": [{"content": {"role": "model",
                    "parts": [{"text": "OK"}]}}]}) + '\n\n').encode()
                now[0] = 16.
        def transport(_transport, request):
            return httpx.Response(200, request=request, headers={"content-type": "text/event-stream"}, stream=Stream())
        with patch.object(probe, "monotonic", side_effect=lambda: now[0]), \
                patch.object(httpx.HTTPTransport, "handle_request", transport):
            result = probe.probe_once("FAKE-KEY")
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["http_requests"], 1)
        self.assertFalse(result["received_exact_ok"])

    def test_budget_denies_second_send_wrong_origin_and_embedding(self):
        budget = probe.StudioBudget()
        budget.reserve("synthetic", operation="stream_generate_content")
        request = httpx.Request("POST", probe.URL, json=probe.EXPECTED_BODY)
        budget.check_request(request)
        with self.assertRaises(probe.SafetyStop):
            budget.check_request(request)
        self.assertEqual(budget.wire_requests, 1)
        for url in ("https://api.openai.com/v1/", "https://api-merchant.payos.vn/", probe.URL.replace("alt=sse", "alt=json")):
            budget = probe.StudioBudget()
            budget.reserve("synthetic")
            with self.assertRaises(probe.SafetyStop):
                budget.check_request(httpx.Request("POST", url, json=probe.EXPECTED_BODY))
            self.assertEqual(budget.wire_requests, 0)

    def test_client_options_and_pre_http_failure(self):
        from google import genai
        with patch.object(genai, "Client", side_effect=ValueError("FAKE-KEY")) as client:
            result = probe.probe_once("FAKE-KEY")
        self.assertEqual(result["http_requests"], 0)
        self.assertEqual(result["status"], "FAIL")
        options = client.call_args.kwargs
        self.assertFalse(options["enterprise"])
        self.assertFalse(options["vertexai"])
        self.assertIsNone(options["http_options"].api_version)
        self.assertNotIn("api_version", options["http_options"].model_fields_set)
        self.assertEqual(options["http_options"].retry_options.attempts, 1)
        self.assertFalse(options["http_options"].client_args["trust_env"])
        self.assertEqual(options["http_options"].timeout, 12000)

    def test_empty_key_cannot_fall_back_to_environment_credentials(self):
        with patch("google.genai.Client") as client:
            for key in (None, "", " "):
                result = probe.probe_once(key)
                self.assertEqual(result["http_requests"], 0)
                self.assertEqual(result["failure_stage"], "before_http")
            client.assert_not_called()

    def test_no_database_or_other_socket_can_connect(self):
        import MySQLdb
        from django.db.backends.base.base import BaseDatabaseWrapper
        with probe.isolation(probe.StudioBudget()):
            for port in (3306, 3310, 3311):
                with socket.socket() as sock, self.assertRaises(probe.SafetyStop):
                    sock.connect(("127.0.0.1", port))
            with self.assertRaises(probe.SafetyStop):
                MySQLdb.connect(host="127.0.0.1", port=3311)
            with self.assertRaises(probe.SafetyStop):
                BaseDatabaseWrapper.ensure_connection(None)

    def test_key_input_and_free_tier_confirmation_are_required_without_executing_cli(self):
        # Inspect dispatch; never call main(run-once) or ask for an actual key.
        import ast
        tree = ast.parse((probe.ROOT / "tools/gemini_studio_probe.py").read_text(encoding="utf-8"))
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
        self.assertTrue(any(n.func.id == "hidden_input" for n in calls))
        source = ast.unparse(next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main"))
        self.assertLess(source.index("!= CONFIRMATION"), source.index("key = hidden_input"))
        self.assertIn("args.mode == 'plan'", source)
