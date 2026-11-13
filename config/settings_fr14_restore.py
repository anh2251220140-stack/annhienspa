"""Isolated FR-14 migration settings; use tools/fr14_restore.py, never tests."""
import os
from django.core.exceptions import ImproperlyConfigured

# Check BEFORE importing the normal settings (which load the main .env).
_password = os.environ.get("ANNHIEN_FR14_RESTORE_PASSWORD", "")
if not _password:
    raise ImproperlyConfigured("Use the FR-14 restore launcher and enter a password locally.")

from .settings import *  # noqa: F403,E402

DATABASES = {"default": {
    "ENGINE": "django.db.backends.mysql",
    "NAME": "annhien_spa_restore_fr14_20261106",
    "USER": "annhien_fr14_restore",
    "PASSWORD": _password,
    "HOST": "127.0.0.1",
    "PORT": "3306",
    "OPTIONS": {"charset": "utf8mb4", "connect_timeout": 5},
    "CONN_MAX_AGE": 0,
}}
del _password

from django.db.backends.signals import connection_created


def verify_restore_connection(sender, connection, **kwargs):
    """Every newly opened connection must match the intended server identity."""
    expected = {
        "ENGINE": "django.db.backends.mysql",
        "NAME": "annhien_spa_restore_fr14_20261106",
        "USER": "annhien_fr14_restore", "HOST": "127.0.0.1", "PORT": "3306",
    }
    if connection.alias != "default" or any(connection.settings_dict.get(k) != v for k, v in expected.items()):
        connection.close()
        raise ImproperlyConfigured("Restore connection configuration mismatch; stopped.")
    with connection.cursor() as cursor:
        cursor.execute("SELECT DATABASE(), CURRENT_USER()")
        database, account = cursor.fetchone()
    if database != expected["NAME"] or account != "annhien_fr14_restore@localhost":
        connection.close()
        raise ImproperlyConfigured("Restore server identity mismatch; stopped.")


connection_created.connect(verify_restore_connection, weak=False, dispatch_uid="fr14_restore_identity")
