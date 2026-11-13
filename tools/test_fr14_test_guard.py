"""Offline guard checks. Run with python -B -m unittest tools.test_fr14_test_guard."""

from contextlib import contextmanager
from unittest import TestCase
from unittest.mock import MagicMock, patch

from django.db.backends.mysql.base import CLIENT, Database, DatabaseWrapper, django_conversions
from django.db.utils import ConnectionHandler
from django.test import override_settings

from config.fr14_test_guard import (
    ACCOUNT, DATABASE, OPTIONS, PRIVILEGES, USER, Guard, GuardError, Target,
    install_guard, require_isolated_database,
)
from tools.fr14_tests import django_context


TARGET = Target(3307, "test-host", "47c73b62-df2c-11f1-b343-df6f8d76a6e0",
                "7db82c55-cb03-11f1-b4b7-ea7eb5144315")
GUARD = Guard(TARGET, "fake-password")


@contextmanager
def fake_connection():
    raw = MagicMock()
    cursor = raw.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (
        DATABASE, ACCOUNT, TARGET.hostname, TARGET.port, TARGET.server_uuid, "8.4.11",
        "MySQL Community Server", "InnoDB", "NONE", "", 1,
    )
    cursor.fetchall.return_value = [
        (f"GRANT USAGE ON *.* TO `{USER}`@`localhost`",),
        (f"GRANT {', '.join(sorted(PRIVILEGES))} ON `{DATABASE}`.* TO `{USER}`@`localhost`",),
    ]
    with (patch.object(Database, "connect", return_value=raw) as driver,
          patch.object(DatabaseWrapper, "init_connection_state")):
        yield driver, raw, cursor


class GuardTests(TestCase):
    def test_media_override_preserves_live_verification(self):
        from django.conf import settings

        with fake_connection() as (driver, raw, cursor), django_context(GUARD) as connections:
            with override_settings(MEDIA_ROOT="test-media"):
                self.assertIsNone(settings.SETTINGS_MODULE)
                require_isolated_database()
                self.assertIs(connections["default"].connection, raw)
                self.assertEqual(driver.call_args.kwargs["port"], 3307)
                self.assertEqual(cursor.execute.call_args_list.count((("SHOW GRANTS",), {})), 2)

    def test_override_of_schema_host_port_or_user_stops_before_connect(self):
        cases = ({"NAME": "annhien_spa"}, {"PORT": "3306"}, {"HOST": "192.0.2.1"}, {"USER": "root"})
        with fake_connection() as (driver, _, _), django_context(GUARD):
            for values in cases:
                with self.subTest(values=values), override_settings(
                    DATABASES={"default": GUARD.database_settings() | values}
                ), self.assertRaises(GuardError):
                    require_isolated_database()
            driver.assert_not_called()

    def test_invalid_driver_parameters_are_rejected_before_opening_socket(self):
        params = dict(host="127.0.0.1", port=3306, database=DATABASE, user=USER,
                      password=GUARD.password, client_flag=CLIENT.FOUND_ROWS,
                      conv=django_conversions, **OPTIONS)
        with fake_connection() as (driver, _, _), install_guard(GUARD):
            wrapper = ConnectionHandler({"default": GUARD.database_settings()})["default"]
            with self.assertRaises(GuardError):
                wrapper.get_new_connection(params)
            with self.assertRaises(GuardError):
                Database.connect(**params)
            driver.assert_not_called()

    def test_wrong_server_uuid_or_grants_closes_connection_before_django_uses_it(self):
        for field in ("uuid", "grants"):
            with self.subTest(field=field), fake_connection() as (_, raw, cursor), install_guard(GUARD):
                if field == "uuid":
                    row = list(cursor.fetchone.return_value)
                    row[4] = TARGET.main_uuid
                    cursor.fetchone.return_value = tuple(row)
                else:
                    cursor.fetchall.return_value.append((f"GRANT SELECT ON *.* TO `{USER}`@`localhost`",))
                wrapper = ConnectionHandler({"default": GUARD.database_settings()})["default"]
                with self.assertRaises(GuardError):
                    wrapper.ensure_connection()
                raw.close.assert_called_once()
                self.assertIsNone(wrapper.connection)

    def test_fixture_guard_requires_an_active_guard(self):
        with self.assertRaises(GuardError):
            require_isolated_database()
