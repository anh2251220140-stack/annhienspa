from django.conf import settings
from django.contrib.auth.models import AbstractUser, UserManager
from django.core.exceptions import ValidationError
from django.db import models
from core.models import ValidatedModel

class SpaUserManager(UserManager):
    def _create_user(self, username, email, password, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email).lower()
        return super()._create_user(username, email, password, **extra_fields)

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", "Admin")
        if extra_fields["role"] != "Admin":
            raise ValueError("Superuser must have role Admin")
        return super().create_superuser(username, email, password, **extra_fields)

class User(AbstractUser):
    class Role(models.TextChoices):
        USER = "User", "Khách hàng"
        ADMIN = "Admin", "Quản trị viên"
    email = models.EmailField(unique=True, max_length=254)
    password = models.CharField(max_length=255)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.USER)
    objects = SpaUserManager()
    REQUIRED_FIELDS = ["email"]

    class Meta:
        db_table = "users"
        constraints = [models.CheckConstraint(condition=models.Q(role__in=["User", "Admin"]), name="user_valid_role")]

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        return super().save(*args, **kwargs)

class Customer(ValidatedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="customer")
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20)
    avatar = models.ImageField(upload_to="avatars/", max_length=255, blank=True, null=True)
    skin_type = models.CharField(max_length=50, blank=True, null=True)
    care_needs = models.TextField(blank=True, null=True)
    preferences = models.TextField(blank=True, null=True)
    budget = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    class Meta:
        db_table = "customers"
        constraints = [models.CheckConstraint(condition=models.Q(budget__isnull=True) | models.Q(budget__gte=0), name="customer_budget_nonnegative")]
    def clean(self):
        if self.user_id and self.user.role != User.Role.USER:
            raise ValidationError({"user": "Hồ sơ khách hàng phải thuộc tài khoản User."})
