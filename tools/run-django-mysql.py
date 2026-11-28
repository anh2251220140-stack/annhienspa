"""Run the complete Django suite with disposable MySQL and offline SQLite on Windows."""

import argparse
from collections import Counter
from contextlib import contextmanager, ExitStack
from datetime import datetime, timedelta, timezone
import inspect
import json
import os
from pathlib import Path
from secrets import token_hex, token_urlsafe
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from unittest import TextTestResult
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
HOST = "127.0.0.1"
MYSQL_PORT = 43361
GUARDED_PORT = 3311
SCHEMA = "annhien_test_django"
TRACKS = ("mysql", "guarded", "sqlite")
GUARDED_MODULES = (
    "core.test_admin_catalog_regression",
    "core.test_admin_promotion_services",
    "core.test_admin_remaining_regression",
    "core.test_employee_admin_concurrency",
)
SQLITE_CLASSES = (
    "ai_features.test_recommendation_integration.RecommendationApplicationTests",
    "ai_features.test_review_integration.ReviewGeminiIntegrationTests",
)
SYSTEM_ENV = {"PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP",
              "USERPROFILE", "PROGRAMFILES", "LOCALAPPDATA", "APPDATA"}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, encoding="utf-8").strip()


def timestamp():
    return datetime.now(timezone(timedelta(hours=7))).isoformat(timespec="seconds")


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_track(test_id):
    if test_id.rsplit(".", 1)[0] in SQLITE_CLASSES:
        return "sqlite"
    if test_id.rsplit(".", 2)[0] in GUARDED_MODULES:
        return "guarded"
    return "mysql"


@contextmanager
def track_results():
    """Capture the same results Django writes to its per-track log."""
    from django.test.runner import DiscoverRunner

    recorded = {}

    class Result(TextTestResult):
        def addSuccess(self, test):
            super().addSuccess(test)
            recorded[test.id()] = {"status": "PASS"}

        def addFailure(self, test, err):
            super().addFailure(test, err)
            recorded[test.id()] = {"status": "FAIL"}

        def addError(self, test, err):
            super().addError(test, err)
            recorded[test.id()] = {"status": "ERROR"}

        def addSkip(self, test, reason):
            super().addSkip(test, reason)
            recorded[test.id()] = {"status": "SKIP", "reason": reason}

        def addExpectedFailure(self, test, err):
            super().addExpectedFailure(test, err)
            recorded[test.id()] = {"status": "EXPECTED_FAILURE"}

        def addUnexpectedSuccess(self, test):
            super().addUnexpectedSuccess(test)
            recorded[test.id()] = {"status": "UNEXPECTED_SUCCESS"}

        def addSubTest(self, test, subtest, err):
            super().addSubTest(test, subtest, err)
            if err:
                recorded[test.id()] = {"status": "FAIL" if issubclass(err[0], test.failureException) else "ERROR"}

    with patch.object(DiscoverRunner, "get_resultclass", return_value=Result):
        yield recorded


def discover_inventory():
    from django.test.runner import DiscoverRunner, iter_test_cases

    tracked = {(ROOT / name).resolve() for name in git("ls-files", "-z").split("\0") if name}
    tests = list(iter_test_cases(DiscoverRunner(verbosity=0).build_suite([])))
    inventory = {test.id(): test_track(test.id()) for test in tests}
    if not tests or len(inventory) != len(tests):
        raise RuntimeError("Empty suite or duplicate test identifiers.")
    for test in tests:
        if Path(inspect.getfile(type(test))).resolve() not in tracked:
            raise RuntimeError(f"Test does not come from a tracked source: {test.id()}")
    return inventory


def run_standard_mysql(directory, password):
    import django
    from django.conf import settings
    from django.db import connections
    from django.db.backends.mysql.base import Database
    from django.test.runner import DiscoverRunner, iter_test_cases
    from tools.fr14_tests import block_network

    settings.DATABASES = {"default": {
        "ENGINE": "django.db.backends.mysql", "NAME": "annhien_unused_default",
        "USER": "root", "PASSWORD": password, "HOST": HOST, "PORT": str(MYSQL_PORT),
        "OPTIONS": {"charset": "utf8mb4", "connect_timeout": 5,
                    "init_command": "SET sql_mode='STRICT_TRANS_TABLES'"},
        "TEST": {"NAME": SCHEMA, "CHARSET": "utf8mb4"},
    }}
    settings.MEDIA_ROOT = directory / "media"
    settings.AI_RAG_DIRECTORY = directory / "vectors"
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    settings.AI_PROVIDER = "mock"
    settings.AI_PAID_CALLS_APPROVED = False
    connect = Database.connect

    def mysql_only(*args, **kwargs):
        target = (kwargs.get("host"), kwargs.get("port"), kwargs.get("user"), kwargs.get("password"))
        if args or target != (HOST, MYSQL_PORT, "root", password):
            raise RuntimeError("Database outside the disposable MySQL instance is forbidden.")
        if kwargs.get("database") not in (None, "", "annhien_unused_default", SCHEMA):
            raise RuntimeError("Unexpected schema on disposable MySQL.")
        return connect(**kwargs)

    class MySQLRunner(DiscoverRunner):
        def build_suite(self, *args, **kwargs):
            suite = super().build_suite(*args, **kwargs)
            return self.test_suite(test for test in iter_test_cases(suite)
                                   if test_track(test.id()) == "mysql")

    with block_network(), patch.object(Database, "connect", mysql_only):
        django.setup()
        inventory = discover_inventory()
        try:
            result = MySQLRunner(verbosity=2, interactive=False).run_tests([])
        finally:
            connections.close_all()
    return result, inventory


