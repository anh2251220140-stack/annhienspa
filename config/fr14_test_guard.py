"""Connection safeguards used only by the disposable MySQL regression runner."""

from contextlib import contextmanager, suppress
from contextvars import ContextVar
from dataclasses import dataclass, field
import os
import re
from typing import ClassVar
from unittest.mock import patch
from uuid import UUID

from django.core.exceptions import ImproperlyConfigured


DATABASE = "annhien_spa_fr14_tests"
USER = "annhien_fr14_tests"
HOST = "127.0.0.1"
TEST_PORT = 3311
PRODUCTION_UUID = "7db82c55-cb03-11f1-b4b7-ea7eb5144315"
RESTORE_UUID = "7408c069-e00d-11f1-930d-523b3040afb1"
APPROVAL_ENV = "ANNHIEN_FR14_TEST_APPROVAL"
APPROVAL_PHRASE = f"ALLOW {HOST}:{TEST_PORT} {DATABASE}"
ACCOUNT_HOST = HOST
ACCOUNT = f"{USER}@{ACCOUNT_HOST}"
ENGINE = "django.db.backends.mysql"
SETTINGS = "config.settings_fr14_tests"
OPTIONS = {"charset": "utf8mb4", "connect_timeout": 5}
PRIVILEGES = frozenset(
    "SELECT INSERT UPDATE DELETE CREATE ALTER INDEX DROP REFERENCES TRIGGER".split()
)


class GuardError(ImproperlyConfigured):
    """Fixed, non-secret diagnostic from a guard check."""


def reject(reason):
    raise GuardError(reason)


def uuid_text(value):
    try:
        parsed = UUID(value)
    except (ValueError, TypeError, AttributeError):
        reject("Missing or invalid instance UUID.")
    if not parsed.int or str(parsed) != value.lower():
        reject("Expected a nonzero UUID in standard hyphenated form.")
    return str(parsed)


@dataclass(frozen=True)
class Target:
    port: int
    hostname: str
    server_uuid: str
    main_uuid: str
    approved: bool = False

    def __post_init__(self):
        self.validate()

    def validate(self):
        # Reject before the driver is called, including a formerly valid target
        # reused by a caller. No production/restore port is ever a fallback.
        if type(self.port) is not int or self.port != TEST_PORT:
            reject("Only the approved test port 3311 is allowed; ports 3306 and 3310 are forbidden.")
        if self.approved is not True:
            reject("Explicit approval for the dedicated 127.0.0.1:3311 test instance is required.")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]{0,254}", self.hostname):
            reject("Set the MySQL test hostname obtained during provisioning.")
        if uuid_text(self.server_uuid) in {PRODUCTION_UUID, RESTORE_UUID, uuid_text(self.main_uuid)}:
            reject("Production and restore UUIDs are forbidden for the test instance.")

    @classmethod
    def from_environment(cls):
        port = os.environ.get("ANNHIEN_FR14_TEST_PORT", "")
        if not re.fullmatch(r"[0-9]{1,5}", port):
            reject("Set ANNHIEN_FR14_TEST_PORT explicitly.")
        return cls(
            int(port),
            os.environ.get("ANNHIEN_FR14_TEST_HOSTNAME", ""),
            os.environ.get("ANNHIEN_FR14_TEST_SERVER_UUID", ""),
            os.environ.get("ANNHIEN_FR14_MAIN_SERVER_UUID", ""),
            approved=os.environ.get(APPROVAL_ENV) == APPROVAL_PHRASE,
        )


