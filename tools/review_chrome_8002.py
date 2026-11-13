"""Standalone loopback acceptance site for FR-14, FR-18 and FR-19."""

import argparse
from contextlib import ExitStack
from datetime import time, timedelta
import json
import os
from pathlib import Path
from secrets import token_urlsafe
import sys
from tempfile import TemporaryDirectory
from threading import Thread
from unittest.mock import patch
from wsgiref.simple_server import WSGIRequestHandler, make_server

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.fr14_tests import block_network

HOST, PORT = "127.0.0.1", 8002
ADMIN, OWNER, OTHER = "review8002_admin", "review8002_user", "review8002_other"


def configure(directory, stack):
    from django.conf import settings
    from django.db.backends.base.base import BaseDatabaseWrapper
    from django.db.backends.mysql.base import Database

    database = str(directory / "reviews.sqlite3")
    connect = BaseDatabaseWrapper.ensure_connection

    def sqlite_only(wrapper):
        if (wrapper.alias, wrapper.vendor, wrapper.settings_dict["NAME"]) != ("default", "sqlite", database):
            raise RuntimeError("8002 requires its dedicated SQLite database.")
        return connect(wrapper)

    # Whitelist environment values so .env and inherited credentials never enter Django settings.
    stack.enter_context(patch.dict(os.environ, {
        "DJANGO_SETTINGS_MODULE": "config.settings", "DJANGO_DEBUG": "true",
        "DJANGO_SECRET_KEY": token_urlsafe(48),
    }, clear=True))
    stack.enter_context(patch("dotenv.load_dotenv", return_value=False))
    stack.enter_context(patch.object(BaseDatabaseWrapper, "ensure_connection", sqlite_only))
    stack.enter_context(patch.object(Database, "connect", side_effect=RuntimeError("MySQL is forbidden on 8002.")))
    stack.enter_context(block_network())

    settings.DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": database}}
    settings.DATABASE_ROUTERS = []
    settings.ALLOWED_HOSTS = [HOST]
    settings.SESSION_COOKIE_NAME = "annhien_review8002_session"
    settings.CSRF_COOKIE_NAME = "annhien_review8002_csrftoken"
    settings.MEDIA_ROOT = directory / "media"
    settings.LOCAL_MEDIA_ENABLED = True
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.PAYOS_CLIENT_ID = settings.PAYOS_API_KEY = settings.PAYOS_CHECKSUM_KEY = ""
    settings.PAYOS_RETURN_URL = settings.PAYOS_CANCEL_URL = f"http://{HOST}:{PORT}/invoice.html"
    settings.STATIC_ROOT = directory / "collected-static"

    import django
    django.setup()
    from billing import gateway
    from django.db import connection

    for name in ("client", "create", "get", "cancel", "verify"):
        stack.enter_context(patch.object(gateway, name, side_effect=RuntimeError("PayOS is forbidden on 8002.")))
    assert not gateway.configured() and connection.vendor == "sqlite"
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA database_list")
        attached = {name: Path(path).resolve() for _, name, path in cursor.fetchall() if name != "temp"}
    assert attached == {"main": Path(database).resolve()}, "Unexpected SQLite file or attached database."
    return database


def seed(passwords, automated):
    from accounts.models import Customer, User
    from appointments.services import book, transition
    from django.db import transaction
    from django.utils import timezone
    from employees.models import Employee, EmployeeSchedule
    from services.models import Service, ServiceCategory

    now = timezone.now()
    past_day = timezone.localdate(now) - timedelta(days=2)
    future_day = timezone.localdate(now) + timedelta(days=2)
    with transaction.atomic():
        admin = User.objects.create_superuser(ADMIN, "admin8002@example.test", passwords["admin"])
        owner = User.objects.create_user(OWNER, "user8002@example.test", passwords["user"])
        Customer.objects.create(user=owner, full_name="Khách nghiệm thu 8002", phone="0000000000")
        if automated:
            other = User.objects.create_user(OTHER, "other8002@example.test", passwords["other"])
            Customer.objects.create(user=other, full_name="Khách kiểm tra quyền 8002", phone="0000000001")
        category = ServiceCategory.objects.create(name="Danh mục thử 8002")
        service = Service.objects.create(category=category, name="Liệu trình nghiệm thu 8002",
                                         description="Dữ liệu thử riêng.", price=300000, duration_minutes=60)
        employee = Employee.objects.create(full_name="Chuyên viên thử 8002", specialty="Liệu trình thử")
        employee.services.add(service)

        def confirmed(day):
            EmployeeSchedule.objects.create(employee=employee, work_date=day, start_time=time(9), end_time=time(17))
            appointment = book(owner, service.pk, employee.pk, day, time(10))
            return transition(admin, appointment.pk, "confirmed")

        with patch("django.utils.timezone.now", return_value=now - timedelta(days=3)):
            appointment = confirmed(past_day)
        if automated:
            confirmed(future_day)
        assert appointment.invoice.payment_status == "unpaid" and appointment.invoice.details.count() == 1
        print(f"Prepared LH-{appointment.pk:06d} ({past_day:%d/%m/%Y} 10:00–11:00), HD-{appointment.invoice.pk} unpaid.", flush=True)


class LocalRequests(WSGIRequestHandler):
    def log_message(self, format, *args):
        # Never put URLs, authentication data or request bodies in the launcher log.
        pass


def serve(directory, passwords, automated):
    from django.contrib.staticfiles.handlers import StaticFilesHandler
    from django.core.management import call_command
    from django.core.wsgi import get_wsgi_application
    from django.db import connections

    with make_server(HOST, PORT, None, handler_class=LocalRequests) as server, ExitStack() as stack:
        already_prepared = (directory / "reviews.sqlite3").is_file()
        database = configure(directory, stack)
        stack.callback(connections.close_all)
        call_command("check")
        if not already_prepared:
            if not passwords:
                raise RuntimeError("Initialize 8002 through start_review_8002.ps1.")
            call_command("migrate", interactive=False, verbosity=0)
            seed(passwords, automated)
        elif passwords:
            raise RuntimeError("The 8002 database already exists. Existing data is preserved.")
        server.set_app(StaticFilesHandler(get_wsgi_application()))
        if automated:
            def stop_at_end_of_input():
                sys.stdin.read()
                server.shutdown()

            Thread(target=stop_at_end_of_input, daemon=True).start()
        print(f"Ready http://{HOST}:{PORT} | SQLite: {database} | MySQL/PayOS blocked | real clock", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("serve", "initialize", "automated"))
    mode = parser.parse_args().mode
    passwords = json.loads(sys.stdin.readline()) if mode == "automated" else (
        json.load(sys.stdin) if mode == "initialize" else None
    )
    if mode == "automated":
        with TemporaryDirectory(prefix="annhien-8002-browser-") as directory:
            serve(Path(directory), passwords, automated=True)
    else:
        directory = ROOT / ".tmp-review-8002"
        if directory.resolve() != directory:
            raise RuntimeError("The local 8002 directory must not be a link.")
        if mode == "serve" and not (directory / "reviews.sqlite3").is_file():
            raise RuntimeError("Initialize 8002 through start_review_8002.ps1.")
        directory.mkdir(exist_ok=True)
        if (directory / "reviews.sqlite3").resolve() != directory / "reviews.sqlite3":
            raise RuntimeError("The local 8002 database must not be a link.")
        serve(directory, passwords, automated=False)


if __name__ == "__main__":
    main()
