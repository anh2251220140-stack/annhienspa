"""Legacy filename, Gemini-only no-cost staging: offline plan/fallback and read-only guarded 3311 preflight.

There is no live/approve switch; retired OpenAI key input is refused. Shared
getpass and isolation helpers remain available to the Gemini launchers.
"""
import argparse
from contextlib import ExitStack, contextmanager
from datetime import datetime
from getpass import getpass, GetPassWarning
import json
import os
from pathlib import Path
import re
from secrets import token_urlsafe
import sys
from uuid import uuid4
import warnings

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
WORK_ROOT = ROOT / ".openai-test"
UUID = "608f399a-e055-11f1-9e4d-d549ecc51722"
DATA = Path(r"D:\AnNhienSpa_MySQL84_Acceptance_Test\data")
FEATURES = ("fr21", "fr22", "fr23")


class StagingError(RuntimeError):
    """A fixed diagnostic that never includes an exception payload or credential."""


def locked_environment(hostname="", system_root=r"C:\Windows"):
    # Never inherit MYSQL/PAYOS/AI secrets or approval flags from a parent shell.
    return {
        "COMPUTERNAME": hostname, "SystemRoot": system_root, "DJANGO_SETTINGS_MODULE": "config.settings",
        "DJANGO_DEBUG": "true", "DJANGO_SECRET_KEY": token_urlsafe(48),
        "AI_PROVIDER": "gemini", "AI_PAID_CALLS_APPROVED": "false",
        "AI_PERSONALIZATION_EXPORT_APPROVED": "false", "AI_REVIEW_EXPORT_APPROVED": "false",
    }


def public_configuration(provider="gemini"):
    # Explicit allowlist, not a dump of environment variables or Django settings.
    if provider not in {"gemini", "mock"}:
        raise StagingError("Only Gemini or internal mock is allowed")
    return {"chat_provider": provider, "embedding_provider": provider,
            "chat_model": "gemini-3.5-flash-lite" if provider == "gemini" else "local-mock-v1",
            "embedding_model": "gemini-embedding-001" if provider == "gemini" else "local-lexical-sha256",
            "paid_calls_approved": False, "personalization_export_approved": False,
            "review_export_approved": False, "external_network": "blocked",
            "google_requests_approved": False, "free_project_confirmed": False, "index_update_approved": False,
            "preflight_target": "127.0.0.1:3311/annhien_spa_fr14_tests", "expected_uuid": UUID}


def hidden_input(prompt):
    if not sys.stdin.isatty():
        raise StagingError("An interactive terminal is required for hidden input.")
    with warnings.catch_warnings():
        warnings.simplefilter("error", GetPassWarning)
        value = getpass(prompt)
    if not value:
        raise StagingError("Hidden input was empty; stopped.")
    return value


@contextmanager
def staged_key(load=False):
    if load:
        raise StagingError("OpenAI key staging is retired; use the Gemini launcher")
    value = ""
    try:
        yield value
    finally:
        os.environ.pop("AI_OPENAI_API_KEY", None)
        value = None


def new_workspace():
    # No configurable path, reuse or cleanup operation; old runs are never deleted.
    if WORK_ROOT.is_symlink() or WORK_ROOT.is_junction():
        raise StagingError("A redirected workspace is forbidden.")
    if WORK_ROOT.resolve().parent != ROOT.resolve():
        raise StagingError("Workspace must stay inside the project.")
    WORK_ROOT.mkdir(exist_ok=True)
    run = WORK_ROOT / (datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid4().hex)
    run.mkdir(exist_ok=False)
    for name in ("data", "vectors", "media"):
        (run / name).mkdir()
    return run


@contextmanager
def forbid_provider_calls():
    from unittest.mock import patch
    from ai_features.integration import OpenAIProvider, ProviderUnavailable
    def reject(*args, **kwargs):
        raise ProviderUnavailable("OpenAI calls are locked in the staging launcher")
    # Defense in depth: the ordinary paid-call flag stays false as well.
    from ai_features.gemini import GeminiProvider
    with patch.object(OpenAIProvider, "_post", side_effect=reject), patch.object(GeminiProvider, "_client", side_effect=reject):
        yield


