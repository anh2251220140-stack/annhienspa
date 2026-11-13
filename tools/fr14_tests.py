"""Discover offline or operate on an explicitly provisioned MySQL test instance."""

import argparse
from collections import Counter
from contextlib import ExitStack, contextmanager
import getpass
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest.loader import _FailedTest
from unittest.mock import patch
import warnings


REGRESSION = ("accounts", "core", "billing", "appointments.test_fr14")


class RunnerError(RuntimeError):
    """Fixed, non-secret diagnostic from a runner check."""


def suite_ids(suite):
    from django.test.runner import iter_test_cases

    cases = list(iter_test_cases(suite))
    if any(isinstance(case, _FailedTest) for case in cases):
        raise RunnerError("Regression test import failed; review before proceeding.")
    ids = [case.id() for case in cases]
    if not ids or len(ids) != len(set(ids)):
        raise RunnerError("Empty regression group or duplicate test IDs.")
    return Counter(ids)


def discover():
    from django.test.runner import DiscoverRunner

    runner = DiscoverRunner(verbosity=0, interactive=False)
    expected = Counter()
    for label in REGRESSION:
        ids = suite_ids(runner.build_suite([label]))
        print(f"{label}: {ids.total()}")
        expected.update(ids)
    combined = suite_ids(runner.build_suite(REGRESSION))
    if combined != expected:
        raise RunnerError("Combined suite does not match the four discovered groups.")
    print(f"Total regression tests: {combined.total()} (discovery only)")
    return combined


@contextmanager
def block_network():
    with ExitStack() as stack:
        for target in ("httpx.Client.send", "httpx.AsyncClient.send",
                       "socket.create_connection", "socket.socket.connect",
                       "socket.socket.connect_ex", "socket.socket.sendto"):
            stack.enter_context(patch(target, side_effect=RuntimeError("External network forbidden.")))
        yield


@contextmanager
def django_context(guard):
    import django
    from django.conf import settings
    from django.db import connections
    from config.fr14_test_guard import SETTINGS, install_guard, offline_database

    with (patch.dict(os.environ, {"DJANGO_SETTINGS_MODULE": SETTINGS,
                                  "DJANGO_DEBUG": "true",
                                  "DJANGO_SECRET_KEY": "fr14-tests-local-only"}),
          install_guard(guard), block_network()):
        try:
            # Reuse application configuration without loading its .env file.
            with patch("dotenv.load_dotenv", return_value=False), offline_database():
                django.setup()
            if settings.SETTINGS_MODULE != SETTINGS or set(connections) != {"default"}:
                raise RunnerError("Unexpected Django settings module or database aliases.")
            yield connections
        finally:
            connections.close_all()


def preflight(connection):
    from django.apps import apps
    from config.fr14_test_guard import active_guard

    version = active_guard().recheck(connection)
    allowed = {m._meta.db_table for m in apps.get_models(include_auto_created=True)}
    allowed.add("django_migrations")
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT TABLE_NAME, TABLE_TYPE, ENGINE FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE()"
        )
        tables = cursor.fetchall()
        if any(name not in allowed or kind != "BASE TABLE" or engine != "InnoDB"
               for name, kind, engine in tables):
            raise RunnerError("Unexpected table, view, or non-InnoDB engine.")
        cursor.execute("SHOW TRIGGERS")
        if cursor.fetchall():
            raise RunnerError("Unexpected triggers in the test schema.")
        cursor.execute(
            "SELECT 1 FROM information_schema.KEY_COLUMN_USAGE WHERE "
            "TABLE_SCHEMA = DATABASE() AND REFERENCED_TABLE_SCHEMA <> DATABASE() LIMIT 1"
        )
        if cursor.fetchone():
            raise RunnerError("Unexpected foreign key to another schema.")
    print(f"Verified test instance, MySQL {version}, InnoDB; {len(tables)} recognized tables.")
    return {name for name, _, _ in tables}


