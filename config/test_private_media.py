"""Synthetic media tests; SimpleTestCase forbids all database queries."""
import importlib
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.backends.signed_cookies import SessionStore
from django.http import Http404
from django.test import Client, RequestFactory, SimpleTestCase, override_settings
from django.urls import clear_url_caches, path, resolve
from PIL import Image

from accounts.models import Customer, User
from config.local_media import local_image
from config.private_media import docker_image

urlpatterns = [path("media/<path:path>", docker_image)]


@override_settings(DOCKER_MEDIA_ENABLED=True, ROOT_URLCONF=__name__, ALLOWED_HOSTS=["testserver"])
class DockerMediaTests(SimpleTestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(prefix="private-media-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.override = override_settings(MEDIA_ROOT=self.root)
        self.override.enable()
        self.addCleanup(self.override.disable)
        for folder in ("avatars", "services", "products", "employees"):
            (self.root / folder).mkdir()
            Image.new("RGB", (12, 12), "green").save(self.root / folder / "fixture.png")
        self.owner = User(pk=11, username="synthetic-owner", role="User", is_active=True)
        self.owner.customer = Customer(user=self.owner, avatar="avatars/fixture.png")
        self.other = User(pk=12, username="synthetic-other", role="User", is_active=True)
        self.other.customer = Customer(user=self.other, avatar="avatars/other.png")
        self.admin = User(pk=13, username="synthetic-admin", role="Admin", is_active=True)
        self.factory = RequestFactory()

    def request(self, user, name="avatars/fixture.png", method="get"):
        request = getattr(self.factory, method)("/media/" + name,
                    REMOTE_ADDR="172.20.0.3", HTTP_X_FORWARDED_FOR="127.0.0.1")
        request.user = user
        return docker_image(request, name)

    def allowed(self, user, name="avatars/fixture.png"):
        response = self.request(user, name)
        self.addCleanup(response.close)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        return response

    def test_owner_get(self):
        self.allowed(self.owner)

    def test_active_admin_get(self):
        self.allowed(self.admin)

    def test_anonymous_cannot_get_avatar(self):
        with self.assertRaises(Http404):
            self.request(AnonymousUser())

    def test_other_customer_cannot_get_avatar(self):
        with self.assertRaises(Http404):
            self.request(self.other)

    def test_inactive_owner_and_admin_denied(self):
        for user in (self.owner, self.admin):
            with self.subTest(role=user.role), self.assertRaises(Http404):
                user.is_active = False
                self.request(user)

    def test_user_without_customer_denied(self):
        user = SimpleNamespace(is_authenticated=True, is_active=True, role="User", customer=None)
        with self.assertRaises(Http404):
            self.request(user)

    def test_other_role_denied(self):
        user = SimpleNamespace(is_authenticated=True, is_active=True, role="Employee")
        with self.assertRaises(Http404):
            self.request(user)

    def test_public_service_product_employee_images(self):
        for folder in ("services", "products", "employees"):
            with self.subTest(folder=folder):
                self.allowed(AnonymousUser(), folder + "/fixture.png")

    def test_cache_and_security_headers(self):
        response = self.allowed(self.owner)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertIn("sandbox", response["Content-Security-Policy"])

    def test_only_get_head(self):
        for method in ("post", "put", "patch", "delete", "options"):
            with self.subTest(method=method):
                self.assertEqual(self.request(self.owner, method=method).status_code, 405)

    @override_settings(SESSION_ENGINE="django.contrib.sessions.backends.signed_cookies")
    def test_head_checks_permission_and_returns_no_body(self):
        with patch("accounts.backends.IdentifierBackend.get_user", return_value=self.owner):
            client = self.authenticated_client(self.owner)
            response = client.head("/media/avatars/fixture.png")
            self.addCleanup(response.close)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(b"".join(response.streaming_content), b"")
            self.assertGreater(int(response["Content-Length"]), 0)
        self.assertEqual(Client().head("/media/avatars/fixture.png").status_code, 404)

    def authenticated_client(self, user):
        # Real SessionMiddleware + AuthenticationMiddleware, signed cookie only.
        # No force_login: it would emit last_login and write a user record.
        session = SessionStore()
        session[SESSION_KEY] = str(user.pk)
        session[BACKEND_SESSION_KEY] = "accounts.backends.IdentifierBackend"
        session[HASH_SESSION_KEY] = user.get_session_auth_hash()
        session.save()
        client = Client()
        client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key
        return client

    @override_settings(SESSION_ENGINE="django.contrib.sessions.backends.signed_cookies")
    def test_authenticated_session_owner_and_other(self):
        for user, status in ((self.owner, 200), (self.other, 404), (self.admin, 200)):
            with self.subTest(role=user.username), patch(
                    "accounts.backends.IdentifierBackend.get_user", return_value=user):
                response = self.authenticated_client(user).get("/media/avatars/fixture.png")
                self.addCleanup(response.close)
                self.assertEqual(response.status_code, status)

    def test_invalid_and_traversal_paths(self):
        for name in ("../fixture.png", "avatars/../products/fixture.png",
                     "/avatars/fixture.png", "avatars//fixture.png", "avatars/.hidden.png",
                     "avatars\\fixture.png", "avatars/%2e%2e/fixture.png", "avatars/x:fixture.png",
                     "avatars/\x00.png", "unknown/fixture.png", "avatars", "avatars/"):
            with self.subTest(name=name), self.assertRaises(Http404):
                self.request(self.admin, name)

    def test_missing_file_and_directory(self):
        for name in ("avatars/missing.png", "services/missing.png", "services"):
            with self.subTest(name=name), self.assertRaises(Http404):
                self.request(self.admin, name)

    def test_reject_corrupt_image(self):
        (self.root / "services/bad.png").write_bytes(b"not an image")
        with self.assertRaises(Http404):
            self.request(self.admin, "services/bad.png")

    def test_reject_mime_extension_mismatch(self):
        (self.root / "services/bad.jpg").write_bytes((self.root / "services/fixture.png").read_bytes())
        with self.assertRaises(Http404):
            self.request(self.admin, "services/bad.jpg")

    def test_reject_active_content(self):
        (self.root / "services/bad.svg").write_text("<svg/>", encoding="utf-8")
        with self.assertRaises(Http404):
            self.request(self.admin, "services/bad.svg")

    def test_reject_oversized_file(self):
        with (self.root / "services/large.png").open("wb") as file:
            file.truncate(20 * 1024 * 1024 + 1)
        with self.assertRaises(Http404):
            self.request(self.admin, "services/large.png")

    def test_symlink_to_private_and_outside_is_denied(self):
        for name, target in (("private.png", self.root / "avatars/fixture.png"),
                             ("outside.png", self.root.parent / "outside.png")):
            link = self.root / "services" / name
            try:
                link.symlink_to(target)
            except OSError:
                self.skipTest("OS does not permit creating test symlinks")
            with self.subTest(name=name), self.assertRaises(Http404):
                self.request(self.admin, "services/" + name)

    def test_symlink_directory_denied(self):
        try:
            (self.root / "services/alias").symlink_to(self.root / "avatars", target_is_directory=True)
        except OSError:
            self.skipTest("OS does not permit creating test symlinks")
        with self.assertRaises(Http404):
            self.request(self.admin, "services/alias/fixture.png")

    @override_settings(DOCKER_MEDIA_ENABLED=False)
    def test_docker_view_disabled_outside_docker_mode(self):
        with self.assertRaises(Http404):
            self.request(self.owner)

    @override_settings(LOCAL_MEDIA_ENABLED=True)
    def test_original_local_guard_still_rejects_proxy(self):
        request = self.factory.get("/media/avatars/fixture.png", REMOTE_ADDR="127.0.0.1",
                                   HTTP_X_FORWARDED_FOR="127.0.0.1")
        request.user = self.owner
        with self.assertRaises(Http404):
            local_image(request, "avatars/fixture.png")

    def test_routing_docker_then_original_windows_mode(self):
        import config.urls
        try:
            for docker, local, expected in ((True, True, docker_image),
                                             (False, True, local_image)):
                with override_settings(DOCKER_MEDIA_ENABLED=docker, LOCAL_MEDIA_ENABLED=local,
                                       ROOT_URLCONF="config.urls"):
                    importlib.reload(config.urls)
                    clear_url_caches()
                    self.assertIs(resolve("/media/avatars/fixture.png").func, expected)
        finally:
            importlib.reload(config.urls)
            clear_url_caches()
