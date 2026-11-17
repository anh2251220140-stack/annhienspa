"""Run chat tests or a temporary loopback site with a dedicated SQLite database."""

import argparse
from contextlib import ExitStack, closing, contextmanager
from getpass import getpass
from http.client import HTTPConnection
import os
from pathlib import Path
from secrets import token_urlsafe
import signal
import socket
import sys
from tempfile import TemporaryDirectory
from threading import Event, Thread
from unittest.mock import patch

from django.core.servers.basehttp import ThreadedWSGIServer, WSGIRequestHandler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.fr14_tests import block_network

HOST, PORT = "127.0.0.1", 8003
SOCKET_TIMEOUT = 5
# The readiness client may connect only to the socket this launcher owns.
_connect = socket.socket.connect


class LocalRequests(WSGIRequestHandler):
    timeout = SOCKET_TIMEOUT

    def log_message(self, format, *args):
        # Do not put request URLs or other client data in the launcher log.
        pass


class LocalServer(ThreadedWSGIServer):
    # server_close waits for workers before the SQLite directory is removed.
    daemon_threads = False

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            # Windows SO_REUSEADDR can allow a second process to bind the same port.
            self.allow_reuse_address = False
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def open_local_socket(server):
    address = server.server_address
    if address[0] != HOST:
        raise RuntimeError("The chat probe requires an IPv4 loopback server.")
    sock = socket.socket()
    try:
        sock.settimeout(SOCKET_TIMEOUT)
        _connect(sock, address)
        return sock
    except BaseException:
        sock.close()
        raise


class LocalHTTPConnection(HTTPConnection):
    def __init__(self, server):
        self.server = server
        super().__init__(*server.server_address, timeout=SOCKET_TIMEOUT)

    def connect(self):
        self.sock = open_local_socket(self.server)


@contextmanager
def running_server(server):
    worker = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.2})
    worker.start()
    try:
        yield worker
    finally:
        server.shutdown()
        worker.join()


def probe_login(server):
    with closing(LocalHTTPConnection(server)) as connection:
        connection.request("GET", "/login.html")
        with connection.getresponse() as response:
            body = response.read()
            if (response.status != 200 or not response.headers.get("Content-Type", "").startswith("text/html")
                    or b'name="identifier"' not in body or b'name="csrfmiddlewaretoken"' not in body):
                raise RuntimeError(f"Login readiness probe failed (HTTP {response.status}).")
            return response.status, len(body)


def smoke_login(server):
    # Leave a speculative browser-style connection open while a second socket
    # loads the login page. The old serial WSGI server stalled here.
    with open_local_socket(server):
        status, size = probe_login(server)
        with closing(LocalHTTPConnection(server)) as connection:
            connection.request("HEAD", "/login.html")
            with connection.getresponse() as response:
                head_status = response.status
                # The existing Django login view accepts GET and POST only.
                allowed = set(response.headers.get("Allow", "").replace(" ", "").split(","))
                if head_status != 405 or allowed != {"GET", "POST"} or response.read():
                    raise RuntimeError(f"Login HEAD smoke check failed (HTTP {response.status}).")
    print(f"Smoke passed with idle connection: GET /login.html {status} ({size} bytes), "
          f"HEAD /login.html {head_status} (Allow: GET, POST).",
          flush=True)


