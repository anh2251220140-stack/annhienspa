"""Read-only connection/schema diagnostics without exposing credentials."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.db import connection
from django.conf import settings
if not settings.DATABASES["default"]["USER"] or not settings.DATABASES["default"]["PASSWORD"]:
    print("MYSQL_USER / MYSQL_PASSWORD are not configured. Run tools/setup_mysql.py locally.")
    raise SystemExit(2)
try:
    with connection.cursor() as cursor:
        cursor.execute("SELECT VERSION()")
        print("MySQL version:", cursor.fetchone()[0])
        tables = connection.introspection.table_names()
        print("Schema tables:", len(tables))
        if 'auth_user' in tables:
            print("STOP: legacy auth_user exists. Do not migrate until reviewed.")
            raise SystemExit(3)
        if 'django_migrations' in tables:
            cursor.execute("SELECT app, name FROM django_migrations ORDER BY id")
            print("Applied migrations:", cursor.fetchall())
except Exception as error:
    print("Connection failed:", type(error).__name__, "code", error.args[0] if error.args else "unknown")
    raise SystemExit(1)
