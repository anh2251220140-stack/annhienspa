"""Run locally in an interactive terminal; credentials never appear in argv/logs."""
import getpass
import secrets
from pathlib import Path
import MySQLdb

ROOT = Path(__file__).resolve().parents[1]
DB = 'annhien_spa'
APP_USER = 'annhien_django'

def main():
    env_path = ROOT / '.env'
    if env_path.exists():
        print('A .env already exists. It was not changed. Configure/reuse it manually; see docs/phase2.md.')
        return
    admin = input('MySQL administrator username [root]: ').strip() or 'root'
    password = getpass.getpass('MySQL administrator password (hidden): ')
    connection = MySQLdb.connect(host='127.0.0.1', port=3306, user=admin, passwd=password, charset='utf8mb4')
    del password
    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s', (DB,))
        if cursor.fetchone()[0]:
            raise RuntimeError('Database already exists. No changes made; inspect before reusing.')
        cursor.execute('SELECT COUNT(*) FROM mysql.user WHERE User=%s', (APP_USER,))
        if cursor.fetchone()[0]:
            raise RuntimeError('Application account already exists. No changes made; do not reset its password.')
        app_password = secrets.token_urlsafe(36)
        # Persist privately before DDL (MySQL DDL cannot roll back). Never overwrite .env.
        content = ('DJANGO_DEBUG=true\nDJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,[::1]\n'
                   f'DJANGO_SECRET_KEY={secrets.token_urlsafe(48)}\nMYSQL_DATABASE={DB}\n'
                   f'MYSQL_USER={APP_USER}\nMYSQL_PASSWORD={app_password}\n'
                   'MYSQL_HOST=127.0.0.1\nMYSQL_PORT=3306\n')
        with env_path.open('x', encoding='utf-8') as stream:
            stream.write(content)
        cursor.execute('CREATE DATABASE `annhien_spa` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
        cursor.execute("CREATE USER %s@'127.0.0.1' IDENTIFIED BY %s", (APP_USER, app_password))
        cursor.execute("GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES, DROP ON `annhien_spa`.* TO %s@'127.0.0.1'", (APP_USER,))
        # A separate, disposable schema only for Django's test runner.
        cursor.execute("GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES, DROP ON `test_annhien_spa`.* TO %s@'127.0.0.1'", (APP_USER,))
    connection.close()
    print('Created database/account and .env. Password was generated and saved locally, not printed.')
    print('Privileges cover only annhien_spa and test_annhien_spa; no global privileges or GRANT OPTION.')

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Do not print connector arguments or SQL that might contain credentials.
        print('Setup stopped:', type(exc).__name__, 'Check local MySQL permissions/state; no existing data was deleted.')
        raise SystemExit(1)
