"""Independent AI Studio-shaped stream probe. Default plan never requests a key."""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sys
from time import monotonic

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.gemini_live import Budget, CONFIRMATION, SafetyStop, isolation, safe_sdk_error

MODEL = "gemini-3.5-flash-lite"
URL = "https://generativelanguage.googleapis.com/v1beta/models/" + MODEL + ":streamGenerateContent?alt=sse"
EXPECTED_BODY = {
    "contents": [{"parts": [{"text": "Reply exactly OK"}], "role": "user"}],
    # Actual google-genai 2.34.0 wire output; do not rewrite its nested key.
    "generationConfig": {"thinkingConfig": {"thinking_level": "MINIMAL"}, "audioTranscriptionConfig": {}},
}


class StudioBudget(Budget):
    def __init__(self):
        super().__init__(maximum=1)

    def check_request(self, request):
        # Independent allowlist: streaming SSE only, exact fixed synthetic body.
        if (self.failed or self.requests != 1 or self.sent_current or self.wire_requests != 0
                or request.method != "POST" or str(request.url) != URL
                or len(request.content) > 4096 or json.loads(request.content) != EXPECTED_BODY):
            self.failed = True
            raise SafetyStop("Unexpected Studio probe request")
        self.sent_current = True
        self.wire_requests += 1


def probe_once(key):
    """Called only after explicit terminal confirmation; tests use a fake key."""
    from google import genai
    from google.genai import types
    from ai_features.config import check_gemini_deadline, gemini_timeout_ms
    end = monotonic() + 15
    budget = StudioBudget()
    http_status = None
    exact_ok = False
    failure_stage = None
    with isolation(budget):
        try:
            if not isinstance(key, str) or not key.strip():
                raise SafetyStop("An explicit nonempty terminal key is required")
            config = types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_level="MINIMAL"),
                audio_transcription_config=types.AudioTranscriptionConfig(),
            )
            # Leave api_version unset: use the installed SDK's Developer API default.
            timeout_ms = gemini_timeout_ms(end - monotonic())
            options = types.HttpOptions(base_url="https://generativelanguage.googleapis.com", timeout=timeout_ms,
                retry_options=types.HttpRetryOptions(attempts=1),
                client_args={"trust_env": False, "follow_redirects": False,
                             "event_hooks": {"request": [lambda request: check_gemini_deadline(request, end - monotonic())]}})
            with genai.Client(api_key=key, vertexai=False, enterprise=False, http_options=options) as client:
                if (end - monotonic()) * 1000 < timeout_ms:
                    raise SafetyStop("Client setup exhausted request allocation")
                budget.reserve("fixed synthetic streaming probe", operation="stream_generate_content")
                contents = [types.Content(role="user", parts=[types.Part.from_text(text="Reply exactly OK")])]
                text = ""
                deadline = end
                with closing(client.models.generate_content_stream(model=MODEL, contents=contents, config=config)) as stream:
                    for number, chunk in enumerate(stream, 1):
                        if number > 64 or monotonic() > deadline:
                            raise SafetyStop("Stream processing bound exceeded")
                        part = chunk.text or ""
                        if not isinstance(part, str) or len(text) + len(part) > 4096:
                            raise SafetyStop("Stream output bound exceeded")
                        text += part
                if budget.wire_requests != 1:
                    raise SafetyStop("No verified HTTP request")
                http_status = 200
                if monotonic() > end:
                    raise SafetyStop("Total probe deadline exceeded")
                exact_ok = text.strip() == "OK"
                text = ""  # Never expose generated text, including unexpected output.
        except Exception as error:
            budget.failed = True
            failure_stage = "before_http" if not budget.wire_requests else "http_or_stream"
            if not budget.diagnostics:
                diagnostic = safe_sdk_error(error)
                if diagnostic is not None:
                    budget.diagnostics.append({"operation": "stream_generate_content", "api_method": "streamGenerateContent",
                                               "model": MODEL, **diagnostic})
            if budget.diagnostics:
                http_status = budget.diagnostics[-1]["http_status"]
        finally:
            key = None
    return {"status": "PASS" if exact_ok and not budget.failed else "FAIL", "model": MODEL,
            "http_status": http_status, "received_exact_ok": exact_ok,
            "failure_stage": failure_stage,
            "maximum_requests": 1, "http_requests": budget.wire_requests,
            "diagnostics": budget.diagnostics, "database_connections": 0}


