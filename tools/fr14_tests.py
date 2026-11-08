"""Discover/verify safely; run the full regression only after cleanup consent."""
import argparse
from contextlib import ExitStack
import getpass
import os
from pathlib import Path
import re
import sys
import warnings
from unittest.mock import patch

DATABASE = "annhien_spa_fr14_tests"
REGRESSION = ["accounts", "core", "billing", "appointments.test_fr14"]
EXPECTED_COUNTS = {"accounts": 17, "core": 47, "billing": 70, "appointments.test_fr14": 17}


def discover():
    """Import and enumerate only; any attempted Django connection is forbidden."""
    from django.test.runner import DiscoverRunner
    from django.db.backends.base.base import BaseDatabaseWrapper
    total = 0
    with patch.object(BaseDatabaseWrapper, "ensure_connection",
                      side_effect=RuntimeError("Database access forbidden during discovery")):
        runner = DiscoverRunner(verbosity=0, interactive=False)
        for label in REGRESSION:
            count = runner.build_suite([label]).countTestCases()
            print(f"{label}: {count}")
            if count != EXPECTED_COUNTS[label]:
                raise RuntimeError("Unexpected discovery count; review before running")
            total += count
        if runner.build_suite(REGRESSION).countTestCases() != total:
            raise RuntimeError("Combined suite count mismatch")
    print(f"Total regression tests: {total} (discovery only)")
    return total


def discovery_only():
    # Placeholder is never used to connect; no real credential is requested.
    from django.db.backends.base.base import BaseDatabaseWrapper
    os.environ["ANNHIEN_FR14_TEST_PASSWORD"] = "discovery-only-no-connection"
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings_fr14_tests"
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    try:
        with patch.object(BaseDatabaseWrapper, "ensure_connection",
                          side_effect=RuntimeError("Database access forbidden during discovery")):
            import django
            django.setup()
            discover()
        return 0
    finally:
        os.environ.pop("ANNHIEN_FR14_TEST_PASSWORD", None)


def preflight(connection):
    from config.settings_fr14_tests import verify_identity
    connection.ensure_connection()
    verify_identity(None, connection)
    with connection.cursor() as cursor:
        cursor.execute("SHOW GRANTS")
        for (grant,) in cursor.fetchall():
            match = re.fullmatch(r"GRANT (.+?) ON (.+?) TO .+", grant)
            if not match:
                raise RuntimeError("Unrecognized grants or roles; manual review required")
            privileges, scope = match.groups()
            if privileges == "USAGE" and scope == "*.*":
                continue
            if (scope.replace("\\_", "_") != "`" + DATABASE + "`.*" or
                    "WITH GRANT OPTION" in grant):
                raise RuntimeError("Account privileges extend beyond test schema")
        cursor.execute("SHOW FULL TABLES")
        tables = cursor.fetchall()
        from django.apps import apps
        allowed = {m._meta.db_table for m in apps.get_models(include_auto_created=True)} | {"django_migrations"}
        if any(name not in allowed or kind != "BASE TABLE" for name, kind in tables):
            raise RuntimeError("Unexpected tables/views; manual review required")
        print("Existing tables:", len(tables), "(no data read or removed)")
        cursor.execute("SHOW TRIGGERS")
        if cursor.fetchall():
            raise RuntimeError("Unexpected triggers")
    print("Verified isolated account/database and recognized table inventory.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("discover", "verify", "run", "regression"), nargs="?", default="verify")
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    if args.action == "discover":
        return discovery_only()
    if not sys.stdin.isatty():
        print("Interactive terminal required for hidden password input.")
        return 1
    os.environ.pop("ANNHIEN_FR14_TEST_PASSWORD", None)
    stage = "password entry"
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            password = getpass.getpass("FR-14 test password (hidden): ")
        if not password:
            print("Missing password; stopped.")
            return 1
        os.environ["ANNHIEN_FR14_TEST_PASSWORD"] = password
        del password
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings_fr14_tests"
        stage = "Django setup"
        import django
        django.setup()
        os.environ.pop("ANNHIEN_FR14_TEST_PASSWORD", None)
        from django.db import connection
        stage = "read-only identity, grants and schema checks"
        preflight(connection)
        discover()
        if args.action == "verify":
            print("Verification only: no migrations or tests executed.")
            return 0
        if input("This will FLUSH ALL rows in the test schema. Type CLEAN " + DATABASE + ": ") != "CLEAN " + DATABASE:
            print("Not confirmed; stopped.")
            return 1
        preflight(connection)
        from django.test.runner import DiscoverRunner
        from django.core.management import call_command

        class IsolatedRunner(DiscoverRunner):
            def setup_databases(self, **kwargs):
                # Do not use Django's create/drop/_nodb machinery.
                preflight(connection)
                call_command("migrate", database="default", interactive=False, verbosity=0)
                from config.settings_fr14_tests import verify_identity
                verify_identity(None, connection)
                call_command("flush", database="default", interactive=False, verbosity=0)
                return None

            def teardown_databases(self, old_config, **kwargs):
                # Leave schema for inspection. Tests themselves may flush its rows.
                pass

        stage = "isolated migrations/tests"
        with ExitStack() as stack:
            # Preserve local signature/SDK tests; block outbound HTTP, not crypto.
            for target in ("httpx.Client.send", "httpx.AsyncClient.send", "socket.create_connection"):
                stack.enter_context(patch(target, side_effect=RuntimeError("External network forbidden")))
            for name in ("create", "get", "cancel"):
                stack.enter_context(patch("billing.gateway." + name,
                                          side_effect=RuntimeError("Unmocked payOS request forbidden")))
            runner = IsolatedRunner(verbosity=2, interactive=False, parallel=1)
            # Both names intentionally run the SAME full regression suite.
            labels = REGRESSION
            suite = runner.build_suite(labels)
            print("Discovered tests:", suite.countTestCases())
            if suite.countTestCases() != sum(EXPECTED_COUNTS.values()):
                raise RuntimeError("Expected full regression suite; stopped")
            failures = runner.run_tests(labels)
        return int(bool(failures))
    except (Exception, KeyboardInterrupt):
        print("Stopped during " + stage + "; no fallback. Review configuration locally; secrets are not printed.")
        return 1
    finally:
        os.environ.pop("ANNHIEN_FR14_TEST_PASSWORD", None)
        if "django.db" in sys.modules:
            from django.db import connections
            connections.close_all()


if __name__ == "__main__":
    raise SystemExit(main())
