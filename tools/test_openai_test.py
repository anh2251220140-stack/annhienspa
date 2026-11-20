"""Offline tests for the no-cost launcher. No secret input or database sockets."""
from contextlib import redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import MagicMock, patch

from tools import openai_test as launcher


class ConfigurationTests(TestCase):
    def test_locked_environment_does_not_contain_inherited_secrets(self):
        values = launcher.locked_environment("test-host")
        self.assertEqual(values["AI_PROVIDER"], "gemini")
        self.assertEqual(values["AI_PAID_CALLS_APPROVED"], "false")
        self.assertEqual(values["AI_PERSONALIZATION_EXPORT_APPROVED"], "false")
        self.assertEqual(values["AI_REVIEW_EXPORT_APPROVED"], "false")
        self.assertEqual(values["SystemRoot"], r"C:\Windows")
        for key in ("AI_OPENAI_API_KEY", "OPENAI_API_KEY", "MYSQL_PASSWORD", "PAYOS_API_KEY"):
            self.assertNotIn(key, values)

    def test_public_config_never_serializes_secrets(self):
        value = launcher.public_configuration()
        self.assertFalse(value["paid_calls_approved"])
        self.assertNotIn("key", json.dumps(value).lower())

    def test_retired_provider_cannot_be_configured_or_staged(self):
        with patch.object(launcher, "new_workspace") as workspace:
            with self.assertRaises(launcher.StagingError):
                launcher.public_configuration("openai")
            with self.assertRaises(launcher.StagingError):
                launcher.fallback("fr21", provider="openai")
            workspace.assert_not_called()

    def test_hidden_input_refuses_noninteractive_echo_fallback(self):
        with patch.object(launcher.sys.stdin, "isatty", return_value=False), patch.object(launcher, "getpass") as reader:
            with self.assertRaises(launcher.StagingError):
                launcher.hidden_input("synthetic prompt")
            reader.assert_not_called()

    def test_hidden_input_refuses_getpass_warning(self):
        with patch.object(launcher.sys.stdin, "isatty", return_value=True), patch.object(launcher, "getpass", side_effect=launcher.GetPassWarning()):
            with self.assertRaises(launcher.GetPassWarning):
                launcher.hidden_input("synthetic prompt")

    def test_hidden_input_rejects_empty(self):
        with patch.object(launcher.sys.stdin, "isatty", return_value=True), patch.object(launcher, "getpass", return_value=""):
            with self.assertRaises(launcher.StagingError):
                launcher.hidden_input("synthetic prompt")

    def test_retired_key_staging_refused_before_read(self):
        with patch.object(launcher, "hidden_input") as reader:
            with self.assertRaises(launcher.StagingError):
                with launcher.staged_key(True):
                    self.fail("Retired staging must not accept a key")
            reader.assert_not_called()

    def test_key_not_requested_by_default(self):
        with patch.object(launcher, "hidden_input") as reader, patch.object(launcher, "os"):
            with launcher.staged_key() as value:
                self.assertEqual(value, "")
            reader.assert_not_called()

    def test_no_paid_or_key_command_line_switch(self):
        for args in (("plan", "--live"), ("plan", "--approve"), ("plan", "--api-key", "synthetic-sentinel")):
            output = StringIO()
            with redirect_stdout(output), self.assertRaises(launcher.StagingError) as error:
                launcher.main(args)
            self.assertNotIn("synthetic-sentinel", str(error.exception) + output.getvalue())

    def test_workspace_is_new_and_never_reuses_old_data(self):
        with TemporaryDirectory() as folder:
            base = Path(folder)
            with patch.object(launcher, "ROOT", base), patch.object(launcher, "WORK_ROOT", base / ".openai-test"):
                first = launcher.new_workspace()
                (first / "keep.txt").write_text("old fixture", encoding="utf-8")
                second = launcher.new_workspace()
                self.assertNotEqual(first, second)
                self.assertTrue((first / "keep.txt").exists())
                self.assertTrue((second / "vectors").is_dir())
                self.assertTrue((second / "data").is_dir())

    def test_workspace_escape_is_rejected(self):
        with TemporaryDirectory() as folder:
            with patch.object(launcher, "ROOT", Path(folder) / "project"), patch.object(launcher, "WORK_ROOT", Path(folder) / "outside"):
                with self.assertRaises(launcher.StagingError):
                    launcher.new_workspace()

    def test_ignore_rules(self):
        for path in (".openai-test/check.json", ".openai-test/data/chat.sqlite3", ".env.openai-test"):
            result = subprocess.run(["git", "check-ignore", "--no-index", "--", path], cwd=launcher.ROOT, capture_output=True)
            self.assertEqual(result.returncode, 0, path)


def fake_raw(guard, *, uuid=launcher.UUID, directory=None):
    from config.fr14_test_guard import ACCOUNT, DATABASE, PRIVILEGES, USER
    raw = MagicMock()
    cursor = raw.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [
        (DATABASE, ACCOUNT, guard.target.hostname, 3311, uuid, "8.4.11", "MySQL Community Server", "InnoDB", "NONE", "", 1),
        (str(directory or launcher.DATA),),
    ]
    cursor.fetchall.return_value = [(f"GRANT USAGE ON *.* TO `{USER}`@`127.0.0.1`",),
        (f"GRANT {', '.join(sorted(PRIVILEGES))} ON `{DATABASE}`.* TO `{USER}`@`127.0.0.1`",)]
    return raw, cursor


