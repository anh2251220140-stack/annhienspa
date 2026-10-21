"""Django reset flow with inactive-account and concurrent-use protection."""
from django.contrib.auth import views as auth_views
from django.contrib.auth.views import INTERNAL_RESET_SESSION_TOKEN
from django.contrib.auth.forms import SetPasswordForm
from django.core.validators import MaxLengthValidator
from django.db import transaction
from django.urls import reverse_lazy
from .models import User

TEMPLATE = "accounts/password_reset.html"

class ResetView(auth_views.PasswordResetView):
    template_name = TEMPLATE
    email_template_name = "accounts/password_reset_email.txt"
    subject_template_name = "accounts/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")
    title = "Quên mật khẩu?"
    extra_context = {"reset_stage": "request"}

class SpaSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Match the existing login form limit so every accepted password is usable.
        for field in self.fields.values():
            field.validators.append(MaxLengthValidator(128))
            field.widget.attrs["maxlength"] = 128

class ConfirmView(auth_views.PasswordResetConfirmView):
    form_class = SpaSetPasswordForm
    template_name = TEMPLATE
    success_url = reverse_lazy("accounts:password_reset_complete")
    title = "Đặt mật khẩu mới"
    extra_context = {"reset_stage": "confirm"}

    def get_user(self, uidb64):
        user = super().get_user(uidb64)
        return user if user and user.is_active and user.has_usable_password() else None

    def form_valid(self, form):
        # Recheck after locking: concurrent requests cannot reuse a token or undo a lock.
        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=self.user.pk)
            token = self.request.session.get(INTERNAL_RESET_SESSION_TOKEN)
            if not user.is_active or not user.has_usable_password() or not self.token_generator.check_token(user, token):
                self.validlink = False
                return self.render_to_response(self.get_context_data())
            form.user = user
            return super().form_valid(form)
