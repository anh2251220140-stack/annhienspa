"""Run the local Chrome test site against its dedicated MySQL schema."""

import argparse
import os
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.fr14_test_guard import Guard, PRIVILEGES, Target, install_guard, offline_database
from tools.fr14_tests import block_network, preflight, require_empty_fixture_tables


class ChromeGuard(Guard):
    database = "annhien_spa_chrome_tests"
    user = "annhien_chrome"
    privileges = frozenset({"SELECT", "INSERT", "UPDATE", "DELETE"})


class ChromeMigrationGuard(ChromeGuard):
    user = "annhien_chrome_migrate"
    privileges = PRIVILEGES


def check_migrations(connection):
    from django.db.migrations.executor import MigrationExecutor

    executor = MigrationExecutor(connection)
    executor.loader.check_consistent_history(connection)
    if executor.migration_plan(executor.loader.graph.leaf_nodes()):
        raise RuntimeError("The Chrome schema has pending migrations.")
    print(f"Chrome migrations applied: {len(executor.loader.applied_migrations)}.")


def smoke_check():
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.test import Client
    from core.pages import PAGES
    from core.views import PUBLIC_PAGES

    def expect(client, url, code):
        actual = client.get(url).status_code
        if actual != code:
            raise RuntimeError(f"{url}: expected HTTP {code}, got {actual}.")

    users = get_user_model().objects
    admin_password = os.environ.pop("ANNHIEN_CHROME_ADMIN_PASSWORD", "")
    if not admin_password:
        raise RuntimeError("The smoke check requires the local Admin test credential.")
    with transaction.atomic():
        user = users.create_user("chrome_route_smoke", "chrome-route-smoke@example.test")
        from accounts.models import Customer

        Customer.objects.create(user=user, full_name="Khách kiểm thử", phone="0900000000")
        user_client = Client(HTTP_HOST="127.0.0.1")
        admin_client = Client(HTTP_HOST="127.0.0.1")
        guest = Client(HTTP_HOST="127.0.0.1")
        user_client.force_login(user)
        login = admin_client.post("/login.html", {"identifier": "chrome_admin", "password": admin_password})
        if login.status_code != 302 or login.headers.get("Location") != "/admin-dashboard.html":
            raise RuntimeError("Chrome Admin login failed.")
        expect(guest, "/login.html", 200)
        expect(guest, "/register.html", 200)
        for page in PUBLIC_PAGES:
            if page not in {"service-detail.html", "promotion-detail.html"}:
                expect(guest, f"/{page}", 200)
        for page in PAGES:
            if page in PUBLIC_PAGES or page in {"login.html", "register.html"}:
                continue
            url = f"/{page}"
            admin_only = page.startswith("admin-")
            expect(admin_client if admin_only else user_client, url, 200)
            expect(user_client if admin_only else admin_client, url, 403)
            expect(guest, url, 302)
        transaction.set_rollback(True)
    print("Admin/User page access, role denials and guest redirects passed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("serve", "prepare", "check"))
    args = parser.parse_args()
    import django
    from django.core.management import call_command
    from django.db import connections

    password = os.environ.pop("ANNHIEN_CHROME_DB_PASSWORD", "")
    if not password:
        raise SystemExit("Use the local PowerShell Chrome launcher.")
    target = Target(3307, os.environ["COMPUTERNAME"],
                    "47c73b62-df2c-11f1-b343-df6f8d76a6e0",
                    "7db82c55-cb03-11f1-b4b7-ea7eb5144315")
    guard = (ChromeMigrationGuard if args.action == "prepare" else ChromeGuard)(target, password)
    del password
    os.environ.update(DJANGO_SETTINGS_MODULE="config.settings_chrome_test",
                      DJANGO_DEBUG="true", DJANGO_SECRET_KEY="chrome-local-settings-bootstrap")
    with install_guard(guard), block_network():
        try:
            with patch("dotenv.load_dotenv", return_value=False), offline_database():
                django.setup()
            conn = connections["default"]
            tables = preflight(conn)
            if args.action == "prepare":
                if tables:
                    raise RuntimeError("Chrome initialization requires an empty schema.")
                require_empty_fixture_tables(conn, tables)
                call_command("migrate", database="default", interactive=False)
                check_migrations(conn)
                from django.contrib.auth import get_user_model

                admin_password = os.environ.pop("ANNHIEN_CHROME_ADMIN_PASSWORD")
                get_user_model().objects.create_superuser(
                    "chrome_admin", "chrome-admin@example.test", admin_password
                )
                print("Created the Chrome Admin account.")
            else:
                check_migrations(conn)
                call_command("check")
                if args.action == "check":
                    smoke_check()
                else:
                    call_command("runserver", "127.0.0.1:8001", use_reloader=False)
        finally:
            connections.close_all()


if __name__ == "__main__":
    main()
