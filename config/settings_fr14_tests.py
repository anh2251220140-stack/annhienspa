"""Disposable MySQL regression settings; require the guarded launcher."""

from .fr14_test_guard import active_guard as _active_guard

_guard = _active_guard()

from .settings import *  # noqa: F403,E402

# Never inherit a MySQL setting, alias, or credential from the application .env.
DATABASES = {"default": _guard.database_settings()}
DATABASE_ROUTERS = []
PAYOS_CLIENT_ID = PAYOS_API_KEY = PAYOS_CHECKSUM_KEY = ""
SECRET_KEY = "fr14-tests-local-only-not-a-production-key"
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
DEBUG = False
del _guard
