"""Opt-in FR-22 authenticated application acceptance; synthetic temporary SQLite.

Never run live automatically. The production recommendation URL is POST-only;
the readback URL below exists solely in this acceptance process, not the website.
"""
import argparse
from contextlib import contextmanager
from datetime import time, timedelta
import json
import os
from pathlib import Path
from secrets import token_urlsafe
import sys
from tempfile import TemporaryDirectory
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
POST_URL = "/api/ai/recommendations/"
READ_URL = "/acceptance/recommendations/"
INPUT = {"skin": "Da khô", "needs": "face", "budget": "300000", "duration": "medium", "interests": "Không gian yên tĩnh"}


def acceptance_urls():
    from django.http import JsonResponse
    from django.middleware.csrf import get_token
    from django.shortcuts import get_object_or_404
    from django.urls import path
    from django.views.decorators.http import require_GET
    from ai_features.assistance_views import access, recommendations
    from ai_features.models import AIRecommendation

    @access()
    @require_GET
    def csrf_ready(request):
        get_token(request)
        return JsonResponse({"ready": True})

    @access()
    @require_GET
    def readback(request, pk):
        # This view is test infrastructure only. No URL is added to the app.
        item = get_object_or_404(AIRecommendation, pk=pk, customer__user=request.user)
        return JsonResponse(json.loads(item.reason))

    return [path("api/ai/recommendations/", recommendations),
            path("acceptance/csrf/", csrf_ready),
            path("acceptance/recommendations/<int:pk>/", readback)]


def seed_synthetic():
    from django.utils import timezone
    from accounts.models import Customer, User
    from appointments.models import Appointment
    from employees.models import Employee, EmployeeSchedule, EmployeeService
    from services.models import Service, ServiceCategory
    owner = User.objects.create_user("fr22_synthetic", "synthetic@example.test", token_urlsafe(24))
    other = User.objects.create_user("fr22_other", "other@example.test", token_urlsafe(24))
    customer = Customer.objects.create(user=owner, full_name="Khách giả lập FR22", phone="123",
        budget=300000, skin_type="Da khô", care_needs=json.dumps(["Dưỡng ẩm, cải thiện da khô"]), preferences="Không gian yên tĩnh")
    Customer.objects.create(user=other, full_name="Khách giả lập khác", phone="123")
    category = ServiceCategory.objects.create(name="Danh mục giả lập FR22")
    def service(name, price, **kwargs):
        values = dict(category=category, name=name, description="Dịch vụ giả lập, không gian yên tĩnh.",
                      price=price, duration_minutes=60, care_group="face")
        values.update(kwargs)
        return Service.objects.create(**values)
    eligible = [service("Dịch vụ giả lập A", 200000), service("Dịch vụ giả lập B", 280000)]
    excluded = [service("Vượt ngân sách", 450000), service("Dịch vụ ẩn", 100000, is_active=False),
                service("Khác nhu cầu", 150000, care_group="hair"), service("Quá thời lượng", 200000, duration_minutes=120)]
    employee = Employee.objects.create(full_name="Nhân viên giả lập", specialty="Dịch vụ giả lập")
    EmployeeService.objects.create(employee=employee, service=eligible[0])
    day = timezone.localdate() - timedelta(days=3)
    EmployeeSchedule.objects.create(employee=employee, work_date=day, start_time=time(8), end_time=time(17))
    Appointment.objects.create(customer=customer, service=eligible[0], employee=employee, appointment_date=day,
        start_time=time(9), end_time=time(10), status="completed")
    return SimpleNamespace(owner=owner, other=other, customer=customer, eligible=eligible, excluded=excluded)


