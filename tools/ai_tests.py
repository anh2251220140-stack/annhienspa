"""AI regression only: new temporary SQLite/media/vector files, all network blocked."""
from contextlib import ExitStack
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from tools.chat_sqlite import configure
    with TemporaryDirectory(prefix="annhien-ai-regression-") as folder, ExitStack() as stack:
        configure(stack, Path(folder))
        from django.conf import settings
        from django.core.management import call_command
        from django.test.runner import DiscoverRunner
        from unittest import TextTestResult
        settings.AI_RAG_DIRECTORY = Path(folder) / "vectors"
        settings.AI_PROVIDER = "mock"
        settings.AI_ASSISTANCE_ENABLED = True
        settings.AI_PAID_CALLS_APPROVED = False
        settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
        records = []

        class Result(TextTestResult):
            def addSuccess(self, test):
                super().addSuccess(test)
                records.append({"test": test.id(), "status": "PASS"})

            def addFailure(self, test, err):
                super().addFailure(test, err)
                records.append({"test": test.id(), "status": "FAIL"})

            def addError(self, test, err):
                super().addError(test, err)
                records.append({"test": test.id(), "status": "ERROR"})

            def addSkip(self, test, reason):
                super().addSkip(test, reason)
                records.append({"test": test.id(), "status": "SKIP", "reason": reason})

        class Runner(DiscoverRunner):
            def get_resultclass(self):
                return Result

        # The reused launcher refuses all MySQL driver connections before any socket.
        call_command("check")
        call_command("makemigrations", "--check", "--dry-run", verbosity=1)
        labels = sys.argv[1:] or ["ai_features.tests.ChatTests", "ai_features.test_rag", "ai_features.test_assistance", "ai_features.test_reference", "ai_features.test_gemini"]
        failures = Runner(verbosity=2, interactive=False).run_tests(labels)
        output = ROOT / "docs" / "ai-regression-results-20261115.json"
        # Do not overwrite prior evidence.
        if output.exists():
            from datetime import datetime
            output = output.with_stem(output.stem + "-" + datetime.now().strftime("%H%M%S%f"))
        output.write_text(json.dumps({"database": "new temporary SQLite only", "network": "blocked",
            "provider": "mock/stub only", "failures": failures, "tests": records}, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Evidence:", output)
        return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