def run_guarded(password, hostname, uuid):
    from config.fr14_test_guard import Guard, Target, PRODUCTION_UUID, offline_database
    from django.test.runner import DiscoverRunner
    from tools import fr14_tests

    guard = Guard(Target(GUARDED_PORT, hostname, uuid, PRODUCTION_UUID, approved=True), password)
    with fr14_tests.django_context(guard) as connections:
        with offline_database():
            expected = fr14_tests.suite_ids(DiscoverRunner(verbosity=0).build_suite(GUARDED_MODULES))

        def confirm_owned_instance(prompt):
            for action in ("MIGRATE", "RUN", "CLEAN"):
                phrase = f"{action} {guard.database}"
                if prompt.endswith(f"on port {GUARDED_PORT}. Type {phrase}: "):
                    print(f"{phrase} authorized for the database created by this runner.")
                    return phrase
            raise RuntimeError("Unexpected confirmation prompt.")

        with patch("builtins.input", side_effect=confirm_owned_instance):
            result = fr14_tests.run_tests(connections["default"], guard, expected, labels=GUARDED_MODULES)
    return result, dict.fromkeys(expected, "guarded")


def run_sqlite(directory):
    from tools.fr14_tests import suite_ids
    from django.conf import settings
    from django.test.runner import DiscoverRunner
    from tools.chat_sqlite import configure

    with ExitStack() as stack:
        configure(stack, directory)
        settings.CSRF_COOKIE_NAME = "csrftoken"
        runner = DiscoverRunner(verbosity=2, interactive=False)
        ids = suite_ids(runner.build_suite(SQLITE_CLASSES))
        result = runner.run_tests(SQLITE_CLASSES)
    return result, dict.fromkeys(ids, "sqlite")


