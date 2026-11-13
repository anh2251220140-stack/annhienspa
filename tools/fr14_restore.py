"""Prompt locally; verify by default. No tests, restore or arbitrary commands."""
import argparse
import getpass
import os
from pathlib import Path
import sys
import warnings

TARGET = "0002_appointment_cancel_reason_appointment_cancelled_at_and_more"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("verify", "migrate"), nargs="?", default="verify")
    args = parser.parse_args()
    if not sys.stdin.isatty():
        print("Run in an interactive local terminal; hidden password input is required.")
        return 1
    # Never accept an old inherited password silently.
    os.environ.pop("ANNHIEN_FR14_RESTORE_PASSWORD", None)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            password = getpass.getpass("Restore account password (hidden): ")
        if not password:
            print("Missing password; stopped.")
            return 1
        os.environ["ANNHIEN_FR14_RESTORE_PASSWORD"] = password
        del password
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings_fr14_restore"
        import django
        django.setup()
        os.environ.pop("ANNHIEN_FR14_RESTORE_PASSWORD", None)
        from django.db import connection
        from config.settings_fr14_restore import verify_restore_connection
        connection.ensure_connection()
        verify_restore_connection(None, connection)
        print("Verified: annhien_spa_restore_fr14_20261106 / annhien_fr14_restore@localhost")
        from django.db.migrations.executor import MigrationExecutor
        executor = MigrationExecutor(connection)
        executor.loader.check_consistent_history(connection)
        plan = executor.migration_plan([("appointments", TARGET)])
        if any(backwards or migration.app_label != "appointments" or migration.name != TARGET
               for migration, backwards in plan):
            print("Unexpected migration/dependency/rollback in plan; stopped.")
            return 1
        print("Plan:", "appointments " + TARGET if plan else "Already applied; no changes.")
        if args.action == "verify":
            print("Read-only verification finished. No migration executed.")
            return 0
        if not plan:
            return 0
        confirmation = input("Type annhien_spa_restore_fr14_20261106 to apply this migration: ")
        if confirmation != "annhien_spa_restore_fr14_20261106":
            print("Not confirmed; stopped.")
            return 1
        verify_restore_connection(None, connection)
        from django.core.management import call_command
        call_command("migrate", "appointments", TARGET, database="default", interactive=False)
        print("Migration command completed on the isolated database only.")
        return 0
    except (Exception, KeyboardInterrupt):
        # Do not print arbitrary driver exceptions, locals or credentials.
        print("Stopped: connection, validation or execution failed. No automatic retry or fallback.")
        return 1
    finally:
        os.environ.pop("ANNHIEN_FR14_RESTORE_PASSWORD", None)
        if "django.db" in sys.modules:
            from django.db import connections
            connections.close_all()


if __name__ == "__main__":
    raise SystemExit(main())
