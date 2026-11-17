"""Fresh-process acceptance startup, fully offline; never calls the live CLI."""
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest import TestCase


class FreshApplicationLauncherTests(TestCase):
    def test_fresh_settings_migrations_sdk_and_cleanup_without_env_or_network(self):
        script = r'''
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import httpx
from tools.fr22_application_test import configure_application, seed_synthetic, application_check, guarded_application
from tools.gemini_live import Budget
from django.conf import settings
try:
    with TemporaryDirectory(prefix="fr22-fresh-offline-") as temp, patch("dotenv.load_dotenv", side_effect=AssertionError("dotenv forbidden")):
        configure_application(Path(temp))
        from django.core.management import call_command
        from django.test import override_settings
        from django.db import connections
        assert settings.AI_PAID_CALLS_APPROVED is False
        assert settings.AI_PERSONALIZATION_EXPORT_APPROVED is False
        assert settings.AI_REVIEW_EXPORT_APPROVED is False
        assert settings.AI_GEMINI_REQUESTS_APPROVED is False
        calls=[]
        def handle(request):
            calls.append(1)
            data=json.loads(json.loads(request.content)["contents"][0]["parts"][0]["text"])
            text=json.dumps({"items":[{"id":data["candidates"][0]["id"],"reason":"Phù hợp dữ liệu giả lập."}]})
            return httpx.Response(200,request=request,json={"candidates":[{"content":{"role":"model","parts":[{"text":text}]}}]})
        transport=httpx.MockTransport(handle)
        def send(client,request,**kwargs):
            for hook in client.event_hooks.get("request",[]):hook(request)
            return transport.handle_request(request)
        budget=Budget(1,generation_only=True)
        with patch.object(httpx.Client,"send",send),guarded_application(budget):
            call_command("migrate",verbosity=0,interactive=False)
            fixture=seed_synthetic()
            with override_settings(AI_GEMINI_API_KEY="fake-fresh-test-key",AI_PERSONALIZATION_EXPORT_APPROVED=True,
                    AI_GEMINI_REQUESTS_APPROVED=True,AI_GEMINI_FREE_TIER_CONFIRMED=True):
                result=application_check(fixture,budget)
            assert len(calls)==1
            assert settings.AI_PERSONALIZATION_EXPORT_APPROVED is False
        connections.close_all()
    assert not Path(temp).exists()
    print(json.dumps({"status":result["status"],"temporary_sqlite_removed":True,"mock_requests":len(calls)}))
except Exception:
    print(json.dumps({"status":"FAIL","code":"FRESH_OFFLINE_CHECK_FAILED"}))
    raise SystemExit(1)
'''
        # No inherited credentials, approval flags or production settings module.
        result = subprocess.run([sys.executable, "-B", "-c", script], cwd=Path(__file__).resolve().parents[1],
            env={"SystemRoot": os.environ.get("SystemRoot", r"C:\Windows")},
            text=True, capture_output=True, encoding="utf-8", timeout=90)
        self.assertEqual(result.returncode, 0, "Fresh offline acceptance failed; no secret payload is displayed")
        report = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual(report, {"status": "PASS", "temporary_sqlite_removed": True, "mock_requests": 1})
