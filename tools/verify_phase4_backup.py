"""Read-only comparison of old columns against our mysqldump backup.

Does not execute backup SQL or print customer records/credentials.
"""
import json
import os
import re
import sys
from datetime import timedelta, time, datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.conf import settings
from django.db import connection


def literal_rows(text):
    result, row, token = [], [], ''
    quoted = was_quoted = escaped = False
    for char in text:
        if escaped:
            token += {'0':'\0', 'n':'\n', 'r':'\r', 't':'\t', 'b':'\b', 'Z':'\x1a'}.get(char, char)
            escaped = False
        elif quoted:
            if char == '\\': escaped = True
            elif char == "'": quoted = False
            else: token += char
        elif char == "'": quoted = was_quoted = True
        elif char == '(':
            row, token, was_quoted = [], '', False
        elif char in ',)':
            if token or was_quoted:
                row.append(('s', token) if was_quoted else ('null', None) if token == 'NULL' else ('n', str(Decimal(token).normalize())))
            token, was_quoted = '', False
            if char == ')': result.append(row)
        elif char not in ';\n\r': token += char
    return result


def normalize(value):
    if value is None: return ('null', None)
    if isinstance(value, (int, Decimal, float)): return ('n', str(Decimal(value).normalize()))
    if isinstance(value, time): return ('s', value.isoformat(timespec='microseconds'))
    if isinstance(value, datetime): return ('s', value.isoformat(sep=' ', timespec='microseconds'))
    if isinstance(value, timedelta):
        seconds = int(value.total_seconds())
        return ('s', f'{seconds//3600:02d}:{seconds//60%60:02d}:{seconds%60:02d}')
    return ('s', str(value))


def main():
    assert connection.settings_dict['NAME'] == 'annhien_spa'
    folder = settings.BASE_DIR / 'backups' / sys.argv[1]
    folder = folder.resolve()
    if folder.parent != (settings.BASE_DIR / 'backups').resolve(): raise ValueError('Invalid backup folder')
    dump = (folder / 'database.sql').read_text(encoding='utf-8')
    checks = []
    for table, ddl in re.findall(r'CREATE TABLE `([A-Za-z0-9_]+)` \((.*?)\) ENGINE=', dump, re.S):
        if table == 'django_migrations': continue
        columns = re.findall(r'^  `([A-Za-z0-9_]+)`', ddl, re.M)
        statements = re.findall(r'INSERT INTO `' + table + r'` VALUES (.*?);\n', dump, re.S)
        expected = [r for statement in statements for r in literal_rows(statement)]
        with connection.cursor() as cursor:
            cursor.execute('SELECT ' + ','.join('`'+c+'`' for c in columns) + ' FROM `' + table + '`')
            actual = [[normalize(v) for v in record] for record in cursor.fetchall()]
        checks.append(dict(table=table, old_rows=len(expected), unchanged=sorted(map(repr, expected)) == sorted(map(repr, actual))))
    report = dict(backup=folder.name, tables=checks, old_columns_and_rows_unchanged=all(c['unchanged'] for c in checks))
    (settings.BASE_DIR / 'docs/phase4-final-data-verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Tables checked:', len(checks), 'unchanged:', report['old_columns_and_rows_unchanged'])
    print('Changed tables:', [c['table'] for c in checks if not c['unchanged']])


if __name__ == '__main__': main()
