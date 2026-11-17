
"""Safely apply exactly four FR14 migrations to the isolated Restore DB."""
import argparse
import getpass
import os
from pathlib import Path
import sys
import warnings

TARGETS = [
    ("billing", "0006_invoicedetail_unique_detail_per_invoice"),
    ("promotions", "0004_promotion_note_is_informational"),
    ("ai_features", "0002_chat_history"),
    ("ai_features", "0003_review_analysis_details"),
]

ALLOWED = set(TARGETS)
PLAN_TARGETS = [
    TARGETS[0],
    TARGETS[1],
    TARGETS[3],
]

EXPECTED_DB = "annhien_spa_restore_fr14_20261106"
CONFIRMATION = (
    "APPLY FOUR FR14 MIGRATIONS TO "
    "annhien_spa_restore_fr14_20261106"
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=("plan", "migrate"),
        nargs="?",
        default="plan",
    )
    args = parser.parse_args()

    if not sys.stdin.isatty():
        print("Interactive local terminal required; stopped.")
        return 1

    os.environ.pop("ANNHIEN_FR14_RESTORE_PASSWORD", None)

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            password = getpass.getpass(
                "Restore account password (hidden): "
            )

        if not password:
            print("Missing password; stopped.")
            return 1

        os.environ["ANNHIEN_FR14_RESTORE_PASSWORD"] = password
        del password

        sys.path.insert(
            0, str(Path(__file__).resolve().parents[1])
        )
        os.environ["DJANGO_SETTINGS_MODULE"] = (
            "config.settings_fr14_restore"
        )

        import django
        django.setup()

        os.environ.pop("ANNHIEN_FR14_RESTORE_PASSWORD", None)

        from django.db import connection
        from django.core.management import call_command
        from django.db.migrations.executor import MigrationExecutor
        from config.settings_fr14_restore import (
            verify_restore_connection,
        )

        def verify_identity():
            connection.close()
            connection.ensure_connection()
            verify_restore_connection(None, connection)

            if connection.settings_dict["NAME"] != EXPECTED_DB:
                raise RuntimeError("Unexpected database.")

        verify_identity()

        executor = MigrationExecutor(connection)
        executor.loader.check_consistent_history(connection)

        plan = executor.migration_plan(PLAN_TARGETS)

        steps = [
            (migration.app_label, migration.name)
            for migration, backwards in plan
        ]

        if any(backwards for migration, backwards in plan):
            print("Rollback detected; stopped.")
            return 1

        unexpected = [step for step in steps if step not in ALLOWED]

        if unexpected:
            print("Unexpected migration dependency; stopped.")
            return 1

        print("===== FR14 FOUR-MIGRATION PLAN =====")

        if not steps:
            print("All four migrations are already applied.")
            return 0

        for app, name in steps:
            print(f"PENDING: {app}.{name}")

        print(f"Target database: {EXPECTED_DB}")
        print("Target server: MySQL 8.4 / 127.0.0.1:3306")
        print("No migration has been executed yet.")

        if args.action == "plan":
            print("Read-only plan completed.")
            return 0

        confirmation = input(
            "\nType the following confirmation exactly:\n"
            f"{CONFIRMATION}\n> "
        )

        if confirmation != CONFIRMATION:
            print("Not confirmed; stopped.")
            return 1

        for app, name in TARGETS:
            verify_identity()

            executor = MigrationExecutor(connection)
            pending = executor.migration_plan([(app, name)])

            if not pending:
                print(f"ALREADY APPLIED: {app}.{name}")
                continue

            if any(
                backwards or
                (migration.app_label, migration.name) not in ALLOWED
                for migration, backwards in pending
            ):
                print("Unexpected execution plan; stopped.")
                return 1

            print(f"\nAPPLYING: {app}.{name}")

            call_command(
                "migrate",
                app,
                name,
                database="default",
                interactive=False,
                verbosity=1,
            )

            verify_identity()

            check = MigrationExecutor(connection)
            remaining = check.migration_plan([(app, name)])

            if remaining:
                print(f"Verification failed: {app}.{name}")
                return 1

            print(f"PASS: {app}.{name}")

        final_executor = MigrationExecutor(connection)
        final_plan = final_executor.migration_plan(PLAN_TARGETS)

        if final_plan:
            print("Final verification failed; pending migrations remain.")
            return 1

        print("\nALL FOUR MIGRATIONS VERIFIED ON RESTORE.")
        print("Main database annhien_spa was not targeted.")
        return 0

    except (Exception, KeyboardInterrupt):
        print(
            "Stopped: connection, validation or execution failed. "
            "Inspect the Restore database before proceeding."
        )
        return 1

    finally:
        os.environ.pop("ANNHIEN_FR14_RESTORE_PASSWORD", None)

        if "django.db" in sys.modules:
            from django.db import connections
            connections.close_all()


if __name__ == "__main__":
    raise SystemExit(main())