def fallback(feature, key="", *, provider="gemini"):
    """Exercise real API orchestration on freshly owned SQLite fixtures, never MySQL."""
    if provider not in {"mock", "gemini"}:
        raise StagingError("Unknown staging provider")
    run = new_workspace()
    from tools.chat_sqlite import configure
    with ExitStack() as stack:
        configure(stack, run / "data")  # blocks MySQL, dotenv, sockets, httpx and PayOS
        from django.conf import settings
        from django.core.management import call_command
        from django.test import Client, override_settings
        stack.enter_context(override_settings(
            AI_PROVIDER=provider, AI_PAID_CALLS_APPROVED=False,
            AI_GEMINI_API_KEY="", AI_GEMINI_MODEL="gemini-3.5-flash-lite", AI_GEMINI_EMBEDDING_MODEL="gemini-embedding-001",
            AI_GEMINI_REQUESTS_APPROVED=False, AI_GEMINI_FREE_TIER_CONFIRMED=False, AI_GEMINI_FREE_TIER_ONLY=True,
            AI_RAG_INDEX_UPDATE_APPROVED=False,
            AI_PERSONALIZATION_EXPORT_APPROVED=False, AI_REVIEW_EXPORT_APPROVED=False,
            AI_RAG_ENABLED=True, AI_RAG_DIRECTORY=run / "vectors", AI_ASSISTANCE_ENABLED=True,
            AI_CHAT_SPA_INFORMATION="Thông tin chỉ dùng cho kiểm thử tổng hợp, không phải dữ liệu Spa thật.",
            SESSION_COOKIE_NAME="annhien_openai_staging_session", CSRF_COOKIE_NAME="annhien_openai_staging_csrf",
            MEDIA_ROOT=run / "media", PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
            ALLOWED_HOSTS=["testserver"],
        ))
        stack.enter_context(forbid_provider_calls())
        expected_db = str(run / "data" / "chat.sqlite3")
        if settings.DATABASES["default"]["ENGINE"] != "django.db.backends.sqlite3" or settings.DATABASES["default"]["NAME"] != expected_db:
            raise StagingError("Unexpected fallback database")
        call_command("migrate", interactive=False, verbosity=0)  # ONLY this new SQLite file
        from accounts.models import Customer, User
        from services.models import Service, ServiceCategory
        category = ServiceCategory.objects.create(name="Danh mục fixture OpenAI")
        service = Service.objects.create(category=category, name="Liệu trình fixture OpenAI", description="Nội dung giả lập để kiểm thử.",
                                         price=200000, duration_minutes=60, care_group="face")
        user = User.objects.create_user("openai_fixture_user", "openai-fixture@example.test", password=None)
        customer = Customer.objects.create(user=user, full_name="Khách fixture", phone="123",
            budget=300000, skin_type="Da thường", care_needs="Dưỡng ẩm, cải thiện da khô")
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)
        def post(path, payload, page="/services.html"):
            if client.get(page).status_code != 200:
                raise StagingError("Fixture page unavailable")
            token = client.cookies[settings.CSRF_COOKIE_NAME].value
            return client.post(path, payload, content_type="application/json", HTTP_X_CSRFTOKEN=token)
        outcomes = []
        selected = FEATURES if feature == "all" else (feature,)
        if "fr21" in selected:
            response = post("/api/ai/chat/", {"question": "Liệu trình fixture OpenAI giá bao nhiêu?", "requestId": str(uuid4())})
            if response.status_code != 200 or response.json()["answer"]["status"] != "fallback":
                raise StagingError("FR-21 did not safely fall back")
            outcomes.append({"feature": "fr21", "status": "PASS", "result": "fallback", "reason": "index_and_provider_calls_locked"})
        if "fr22" in selected:
            response = post("/api/ai/recommendations/", {})
            body = response.json()
            if response.status_code != 200 or body["mode"] != "rule" or [s["id"] for s in body["items"]] != [service.pk]:
                raise StagingError("FR-22 did not safely use the rule fallback")
            outcomes.append({"feature": "fr22", "status": "PASS", "result": "rule", "reason": "personalization_export_not_approved"})
        if "fr23" in selected:
            from datetime import time, timedelta
            from django.contrib.auth.models import Permission
            from django.utils import timezone
            from appointments.models import Appointment
            from employees.models import Employee, EmployeeSchedule, EmployeeService
            from reviews.models import Review, ReviewReply
            employee = Employee.objects.create(full_name="Nhân viên fixture", specialty="Kiểm thử")
            EmployeeService.objects.create(employee=employee, service=service)
            day = timezone.localdate() - timedelta(days=2)
            EmployeeSchedule.objects.create(employee=employee, work_date=day, start_time=time(8), end_time=time(17))
            appointment = Appointment.objects.create(customer=customer, service=service, employee=employee,
                appointment_date=day, start_time=time(9), end_time=time(10), status="completed")
            original = "Nhận xét fixture: không gian yên tĩnh."
            review = Review.objects.create(appointment=appointment, customer=customer, service=service, rating=5, comment=original)
            admin = User.objects.create_user("openai_fixture_admin", "openai-admin@example.test", password=None, role="Admin")
            admin.user_permissions.add(Permission.objects.get(content_type__app_label="ai_features", codename="change_aireviewanalysis"))
            client.force_login(admin)
            response = post(f"/api/ai/reviews/{review.pk}/analyze/", {}, "/admin-reviews.html")
            if (response.status_code != 200 or response.json()["analysis"]["mode"] != "rule"
                    or Review.objects.get(pk=review.pk).comment != original or ReviewReply.objects.exists()):
                raise StagingError("FR-23 did not safely preserve the review")
            outcomes.append({"feature": "fr23", "status": "PASS", "result": "rule", "reason": "review_export_not_approved"})
        report = {"configuration": public_configuration(provider), "database": "new dedicated SQLite only",
                  "workspace": str(run), "openai_http_calls": 0, "gemini_http_calls": 0, "payos_calls": 0, "results": outcomes}
        from billing.models import Invoice, Payment
        if Invoice.objects.exists() or Payment.objects.exists():
            raise StagingError("Financial fixture data was not expected")
        report["financial_records"] = {"invoices": 0, "payments": 0}
        (run / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        (run / "data" / "fixture-description.json").write_text(json.dumps({
            "synthetic_only": True, "features": list(selected), "copied_from_mysql": False}), encoding="utf-8")
    return report


def validate_read_sql(sql):
    value = sql.strip()
    # Django's MySQL backend performs these exact non-data session settings.
    session_setup = {"SET SQL_AUTO_IS_NULL = 0", "SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED"}
    if value and all(part.strip().upper() in session_setup for part in value.split(";")):
        return
    if ";" in value.rstrip(";") or not re.match(r"^(SELECT|SHOW|DESCRIBE|EXPLAIN)\s", value, re.I):
        raise StagingError("Only read-only preflight statements are allowed")
    if re.search(r"\b(FOR\s+UPDATE|INTO\s+(OUTFILE|DUMPFILE)|GET_LOCK|RELEASE_LOCK|SLEEP|BENCHMARK)\b", value, re.I):
        raise StagingError("Unexpected preflight SQL")


def readonly_guard(hostname, password, report):
    from config.fr14_test_guard import Guard, GuardError, Target, PRODUCTION_UUID
    target = Target(3311, hostname, UUID, PRODUCTION_UUID, approved=True)
    class ReadOnlyGuard(Guard):
        def verify_session(self, raw):
            version = super().verify_session(raw)
            with raw.cursor() as cursor:
                cursor.execute("SELECT @@datadir")
                directory = cursor.fetchone()[0]
                if Path(directory).resolve() != DATA.resolve():
                    raise GuardError("Unexpected test datadir")
                cursor.execute("SET SESSION TRANSACTION READ ONLY")
            report.update(host="127.0.0.1", port=3311, uuid=UUID, datadir=directory,
                          database=self.database, account="annhien_fr14_tests@127.0.0.1", version=version,
                          grants="verified exact schema-only privileges", session="READ ONLY")
            return version
    return ReadOnlyGuard(target, password)


def preflight(hostname):
    """No fixture creation, migrations, cleanup, key input or business row reads."""
    from tools import fr14_tests as runner
    from unittest.mock import patch
    local_uuid = re.search(r"(?m)^server-uuid\s*=\s*([a-f0-9-]+)\s*$", (DATA / "auto.cnf").read_text(encoding="utf-8-sig"))
    if not local_uuid or local_uuid[1] != UUID or DATA.is_symlink() or DATA.is_junction():
        raise StagingError("Local test instance identity mismatch")
    report = {}
    password = hidden_input("MySQL 3311 test password (hidden; read-only preflight): ")
    try:
        with runner.django_context(readonly_guard(hostname, password, report)) as connections:
            from django.db.backends.utils import CursorWrapper
            execute = CursorWrapper.execute
            def readonly(cursor, sql, params=None):
                validate_read_sql(sql)
                return execute(cursor, sql, params)
            with patch.object(CursorWrapper, "execute", readonly), patch.object(CursorWrapper, "executemany", side_effect=StagingError("Bulk SQL forbidden")):
                connection = connections["default"]
                tables = runner.preflight(connection)
                pending = runner.migration_plan(connection)
                report.update(tables=len(tables), pending_migrations=pending, status="BLOCKED" if pending else "PASS")
    finally:
        password = None
    return report


def main(argv=None):
    class SafeParser(argparse.ArgumentParser):
        def error(self, message):
            # argparse's default message echoes unknown arguments (possibly a pasted key).
            raise StagingError("Invalid arguments. Use --help; never pass credentials as arguments.")
    parser = SafeParser(description=__doc__)
    parser.add_argument("mode", choices=("plan", "key-check", "preflight", "fallback"))
    parser.add_argument("--feature", choices=(*FEATURES, "all"), default="fr21")
    parser.add_argument("--load-key", action="store_true", help="Hidden terminal input only; paid calls remain locked")
    args = parser.parse_args(argv)
    if args.load_key and args.mode not in {"key-check", "fallback"}:
        parser.error("Key input is available only for key-check or fallback")
    if Path(sys.prefix).resolve() != (ROOT / ".venv").resolve():
        raise StagingError("Use the project .venv Python")
    # Only these non-secret OS values survive; SystemRoot is needed by Windows asyncio.
    hostname = os.environ.get("COMPUTERNAME", "")
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    os.environ.clear()
    os.environ.update(locked_environment(hostname, system_root))
    if args.mode == "plan":
        report = {"configuration": public_configuration(), "database_connected": False, "provider_called": False}
    elif args.mode == "preflight":
        report = preflight(hostname)
        run = new_workspace()
        report.update(configuration=public_configuration(), workspace=str(run))
        (run / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        with staged_key(args.load_key or args.mode == "key-check") as key:
            if args.mode == "key-check":
                report = {"configuration": public_configuration(), "key_input": "received in memory; not validated or saved",
                          "database_connected": False, "provider_called": False}
            else:
                report = fallback(args.feature, key)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 1 if report.get("status") == "BLOCKED" else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyboardInterrupt, EOFError):
        print("Stopped; no live provider calls were enabled.")
        raise SystemExit(1)
    except Exception as error:
        # Never echo exception text/traceback: a provider/driver error may contain secrets.
        print(f"Stopped ({type(error).__name__}); no alternate database or live provider will be used.")
        raise SystemExit(1)
