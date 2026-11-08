"""Disposable FR-14 database only. Launch through tools/fr14_tests.py."""
import os
from django.core.exceptions import ImproperlyConfigured

_password = os.environ.get("ANNHIEN_FR14_TEST_PASSWORD", "")
if not _password:
    raise ImproperlyConfigured("Enter the test password using tools/fr14_tests.py.")

from .settings import *  # noqa: F403,E402

DATABASES = {"default": {
    "ENGINE": "django.db.backends.mysql",
    "NAME": "annhien_spa_fr14_tests",
    "USER": "annhien_fr14_tests", "PASSWORD": _password,
    "HOST": "127.0.0.1", "PORT": "3306",
    "OPTIONS": {"charset": "utf8mb4", "connect_timeout": 5},
    "CONN_MAX_AGE": 0,
    "TEST": {"NAME": "annhien_spa_fr14_tests"},
}}
del _password
PAYOS_CLIENT_ID = PAYOS_API_KEY = PAYOS_CHECKSUM_KEY = ""
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
DEBUG = False

# Guard BEFORE opening a socket, including connections in test worker threads.
from django.db.backends.mysql.base import DatabaseWrapper
from django.db.backends.signals import connection_created

_original_params = DatabaseWrapper.get_connection_params


def checked_params(self):
    expected = {"NAME": "annhien_spa_fr14_tests", "USER": "annhien_fr14_tests",
                "HOST": "127.0.0.1", "PORT": "3306"}
    if (self.alias != "default" or
            any(self.settings_dict.get(k) != v for k, v in expected.items()) or
            self.settings_dict.get("TEST", {}).get("NAME") != expected["NAME"]):
        raise ImproperlyConfigured("Blocked connection outside FR-14 test database.")
    return _original_params(self)


DatabaseWrapper.get_connection_params = checked_params


def verify_identity(sender, connection, **kwargs):
    checked_params(connection)
    with connection.cursor() as cursor:
        cursor.execute("SELECT DATABASE(), CURRENT_USER()")
        identity = cursor.fetchone()
    if identity != ("annhien_spa_fr14_tests", "annhien_fr14_tests@localhost"):
        connection.close()
        raise ImproperlyConfigured("FR-14 test server identity mismatch.")


connection_created.connect(verify_identity, weak=False, dispatch_uid="fr14_tests_identity")
