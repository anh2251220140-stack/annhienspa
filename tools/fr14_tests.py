"""Discover offline or operate on an explicitly approved 127.0.0.1:3311 instance.

prepare prints and confirms a schema-only migration plan; it never runs tests.
retest requires an already migrated, fixture-empty schema. Cleanup preserves
system tables and never flushes or disables foreign-key/check constraints.
Connections require ANNHIEN_FR14_TEST_APPROVAL to match the guard's exact
approval phrase, in addition to the provisioned hostname and instance UUID.
"""

import argparse
from collections import Counter
from contextlib import ExitStack, contextmanager
import getpass
import heapq
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest.loader import _FailedTest
from unittest.mock import patch
import warnings


# Add only the missing MySQL chat race, not the ordinary ChatTests inventory.
REGRESSION = ("accounts", "core", "billing", "appointments.test_fr14",
              "ai_features.tests.ConcurrentChatTests")
SYSTEM_TABLES = frozenset({"django_migrations", "django_content_type", "auth_permission"})


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
        raise RunnerError("Combined suite does not match the configured regression groups.")
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
    with connection.cursor() as cursor:
        for table in sorted(tables - SYSTEM_TABLES):
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
    preserved = SYSTEM_TABLES
    pending = tables - preserved
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME "
            "FROM information_schema.KEY_COLUMN_USAGE "
            "WHERE TABLE_SCHEMA = DATABASE() AND REFERENCED_TABLE_SCHEMA = DATABASE()"
        )
        foreign_keys = set(cursor.fetchall())
    self_references = {(child, column, target_column)
                       for child, column, parent, target_column in foreign_keys if child == parent}
    expected_self = {("chat_messages", "reply_to_id", "id"), ("chat_messages", "retry_of_id", "id")}
    if self_references != (expected_self if "chat_messages" in tables else set()):
        raise RunnerError("Unexpected or missing self-referencing foreign keys; stopped before deleting rows.")
    references = {(child, parent) for child, _, parent, _ in foreign_keys}
    if any(child not in tables or parent not in tables for child, parent in references):
        raise RunnerError("A fixture foreign key references an unexpected table.")
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


def chat_message_delete_order(rows):
    """Plan all rows first. Never rely on PK order or disable FK/check constraints."""
    parents = {}
    for identifier, reply_to, retry_of in rows:
        if (type(identifier) is not int or identifier <= 0 or identifier in parents or
                any(value is not None and (type(value) is not int or value <= 0)
                    for value in (reply_to, retry_of))):
            raise RunnerError("Invalid or duplicate chat fixture IDs; stopped before deleting rows.")
        parents[identifier] = {value for value in (reply_to, retry_of) if value is not None}
    if any(parent not in parents for references in parents.values() for parent in references):
        raise RunnerError("Missing chat fixture parent; stopped before deleting rows.")
    child_counts = dict.fromkeys(parents, 0)
    for references in parents.values():
        for parent in references:
            child_counts[parent] += 1
    leaves = [identifier for identifier, count in child_counts.items() if count == 0]
    heapq.heapify(leaves)
    order = []
    while leaves:
        identifier = heapq.heappop(leaves)
        order.append(identifier)
        for parent in sorted(parents[identifier]):
            child_counts[parent] -= 1
            if child_counts[parent] == 0:
                heapq.heappush(leaves, parent)
    if len(order) != len(parents):
        raise RunnerError("Cyclic chat fixture references; stopped before deleting rows.")
    return order


def remove_fixture_rows(connection, guard, *, expected_order=None):
    """Delete only verified test fixtures, transactionally, retaining system tables."""
    from django.db import transaction

    guard.recheck(connection)
    tables = preflight(connection)
    order = fixture_delete_order(connection, tables)
    if expected_order is not None and order != expected_order:
        raise RunnerError("Test table dependencies changed; stopped before deleting rows.")
    with transaction.atomic(using="default"), connection.cursor() as cursor:
        # Validate every chat edge before deleting from ANY fixture table.
        messages = []
        if "chat_messages" in tables:
            cursor.execute("SELECT id, reply_to_id, retry_of_id FROM chat_messages ORDER BY id FOR UPDATE")
            messages = chat_message_delete_order(cursor.fetchall())
        for table in order:
            if table == "chat_messages":
                for identifier in messages:
                    cursor.execute("DELETE FROM chat_messages WHERE id = %s", [identifier])
                    if cursor.rowcount != 1:
                        raise RunnerError("Chat fixture changed during cleanup; transaction aborted.")
            else:
                quoted = connection.ops.quote_name(table)
                cursor.execute(f"SELECT 1 FROM {quoted} LIMIT 1")
                if cursor.fetchone() is not None:
                    cursor.execute(f"DELETE FROM {quoted}")
        require_empty_fixture_tables(connection, tables)


def migration_plan(connection):
    from django.db.migrations.executor import MigrationExecutor

    executor = MigrationExecutor(connection)
    executor.loader.check_consistent_history(connection)
    if executor.loader.detect_conflicts():
        raise RunnerError("Conflicting migration branches; stopped.")
    plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
    if any(backwards for _, backwards in plan):
        raise RunnerError("Backwards migrations are forbidden.")
    return [(migration.app_label, migration.name) for migration, _ in plan]