@contextmanager
def disposable_mysql(directory, mysql_bin, port, log):
    with socket.socket() as probe:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        probe.bind((HOST, port))

    data = directory / "data"
    data.mkdir()
    init = directory / "bootstrap.sql"
    pid = directory / "mysql.pid"
    password, guard_password = ("SpaTest!" + token_hex(24) for _ in range(2))
    bootstrap = f"ALTER USER 'root'@'localhost' IDENTIFIED BY '{password}';\n"
    if port == GUARDED_PORT:
        from config.fr14_test_guard import DATABASE, USER, PRIVILEGES

        bootstrap += (f"CREATE DATABASE {DATABASE} CHARACTER SET utf8mb4;\n"
                      f"CREATE USER '{USER}'@'{HOST}' IDENTIFIED BY '{guard_password}';\n"
                      f"GRANT {','.join(sorted(PRIVILEGES))} ON {DATABASE}.* TO '{USER}'@'{HOST}';\n")
    init.write_text(bootstrap, encoding="ascii")
    launch = [str(mysql_bin / "mysqld.exe"), "--no-defaults", f"--basedir={mysql_bin.parent}",
              f"--datadir={data}", f"--log-error={log}"]
    subprocess.run([*launch, "--initialize-insecure"], check=True, timeout=120,
                   creationflags=subprocess.CREATE_NO_WINDOW)
    instance = subprocess.Popen([
        *launch, f"--port={port}", f"--bind-address={HOST}", "--mysqlx=OFF", "--skip-log-bin",
        "--no-monitor", f"--pid-file={pid}", f"--init-file={init}", "--innodb-buffer-pool-size=128M",
        *(["--partial-revokes=ON"] if port == GUARDED_PORT else []),
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    credentials = ["--no-defaults", "--protocol=TCP", "-h", HOST, "-P", str(port), "-u", "root"]
    db_env = dict(os.environ, MYSQL_PWD=password)
    verified = False
    try:
        for _ in range(35):
            if instance.poll() is not None:
                raise RuntimeError(f"Disposable MySQL exited; see {log.name}.")
            query = subprocess.run([
                str(mysql_bin / "mysql.exe"), *credentials, "--connect-timeout=2", "-N", "-B", "--raw",
                "-e", "SELECT @@port, @@datadir, @@version, @@pid_file, @@hostname, @@server_uuid",
            ], env=db_env, capture_output=True, text=True, encoding="utf-8", timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW)
            if query.returncode:
                time.sleep(1)
                continue
            seen_port, seen_dir, version, seen_pid, hostname, uuid = query.stdout.strip().split("\t")
            if (int(seen_port) != port or Path(seen_dir).resolve() != data.resolve()
                    or Path(seen_pid).resolve() != pid.resolve() or int(pid.read_text()) != instance.pid):
                raise RuntimeError("MySQL identity differs from the instance owned by this run.")
            verified = True
            break
        if not verified:
            raise RuntimeError(f"Disposable MySQL did not start; see {log.name}.")
        init.unlink()
        yield password, guard_password, version, hostname, uuid
    finally:
        try:
            if verified and instance.poll() is None:
                subprocess.run([str(mysql_bin / "mysqladmin.exe"), *credentials, "shutdown"], env=db_env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25,
                               creationflags=subprocess.CREATE_NO_WINDOW)
        finally:
            if instance.poll() is None:
                instance.terminate()
            instance.wait(timeout=25)


def child(track, output, mysql_bin):
    started = timestamp()
    safe_env = {key: value for key, value in os.environ.items() if key.upper() in SYSTEM_ENV}
    safe_env.update(DJANGO_SETTINGS_MODULE="config.settings", DJANGO_DEBUG="true",
                    DJANGO_SECRET_KEY=token_urlsafe(48))
    version = None
    with (TemporaryDirectory(prefix="annhien-test-") as temporary,
          patch.dict(os.environ, safe_env, clear=True), patch("dotenv.load_dotenv", return_value=False),
          track_results() as results):
        directory = Path(temporary)
        if track == "sqlite":
            exit_code, inventory = run_sqlite(directory)
        else:
            port = MYSQL_PORT if track == "mysql" else GUARDED_PORT
            with disposable_mysql(directory, mysql_bin, port, output / f"{track}-server.log") as server:
                password, guard_password, version, hostname, uuid = server
                if track == "mysql":
                    exit_code, inventory = run_standard_mysql(directory, password)
                else:
                    exit_code, inventory = run_guarded(guard_password, hostname, uuid)
    write_json(output / f"{track}.json", {
        "started": started, "finished": timestamp(), "mysql_version": version,
        "inventory": inventory, "results": results,
    })
    return int(bool(exit_code))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mysql-bin", type=Path,
                        default=Path("C:/Program Files/MySQL/MySQL Server 8.4/bin"))
    parser.add_argument("--output-dir", required=True, type=Path,
                        help="Directory for a new timestamped log and JSON report.")
    parser.add_argument("--expect-commit", help="Require this exact commit and a clean tracked worktree.")
    parser.add_argument("--track", choices=TRACKS, help=argparse.SUPPRESS)
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)
    args.mysql_bin = args.mysql_bin.resolve()
    args.output_dir = args.output_dir.resolve()
    if args.track:
        return child(args.track, args.output_dir, args.mysql_bin)
    if os.name != "nt":
        parser.error("This runner requires Windows and local MySQL 8.4 binaries.")
    for binary in ("mysqld.exe", "mysql.exe", "mysqladmin.exe"):
        if not (args.mysql_bin / binary).is_file():
            parser.error(f"Missing {binary} in --mysql-bin.")
    commit = git("rev-parse", "HEAD")
    dirty = bool(git("status", "--porcelain", "--untracked-files=no"))
    if args.expect_commit and (dirty or commit != git("rev-parse", args.expect_commit)):
        parser.error("The tracked worktree must match --expect-commit exactly.")
    output = args.output_dir / datetime.now().strftime("django-%Y%m%d-%H%M%S-%f")
    output.mkdir(parents=True)
    combined = {}
    ok = True
    for track in TRACKS:
        log = output / f"{track}.log"
        print(f"Running {track} tests. Log: {log}", flush=True)
        with log.open("w", encoding="utf-8") as stream:
            result = subprocess.run([
                sys.executable, "-X", "utf8", "-B", str(Path(__file__).resolve()), "--track", track,
                "--output-dir", str(output), "--mysql-bin", str(args.mysql_bin),
            ], stdout=stream, stderr=subprocess.STDOUT)
        ok = (result.returncode == 0) and ok
        evidence = output / f"{track}.json"
        if evidence.is_file():
            combined[track] = json.loads(evidence.read_text(encoding="utf-8"))

    inventory = combined.get("mysql", {}).get("inventory", {})
    counts = {}
    for track, evidence in combined.items():
        expected = {key for key, value in inventory.items() if value == track}
        recorded = evidence["results"]
        if not expected or set(recorded) != expected:
            ok = False
        counts[track] = dict(Counter(item["status"] for item in recorded.values()))
        for missing in sorted(expected - recorded.keys()):
            print(f"Not reported: {missing}")
    ok = ok and len(combined) == len(TRACKS)
    if args.expect_commit:
        ok = ok and git("rev-parse", "HEAD") == commit and not git("status", "--porcelain", "--untracked-files=no")
    summary = {"commit": commit, "tracked_worktree_clean_at_start": not dirty,
               "discovered": len(inventory), "counts": counts, "passed": ok}
    write_json(output / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return int(not ok)


if __name__ == "__main__":
    raise SystemExit(main())