def check_grants(rows, partial_revokes, *, database=DATABASE, user=USER, required=PRIVILEGES):
    # With partial_revokes=OFF, a bare underscore is a GRANT wildcard.
    scope = database if partial_revokes else database.replace("_", r"\_")
    account = rf"[`']{re.escape(user)}[`']@[`']{re.escape(ACCOUNT_HOST)}[`']"
    allowed_scope = f"`{scope}`.*"
    saw_usage = False
    privileges = set()
    for (grant,) in rows:
        match = re.fullmatch(rf"GRANT ([A-Z, ]+) ON (.+) TO {account}", grant)
        if not match:
            reject("Unexpected grant, role, proxy, or GRANT OPTION.")
        granted, granted_scope = match.groups()
        if granted == "USAGE" and granted_scope == "*.*":
            saw_usage = True
        elif granted_scope == allowed_scope:
            items = set(granted.split(", "))
            if not items <= required:
                reject("Unexpected privileges on the test schema.")
            privileges.update(items)
        else:
            reject("A grant extends beyond the literal test schema.")
    if not saw_usage or privileges != required:
        reject("The account lacks the expected schema-only grants.")


@dataclass(frozen=True)
class Guard:
    database: ClassVar[str] = DATABASE
    user: ClassVar[str] = USER
    privileges: ClassVar[frozenset[str]] = PRIVILEGES
    target: Target | None
    password: str = field(default="", repr=False)

    def database_settings(self):
        if self.target:
            self.target.validate()
        return {
            "ENGINE": ENGINE, "NAME": self.database, "USER": self.user,
            "PASSWORD": self.password, "HOST": HOST,
            "PORT": str(self.target.port) if self.target else "",
            "OPTIONS": OPTIONS.copy(), "CONN_MAX_AGE": 0,
            "TEST": {"NAME": self.database},
        }

    def check_settings(self, alias, values):
        expected = self.database_settings()
        test = values.get("TEST", {})
        if (alias != "default" or
                any(values.get(k) != v for k, v in expected.items() if k != "TEST") or
                test.get("NAME") != self.database or test.get("MIRROR") is not None):
            reject("Blocked unapproved database alias, settings, or OPTIONS.")

    def check_params(self, params):
        from django.db.backends.mysql.base import CLIENT, django_conversions

        if not self.target or not self.password:
            reject("Database access is disabled.")
        self.target.validate()
        expected = dict(host=HOST, port=self.target.port, database=self.database, user=self.user,
                        password=self.password, client_flag=CLIENT.FOUND_ROWS, **OPTIONS)
        if (params.get("conv") is not django_conversions or
                {k: v for k, v in params.items() if k != "conv"} != expected):
            reject("Blocked unexpected final mysqlclient connection parameters.")

    def verify_session(self, raw):
        if not self.target:
            reject("Database access is disabled.")
        self.target.validate()
        with raw.cursor() as cursor:
            cursor.execute(
                "SELECT DATABASE(), CURRENT_USER(), @@hostname, @@port, @@server_uuid, "
                "VERSION(), @@version_comment, @@default_storage_engine, "
                "CURRENT_ROLE(), @@GLOBAL.mandatory_roles, "
                "CAST(@@GLOBAL.partial_revokes AS UNSIGNED)"
            )
            (schema, account, hostname, port, server_uuid, version, version_comment,
             engine, role, mandatory_roles, partial_revokes) = cursor.fetchone()
            if (schema != self.database or account != f"{self.user}@{ACCOUNT_HOST}" or
                    hostname.casefold() != self.target.hostname.casefold() or
                    port != self.target.port or
                    uuid_text(server_uuid) != uuid_text(self.target.server_uuid) or
                    uuid_text(server_uuid) == uuid_text(self.target.main_uuid)):
                reject("Server identity mismatch (schema, account, hostname, port, or UUID).")
            release = re.match(r"^(\d+)\.(\d+)\.(\d+)", version)
            if (not release or tuple(map(int, release.groups())) < (8, 0, 11) or
                    "mysql" not in version_comment.casefold() or
                    "mariadb" in version.casefold() or engine.upper() != "INNODB"):
                reject("Expected supported MySQL with default InnoDB.")
            if role != "NONE" or mandatory_roles or partial_revokes not in (0, 1):
                reject("Unexpected roles or unresolved GRANT wildcard policy.")
            cursor.execute("SHOW GRANTS")
            check_grants(cursor.fetchall(), partial_revokes, database=self.database,
                         user=self.user, required=self.privileges)
        return release.group()

    def recheck(self, connection):
        self.check_settings(connection.alias, connection.settings_dict)
        connection.ensure_connection()
        try:
            return self.verify_session(connection.connection)
        except BaseException:
            connection.close()
            raise


