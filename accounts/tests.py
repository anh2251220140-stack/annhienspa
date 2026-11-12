from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from PIL import Image
from .models import Customer

User = get_user_model()
INTERNATIONAL_PHONE_AT_LIMIT = "+84 (90) 1234-567890"
PASSWORD_AT_LIMIT = " " + ("M9!kT7_wR3#qV2%z" * 8)[:126] + " "

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
        self.assertEqual(len(INTERNATIONAL_PHONE_AT_LIMIT), 20)
        self.assertEqual(len(PASSWORD_AT_LIMIT), 128)
        shared_phone = self.user.customer.phone
        cases = (
            ("newuser", "0901234567", "SecurePass!5492"),
            ("international", INTERNATIONAL_PHONE_AT_LIMIT, PASSWORD_AT_LIMIT),
            ("sharedphone", shared_phone, "SecurePass!5492"),
        )
        for username, phone, password in cases:
            with self.subTest(username=username):
                response = self.registration(
                    username=username, email=f"{username}@example.com", phone=f"  {phone}  ",
                    password=password, confirmPassword=password, role="Admin", is_staff="true", is_superuser="true",
                )
                self.assertRedirects(response, "/login.html?registered=success")
                user = User.objects.get(username=username)
                self.assertTrue(user.check_password(password))
                self.assertNotEqual(user.password, password)
                self.assertEqual(user.role, "User")
                self.assertFalse(user.is_staff)
                self.assertFalse(user.is_superuser)
                self.assertEqual(user.customer.full_name, "Khách mới")
                self.assertEqual(user.customer.phone, phone)
        self.assertEqual(Customer.objects.filter(phone=shared_phone).count(), 2)

    def test_duplicate_email_and_username_case_insensitive(self):
        for data in ({"email": "LANANH@example.com"}, {"username": "LANANH"}):
            response = self.registration(**data)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(set(response.context["form"].errors), set(data))
        self.assertEqual(User.objects.count(), 2)
        self.assertEqual(Customer.objects.count(), 1)

    def test_invalid_password_confirmation_and_required_fields(self):
        for data in ({"confirmPassword": "mismatch"}, {"password": "12345678", "confirmPassword": "12345678"},
                     {"fullName": ""}, {"email": "not-email"}, {"phone": ""}):
            response = self.registration(**data)
            self.assertTrue(response.context["form"].errors)
        self.assertEqual(User.objects.count(), 2)
        self.assertEqual(Customer.objects.count(), 1)

        long_password = PASSWORD_AT_LIMIT + "!"
        cases = [
            ({"phone": " \t "}, {"phone": "required"}),
            ({"phone": INTERNATIONAL_PHONE_AT_LIMIT + "1"}, {"phone": "max_length"}),
            ({"password": long_password}, {"password": "max_length"}),
            ({"confirmPassword": long_password}, {"confirmPassword": "max_length"}),
            ({"password": long_password, "confirmPassword": long_password},
             {"password": "max_length", "confirmPassword": "max_length"}),
        ]
        invalid_phones = ("abcdef", "--- ( )", "090@123", "090+123", "++84901234567", "(090123", "090123)", "(09-0)")
        cases.extend(({"phone": phone}, {"phone": "invalid_phone"}) for phone in invalid_phones)
        error_ids = {"phone": "phone-error", "password": "password-error", "confirmPassword": "confirm-password-error"}
        for index, (data, expected_errors) in enumerate(cases):
            with self.subTest(case=index, fields=tuple(expected_errors)):
                response = self.registration(**data)
                self.assertEqual(response.status_code, 200)
                errors = response.context["form"].errors
                self.assertEqual({field: [error.code for error in entries] for field, entries in errors.as_data().items()},
                                 {field: [code] for field, code in expected_errors.items()})
                for field in expected_errors:
                    self.assertContains(response, f'<span id="{error_ids[field]}" class="field-error" '
                                                  f'data-field-error="{field}" aria-live="polite">{errors[field][0]}</span>', html=True)
                self.assertEqual(User.objects.count(), 2)
                self.assertEqual(Customer.objects.count(), 1)

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
        self.assertEqual(Customer.objects.count(), 1)

    def test_logout_modal_keeps_existing_interface(self):
        self.client.force_login(self.user)
        response = self.client.get("/home.html")
        self.assertContains(response, 'id="spa-logout-form"')
        self.assertContains(response, 'action="/accounts/logout/"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertIn("no-store", response.headers["Cache-Control"])


class ProfilePhoneTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("profilephone", "profilephone@example.test", "ProfilePass!5831")
        cls.customer = Customer.objects.create(user=cls.user, full_name="Khách kiểm thử", phone="0900000000")

    def update_profile(self, **overrides):
        return self.client.post("/api/profile/", {
            "name": self.customer.full_name,
            "username": self.user.username,
            "email": self.user.email,
            **overrides,
        })

    def test_registration_and_profile_accept_the_same_numbers(self):
        for index, phone in enumerate(("12345", INTERNATIONAL_PHONE_AT_LIMIT, self.customer.phone)):
            with self.subTest(phone=phone):
                username = f"registerphone{index}"
                response = self.client.post("/register.html", {
                    "fullName": "Khách đăng ký",
                    "username": username,
                    "email": f"{username}@example.test",
                    "phone": f"  {phone}  ",
                    "password": "SecurePass!5492",
                    "confirmPassword": "SecurePass!5492",
                })
                self.assertRedirects(response, "/login.html?registered=success")
                self.client.force_login(self.user)
                response = self.update_profile(phone=f"  {phone}  ", name="Tên đã cập nhật")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["item"]["phone"], phone)
                self.customer.refresh_from_db()
                self.assertEqual(self.customer.phone, phone)
                self.assertEqual(self.customer.full_name, "Tên đã cập nhật")
                self.assertEqual(Customer.objects.filter(phone=phone).count(), 2)
                self.client.logout()

    def test_registration_and_profile_reject_the_same_invalid_numbers(self):
        profile_client = self.client
        profile_client.force_login(self.user)
        registration_client = Client()
        for phone in ("", " \t ", "--------", "090+123", "(090123", "abcdef", INTERNATIONAL_PHONE_AT_LIMIT + "1"):
            with self.subTest(phone=phone):
                registration = registration_client.post("/register.html", {
                    "fullName": "Khách đăng ký",
                    "username": "invalidphone",
                    "email": "invalidphone@example.test",
                    "phone": phone,
                    "password": "SecurePass!5492",
                    "confirmPassword": "SecurePass!5492",
                })
                errors = list(registration.context["form"].errors["phone"])
                self.assertTrue(errors)
                profile = self.update_profile(phone=phone, name="Không được lưu")
                self.assertEqual(profile.status_code, 400)
                self.assertEqual(profile.json()["errors"]["phone"], errors)
                self.customer.refresh_from_db()
                self.assertEqual(self.customer.phone, "0900000000")
                self.assertEqual(self.customer.full_name, "Khách kiểm thử")
                self.assertFalse(User.objects.filter(username="invalidphone").exists())

    def test_legacy_phone_is_preserved_when_saving_care_and_avatar(self):
        self.client.force_login(self.user)
        image = BytesIO()
        Image.new("RGB", (8, 8), "brown").save(image, "PNG")
        png = image.getvalue()
        with TemporaryDirectory() as directory, self.settings(MEDIA_ROOT=directory):
            for legacy in ("", "  --------  "):
                with self.subTest(legacy=legacy):
                    Customer.objects.filter(pk=self.customer.pk).update(phone=legacy)
                    response = self.update_profile(skin="Da khô", needs=["Dưỡng ẩm"], budget="300000")
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json()["item"]["phone"], legacy)
                    response = self.update_profile(
                        phone=legacy.strip(), skin="Da dầu",
                        avatar=SimpleUploadedFile("portrait.png", png, content_type="image/png"),
                    )
                    self.assertEqual(response.status_code, 200)
                    self.customer.refresh_from_db()
                    self.assertEqual(self.customer.phone, legacy)
                    self.assertEqual(self.customer.skin_type, "Da dầu")
                    self.assertEqual((Path(directory) / self.customer.avatar.name).read_bytes(), png)
                    response = self.update_profile(phone="abc", skin="Da thường")
                    self.assertEqual(response.status_code, 400)
                    self.customer.refresh_from_db()
                    self.assertEqual(self.customer.phone, legacy)
                    self.assertEqual(self.customer.skin_type, "Da dầu")
                    self.assertEqual(self.update_profile(phone="12345").status_code, 200)
                    self.customer.refresh_from_db()
                    self.assertEqual(self.customer.phone, "12345")