class GuardTests(TestCase):
    def test_only_3311_target_is_constructed(self):
        guard = launcher.readonly_guard("test-host", "synthetic-password", {})
        self.assertEqual(guard.target.port, 3311)
        self.assertEqual(guard.target.server_uuid, launcher.UUID)
        self.assertEqual(guard.database, "annhien_spa_fr14_tests")

    def test_production_and_restore_ports_refused_before_driver_socket(self):
        from config.fr14_test_guard import GuardError, install_guard
        from django.db.backends.mysql.base import Database
        guard = launcher.readonly_guard("test-host", "synthetic-password", {})
        with patch.object(Database, "connect") as driver, install_guard(guard):
            for port in (3306, 3310):
                with self.assertRaises(GuardError):
                    Database.connect(host="127.0.0.1", port=port)
            driver.assert_not_called()

    def test_identity_grants_datadir_then_readonly_session(self):
        report = {}
        guard = launcher.readonly_guard("test-host", "synthetic-password", report)
        raw, cursor = fake_raw(guard)
        self.assertEqual(guard.verify_session(raw), "8.4.11")
        self.assertEqual(report["session"], "READ ONLY")
        cursor.execute.assert_called_with("SET SESSION TRANSACTION READ ONLY")

    def test_wrong_uuid_rejected(self):
        from config.fr14_test_guard import GuardError, RESTORE_UUID
        guard = launcher.readonly_guard("test-host", "synthetic-password", {})
        raw, cursor = fake_raw(guard, uuid=RESTORE_UUID)
        with self.assertRaises(GuardError):
            guard.verify_session(raw)
        self.assertNotIn(("SET SESSION TRANSACTION READ ONLY",), [x.args for x in cursor.execute.call_args_list])

    def test_wrong_datadir_rejected(self):
        from config.fr14_test_guard import GuardError
        guard = launcher.readonly_guard("test-host", "synthetic-password", {})
        raw, _ = fake_raw(guard, directory=Path(r"D:\not-the-test-instance"))
        with self.assertRaises(GuardError):
            guard.verify_session(raw)

    def test_read_only_sql_allows_only_metadata_and_known_session_setup(self):
        for sql in ("SELECT VERSION()", "SHOW GRANTS", "SELECT name FROM django_migrations",
                    "SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED",
                    "SET SQL_AUTO_IS_NULL = 0; SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED"):
            launcher.validate_read_sql(sql)
        for sql in ("UPDATE invoices SET total_amount=0", "DELETE FROM chat_messages", "DROP DATABASE test",
                    "SELECT 1; DELETE FROM reviews", "SELECT * FROM reviews FOR UPDATE", "SELECT GET_LOCK('x',1)",
                    "SET SESSION TRANSACTION READ WRITE", "SELECT x INTO OUTFILE '/tmp/x'", "/* x */ SELECT 1"):
            with self.subTest(sql=sql), self.assertRaises(launcher.StagingError):
                launcher.validate_read_sql(sql)


class OfflineRuntimeTests(TestCase):
    def test_plan_without_database_or_key(self):
        result = subprocess.run([sys.executable, "-B", "tools/openai_test.py", "plan"], cwd=launcher.ROOT, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0)
        report = json.loads(result.stdout)
        self.assertFalse(report["database_connected"])
        self.assertFalse(report["provider_called"])

    def test_all_features_use_synthetic_sqlite_and_no_external_calls(self):
        result = subprocess.run([sys.executable, "-B", "tools/openai_test.py", "fallback", "--feature", "all"],
                                cwd=launcher.ROOT, capture_output=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout.decode("ascii", errors="replace"))
        report = json.loads(result.stdout)
        self.assertEqual([r["feature"] for r in report["results"]], list(launcher.FEATURES))
        self.assertTrue(all(r["status"] == "PASS" for r in report["results"]))
        self.assertEqual(report["openai_http_calls"], 0)
        self.assertEqual(report["payos_calls"], 0)
        self.assertEqual(report["financial_records"], {"invoices": 0, "payments": 0})
        self.assertEqual(report["database"], "new dedicated SQLite only")
        self.assertFalse(report["configuration"]["paid_calls_approved"])
        self.assertFalse(report["configuration"]["personalization_export_approved"])
        self.assertFalse(report["configuration"]["review_export_approved"])

    def test_each_feature_can_run_independently(self):
        for feature in launcher.FEATURES:
            with self.subTest(feature=feature):
                result = subprocess.run([sys.executable, "-B", "tools/openai_test.py", "fallback", "--feature", feature],
                                        cwd=launcher.ROOT, capture_output=True, timeout=45)
                self.assertEqual(result.returncode, 0)
                report = json.loads(result.stdout)
                self.assertEqual([r["feature"] for r in report["results"]], [feature])
                self.assertEqual(report["results"][0]["status"], "PASS")
                self.assertEqual(report["financial_records"], {"invoices": 0, "payments": 0})


if __name__ == "__main__":
    main(verbosity=2)
