"""Offline Blob/auth regression. Never connects to MySQL, Blob, AI or payOS."""
from contextlib import ExitStack
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.chat_sqlite import configure


def main():
    with TemporaryDirectory(prefix='annhien-blob-tests-') as directory, ExitStack() as stack:
        configure(stack, Path(directory))
        from django.conf import settings
        from django.test.runner import DiscoverRunner
        settings.PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
        settings.SESSION_COOKIE_NAME = 'sessionid'
        settings.CSRF_COOKIE_NAME = 'csrftoken'
        labels = sys.argv[1:] or ['config.test_blob_media', 'accounts.tests',
                                  'accounts.test_profile_security', 'accounts.test_password_reset']
        return bool(DiscoverRunner(verbosity=1, interactive=False).run_tests(labels))


if __name__ == '__main__':
    raise SystemExit(main())