@contextmanager
def guarded_application(budget):
    from django.db import connections
    from django.db.backends.base.base import BaseDatabaseWrapper
    from tools.gemini_live import isolation, SafetyStop
    original = BaseDatabaseWrapper.ensure_connection
    database = connections["default"].settings_dict["NAME"]
    if connections["default"].vendor != "sqlite":
        raise SafetyStop("Acceptance requires isolated SQLite")

    def sqlite_only(wrapper):
        if (wrapper.alias != "default" or wrapper.vendor != "sqlite"
                or wrapper.settings_dict["NAME"] != database):
            raise SafetyStop("Unexpected database target")
        return original(wrapper)

    # Reuse official-origin, port 443, no redirects, one-request wire guard.
    # The only ORM exception to the adapter probe's blanket deny is THIS SQLite.
    with isolation(budget), patch.object(BaseDatabaseWrapper, "ensure_connection", sqlite_only):
        yield


def application_check(fixture, budget):
    from decimal import Decimal
    from django.core.cache import cache
    from django.test import Client
    from ai_features.models import AIRecommendation
    from tools.gemini_live import SafetyStop
    cache.clear()
    client = Client(enforce_csrf_checks=True)
    client.force_login(fixture.owner)
    ready = client.get("/acceptance/csrf/")
    if ready.status_code != 200 or AIRecommendation.objects.exists():
        raise SafetyStop("Acceptance must start with empty recommendation fixtures")
    from django.conf import settings
    csrf = client.cookies[settings.CSRF_COOKIE_NAME].value
    # Record the production GET limitation rather than pretending this is shipped.
    production_get = client.get(POST_URL).status_code
    if production_get != 405:
        raise SafetyStop("Unexpected production recommendation API contract")
    budget.reserve(INPUT, operation="fr22-authenticated-application")
    response = client.post(POST_URL, INPUT, content_type="application/json", HTTP_X_CSRFTOKEN=csrf)
    result = response.json()
    if response.status_code != 200 or result.get("mode") != "ai" or budget.wire_requests != 1 or budget.failed:
        raise SafetyStop("Application did not return a validated AI recommendation")
    rows = result.get("items")
    allowed = {s.pk: s for s in fixture.eligible}
    if (not isinstance(rows, list) or not 1 <= len(rows) <= 3
            or len({r.get("id") for r in rows}) != len(rows)):
        raise SafetyStop("Invalid application recommendation count")
    for row in rows:
        service = allowed.get(row.get("id"))
        if (service is None or Decimal(row["price"]) != service.price or service.price > Decimal(INPUT["budget"])
                or service.care_group != INPUT["needs"] or not service.is_active
                or not 60 <= service.duration_minutes <= 90 or not row.get("reason")):
            raise SafetyStop("Recommendation violates synthetic policy")
    record = AIRecommendation.objects.get(customer=fixture.customer)
    saved = json.loads(record.reason)
    if saved != {"mode": "ai", "items": rows} or record.recommended_services != [r["id"] for r in rows]:
        raise SafetyStop("Recommendation persistence mismatch")
    restored = client.get(f"{READ_URL}{record.pk}/")
    if restored.status_code != 200 or restored.json() != saved:
        raise SafetyStop("Acceptance GET readback mismatch")
    client.force_login(fixture.other)
    if client.get(f"{READ_URL}{record.pk}/").status_code != 404:
        raise SafetyStop("Acceptance readback ownership failed")
    if budget.wire_requests != 1 or AIRecommendation.objects.count() != 1:
        raise SafetyStop("Readback changed state or invoked provider")
    return {"status": "PASS", "scope": "authenticated Django POST + SQLite persistence + acceptance-only GET",
            "production_get_supported": False, "production_get_status": production_get,
            "acceptance_get_only": True, "synthetic_only": True, "http_requests": 1,
            "response_mode": "ai", "policy_validated": True, "persisted": True, "readback_verified": True,
            "ownership_verified": True, "selected_services": len(rows)}