def prepare_schema(connection, guard):
    """Explicit schema-only operation; does not discover or execute regression tests."""
    from django.apps import apps
    from django.core.management import call_command

    tables = preflight(connection)
    require_empty_fixture_tables(connection, tables)
    plan = migration_plan(connection)
    if plan:
        print("Pending test migrations:")
        for app, name in plan:
            print(f"  {app}.{name}")
        confirm("PREPARE", f"Apply {len(plan)} migrations only; no regression or cleanup", guard.target)
        # Approval is not permission to reuse a schema that changed meanwhile.
        guard.recheck(connection)
        require_empty_fixture_tables(connection, preflight(connection))
        if migration_plan(connection) != plan:
            raise RunnerError("Migration plan changed after confirmation; stopped.")
        call_command("migrate", database="default", interactive=False, verbosity=1)
    if migration_plan(connection):
        raise RunnerError("Test migrations remain pending; no tests or cleanup executed.")
    tables = preflight(connection)
    expected = {model._meta.db_table for model in apps.get_models(include_auto_created=True)}
    expected.add("django_migrations")
    if tables != expected:
        raise RunnerError("Prepared test schema is incomplete or unexpected.")
    require_empty_fixture_tables(connection, tables)
    fixture_delete_order(connection, tables)
    print("Test schema prepared and verified; no regression tests or cleanup executed.")


def run_tests(connection, guard, expected, *, labels=REGRESSION, reuse_schema=False):
    from django.core.management import call_command
    from django.test import TransactionTestCase
    from django.test.runner import DiscoverRunner

    def check_reused_schema():
        tables = preflight(connection)
        require_empty_fixture_tables(connection, tables)
        if "django_migrations" not in tables:
            raise RunnerError("Retest requires a schema that is already migrated.")
        if migration_plan(connection):
            raise RunnerError("Pending migrations; retest will not change the schema.")
        return fixture_delete_order(connection, tables)

    if reuse_schema:
        delete_order = check_reused_schema()
        confirm("RUN", f"Run {expected.total()} tests; delete only temporary test rows", guard.target)
    else:
        delete_order = None
        require_empty_fixture_tables(connection, preflight(connection))
        confirm("MIGRATE", "Apply pending Django migrations", guard.target)
        confirm("RUN", f"Run {expected.total()} discovered regression tests", guard.target)
        confirm("CLEAN", "Transaction tests may delete disposable fixture rows", guard.target)

    def remove_transaction_fixtures(test):
        if test._databases_names() != ["default"]:
            raise RunnerError("Unexpected fixture database; stopped before deleting rows.")
        if delete_order is None:
            raise RunnerError("Fixture cleanup was not prepared.")
        remove_fixture_rows(connection, guard, expected_order=delete_order)

    class IsolatedRunner(DiscoverRunner):
        def build_suite(self, *args, **kwargs):
            from config.fr14_test_guard import offline_database

            with offline_database():
                suite = super().build_suite(*args, **kwargs)
            if suite_ids(suite) != expected:
                raise RunnerError("Suite changed after offline discovery; stopped.")
            return suite

        def setup_databases(self, **kwargs):
            nonlocal delete_order
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
            delete_order = check_reused_schema()

        def teardown_databases(self, old_config, **kwargs):
            require_empty_fixture_tables(connection, preflight(connection))

    with TemporaryDirectory(prefix="annhien-fr14-") as directory, ExitStack() as stack:
        from django.test.utils import override_settings

        stack.enter_context(override_settings(MEDIA_ROOT=directory, FILE_UPLOAD_TEMP_DIR=directory))
        from django.core.management.commands.flush import Command as FlushCommand
        from django.core.management.commands.migrate import Command as MigrateCommand

        stack.enter_context(patch.object(FlushCommand, "handle", side_effect=RunnerError(
            "Flush is forbidden; use guarded fixture cleanup."
        )))
        if reuse_schema:
            stack.enter_context(patch.object(MigrateCommand, "handle", side_effect=RunnerError(
                "Migrate is forbidden in retest mode."
            )))
        stack.enter_context(patch.object(TransactionTestCase, "_fixture_teardown", remove_transaction_fixtures))
        for operation in ("create", "get", "cancel"):
            stack.enter_context(patch(f"billing.gateway.{operation}",
                                      side_effect=RuntimeError("Unmocked payOS request forbidden.")))
        runner = IsolatedRunner(verbosity=2, interactive=False, parallel=1, failfast=reuse_schema)
        return int(bool(runner.run_tests(labels)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("discover", "preflight", "verify", "prepare", "run",
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
            if action == "prepare":
                stage = "confirmed schema preparation only"
                prepare_schema(connection, guard)
                return 0
            if action == "cleanup":
                if not preflight(connection):
                    print("No test tables to clean.")
                    return 0
                confirm("CLEAN", "Delete disposable fixture rows; preserve migrations and permissions", target)
                stage = "explicit test cleanup"
                remove_fixture_rows(connection, guard)
                print("Fixture cleanup verified; no flush or schema reset executed.")
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
