import re
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from .models import User

@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", PASSWORD_RESET_TIMEOUT=3600)
class PasswordResetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("resetuser", "reset@example.com", "OldPassword!765")
        self.request_url = reverse("accounts:password_reset")
        self.passwords = {"new_password1":"NewPassword!984", "new_password2":"NewPassword!984"}

    def link(self):
        return reverse("accounts:password_reset_confirm", kwargs={"uidb64":urlsafe_base64_encode(force_bytes(self.user.pk)), "token":default_token_generator.make_token(self.user)})

    def test_email_success_new_login_old_password_and_reuse(self):
        existing = Client();existing.force_login(self.user)
        before = self.user.password
        response = self.client.post(self.request_url, {"email":"RESET@example.com"})
        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox),1)
        self.user.refresh_from_db();self.assertEqual(self.user.password,before)
        link = re.search(r"http://testserver(/\S+)", mail.outbox[0].body).group(1)
        response = self.client.get(link);self.assertEqual(response.status_code,302)
        clean_url = response.url;self.assertIn("set-password",clean_url)
        self.assertContains(self.client.get(clean_url),'autocomplete="new-password"')
        self.assertRedirects(self.client.post(clean_url,self.passwords),reverse("accounts:password_reset_complete"))
        self.assertFalse(Client().login(username="resetuser",password="OldPassword!765"))
        self.assertTrue(Client().login(username="resetuser",password="NewPassword!984"))
        self.assertEqual(existing.get("/api/appointments/").status_code,401)
        self.assertFalse(self.client.get(link).context["validlink"])
        self.assertFalse(self.client.post(clean_url,self.passwords).context["validlink"])
        self.user.refresh_from_db();self.assertEqual(self.user.role,"User");self.assertTrue(self.user.is_active)

    def test_unknown_locked_and_unusable_same_response(self):
        locked=User.objects.create_user("locked","locked@example.com","OldPassword!765",is_active=False)
        unusable=User.objects.create_user("unusable","unusable@example.com",None)
        bodies=[]
        for address in (self.user.email,"missing@example.com",locked.email,unusable.email):
            response=self.client.post(self.request_url,{"email":address},follow=True)
            self.assertEqual(response.status_code,200)
            bodies.append(re.sub(r'name="csrfmiddlewaretoken" value="[^"]+"', 'name="csrfmiddlewaretoken"',response.content.decode()))
        self.assertTrue(all(body==bodies[0] for body in bodies))
        self.assertEqual(len(mail.outbox),1)

    def test_expired_and_invalid_tokens(self):
        now=default_token_generator._now()
        with patch.object(default_token_generator,"_now",return_value=now-timedelta(seconds=3601)):
            expired=self.link()
        for link in (expired,self.link().rstrip("/")+"broken/",reverse("accounts:password_reset_confirm",kwargs={"uidb64":"bad", "token":"bad"})):
            self.assertFalse(self.client.get(link).context["validlink"])
        self.user.refresh_from_db();self.assertTrue(self.user.check_password("OldPassword!765"))

    def test_locked_after_token_issued_and_before_submit(self):
        link=self.link();clean_url=self.client.get(link).url
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        self.assertFalse(self.client.post(clean_url,self.passwords).context["validlink"])
        self.assertFalse(self.client.get(link).context["validlink"])
        self.user.refresh_from_db();self.assertFalse(self.user.is_active);self.assertTrue(self.user.check_password("OldPassword!765"))

    def test_validation_and_csrf(self):
        clean_url=self.client.get(self.link()).url
        for data in ({"new_password1":"X!"*65,"new_password2":"X!"*65},{"new_password1":"123", "new_password2":"123"},{**self.passwords,"new_password2":"Different!987"}):
            response=self.client.post(clean_url,data);self.assertTrue(response.context["form"].errors)
        c=Client(enforce_csrf_checks=True)
        self.assertEqual(c.post(self.request_url,{"email":self.user.email}).status_code,403)
        clean_url=c.get(self.link()).url
        self.assertEqual(c.post(clean_url,self.passwords).status_code,403)
        self.user.refresh_from_db();self.assertTrue(self.user.check_password("OldPassword!765"))

    def test_admin_reset_does_not_change_privileges(self):
        self.user=User.objects.create_superuser("resetadmin","adminreset@example.com","OldPassword!765")
        clean_url=self.client.get(self.link()).url
        self.assertRedirects(self.client.post(clean_url,self.passwords),reverse("accounts:password_reset_complete"))
        self.user.refresh_from_db();self.assertTrue(self.user.check_password("NewPassword!984"));self.assertEqual(self.user.role,"Admin");self.assertTrue(self.user.is_superuser);self.assertTrue(self.user.is_staff)

    def test_login_link_and_reset_templates(self):
        self.assertContains(self.client.get("/login.html"),self.request_url)
        for name in ("password_reset","password_reset_done","password_reset_complete"):
            self.assertEqual(self.client.get(reverse("accounts:"+name)).status_code,200)