def configure(stack, directory):
    from django.conf import settings
    from django.db.backends.base.base import BaseDatabaseWrapper
    from django.db.backends.mysql.base import Database

    connect = BaseDatabaseWrapper.ensure_connection

    def sqlite_only(wrapper):
        if wrapper.vendor != "sqlite" or wrapper.alias != "default":
            raise RuntimeError("Chat acceptance requires SQLite.")
        name = str(wrapper.settings_dict["NAME"])
        if name not in (database, "file:memorydb_default?mode=memory&cache=shared"):
            raise RuntimeError("Unexpected SQLite database for chat acceptance.")
        return connect(wrapper)

    database = str(directory / "chat.sqlite3")
    stack.enter_context(patch.dict(os.environ, {"DJANGO_SETTINGS_MODULE": "config.settings", "DJANGO_DEBUG": "true",
                                                "DJANGO_SECRET_KEY": token_urlsafe(48)}, clear=True))
    stack.enter_context(patch("dotenv.load_dotenv", return_value=False))
    stack.enter_context(patch.object(BaseDatabaseWrapper, "ensure_connection", sqlite_only))
    stack.enter_context(patch.object(Database, "connect", side_effect=RuntimeError("MySQL is forbidden.")))
    stack.enter_context(block_network())

    settings.DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": database}}
    settings.AI_CHAT_ENABLED = True
    settings.AI_PROVIDER = "mock"
    settings.AI_PAID_CALLS_APPROVED = False
    settings.AI_RAG_ENABLED = False
    settings.AI_RAG_DIRECTORY = directory / "vectors"
    settings.AI_ASSISTANCE_ENABLED = True
    settings.AI_CHAT_SPA_INFORMATION = "Giờ mở cửa của Spa kiểm thử: 09:00–21:00."
    settings.SESSION_COOKIE_NAME = "annhien_chat_acceptance_session"
    settings.CSRF_COOKIE_NAME = "annhien_chat_acceptance_csrftoken"
    settings.MEDIA_ROOT = directory / "media"
    settings.STATIC_ROOT = directory / "collected-static"
    settings.STATIC_ROOT.mkdir()
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

    import django
    django.setup()
    from billing import gateway
    from django.db import connections

    stack.callback(connections.close_all)
    for name in ("client", "create", "get", "cancel", "verify"):
        stack.enter_context(patch.object(gateway, name, side_effect=RuntimeError("PayOS is forbidden.")))


def seed(password):
    from django.contrib.auth.models import Permission
    from accounts.models import Customer, User
    from services.models import Service, ServiceCategory

    user = User.objects.create_user("chat_demo_user", "chat-user@example.test", password)
    Customer.objects.create(user=user, full_name="Khách kiểm thử Chatbot", phone="0000000000")
    admin = User.objects.create_user("chat_demo_admin", "chat-admin@example.test", password, role=User.Role.ADMIN)
    admin.user_permissions.add(Permission.objects.get(content_type__app_label="ai_features", codename="read_chat_history"))
    admin.user_permissions.add(Permission.objects.get(content_type__app_label="ai_features", codename="change_aireviewanalysis"))
    User.objects.create_superuser("chat_demo_unassigned", "chat-unassigned@example.test", password)
    category = ServiceCategory.objects.create(name="Danh mục thử Chatbot")
    Service.objects.create(category=category, name="Massage thử Chatbot", description="Dữ liệu kiểm thử.",
                           price=390000, duration_minutes=60)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("test", "serve", "smoke"))
    parser.add_argument("labels", nargs="*")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="annhien-chat-") as folder, ExitStack() as stack:
        configure(stack, Path(folder))
        from django.core.management import call_command

        if args.mode == "test":
            call_command("test", *(args.labels or ["ai_features", "core.tests", "core.test_models"]), interactive=False)
            return

        from django.contrib.staticfiles.handlers import StaticFilesHandler
        from django.core.wsgi import get_wsgi_application

        password = token_urlsafe(24) if args.mode == "smoke" else getpass("Temporary demo password: ")
        if not password:
            parser.error("A temporary password is required.")
        port = 0 if args.mode == "smoke" else PORT
        with LocalServer((HOST, port), LocalRequests) as server:
            call_command("migrate", interactive=False, verbosity=0)
            seed(password)
            server.set_app(StaticFilesHandler(get_wsgi_application()))
            with running_server(server) as worker:
                if args.mode == "smoke":
                    smoke_login(server)
                    return
                status, size = probe_login(server)
                print(f"Ready http://{HOST}:{PORT} | GET /login.html {status} ({size} bytes) | "
                      "dedicated SQLite | mock provider | Ctrl+C to stop", flush=True)
                wait = Event()
                while worker.is_alive():
                    # A bounded wait lets the Windows main thread receive Ctrl+C
                    # while the worker handles requests or waits for connections.
                    wait.wait(0.2)
                raise RuntimeError("The chat HTTP server stopped unexpectedly.")


if __name__ == "__main__":
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, signal.default_int_handler)
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped. Temporary chat data cleaned up.", flush=True)
