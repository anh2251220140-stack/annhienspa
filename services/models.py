from django.db import models
from core.models import ValidatedModel

class ServiceCategory(ValidatedModel):
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    class Meta:
        db_table = "service_categories"

class Service(ValidatedModel):
    category = models.ForeignKey(ServiceCategory, on_delete=models.PROTECT, related_name="services")
    name = models.CharField(max_length=150)
    description = models.TextField()
    price = models.DecimalField(max_digits=12, decimal_places=2)
    duration_minutes = models.PositiveIntegerField()
    image = models.ImageField(upload_to="services/", max_length=255, blank=True, null=True)
    introduction = models.TextField(blank=True, default="")
    benefits = models.TextField(blank=True, default="")
    steps = models.TextField(blank=True, default="")
    suitable = models.TextField(blank=True, default="")
    note = models.TextField(blank=True, default="")
    gallery = models.ImageField(upload_to="services/details/", max_length=255, blank=True, null=True)
    image_preset = models.CharField(max_length=255, blank=True, default="")
    gallery_preset = models.CharField(max_length=255, blank=True, default="")
    care_group = models.CharField(max_length=20, blank=True, default="", choices=[("relax","Thư giãn"),("face","Da mặt"),("body","Cơ thể"),("hair","Tóc / da đầu")])
    is_active = models.BooleanField(default=True)
    class Meta:
        db_table = "services"
        constraints = [models.CheckConstraint(condition=models.Q(price__gte=0), name="service_price_nonnegative"),
                       models.CheckConstraint(condition=models.Q(duration_minutes__gt=0), name="service_duration_positive")]
