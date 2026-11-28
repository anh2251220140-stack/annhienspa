import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() == "true"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("Set DJANGO_SECRET_KEY in the environment.")
    from django.core.management.utils import get_random_secret_key
    SECRET_KEY = get_random_secret_key()
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]").split(",")
# Explicit HTTPS origins for deployments behind a reverse proxy; token checks remain enabled.
CSRF_TRUSTED_ORIGINS = [
    origin.strip() for origin in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]
INSTALLED_APPS = [
    "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions",
    "django.contrib.messages", "django.contrib.staticfiles",
] + "accounts services products employees appointments promotions billing reviews dashboard ai_features core".split()
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True,
    "OPTIONS": {"context_processors": ["django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages", "accounts.context_processors.auth_ui"]}}]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
DATABASES = {"default": {
    "ENGINE": "django.db.backends.mysql",
    "NAME": os.getenv("MYSQL_DATABASE", "annhien_spa"),
    "USER": os.getenv("MYSQL_USER", ""), "PASSWORD": os.getenv("MYSQL_PASSWORD", ""),
    "HOST": os.getenv("MYSQL_HOST", "127.0.0.1"), "PORT": os.getenv("MYSQL_PORT", "3306"),
    "OPTIONS": {"charset": "utf8mb4", "init_command": "SET sql_mode='STRICT_TRANS_TABLES'", "connect_timeout": 5},
}}
# Docker changes only the transport address. Preserve HOST from the Windows .env
# so the same physical database retains its existing RAG namespace.
docker_mysql_host = os.getenv("DOCKER_MYSQL_CONNECT_HOST")
if docker_mysql_host:
    DATABASES["default"]["OPTIONS"]["host"] = docker_mysql_host
AUTH_PASSWORD_VALIDATORS = [{"NAME": "django.contrib.auth.password_validation." + name} for name in [
    "UserAttributeSimilarityValidator", "MinimumLengthValidator", "CommonPasswordValidator", "NumericPasswordValidator"]]
LANGUAGE_CODE = "vi"
TIME_ZONE = "Asia/Ho_Chi_Minh"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
# Preserved asset copies; the original frontend remains independently usable.
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
# Explicitly opt in on the local development machine only.
LOCAL_MEDIA_ENABLED = os.getenv("DJANGO_LOCAL_MEDIA_ENABLED", "false").lower() == "true"
# Opt-in Docker route; direct Windows/local media behavior remains unchanged.
DOCKER_MEDIA_ENABLED = os.getenv("DJANGO_DOCKER_MEDIA_ENABLED", "false").lower() == "true"
# Vercel alone uses the connected PRIVATE Blob store. Windows/Docker keep their
# existing filesystem storage, even if a Blob token is present locally.
BLOB_MEDIA_ENABLED = (
    os.getenv("VERCEL") == "1"
    and os.getenv("DJANGO_BLOB_MEDIA_ENABLED", "true").lower() == "true"
)
if BLOB_MEDIA_ENABLED:
    STORAGES = {
        "default": {"BACKEND": "config.blob_media.PrivateBlobStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
    MIDDLEWARE += ["config.blob_media.BlobFailureMiddleware"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
X_FRAME_OPTIONS = "DENY"


AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["accounts.backends.IdentifierBackend"]
LOGIN_URL = "/login.html"
LOGIN_REDIRECT_URL = "/home.html"
LOGOUT_REDIRECT_URL = "/index.html"

SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

# Password reset mail. Configure credentials locally; never commit .env.
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "true").lower() == "true"
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "false").lower() == "true"
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "An Nhien Spa <noreply@example.com>")
PASSWORD_RESET_TIMEOUT = int(os.getenv("PASSWORD_RESET_TIMEOUT", "3600"))

PAYOS_CLIENT_ID = os.getenv("PAYOS_CLIENT_ID", "")
PAYOS_API_KEY = os.getenv("PAYOS_API_KEY", "")
PAYOS_CHECKSUM_KEY = os.getenv("PAYOS_CHECKSUM_KEY", "")
# The public coursework deployment must not issue live payment links.
PAYOS_DEMO_ONLY = (os.getenv("VERCEL") == "1"
                  or os.getenv("PAYOS_DEMO_ONLY", "false").lower() == "true")
PAYOS_RETURN_URL = os.getenv("PAYOS_RETURN_URL", "http://127.0.0.1:8000/invoice.html")
PAYOS_CANCEL_URL = os.getenv("PAYOS_CANCEL_URL", "http://127.0.0.1:8000/invoice.html")

# Chat supports Gemini with explicit approval, and a local mock for testing.
AI_CHAT_ENABLED = os.getenv("AI_CHAT_ENABLED", "false").lower() == "true"
AI_CHAT_DAILY_LIMIT = int(os.getenv("AI_CHAT_DAILY_LIMIT", "30"))
AI_CHAT_COOLDOWN_SECONDS = int(os.getenv("AI_CHAT_COOLDOWN_SECONDS", "5"))
AI_CHAT_SPA_INFORMATION = os.getenv("AI_CHAT_SPA_INFORMATION", "")