def configure_application(folder):
    import django
    from django.conf import settings
    from tools.gemini_live import SafetyStop
    if settings.configured:
        raise SafetyStop("A fresh acceptance process is required")
    settings.configure(SECRET_KEY=token_urlsafe(48), DEBUG=False, ALLOWED_HOSTS=["testserver"],
        USE_TZ=True, TIME_ZONE="Asia/Ho_Chi_Minh", AUTH_USER_MODEL="accounts.User",
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": str(folder / "acceptance.sqlite3")}},
        INSTALLED_APPS=["django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions"] +
            "accounts services products employees appointments promotions billing reviews ai_features".split(),
        MIDDLEWARE=["django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.csrf.CsrfViewMiddleware",
                    "django.contrib.auth.middleware.AuthenticationMiddleware"],
        PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
        SESSION_COOKIE_NAME="fr22_acceptance_session", CSRF_COOKIE_NAME="fr22_acceptance_csrf",
        MEDIA_ROOT=str(folder / "media"), AI_PROVIDER="gemini", AI_PAID_CALLS_APPROVED=False,
        AI_PERSONALIZATION_EXPORT_APPROVED=False, AI_REVIEW_EXPORT_APPROVED=False,
        AI_GEMINI_REQUESTS_APPROVED=False, AI_GEMINI_FREE_TIER_CONFIRMED=False,
        AI_GEMINI_FREE_TIER_ONLY=True, AI_GEMINI_MODEL="gemini-3.5-flash-lite",
        AI_GEMINI_EMBEDDING_MODEL="gemini-embedding-001", AI_RAG_ENABLED=False, AI_CHAT_ENABLED=False)
    django.setup()
    urls = ModuleType("fr22_acceptance_urls")
    urls.urlpatterns = acceptance_urls()
    sys.modules[urls.__name__] = urls
    settings.ROOT_URLCONF = urls.__name__


def main(argv=None):
    from tools.openai_test import StagingError, hidden_input, locked_environment
    from tools.gemini_live import Budget, CONFIRMATION
    class SafeParser(argparse.ArgumentParser):
        def error(self, message):
            raise StagingError("Invalid arguments; credentials must never be CLI arguments")
    parser = SafeParser(description=__doc__)
    parser.add_argument("mode", choices=["live"])
    parser.parse_args(argv)
    if Path(sys.prefix).resolve() != (ROOT / ".venv").resolve() or not sys.stdin.isatty():
        raise StagingError("Use project .venv in an interactive terminal")
    print("FR-22 application acceptance: synthetic SQLite; at most ONE Gemini POST; no retry.")
    print("Verify this key's AI Studio project is Free Tier, billing disabled and quota available.")
    print("This launcher cannot inspect Google's billing state or guarantee zero cost.")
    if input("Type " + CONFIRMATION + ": ").strip() != CONFIRMATION:
        raise StagingError("Free Tier was not confirmed")
    values = locked_environment(os.environ.get("COMPUTERNAME", ""), os.environ.get("SystemRoot", r"C:\Windows"))
    os.environ.clear()
    os.environ.update(values)
    budget = Budget(1, generation_only=True)
    with TemporaryDirectory(prefix="annhien-fr22-app-") as folder:
        configure_application(Path(folder))
        from django.core.management import call_command
        from django.db import connections
        from django.test import override_settings
        from billing import gateway
        from contextlib import ExitStack
        key = None
        try:
            with guarded_application(budget), ExitStack() as stack:
                for name in ("client", "create", "get", "cancel", "verify"):
                    stack.enter_context(patch.object(gateway, name, side_effect=StagingError("PayOS forbidden")))
                call_command("migrate", interactive=False, verbosity=0)
                fixture = seed_synthetic()
                key = hidden_input("Gemini API key (hidden; synthetic FR22 only): ")
                with override_settings(AI_GEMINI_API_KEY=key, AI_PERSONALIZATION_EXPORT_APPROVED=True,
                        AI_GEMINI_REQUESTS_APPROVED=True, AI_GEMINI_FREE_TIER_CONFIRMED=True):
                    report = application_check(fixture, budget)
        except Exception:
            report = {"status": "FAIL", "code": "APPLICATION_ACCEPTANCE_FAILED", "http_requests": budget.wire_requests,
                      "fallback_is_not_pass": True, "production_get_supported": False}
        finally:
            key = None
            connections.close_all()
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Exception, KeyboardInterrupt):
        print('Stopped safely; no retry. No exception payload is displayed.')
        raise SystemExit(1)
