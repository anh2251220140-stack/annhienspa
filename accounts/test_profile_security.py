from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import authenticate
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import path, reverse
from PIL import Image

from config.local_media import local_image
from .models import Customer, User


# Route the conditional local media endpoint through Django's test client.
urlpatterns = [path("media/<path:path>", local_image)]


class ProfilePasswordTests(TestCase):
    current_password = "OldExample!5472"
    new_password = "NewExample!6298"

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("profileowner", "owner@example.test", cls.current_password)
        Customer.objects.create(user=cls.user, full_name="Khách kiểm thử", phone="0900000000")
        cls.admin = User.objects.create_superuser("profileadmin", "admin@example.test", cls.current_password)

    def post_change(self, client=None, **overrides):
        payload = {
            "old_password": self.current_password,
            "new_password1": self.new_password,
            "new_password2": self.new_password,
            **overrides,
        }
        return (client or self.client).post(reverse("accounts:password_change"), payload)

    def test_requires_user_role_post_and_csrf(self):
        self.assertEqual(self.post_change().status_code, 401)
        self.client.force_login(self.admin)
        self.assertEqual(self.post_change().status_code, 403)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.assertEqual(csrf_client.get(reverse("accounts:password_change")).status_code, 405)
        self.assertEqual(self.post_change(client=csrf_client).status_code, 403)
        self.assertEqual(csrf_client.get("/profile.html").status_code, 200)
        token = csrf_client.cookies["csrftoken"].value
        self.assertEqual(self.post_change(client=csrf_client, csrfmiddlewaretoken=token).status_code, 200)
        self.assertEqual(csrf_client.get("/profile.html").status_code, 200)

    def test_invalid_passwords_leave_account_unchanged(self):
        self.client.force_login(self.user)
        original_hash = self.user.password
        cases = (
            ({"old_password": "wrong"}, "old_password", "Mật khẩu hiện tại không chính xác."),
            ({"new_password2": "different"}, "new_password2", "Xác nhận mật khẩu mới không khớp."),
            ({"new_password1": "123", "new_password2": "123"}, "new_password2", "Mật khẩu mới phải có ít nhất 8 ký tự."),
            ({"new_password1": "A" * 129, "new_password2": "A" * 129}, "new_password1", "Mật khẩu mới không được vượt quá 128 ký tự."),
        )
        for payload, field, message in cases:
            with self.subTest(field=field, message=message):
                response = self.post_change(**payload)
                self.assertEqual(response.status_code, 400)
                errors = response.json()["errors"][field]
                self.assertIn(message, errors)
                self.user.refresh_from_db()
                self.assertEqual(self.user.password, original_hash)

    def test_changes_only_owner_password_rotates_session_and_invalidates_other_session(self):
        other_session = Client()
        other_session.force_login(self.user)
        self.client.force_login(self.user)
        previous_session = self.client.session.session_key
        self.assertEqual(self.post_change(user_id=self.admin.pk).status_code, 200)
        self.assertNotEqual(self.client.session.session_key, previous_session)
        self.assertEqual(self.client.get("/profile.html").status_code, 200)
        self.assertEqual(other_session.get("/profile.html").status_code, 302)
        self.assertIsNone(authenticate(username=self.user.username, password=self.current_password))
        self.assertEqual(authenticate(username=self.user.username, password=self.new_password), self.user)
        self.user.refresh_from_db()
        self.admin.refresh_from_db()
        self.assertNotEqual(self.user.password, self.new_password)
        self.assertTrue(self.admin.check_password(self.current_password))


class ProfileAvatarTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("avatarowner", "avatar@example.test", "AvatarExample!5831")
        cls.customer = Customer.objects.create(user=cls.owner, full_name="Khách kiểm thử", phone="0900000000")
        cls.other = User.objects.create_user("otheravatar", "other@example.test", "OtherExample!1698")
        cls.admin = User.objects.create_superuser("avataradmin", "avataradmin@example.test", "AdminExample!8261")

    def test_uploaded_avatar_bytes_and_loopback_permissions(self):
        image = BytesIO()
        Image.new("RGB", (8, 8), "brown").save(image, "PNG")
        data = image.getvalue()
        with TemporaryDirectory() as directory, self.settings(MEDIA_ROOT=directory, LOCAL_MEDIA_ENABLED=True):
            self.client.force_login(self.owner)
            response = self.client.post("/api/profile/", {
                "name": self.customer.full_name,
                "username": self.owner.username,
                "email": self.owner.email,
                "phone": self.customer.phone,
                "avatar": SimpleUploadedFile("portrait.png", data, content_type="image/png"),
            })
            self.assertEqual(response.status_code, 200)
            self.customer.refresh_from_db()
            avatar_name = self.customer.avatar.name
            self.assertTrue(avatar_name.startswith("avatars/"))
            self.assertEqual(response.json()["item"]["avatar"], "/media/" + avatar_name)
            self.assertEqual((Path(directory) / avatar_name).read_bytes(), data)

            url = "/media/" + avatar_name
            admin_client = Client()
            admin_client.force_login(self.admin)
            other_client = Client()
            other_client.force_login(self.other)
            with self.settings(ROOT_URLCONF=__name__):
                for client in (self.client, admin_client):
                    result = client.get(url, HTTP_HOST="localhost")
                    self.assertEqual(result.status_code, 200)
                    self.assertEqual(result.headers["Content-Type"], "image/png")
                    self.assertEqual(b"".join(result.streaming_content), data)
                self.assertEqual(other_client.get(url, HTTP_HOST="localhost").status_code, 404)
                for headers in ({"HTTP_X_FORWARDED_FOR": "127.0.0.1"},
                                {"REMOTE_ADDR": "192.0.2.1"}):
                    self.assertEqual(self.client.get(url, HTTP_HOST="localhost", **headers).status_code, 404)
                with self.settings(LOCAL_MEDIA_ENABLED=False):
                    self.assertEqual(self.client.get(url, HTTP_HOST="localhost").status_code, 404)
