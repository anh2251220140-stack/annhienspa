from django.db import models
from core.models import ValidatedModel

class Promotion(ValidatedModel):
    class DiscountType(models.TextChoices):
        PERCENT = "percent", "Phần trăm"
        AMOUNT = "amount", "Số tiền"
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices)
    discount_value = models.DecimalField(max_digits=12, decimal_places=2)
    min_amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    max_discount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    start_date = models.DateField()
    end_date = models.DateField()
    detail = models.TextField(blank=True, default="")
    conditions = models.TextField(blank=True, default="")
    note = models.TextField(blank=True, default="")
    badge = models.CharField(max_length=80, blank=True, default="")
    accent = models.CharField(max_length=20, default="champagne", choices=[("champagne","Champagne"),("terracotta","Terracotta"),("caramel","Caramel")])
    aliases = models.TextField(blank=True, default="")
    scope_note = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    services = models.ManyToManyField("services.Service", through="PromotionService", related_name="promotions")
    class Meta:
        db_table = "promotions"
        constraints = [
            models.CheckConstraint(condition=models.Q(end_date__gte=models.F("start_date")), name="promotion_valid_dates"),
            models.CheckConstraint(condition=models.Q(discount_value__gt=0), name="promotion_positive_discount"),
            models.CheckConstraint(condition=models.Q(discount_type="amount") | models.Q(discount_type="percent", discount_value__lte=100), name="promotion_valid_discount"),
            models.CheckConstraint(condition=models.Q(min_amount__isnull=True) | models.Q(min_amount__gte=0), name="promotion_min_nonnegative"),
            models.CheckConstraint(condition=models.Q(max_discount__isnull=True) | models.Q(max_discount__gte=0), name="promotion_max_nonnegative")]

class PromotionService(ValidatedModel):
    promotion = models.ForeignKey(Promotion, on_delete=models.PROTECT)
    service = models.ForeignKey("services.Service", on_delete=models.PROTECT)
    class Meta:
        db_table = "promotion_services"
        constraints = [models.UniqueConstraint(fields=["promotion", "service"], name="unique_promotion_service")]
