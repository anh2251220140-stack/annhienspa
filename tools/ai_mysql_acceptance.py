"""Approved AI-only acceptance on guarded 3311. Never uses Django create/drop/flush."""
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from getpass import getpass, GetPassWarning
import json
import os
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import warnings

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
UUID = "608f399a-e055-11f1-9e4d-d549ecc51722"
DATA = Path(r"D:\AnNhienSpa_MySQL84_Acceptance_Test\data")
LABELS = ("ai_features.tests.ChatTests", "ai_features.test_rag", "ai_features.test_assistance", "ai_features.test_reference")


def main():
    if Path(sys.prefix).resolve() != (ROOT / ".venv").resolve() or not sys.stdin.isatty():
        raise RuntimeError("Use the project venv in an interactive terminal for hidden password input.")
    local_uuid = re.search(r"(?m)^server-uuid\s*=\s*([a-f0-9-]+)\s*$", (DATA / "auto.cnf").read_text(encoding="utf-8-sig"))
    if not local_uuid or local_uuid[1] != UUID or DATA.is_symlink():
        raise RuntimeError("Unexpected local test instance identity.")
    from config.fr14_test_guard import Guard, GuardError, Target, PRODUCTION_UUID, offline_database
    from tools import fr14_tests as runner
    target = Target(3311, os.environ["COMPUTERNAME"], UUID, PRODUCTION_UUID, approved=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output = ROOT / "docs" / f"ai-mysql-acceptance-{stamp}"
    output.mkdir(exist_ok=False)
    report = {"status": "awaiting_hidden_password", "tests": []}
    def save():
        (output / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    class DatadirGuard(Guard):
        def verify_session(self, raw):
            version = super().verify_session(raw)
            with raw.cursor() as cursor:
                cursor.execute("SELECT @@port,@@server_uuid,@@datadir,DATABASE(),CURRENT_USER()")
                port, uuid, directory, schema, account = cursor.fetchone()
            if (port != 3311 or uuid != UUID or Path(directory).resolve() != DATA.resolve()
                    or schema != "annhien_spa_fr14_tests" or account != "annhien_fr14_tests@127.0.0.1"):
                raise GuardError("Unexpected live AI test identity; stopped.")
            report["identity"] = {"port": port, "uuid": uuid, "datadir": directory, "schema": schema, "account": account}
            return version
    save()
    secret = None
    try:
        print("AI-only tests | 127.0.0.1:3311 | exact UUID guard | no paid AI", flush=True)
        with warnings.catch_warnings():
            warnings.simplefilter("error", GetPassWarning)
            secret = getpass("MySQL 3311 test password (hidden): ")
        if not secret:
            raise RuntimeError("No password entered")
        class SafeLog:
            def __init__(self, stream): self.stream = stream
            def write(self, text):
                text = text.replace(secret, "<redacted>")
                self.stream.write(text)
                self.stream.flush()
                return len(text)
            def flush(self): self.stream.flush()
        guard = DatadirGuard(target, secret)
        with (output / "execution.txt").open("x", encoding="utf-8") as log, TemporaryDirectory(prefix="spa-ai-mysql-") as folder:
            with redirect_stdout(SafeLog(log)), redirect_stderr(SafeLog(log)), runner.django_context(guard) as connections:
                from django.conf import settings
                from django.core.management import call_command
                from django.test.runner import DiscoverRunner
                settings.AI_RAG_DIRECTORY = Path(folder) / "vectors"
                settings.AI_PROVIDER = "mock"
                settings.AI_PAID_CALLS_APPROVED = False
                settings.AI_ASSISTANCE_ENABLED = True
                connection = connections["default"]
                tables = runner.preflight(connection)
                runner.require_empty_fixture_tables(connection, tables)
                plan = runner.migration_plan(connection)
                if plan not in ([], [("ai_features", "0003_review_analysis_details")]):
                    raise RuntimeError("Migration plan contains unapproved changes.")
                report.update(status="verified_empty_test_schema", plan=plan, tables_before=len(tables))
                save()
                guard.recheck(connection)
                if runner.migration_plan(connection) != plan:
                    raise RuntimeError("Migration plan changed")
                if plan:
                    call_command("migrate", "ai_features", "0003_review_analysis_details", database="default", interactive=False)
                if runner.migration_plan(connection):
                    raise RuntimeError("Unexpected pending migrations")
                with offline_database():
                    expected = runner.suite_ids(DiscoverRunner(verbosity=0).build_suite(LABELS))
                class Result(unittest.TextTestResult):
                    def record(self, test, status, reason=None):
                        report["tests"].append({"test": test.id(), "status": status, **({"reason": reason} if reason else {})})
                        save()
                    def addSuccess(self, test): super().addSuccess(test); self.record(test, "PASS")
                    def addFailure(self, test, err): super().addFailure(test, err); self.record(test, "FAIL")
                    def addError(self, test, err): super().addError(test, err); self.record(test, "ERROR")
                    def addSkip(self, test, reason): super().addSkip(test, reason); self.record(test, "BLOCKED", reason)
                    def addSubTest(self, test, subtest, err):
                        super().addSubTest(test, subtest, err)
                        if err: self.record(test, "FAIL")
                def approved(action, operation, selected):
                    if action != "RUN" or selected != target:
                        raise RuntimeError("Unexpected runner operation")
                with patch.object(runner, "confirm", side_effect=approved), patch.object(DiscoverRunner, "get_resultclass", return_value=Result):
                    failed = runner.run_tests(connection, guard, expected, labels=LABELS, reuse_schema=True)
                runner.require_empty_fixture_tables(connection, runner.preflight(connection))
                call_command("check")
                call_command("makemigrations", "--check", "--dry-run")
                report.update(status="complete" if not failed else "tests_failed", failures=failed,
                              empty_fixtures_after=True, pending_migrations=runner.migration_plan(connection))
                save()
    except BaseException as error:
        report.update(status="stopped", error=type(error).__name__ + ": " + str(error).replace(secret, "<redacted>") if secret else type(error).__name__)
        save()
    finally:
        secret = None
    print("AI MySQL evidence:", output, "| status:", report["status"], flush=True)
    return 0 if report["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