_active_guard = None
_driver_permit = ContextVar("fr14_mysql_driver_permit", default=False)


def active_guard():
    if _active_guard is None:
        reject("Use tools/fr14_tests.py; direct Django commands are forbidden.")
    return _active_guard


def require_isolated_database():
    """Used before test fixtures are created; also checks the live session."""
    from django.conf import settings
    from django.db import connections

    guard = active_guard()
    # Django's UserSettingsHolder reports None for SETTINGS_MODULE during
    # override_settings. The runner still pins the module in the environment.
    if (os.environ.get("DJANGO_SETTINGS_MODULE") != SETTINGS or
            settings.SETTINGS_MODULE not in {SETTINGS, None} or
            set(settings.DATABASES) != {"default"} or set(connections) != {"default"}):
        reject("Use the guarded isolated FR-14 runner.")
    guard.check_settings("default", settings.DATABASES["default"])
    guard.recheck(connections["default"])


@contextmanager
def offline_database():
    from django.db.backends.base.base import BaseDatabaseWrapper
    from django.db.backends.mysql.base import DatabaseWrapper

    with (patch.object(BaseDatabaseWrapper, "ensure_connection",
                       side_effect=GuardError("Database access forbidden during discovery.")),
          patch.object(DatabaseWrapper, "get_new_connection",
                       side_effect=GuardError("Database access forbidden during discovery."))):
        yield


@contextmanager
def install_guard(guard):
    """Keep the same checks active across all Django wrappers and worker threads."""
    from django.db.backends.mysql.base import Database, DatabaseWrapper
    from django.db.utils import ConnectionHandler

    global _active_guard
    if _active_guard is not None:
        reject("Database guard is already installed.")

    create_wrapper = ConnectionHandler.create_connection
    get_params = DatabaseWrapper.get_connection_params
    open_wrapper = DatabaseWrapper.get_new_connection
    open_driver = Database.connect

    def checked_wrapper(handler, alias):
        if set(handler.settings) != {"default"} or alias != "default":
            reject("Blocked unexpected database alias.")
        guard.check_settings(alias, handler.settings[alias])
        return create_wrapper(handler, alias)

    def checked_params(wrapper):
        guard.check_settings(wrapper.alias, wrapper.settings_dict)
        params = get_params(wrapper)
        guard.check_params(params)
        return params

    def checked_open(wrapper, params):
        guard.check_settings(wrapper.alias, wrapper.settings_dict)
        guard.check_params(params)
        token = _driver_permit.set(True)
        try:
            return open_wrapper(wrapper, params)
        finally:
            _driver_permit.reset(token)

    def checked_driver(*args, **params):
        if args or not _driver_permit.get():
            reject("Blocked direct mysqlclient connection.")
        guard.check_params(params)
        raw = open_driver(**params)
        # Verify before Django can initialize the session or run any ORM query.
        try:
            guard.verify_session(raw)
        except BaseException:
            with suppress(Exception):
                raw.close()
            raise
        return raw

    _active_guard = guard
    try:
        with (patch.object(ConnectionHandler, "create_connection", checked_wrapper),
              patch.object(DatabaseWrapper, "get_connection_params", checked_params),
              patch.object(DatabaseWrapper, "get_new_connection", checked_open),
              patch.object(Database, "connect", checked_driver),
              patch.object(Database, "Connect", checked_driver),
              patch.object(Database, "Connection", checked_driver)):
            yield
    finally:
        _active_guard = None
