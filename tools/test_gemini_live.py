"""Offline only: fake keys and HTTP transport; no actual live invocation."""
from contextlib import redirect_stdout
import ast
from io import StringIO
import json
from pathlib import Path
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import httpx

from tools import gemini_live as live


class GeminiLiveTests(TestCase):
    @classmethod
    def setUpClass(cls):
        live.configure()

    def test_free_tier_confirmation_precedes_hidden_key(self):
        with patch.object(live.sys.stdin, "isatty", return_value=True), patch("builtins.input", return_value="no"), \
                patch("tools.openai_test.hidden_input") as key, redirect_stdout(StringIO()):
            with self.assertRaises(live.SafetyStop):
                live.live("fr21")
            key.assert_not_called()

    def test_nonterminal_cannot_read_key(self):
        with patch.object(live.sys.stdin, "isatty", return_value=False), patch("tools.openai_test.hidden_input") as key:
            with self.assertRaises(live.SafetyStop):
                live.live("fr22")
            key.assert_not_called()

    def test_getpass_is_hidden_and_warning_fails_closed(self):
        from getpass import GetPassWarning
        from tools.openai_test import hidden_input
        with patch("tools.openai_test.sys.stdin.isatty", return_value=True), \
                patch("tools.openai_test.getpass", return_value="FAKE-KEY") as getpass:
            self.assertEqual(hidden_input("hidden: "), "FAKE-KEY")
            getpass.assert_called_once_with("hidden: ")
        with patch("tools.openai_test.sys.stdin.isatty", return_value=True), \
                patch("tools.openai_test.getpass", side_effect=GetPassWarning("echo disabled unavailable")):
            with self.assertRaises(GetPassWarning):
                hidden_input("hidden: ")

    def test_budget_request_limit_and_no_retry(self):
        budget = live.Budget(1)
        budget.reserve("synthetic")
        with self.assertRaises(live.SafetyStop):
            budget.reserve("synthetic")
        self.assertTrue(budget.failed)

    def test_input_limits(self):
        for embedding, length in ((True, 1800), (False, 6000)):
            with self.subTest(embedding=embedding), self.assertRaises(live.SafetyStop):
                live.Budget(3).reserve("x" * length, embedding=embedding)
        budget = live.Budget(3, input_bytes=11990)
        with self.assertRaises(live.SafetyStop):
            budget.reserve("x")

    def test_wire_guard_blocks_origins_redirect_targets_and_unbounded_output(self):
        for url in ("http://generativelanguage.googleapis.com/v1beta/models/x", "https://api.openai.com/v1/",
                    "https://generativelanguage.googleapis.com.evil.test/", "https://api-merchant.payos.vn/",
                    "https://generativelanguage.googleapis.com:3311/", "https://generativelanguage.googleapis.com/other"):
            with self.subTest(url=url), self.assertRaises(live.SafetyStop):
                budget = live.Budget(1)
                budget.reserve("x")
                budget.check_request(httpx.Request("POST", url, json={}))
        for tokens in (None, 0, 1501):
            budget = live.Budget(1)
            budget.reserve("x")
            with self.assertRaises(live.SafetyStop):
                budget.check_request(httpx.Request("POST", self.chat_url(), json={"generationConfig": {"maxOutputTokens": tokens}}))

    @staticmethod
    def chat_url():
        return "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent"

    def test_wire_guard_denies_duplicate_send_for_same_operation(self):
        budget = live.Budget(3)
        budget.reserve("x")
        request = httpx.Request("POST", self.chat_url(), json={"generationConfig": {"maxOutputTokens": 1500}})
        budget.check_request(request)
        with self.assertRaises(live.SafetyStop):
            budget.check_request(request)
        self.assertEqual(budget.wire_requests, 1)

    def test_database_and_other_sockets_are_blocked_before_connect(self):
        import MySQLdb
        from django.db import connection
        with live.isolation(live.Budget(1)):
            for port in (3306, 3310, 3311, 443):
                with socket.socket() as sock, self.assertRaises(live.SafetyStop):
                    sock.connect(("127.0.0.1", port))
            for connector in (MySQLdb.connect, MySQLdb.Connect, MySQLdb.Connection, MySQLdb._mysql.connect):
                with self.assertRaises(live.SafetyStop):
                    connector(host="127.0.0.1", port=3311)
            with self.assertRaises(live.SafetyStop):
                connection.ensure_connection()

    def execute_probe(self, feature, *, status=200, error=None, malformed=False, fail_at=None, error_body=None,
                      generation_only=False, advance=None):
        from django.test import override_settings
        requests = []
        self.last_requests = requests
        def transport(_transport, request):
            requests.append(request)
            if error:
                raise error
            if status != 200 and (fail_at is None or len(requests) == fail_at):
                return httpx.Response(status, json=error_body or {"error": {"message": "FAKE-SECRET-MUST-NOT-LEAK"}}, request=request)
            if "embed" in request.url.path.lower():
                body = {"embeddings": [{"values": [1.] + [0.] * 767}]}
            else:
                value = {"fr21": {"answer": "Dịch vụ giả lập: 200000 VND, 60 phút.", "sources": ["service:900001"]},
                         "fr22": {"items": [{"id": 900001, "reason": "Phù hợp ngân sách."}]},
                         "fr23": {"sentiment": "positive", "summary": "Đánh giá giả lập tích cực.",
                                  "themes": ["Không gian"], "priority": "low", "actions": ["Duy trì chất lượng."]}}[feature]
                text = "not-json FAKE-SECRET-MUST-NOT-LEAK" if malformed else json.dumps(value)
                body = {"candidates": [{"content": {"parts": [{"text": text}], "role": "model"}, "finishReason": "STOP"}]}
            if advance is not None:
                advance()
            return httpx.Response(200, json=body, request=request)
        budget = live.Budget(1 if generation_only else live.FEATURES[feature], generation_only=generation_only)
        self.last_budget = budget
        mock_transport = httpx.MockTransport(lambda request: transport(None, request))
        def mock_only_send(client, request, **kwargs):
            # Compose with the SQLite runner's network deny: never restore a real
            # sender. The live guard still checks each serialized request above us.
            for hook in client.event_hooks.get("request", []):
                hook(request)
            return mock_transport.handle_request(request)
        with TemporaryDirectory(prefix="gemini-offline-test-") as temp, \
                patch.object(httpx.Client, "send", mock_only_send), live.isolation(budget), override_settings(
                    AI_GEMINI_API_KEY="FAKE-SECRET-MUST-NOT-LEAK", AI_GEMINI_REQUESTS_APPROVED=True,
                    AI_GEMINI_FREE_TIER_CONFIRMED=True, AI_GEMINI_FREE_TIER_ONLY=True):
            if generation_only:
                result = live.fr21_generation(live.bounded_provider(budget))
            else:
                result = live.probe(feature, live.bounded_provider(budget), Path(temp))
        return result, budget, requests

    def test_generate_only_200_matches_full_fr21_generate_request_exactly(self):
        _, _, full_requests = self.execute_probe("fr21")
        from ai_features.gemini import GeminiProvider
        with patch.object(GeminiProvider, "embed", side_effect=AssertionError("Embedding forbidden")), \
                patch.object(GeminiProvider, "embed_query", side_effect=AssertionError("Query embedding forbidden")), \
                patch("sqlite3.connect", side_effect=AssertionError("Database forbidden")):
            result, budget, requests = self.execute_probe("fr21", generation_only=True)
        self.assertIn("Nguồn:", result["answer"])
        self.assertEqual(budget.wire_requests, 1)
        self.assertEqual(budget.maximum, 1)
        self.assertEqual(len(requests), 1)
        self.assertEqual(str(requests[0].url), self.chat_url())
        self.assertEqual(json.loads(requests[0].content), json.loads(full_requests[2].content))

    def test_generate_only_http400_stops_after_one_and_preserves_safe_diagnostics(self):
        from ai_features.integration import ProviderUnavailable
        with self.assertRaises(ProviderUnavailable):
            self.execute_probe("fr21", generation_only=True, status=400, error_body={"error": {
                "code": 400, "status": "INVALID_ARGUMENT",
                "message": "maxOutputTokens is not supported. FAKE-SECRET-MUST-NOT-LEAK private@example.test"}})
        self.assertEqual(len(self.last_requests), 1)
        self.assertEqual(self.last_budget.maximum, 1)
        diagnostic, = self.last_budget.diagnostics
        self.assertEqual(diagnostic["operation"], "generate_content")
        self.assertEqual(diagnostic["model"], "gemini-3.5-flash-lite")
        self.assertEqual(diagnostic["http_status"], 400)
        self.assertEqual(diagnostic["google_error_code"], 400)
        self.assertEqual(diagnostic["google_error_status"], "INVALID_ARGUMENT")
        self.assertIn("maxOutputTokens", diagnostic["message"])
        self.assertIn("UNSUPPORTED_PARAMETER", diagnostic["google_error_message_safe"])
        self.assertIn("generationConfig.maxOutputTokens", diagnostic["google_error_message_safe"])
        self.assertNotIn("FAKE-SECRET-MUST-NOT-LEAK", json.dumps(diagnostic))
        self.assertNotIn("private@example.test", json.dumps(diagnostic))

    def test_generate_only_pre_http_error_sends_nothing(self):
        from ai_features.gemini import GeminiProvider
        with live.isolation(live.Budget(1)), patch.object(GeminiProvider, "_client") as sdk, \
                patch.object(httpx.HTTPTransport, "handle_request") as transport:
            with self.assertRaises(live.SafetyStop):
                live.fr21_generation(live.bounded_provider(live.Budget(0)))
        sdk.assert_not_called()
        transport.assert_not_called()

    def test_generate_only_has_no_database_apps_or_vector_index_in_fresh_process(self):
        code = r'''
import os, sys
system_root = os.environ.get('SystemRoot', r'C:\Windows')
os.environ.clear()
os.environ['SystemRoot'] = system_root
from tools.gemini_live import Budget, isolation, configure
with isolation(Budget(1)):
    configure(generation_only=True)
    from django.conf import settings
    assert settings.INSTALLED_APPS == []
    assert settings.DATABASES['default']['ENGINE'] == 'django.db.backends.dummy'
    assert 'config.settings' not in sys.modules
    assert 'ai_features.rag' not in sys.modules
print('isolated configuration PASS')
'''
        result = subprocess.run([sys.executable, "-B", "-c", code], cwd=live.ROOT,
                                capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))

    def test_generate_only_rejects_all_and_other_features_before_any_prompt(self):
        with patch("builtins.input") as confirmation, patch("tools.openai_test.hidden_input") as key:
            for feature in ("all", "fr22", "fr23"):
                with self.assertRaises(live.SafetyStop):
                    live.generate_only(feature)
        confirmation.assert_not_called()
        key.assert_not_called()

    def test_generate_only_cli_rejects_other_features_before_dispatch(self):
        tree = ast.parse((live.ROOT / "tools" / "gemini_test.py").read_text(encoding="utf-8"))
        branch = next(node for node in ast.walk(tree) if isinstance(node, ast.If)
                      and ast.unparse(node.test) == "args.mode == 'generate-only'")
        self.assertEqual(ast.unparse(branch.body[0].test), "args.feature != 'fr21'")
        self.assertIsInstance(branch.body[0].body[0], ast.Raise)
        self.assertTrue(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                            and node.func.id == "generate_only" for node in ast.walk(branch)))

    def test_generate_only_budget_rejects_embedding_before_http(self):
        budget = live.Budget(1, generation_only=True)
        with self.assertRaises(live.SafetyStop):
            budget.reserve(["synthetic"], embedding=True)
        self.assertEqual(budget.wire_requests, 0)
        budget = live.Budget(1, generation_only=True)
        budget.reserve("synthetic")
        with self.assertRaises(live.SafetyStop):
            budget.check_request(httpx.Request("POST",
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent",
                json={"content": "synthetic"}))
        self.assertEqual(budget.wire_requests, 0)

    def test_generate_only_report_hides_generated_text_and_uses_one_request(self):
        def response(_transport, request):
            return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": json.dumps({
                "answer": "Dịch vụ giả lập: 200000 VND, 60 phút.", "sources": ["service:900001"]})}],
                "role": "model"}, "finishReason": "STOP"}]}, request=request)
        with patch.object(live.sys.stdin, "isatty", return_value=True), \
                patch("builtins.input", return_value=live.CONFIRMATION), patch.object(live, "configure") as configure, \
                patch("tools.openai_test.hidden_input", return_value="FAKE-SECRET-MUST-NOT-LEAK"), \
                patch.object(httpx.HTTPTransport, "handle_request", response), \
                patch.object(live, "TemporaryDirectory", side_effect=AssertionError("No vector workspace")), \
                redirect_stdout(StringIO()):
            result = live.generate_only("fr21")
        configure.assert_called_once_with(generation_only=True)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["maximum_requests"], 1)
        self.assertEqual(result["http_requests"], 1)
        self.assertEqual(result["result"], {"grounded_response_validated": True})
        self.assertNotIn("FAKE-SECRET-MUST-NOT-LEAK", json.dumps(result))
        self.assertNotIn("answer", result["result"])

    def test_fr21_actual_adapter_and_temporary_vector_index(self):
        result, budget, requests = self.execute_probe("fr21")
        self.assertEqual(budget.wire_requests, 3)
        self.assertEqual(len(requests), 3)
        self.assertIn("Nguồn:", result["answer"])

    def test_fr22_actual_adapter(self):
        result, budget, requests = self.execute_probe("fr22")
        self.assertEqual(result["items"][0]["id"], 900001)
        self.assertEqual(result["items"][0]["reason"], "Phù hợp ngân sách.")
        self.assertEqual(budget.wire_requests, 1)
        self.assertEqual(len(requests), 1)
        request = requests[0]
        self.assertEqual(request.method, "POST")
        self.assertEqual(str(request.url), self.chat_url())
        body = json.loads(request.content)
        payload = json.loads(body["contents"][0]["parts"][0]["text"])
        self.assertEqual(payload["budget"], 300000)
        self.assertEqual(payload["minutesMaximum"], 90)
        self.assertEqual(payload["needs"], "face")
        self.assertEqual([row["id"] for row in payload["candidates"]], [900001])
        self.assertEqual(body["generationConfig"]["maxOutputTokens"], 1500)

    def test_fr23_actual_adapter(self):
        result, budget, _ = self.execute_probe("fr23")
        self.assertEqual(result["sentiment"], "positive")
        self.assertEqual(budget.wire_requests, 1)

    def test_quota_auth_timeout_and_bad_json_are_not_retried(self):
        from ai_features.integration import ProviderUnavailable
        for options in ({"status": 429}, {"status": 401}, {"status": 403},
                        {"error": httpx.ReadTimeout("FAKE-SECRET-MUST-NOT-LEAK")}, {"malformed": True}):
            with self.subTest(options=list(options)), self.assertRaises((ProviderUnavailable, TimeoutError, live.SafetyStop)) as caught:
                self.execute_probe("fr22", **options)
            self.assertNotIn("FAKE-SECRET-MUST-NOT-LEAK", str(caught.exception))
            self.assertEqual(len(self.last_requests), 1)

    def test_sdk_apierror_nested_payload_is_sanitized_at_transport_failure(self):
        from google.genai.errors import ClientError
        from ai_features.integration import ProviderUnavailable
        sdk_error = ClientError(400, {"error": {"code": 400, "status": "INVALID_ARGUMENT",
            "message": "FAKE-SECRET-MUST-NOT-LEAK", "details": [{
                "@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": "API_KEY_INVALID",
                "domain": "googleapis.com", "metadata": {"service": "generativelanguage.googleapis.com",
                "consumer": "PRIVATE-PROJECT"}}]}})
        with self.assertRaises(ProviderUnavailable):
            self.execute_probe("fr22", error=sdk_error)
        self.assertEqual(len(self.last_requests), 1)
        diagnostic, = self.last_budget.diagnostics
        self.assertEqual(diagnostic["operation"], "generate_content")
        self.assertEqual(diagnostic["http_status"], 400)
        self.assertEqual(diagnostic["details"][0]["reason"], "API_KEY_INVALID")
        self.assertNotIn("FAKE-SECRET-MUST-NOT-LEAK", json.dumps(diagnostic))
        self.assertNotIn("PRIVATE-PROJECT", json.dumps(diagnostic))

    def test_http_400_identifies_each_fr21_operation_without_retry(self):
        from ai_features.integration import ProviderUnavailable
        body = {"error": {"code": 400, "status": "INVALID_ARGUMENT",
            "message": "Invalid maxOutputTokens. FAKE-SECRET-MUST-NOT-LEAK private-person@example.test",
            "details": [{"request": "PRIVATE-PROMPT", "headers": {"x-goog-api-key": "FAKE-SECRET-MUST-NOT-LEAK"}}]}}
        for number, operation in enumerate(("document_embedding", "query_embedding", "generate_content"), 1):
            with self.subTest(operation=operation), self.assertRaises(ProviderUnavailable):
                self.execute_probe("fr21", status=400, fail_at=number, error_body=body)
            self.assertEqual(len(self.last_requests), number)
            self.assertTrue(self.last_budget.failed)
            diagnostic, = self.last_budget.diagnostics
            self.assertEqual(diagnostic["operation"], operation)
            self.assertEqual(diagnostic["http_status"], 400)
            self.assertEqual(diagnostic["google_error_code"], 400)
            self.assertEqual(diagnostic["google_error_status"], "INVALID_ARGUMENT")
            self.assertEqual(diagnostic["model"], "gemini-3.5-flash-lite" if number == 3 else "gemini-embedding-001")
            if number == 3:
                self.assertEqual(diagnostic["api_method"], "generateContent")
            self.assertIn("maxOutputTokens", diagnostic["message"])
            for sensitive in ("FAKE-SECRET-MUST-NOT-LEAK", "private-person", "PRIVATE-PROMPT", "x-goog-api-key"):
                self.assertNotIn(sensitive, json.dumps(diagnostic))

    def test_google_error_redaction_rejects_arbitrary_messages_and_codes(self):
        for body in ({"error": {"code": "SECRET", "status": "SECRET", "message": "PRIVATE-FREE-TEXT"}},
                     {"error": "PRIVATE-FREE-TEXT"}, ["PRIVATE-FREE-TEXT"]):
            diagnostic = live.safe_google_error(httpx.Response(400, json=body))
            self.assertEqual(diagnostic["http_status"], 400)
            self.assertIsNone(diagnostic["google_error_code"])
            self.assertIsNone(diagnostic["google_error_status"])
            self.assertNotIn("PRIVATE-FREE-TEXT", json.dumps(diagnostic))
            self.assertNotIn("SECRET", json.dumps(diagnostic))
        for response in (httpx.Response(400, text="<html>PRIVATE-FREE-TEXT</html>"),
                         httpx.Response(400, text="PRIVATE-FREE-TEXT" * 2000)):
            self.assertNotIn("PRIVATE-FREE-TEXT", json.dumps(live.safe_google_error(response)))

    def test_fallback_report_preserves_http_400_diagnostic_after_adapter_sanitizes_error(self):
        def rejected(_transport, request):
            return httpx.Response(400, json={"error": {"code": 400, "status": "INVALID_ARGUMENT",
                "message": "PRIVATE-PROVIDER-MESSAGE"}}, request=request)
        with patch.object(live.sys.stdin, "isatty", return_value=True), \
                patch("builtins.input", return_value=live.CONFIRMATION), patch.object(live, "configure"), \
                patch("tools.openai_test.hidden_input", return_value="FAKE-SECRET-MUST-NOT-LEAK"), \
                patch.object(httpx.HTTPTransport, "handle_request", rejected), redirect_stdout(StringIO()):
            result = live.live("fr22")
        self.assertEqual(result["status"], "FALLBACK")
        self.assertEqual(result["http_requests"], 1)
        self.assertEqual(result["diagnostics"][0]["http_status"], 400)
        self.assertEqual(result["diagnostics"][0]["operation"], "generate_content")
        for private in ("FAKE-SECRET-MUST-NOT-LEAK", "PRIVATE-PROVIDER-MESSAGE"):
            self.assertNotIn(private, json.dumps(result))

    def test_invalid_structured_fields_are_rejected_for_each_feature(self):
        from unittest.mock import Mock
        provider = Mock()
        provider.structured.return_value = {"items": [{"id": 123, "reason": "Unknown service"}]}
        with self.assertRaises(live.SafetyStop):
            live.probe("fr22", provider, Path("unused"))
        provider.structured.return_value = {"sentiment": "unknown", "priority": "high"}
        with self.assertRaises(live.SafetyStop):
            live.probe("fr23", provider, Path("unused"))

    def test_each_feature_has_honest_local_fallback(self):
        self.assertEqual(live.synthetic_fallback("fr21")["mode"], "fallback")
        self.assertEqual(live.synthetic_fallback("fr22")["mode"], "rule")
        self.assertEqual(live.synthetic_fallback("fr23")["mode"], "rule")

    def test_invalid_feature_denied(self):
        with patch.object(live.sys.stdin, "isatty", return_value=True), \
                patch("builtins.input") as confirmation, patch("tools.openai_test.hidden_input") as key, \
                patch.object(live, "isolation") as isolation:
            with self.assertRaises(live.SafetyStop):
                live.live("all")
            confirmation.assert_not_called()
            key.assert_not_called()
            isolation.assert_not_called()

    def test_cli_all_is_rejected_before_live_dispatch_without_executing_cli(self):
        tree = ast.parse((live.ROOT / "tools" / "gemini_test.py").read_text(encoding="utf-8"))
        main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
        branch = next(node for node in main.body if isinstance(node, ast.If)
                      and ast.unparse(node.test) == "args.mode == 'live'")
        guard = branch.body[0]
        self.assertIsInstance(guard, ast.If)
        self.assertEqual(ast.unparse(guard.test), "args.feature == 'all'")
        self.assertIsInstance(guard.body[0], ast.Raise)
        self.assertNotIn("all", live.FEATURES)

    def test_scoped_key_and_fallback_do_not_leak(self):
        from django.conf import settings
        from ai_features.integration import ProviderUnavailable
        output = StringIO()
        with patch.object(live.sys.stdin, "isatty", return_value=True), \
                patch("builtins.input", return_value=live.CONFIRMATION), patch.object(live, "configure"), \
                patch("tools.openai_test.hidden_input", return_value="FAKE-SECRET-MUST-NOT-LEAK"), \
                patch.object(live, "probe", side_effect=ProviderUnavailable("FAKE-SECRET-MUST-NOT-LEAK")), redirect_stdout(output):
            result = live.live("fr22")
        self.assertEqual(result["status"], "FALLBACK")
        self.assertEqual(result["http_requests"], 0)
        self.assertEqual(result["diagnostics"], [])
        self.assertNotIn("FAKE-SECRET-MUST-NOT-LEAK", output.getvalue() + json.dumps(result))
        self.assertFalse(hasattr(settings, "AI_GEMINI_API_KEY"))
        self.assertFalse(settings.AI_PERSONALIZATION_EXPORT_APPROVED)
        self.assertFalse(settings.AI_REVIEW_EXPORT_APPROVED)
