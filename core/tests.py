import hashlib
import json
from html.parser import HTMLParser
from urllib.parse import urlsplit
from django.conf import settings
from django.contrib.staticfiles import finders
from django.test import TestCase, SimpleTestCase
from accounts.models import User
from core.pages import PAGES
from core.views import PUBLIC_PAGES

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in ("href", "src", "action") and value:
                self.links.append(value)

class SourcePreservationTests(SimpleTestCase):
    def test_original_sources_and_visual_assets_unchanged(self):
        manifest = json.loads((settings.BASE_DIR / "docs/frontend-manifest.json").read_text(encoding="utf-8"))
        for name, expected in manifest.items():
            with self.subTest(file=name):
                self.assertEqual(hashlib.sha256((settings.BASE_DIR / name).read_bytes()).hexdigest(), expected)
                if name.startswith(("css/", "images/")):
                    self.assertEqual(hashlib.sha256((settings.BASE_DIR / "static" / name).read_bytes()).hexdigest(), expected)

class PageAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("viewer", "viewer@example.com", "StrongTest!9372")
        cls.admin = User.objects.create_superuser("manager", "manager@example.com", "StrongTest!9372")

    def test_all_27_pages_render_for_correct_role_and_static_resources(self):
        self.assertEqual(len(PAGES), 27)
        for page in PAGES:
            self.client.logout()
            if page not in PUBLIC_PAGES | {"login.html", "register.html"}:
                self.client.force_login(self.admin if page.startswith("admin-") else self.user)
            response = self.client.get("/" + page)
            with self.subTest(page=page):
                self.assertEqual(response.status_code, 200)
                parsed = Links()
                parsed.feed(response.content.decode())
                for link in parsed.links:
                    path = urlsplit(link).path
                    if path.startswith("/static/"):
                        self.assertIsNotNone(finders.find(path[8:]), link)
                    if path.endswith(".html"):
                        self.assertIn(path.lstrip("/"), PAGES)
                self.assertContains(response, 'id="spa-auth-context"')

    def test_guest_cannot_open_any_protected_page(self):
        for page in PAGES:
            if page not in PUBLIC_PAGES | {"login.html", "register.html"}:
                response = self.client.get("/" + page)
                self.assertEqual(response.status_code, 302, page)
                self.assertTrue(response.url.startswith("/login.html"))

    def test_user_cannot_open_any_admin_page_even_with_fake_cookie(self):
        self.client.force_login(self.user)
        self.client.cookies["spa-auth"] = '{"role":"Admin","authenticated":true}'
        for page in PAGES:
            if page.startswith("admin-"):
                self.assertEqual(self.client.get("/" + page).status_code, 403, page)

    def test_admin_cannot_open_customer_private_pages(self):
        self.client.force_login(self.admin)
        for page in ("home.html", "profile.html", "booking.html", "appointments.html", "invoice.html", "reviews.html"):
            self.assertEqual(self.client.get("/" + page).status_code, 403)

    def test_production_guard_and_authenticated_landing(self):
        with self.settings(DEBUG=False):
            self.assertEqual(self.client.get("/home.html").status_code, 302)
            self.client.force_login(self.user)
            self.assertRedirects(self.client.get("/"), "/home.html")
            self.assertEqual(self.client.get("/admin-dashboard.html").status_code, 403)
