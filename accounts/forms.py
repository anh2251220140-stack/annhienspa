import re

from django import forms
from django.contrib.auth import authenticate, password_validation
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.validators import MaxLengthValidator
from django.db import transaction
from .models import User, Customer


class ProfilePasswordChangeForm(PasswordChangeForm):
    error_messages = {
        **PasswordChangeForm.error_messages,
        "password_incorrect": "Mật khẩu hiện tại không chính xác.",
        "password_mismatch": "Xác nhận mật khẩu mới không khớp.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.error_messages["required"] = "Vui lòng nhập đầy đủ các trường mật khẩu."
        for name in ("new_password1", "new_password2"):
            self.fields[name].validators.append(MaxLengthValidator(128, "Mật khẩu mới không được vượt quá 128 ký tự."))

    def validate_password_for_user(self, user, password_field_name="password2"):
        super().validate_password_for_user(user, password_field_name)
        # Django's Vietnamese catalog can fall back to English for this plural message.
        for error in self.errors.as_data().get(password_field_name, []):
            if error.code == "password_too_short":
                error.message = "Mật khẩu mới phải có ít nhất %(min_length)d ký tự."


class LoginForm(forms.Form):
    identifier = forms.CharField(max_length=254)
    password = forms.CharField(strip=False, widget=forms.PasswordInput)
    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        self.user = None
    def clean(self):
        data = super().clean()
        if data.get("identifier") and data.get("password"):
            self.user = authenticate(self.request, username=data["identifier"], password=data["password"])
            if self.user is None:
                raise forms.ValidationError("Thông tin đăng nhập không chính xác hoặc tài khoản đã bị khóa.")
        return data

class CustomerPhoneField(forms.CharField):
    def __init__(self):
        super().__init__(max_length=20, error_messages={
            "required": "Vui lòng nhập số điện thoại.",
            "max_length": "Số điện thoại không được vượt quá %(limit_value)d ký tự.",
        })

    def clean(self, value):
        value = super().clean(value)
        digit_or_group = r"(?:\d|\(\d+\))"
        if not re.fullmatch(rf"\+?{digit_or_group}(?: *(?:- *)?{digit_or_group})*", value):
            raise forms.ValidationError(
                "Số điện thoại không hợp lệ. Ví dụ: +84 (90) 123-4567.", code="invalid_phone",
            )
        return value


class RegistrationForm(forms.Form):
    fullName = forms.CharField(max_length=150)
    email = forms.EmailField(max_length=254)
    username = forms.CharField(max_length=150, validators=[UnicodeUsernameValidator()])
    phone = CustomerPhoneField()
    password = forms.CharField(
        max_length=128, strip=False, widget=forms.PasswordInput,
        error_messages={"max_length": "Mật khẩu không được vượt quá %(limit_value)d ký tự."},
    )
    confirmPassword = forms.CharField(
        max_length=128, strip=False, widget=forms.PasswordInput,
        error_messages={"max_length": "Xác nhận mật khẩu không được vượt quá %(limit_value)d ký tự."},
    )

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists() or User.objects.filter(username__iexact=email).exists():
            raise forms.ValidationError("Email đã được sử dụng.")
        return email

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username__iexact=username).exists() or User.objects.filter(email__iexact=username).exists():
            raise forms.ValidationError("Tên đăng nhập đã được sử dụng.")
        return username

    def clean(self):
        data = super().clean()
        if data.get("password") and data.get("confirmPassword") and data["password"] != data["confirmPassword"]:
            self.add_error("confirmPassword", "Xác nhận mật khẩu không khớp.")
        if data.get("password"):
            user = User(username=data.get("username", ""), email=data.get("email", ""))
            try:
                password_validation.validate_password(data["password"], user)
            except forms.ValidationError as error:
                self.add_error("password", error)
        return data

    @transaction.atomic
    def save(self):
        data = self.cleaned_data
        user = User.objects.create_user(username=data["username"], email=data["email"], password=data["password"], role=User.Role.USER)
        Customer.objects.create(user=user, full_name=data["fullName"], phone=data["phone"])
        return user