def require_empty_fixture_tables(connection, tables):
    # Preserve migration history and Django's generated lookup tables.
    system_tables = {"django_migrations", "django_content_type", "auth_permission"}
    with connection.cursor() as cursor:
        for table in sorted(tables - system_tables):
            cursor.execute(f"SELECT 1 FROM {connection.ops.quote_name(table)} LIMIT 1")
            if cursor.fetchone() is not None:
                raise RunnerError("Test schema contains rows. Review them; cleanup is a separate command.")


def confirm(action, operation, target):
    from config.fr14_test_guard import DATABASE

    phrase = f"{action} {DATABASE}"
    if input(f"{operation} on port {target.port}. Type {phrase}: ") != phrase:
        raise RunnerError("Confirmation declined; stopped.")


def fixture_delete_order(connection, tables):
    """Keep migrations, content types and permissions intact, including their FKs."""
    preserved = {"django_migrations", "django_content_type", "auth_permission"}
    pending = tables - preserved
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT TABLE_NAME, REFERENCED_TABLE_NAME FROM information_schema.KEY_COLUMN_USAGE "
            "WHERE TABLE_SCHEMA = DATABASE() AND REFERENCED_TABLE_SCHEMA = DATABASE()"
        )
        references = set(cursor.fetchall())
    if any(child in preserved and parent in pending for child, parent in references):
        raise RunnerError("A preserved table references a fixture table.")
    order = []
    while pending:
        parents = {parent for child, parent in references if child != parent and child in pending}
        leaves = sorted(pending - parents)
        if not leaves:
            raise RunnerError("Unexpected fixture table dependencies; stopped before deleting rows.")
        order.extend(leaves)
        pending -= set(leaves)
    return order


