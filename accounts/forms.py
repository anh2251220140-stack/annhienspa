from django import forms
from django.contrib.auth import authenticate, password_validation
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import transaction
from .models import User, Customer

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

class RegistrationForm(forms.Form):
    fullName = forms.CharField(max_length=150)
    email = forms.EmailField(max_length=254)
    username = forms.CharField(max_length=150, validators=[UnicodeUsernameValidator()])
    phone = forms.CharField(max_length=20)
    password = forms.CharField(strip=False, widget=forms.PasswordInput)
    confirmPassword = forms.CharField(strip=False, widget=forms.PasswordInput)

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
