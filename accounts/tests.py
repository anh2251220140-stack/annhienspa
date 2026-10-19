from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.test import TestCase, Client
from .models import Customer

User = get_user_model()

class AuthenticationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("lananh", "lananh@example.com", "StrongTest!9372")
        Customer.objects.create(user=cls.user, full_name="Lan Anh", phone="0900000000")
        cls.admin = User.objects.create_superuser("manager", "manager@example.com", "StrongTest!9372")

    def registration(self, **overrides):
        data = {"fullName": "Khách mới", "username": "newuser", "email": "new@example.com",
                "phone": "0901234567", "password": "SecurePass!5492", "confirmPassword": "SecurePass!5492"}
        data.update(overrides)
        return self.client.post("/register.html", data)

    def test_registration_hash_and_customer_role(self):
        response = self.registration(role="Admin", is_staff="true", is_superuser="true")
        self.assertRedirects(response, "/login.html?registered=success")
        user = User.objects.get(username="newuser")
        self.assertTrue(user.check_password("SecurePass!5492"))
        self.assertNotEqual(user.password, "SecurePass!5492")
        self.assertEqual(user.role, "User")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.customer.full_name, "Khách mới")

    def test_duplicate_email_and_username_case_insensitive(self):
        for data in ({"email": "LANANH@example.com"}, {"username": "LANANH"}):
            response = self.registration(**data)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].errors)
        self.assertEqual(User.objects.count(), 2)

    def test_invalid_password_confirmation_and_required_fields(self):
        for data in ({"confirmPassword": "mismatch"}, {"password": "12345678", "confirmPassword": "12345678"},
                     {"fullName": ""}, {"email": "not-email"}, {"phone": ""}):
            response = self.registration(**data)
            self.assertTrue(response.context["form"].errors)
        self.assertEqual(User.objects.count(), 2)

    def test_login_username_email_roles_and_session(self):
        for identifier, expected in [("LANANH", "/home.html"), ("LANANH@example.com", "/home.html"), ("manager", "/admin-dashboard.html")]:
            response = self.client.post("/login.html", {"identifier": identifier, "password": "StrongTest!9372"})
            self.assertRedirects(response, expected)
            self.assertIn("_auth_user_id", self.client.session)
            self.assertTrue(Session.objects.filter(session_key=self.client.session.session_key).exists())
            self.client.post("/accounts/logout/")

    def test_invalid_inactive_and_demo_login_rejected(self):
        for identifier, password in [("lananh", "wrong"), ("admin", "Admin@123"), ("user", "User@123")]:
            response = self.client.post("/login.html", {"identifier": identifier, "password": password})
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("_auth_user_id", self.client.session)
        self.user.is_active = False
        self.user.save()
        self.client.post("/login.html", {"identifier": "lananh", "password": "StrongTest!9372"})
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_csrf_required_for_all_auth_posts(self):
        client = Client(enforce_csrf_checks=True)
        for url in ("/login.html", "/register.html", "/accounts/logout/"):
            self.assertEqual(client.post(url, {}).status_code, 403)
        client.get("/login.html")
        token = client.cookies["csrftoken"].value
        response = client.post("/login.html", {"identifier": "lananh", "password": "StrongTest!9372", "csrfmiddlewaretoken": token})
        self.assertEqual(response.status_code, 302)
        old_key = client.session.session_key
        self.assertEqual(client.get("/accounts/logout/").status_code, 405)
        self.assertEqual(client.post("/accounts/logout/", {"csrfmiddlewaretoken": client.cookies["csrftoken"].value}).status_code, 302)
        self.assertFalse(Session.objects.filter(session_key=old_key).exists())
        self.assertNotIn("_auth_user_id", client.session)

    def test_open_redirect_ignored_and_no_credentials_in_response(self):
        response = self.client.post("/login.html?next=https://example.com", {"identifier": "lananh", "password": "StrongTest!9372"})
        self.assertEqual(response.url, "/home.html")
        self.assertNotContains(self.client.get("/home.html"), "StrongTest!9372")

    def test_inactive_session_loses_access(self):
        self.client.force_login(self.user)
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        self.assertEqual(self.client.get("/home.html").status_code, 302)

    def test_register_rollback_if_customer_creation_fails(self):
        from unittest.mock import patch
        from django.db import IntegrityError
        with patch("accounts.forms.Customer.objects.create", side_effect=IntegrityError("test failure")):
            response = self.registration()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="newuser").exists())

    def test_logout_modal_keeps_existing_interface(self):
        self.client.force_login(self.user)
        response = self.client.get("/home.html")
        self.assertContains(response, 'id="spa-logout-form"')
        self.assertContains(response, 'action="/accounts/logout/"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertIn("no-store", response.headers["Cache-Control"])
