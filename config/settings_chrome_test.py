"""Local Chrome integration site. Launch through tools/chrome_test.py."""

import os
from pathlib import Path
from secrets import token_urlsafe

from .fr14_test_guard import active_guard

_guard = active_guard()
if _guard.database != "annhien_spa_chrome_tests":
    raise RuntimeError("Chrome settings require the dedicated Chrome database guard.")

from .settings import *  # noqa: E402,F403

DATABASES = {"default": _guard.database_settings()}
DATABASE_ROUTERS = []
SECRET_KEY = token_urlsafe(64)
DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = False
SESSION_COOKIE_NAME = "annhien_chrome_session"
CSRF_COOKIE_NAME = "annhien_chrome_csrftoken"
MEDIA_ROOT = Path(os.environ["ANNHIEN_CHROME_MEDIA_ROOT"])
LOCAL_MEDIA_ENABLED = True
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
PAYOS_CLIENT_ID = PAYOS_API_KEY = PAYOS_CHECKSUM_KEY = ""
PAYOS_RETURN_URL = PAYOS_CANCEL_URL = "http://127.0.0.1:8001/invoice.html"
del _guard
