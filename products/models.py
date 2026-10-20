from django.db import models
from core.models import ValidatedModel

class CareProduct(ValidatedModel):
    name = models.CharField(max_length=150)
    product_type = models.CharField(max_length=100)
    description = models.TextField()
    skin_type = models.TextField(blank=True, null=True)
    suitable_for = models.TextField(blank=True, null=True)
    benefits = models.TextField(blank=True, null=True)
    ingredients = models.TextField(blank=True, null=True)
    usage_instructions = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to="products/", max_length=255, blank=True, null=True)
    note = models.TextField(blank=True, default="")
    image_preset = models.CharField(max_length=255, blank=True, default="")
    care_group = models.CharField(max_length=20, blank=True, default="", choices=[("relax","Thư giãn"),("face","Da mặt"),("body","Cơ thể"),("hair","Tóc / da đầu")])
    is_active = models.BooleanField(default=True)
    services = models.ManyToManyField("services.Service", through="ServiceProduct", related_name="care_products")
    class Meta:
        db_table = "care_products"

class ServiceProduct(ValidatedModel):
    service = models.ForeignKey("services.Service", on_delete=models.PROTECT)
    product = models.ForeignKey(CareProduct, on_delete=models.PROTECT)
    class Meta:
        db_table = "service_products"
        constraints = [models.UniqueConstraint(fields=["service", "product"], name="unique_service_product")]