def offline_tests():
    """Run all Studio probe tests and SDK-default wire checks without live CLI."""
    import importlib.metadata
    import unittest
    from unittest.mock import patch
    import httpx
    from tools.test_gemini_studio_probe import StudioProbeTests

    class SDKDefaultTests(unittest.TestCase):
        def test_actual_sdk_default_serializes_v1beta_url_and_unchanged_payload(self):
            case = StudioProbeTests()
            result = case.run_probe()
            self.assertEqual(result["status"], "PASS")
            request, = case.requests
            self.assertEqual(request.url.path, "/v1beta/models/gemini-3.5-flash-lite:streamGenerateContent")
            self.assertEqual(request.url.query, b"alt=sse")
            self.assertEqual(json.loads(request.content), EXPECTED_BODY)
            self.assertEqual(importlib.metadata.version("google-genai"), "2.34.0")

        def test_api_version_is_unspecified_and_security_options_preserved(self):
            from google import genai
            with patch.object(genai, "Client", side_effect=ValueError("synthetic")) as client:
                result = probe_once("FAKE-KEY")
            self.assertEqual(result["http_requests"], 0)
            args = client.call_args.kwargs
            options = args["http_options"]
            self.assertIsNone(options.api_version)
            self.assertNotIn("api_version", options.model_fields_set)
            self.assertEqual(options.retry_options.attempts, 1)
            self.assertFalse(options.client_args["trust_env"])
            self.assertFalse(options.client_args["follow_redirects"])
            self.assertFalse(args["vertexai"])
            self.assertFalse(args["enterprise"])

        def test_http400_still_safe_and_not_retried(self):
            case = StudioProbeTests()
            result = case.run_probe(status=400)
            self.assertEqual(result["status"], "FAIL")
            self.assertEqual(result["http_status"], 400)
            self.assertEqual(len(case.requests), 1)
            self.assertNotIn("FAKE-KEY", json.dumps(result))

        def test_guard_blocks_forced_v1_endpoint_before_send(self):
            budget = StudioBudget()
            budget.reserve("synthetic")
            with self.assertRaises(SafetyStop):
                budget.check_request(httpx.Request("POST", URL.replace("/v1beta/", "/v1/"), json=EXPECTED_BODY))
            self.assertEqual(budget.wire_requests, 0)

        def test_payload_matches_getcode_structure_with_default_sdk_client(self):
            from google import genai
            from google.genai import types
            case = StudioProbeTests()
            self.assertEqual(case.run_probe()["status"], "PASS")
            reference = []
            def transport(_transport, request):
                reference.append(request)
                event = {"candidates": [{"content": {"role": "model", "parts": [{"text": "OK"}]}}]}
                return httpx.Response(200, request=request, headers={"content-type": "text/event-stream"},
                                      content=("data: " + json.dumps(event) + "\n\n").encode())
            budget = StudioBudget()
            system_root = os.environ.get("SystemRoot", r"C:\Windows")
            with patch.dict(os.environ, {"SystemRoot": system_root}, clear=True), \
                    patch.object(httpx.HTTPTransport, "handle_request", transport), isolation(budget):
                budget.reserve("synthetic reference", operation="stream_generate_content")
                with genai.Client(api_key="FAKE-KEY") as client:
                    contents = [types.Content(role="user", parts=[types.Part.from_text(text="Reply exactly OK")])]
                    config = types.GenerateContentConfig(
                        thinking_config=types.ThinkingConfig(thinking_level="MINIMAL"),
                        audio_transcription_config=types.AudioTranscriptionConfig())
                    with closing(client.models.generate_content_stream(model=MODEL, contents=contents, config=config)) as stream:
                        for _ in stream:
                            pass
            request, = reference
            self.assertEqual(request.url, case.requests[0].url)
            self.assertEqual(json.loads(request.content), json.loads(case.requests[0].content))

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SDKDefaultTests)
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(StudioProbeTests))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


def main(argv=None):
    class Parser(argparse.ArgumentParser):
        def error(self, message):
            raise SafetyStop("Invalid arguments; credentials must never be command arguments")
    parser = Parser(description=__doc__)
    parser.add_argument("mode", choices=("plan", "run-once"), nargs="?", default="plan")
    args = parser.parse_args(argv)
    if Path(sys.prefix).resolve() != (ROOT / ".venv").resolve():
        raise SafetyStop("Use project .venv")
    # Never inherit production/provider credentials, approvals, proxies or settings.
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    os.environ.clear()
    os.environ["SystemRoot"] = system_root
    if args.mode == "plan":
        report = {"status": "NOT_RUN", "model": MODEL, "maximum_requests": 1,
                  "key_requested": False, "http_requests": 0}
    else:
        if not sys.stdin.isatty():
            raise SafetyStop("Interactive terminal required")
        print("Verify THIS key's AI Studio project is Free Tier and paid billing is disabled.")
        print("This tool cannot verify billing or guarantee zero cost. Cancel if unsure.")
        if input(f"Type {CONFIRMATION}: ").strip() != CONFIRMATION:
            raise SafetyStop("Free Tier not verified")
        from tools.openai_test import hidden_input
        key = hidden_input("Gemini Studio test key (hidden): ")
        try:
            report = probe_once(key)
        finally:
            key = None
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Exception, KeyboardInterrupt) as error:
        print(f"Stopped ({type(error).__name__}); no retry or alternate provider.")
        raise SystemExit(1)