def run_tests(connection, guard, expected, *, labels=REGRESSION, reuse_schema=False):
    from django.core.management import call_command
    from django.db import transaction
    from django.db.migrations.executor import MigrationExecutor
    from django.test import TransactionTestCase
    from django.test.runner import DiscoverRunner

    def check_reused_schema():
        tables = preflight(connection)
        require_empty_fixture_tables(connection, tables)
        if "django_migrations" not in tables:
            raise RunnerError("Retest requires a schema that is already migrated.")
        executor = MigrationExecutor(connection)
        executor.loader.check_consistent_history(connection)
        if executor.migration_plan(executor.loader.graph.leaf_nodes()):
            raise RunnerError("Pending migrations; retest will not change the schema.")
        return fixture_delete_order(connection, tables)

    if reuse_schema:
        delete_order = check_reused_schema()
        confirm("RUN", f"Run {expected.total()} tests; delete only temporary test rows", guard.target)
    else:
        require_empty_fixture_tables(connection, preflight(connection))
        confirm("MIGRATE", "Apply pending Django migrations", guard.target)
        confirm("RUN", f"Run {expected.total()} discovered regression tests", guard.target)
        confirm("CLEAN", "Transaction tests may flush disposable test rows", guard.target)

    def remove_transaction_fixtures(test):
        if test._databases_names() != ["default"]:
            raise RunnerError("Unexpected fixture database; stopped before deleting rows.")
        guard.recheck(connection)
        with transaction.atomic(using="default"), connection.cursor() as cursor:
            for table in delete_order:
                quoted = connection.ops.quote_name(table)
                cursor.execute(f"SELECT 1 FROM {quoted} LIMIT 1")
                if cursor.fetchone() is not None:
                    cursor.execute(f"DELETE FROM {quoted}")

    class IsolatedRunner(DiscoverRunner):
        def build_suite(self, *args, **kwargs):
            from config.fr14_test_guard import offline_database

            with offline_database():
                suite = super().build_suite(*args, **kwargs)
            if suite_ids(suite) != expected:
                raise RunnerError("Suite changed after offline discovery; stopped.")
            return suite

        def setup_databases(self, **kwargs):
            # Never use Django's create/drop/_nodb machinery or flush before running.
            if set(kwargs["aliases"]) != {"default"}:
                raise RunnerError("Tests requested an unexpected database alias.")
            if reuse_schema:
                if check_reused_schema() != delete_order:
                    raise RunnerError("Test table dependencies changed.")
                return None
            require_empty_fixture_tables(connection, preflight(connection))
            call_command("migrate", database="default", interactive=False, verbosity=1)
            require_empty_fixture_tables(connection, preflight(connection))

        def teardown_databases(self, old_config, **kwargs):
            if reuse_schema:
                require_empty_fixture_tables(connection, preflight(connection))

    with TemporaryDirectory(prefix="annhien-fr14-") as directory, ExitStack() as stack:
        from django.test.utils import override_settings

        stack.enter_context(override_settings(MEDIA_ROOT=directory, FILE_UPLOAD_TEMP_DIR=directory))
        if reuse_schema:
            from django.core.management.commands.flush import Command as FlushCommand
            from django.core.management.commands.migrate import Command as MigrateCommand

            for command in (FlushCommand, MigrateCommand):
                stack.enter_context(patch.object(command, "handle", side_effect=RunnerError(
                    "Flush and migrate are forbidden in retest mode."
                )))
            stack.enter_context(patch.object(TransactionTestCase, "_fixture_teardown", remove_transaction_fixtures))
        for operation in ("create", "get", "cancel"):
            stack.enter_context(patch(f"billing.gateway.{operation}",
                                      side_effect=RuntimeError("Unmocked payOS request forbidden.")))
        runner = IsolatedRunner(verbosity=2, interactive=False, parallel=1, failfast=reuse_schema)
        return int(bool(runner.run_tests(labels)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("discover", "preflight", "verify", "run",
                                          "regression", "cleanup", "retest"),
                        nargs="?", default="discover")
    parser.add_argument("labels", nargs="*", help="Optional test labels for retest only.")
    args = parser.parse_args()
    action = {"verify": "preflight", "regression": "run"}.get(args.action, args.action)
    if args.labels and action != "retest":
        parser.error("Test labels are only allowed with retest.")
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from config.fr14_test_guard import Guard, GuardError, Target, offline_database

    stage = "offline discovery"
    try:
        if action == "discover":
            with django_context(Guard(None)), offline_database():
                discover()
            return 0
        stage = "test target configuration"
        target = Target.from_environment()
        stage = "hidden password entry"
        if not sys.stdin.isatty():
            print("Interactive terminal required for hidden test password input.")
            return 1
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            password = getpass.getpass("FR-14 test password (hidden): ")
        if not password:
            print("Missing password; stopped.")
            return 1
        guard = Guard(target, password)
        del password
        stage = "offline Django setup"
        with django_context(guard) as connections:
            labels = tuple(args.labels) or REGRESSION
            if action in {"run", "retest"}:
                stage = "offline discovery"
                with offline_database():
                    expected = discover()
                    if args.labels:
                        from django.test.runner import DiscoverRunner

                        selected = suite_ids(DiscoverRunner(verbosity=0).build_suite(labels))
                        if selected - expected:
                            raise RunnerError("Retest labels must belong to the regression suite.")
                        expected = selected
                    print(f"Selected regression tests: {expected.total()}")
            stage = "read-only preflight"
            connection = connections["default"]
            if action == "preflight":
                preflight(connection)
                print("Read-only verification; no migrations, tests, or cleanup executed.")
                return 0
            if action == "cleanup":
                if not preflight(connection):
                    print("No test tables to clean.")
                    return 0
                confirm("CLEAN", "Flush disposable test rows", target)
                preflight(connection)
                from django.core.management import call_command

                stage = "explicit test cleanup"
                call_command("flush", database="default", interactive=False, verbosity=1)
                return 0
            stage = "verified test migrations/regression"
            return run_tests(connection, guard, expected, labels=labels, reuse_schema=action == "retest")
    except (GuardError, RunnerError) as exc:
        print(exc)
        print(f"Stopped during {stage}; no fallback.")
    except (Exception, KeyboardInterrupt):
        print(f"Stopped during {stage}; no fallback.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
