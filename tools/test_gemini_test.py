"""No network, key input or MySQL: subprocess checks of Gemini staging."""
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[1]


class GeminiLauncherTests(TestCase):
    def run_launcher(self, *args):
        return subprocess.run([sys.executable, "-B", "tools/gemini_test.py", *args], cwd=ROOT, capture_output=True, timeout=45)

    def test_official_sdk_is_pinned_and_importable_without_client(self):
        from google.genai import types
        self.assertEqual(importlib.metadata.version("google-genai"), "2.34.0")
        self.assertEqual(types.HttpRetryOptions(attempts=1).attempts, 1)

    def test_plan_is_gemini_and_every_permission_is_locked(self):
        result = self.run_launcher("plan")
        self.assertEqual(result.returncode, 0)
        value = json.loads(result.stdout)
        self.assertEqual(value["configuration"]["chat_provider"], "gemini")
        self.assertEqual(value["configuration"]["embedding_model"], "gemini-embedding-001")
        for name in ("google_requests_approved", "free_project_confirmed", "index_update_approved", "database_connected", "key_loaded", "provider_called"):
            self.assertFalse(value[name])
        for name in ("paid_calls_approved", "personalization_export_approved", "review_export_approved"):
            self.assertFalse(value["configuration"][name])

    def test_key_input_live_switch_and_unverified_model_cannot_be_passed(self):
        for args in (("key-check",), ("plan", "--live"), ("plan", "--api-key", "synthetic-sentinel"), ("plan", "--model", "unverified")):
            result = self.run_launcher(*args)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn(b"synthetic-sentinel", result.stdout + result.stderr)

    def test_three_features_have_independent_safe_fallbacks(self):
        for feature in ("fr21", "fr22", "fr23"):
            with self.subTest(feature=feature):
                result = self.run_launcher("fallback", "--feature", feature)
                self.assertEqual(result.returncode, 0, result.stdout.decode("ascii", errors="replace"))
                value = json.loads(result.stdout)
                self.assertEqual([row["feature"] for row in value["results"]], [feature])
                self.assertEqual(value["results"][0]["status"], "PASS")
                self.assertEqual(value["configuration"]["chat_provider"], "gemini")
                self.assertIn(".gemini-test", value["workspace"])
                self.assertEqual(value["gemini_http_calls"], 0)
                self.assertEqual(value["openai_http_calls"], 0)
                self.assertEqual(value["payos_calls"], 0)
                self.assertEqual(value["financial_records"], {"invoices": 0, "payments": 0})

    def test_git_ignores_gemini_workspaces_and_environment_files(self):
        for name in (".gemini-test/data/chat.sqlite3", ".gemini-test/vectors/probe", ".env.gemini-test"):
            result = subprocess.run(["git", "check-ignore", "--no-index", "--", name], cwd=ROOT, capture_output=True)
            self.assertEqual(result.returncode, 0)
