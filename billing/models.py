from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from core.models import TimestampedModel, ValidatedModel

class Invoice(TimestampedModel):
    class Status(models.TextChoices):
        UNPAID = "unpaid", "Chưa thanh toán"
        PAID = "paid", "Đã thanh toán"
        CANCELLED = "cancelled", "Đã hủy"
    appointment = models.OneToOneField("appointments.Appointment", on_delete=models.PROTECT, related_name="invoice")
    promotion = models.ForeignKey("promotions.Promotion", on_delete=models.PROTECT, blank=True, null=True)
    promotion_code_snapshot = models.CharField(max_length=50, blank=True, default="")
    historical_basis = models.TextField(blank=True, default="", max_length=2000)
    payment_preference = models.CharField(max_length=10, blank=True, default="", choices=[("", "Chưa chọn"), ("online", "payOS"), ("spa", "Tại Spa")])
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_status = models.CharField(max_length=30, choices=Status.choices, default=Status.UNPAID)
    class Meta:
        db_table = "invoices"
        constraints = [
            models.CheckConstraint(condition=models.Q(subtotal__gte=0, discount_amount__gte=0, total_amount__gte=0), name="invoice_nonnegative_amounts"),
            models.CheckConstraint(condition=models.Q(total_amount=models.F("subtotal")-models.F("discount_amount")), name="invoice_total_matches"),
            models.CheckConstraint(condition=models.Q(payment_status__in=["unpaid", "paid", "cancelled"]), name="invoice_valid_status")]
    def clean(self):
        if self._state.adding and self.appointment_id and self.appointment.status != "confirmed" and not (self.appointment.status == "completed" and self.historical_basis):
            raise ValidationError("Chỉ lập hóa đơn cho lịch hẹn đã xác nhận.")
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk, payment_status="paid").first()
            if previous and any(getattr(previous, name) != getattr(self, name) for name in
                ("subtotal", "discount_amount", "total_amount", "promotion_id", "promotion_code_snapshot", "historical_basis", "appointment_id", "payment_status", "payment_preference")):
                raise ValidationError("Không được thay đổi số tiền hoặc liên kết hóa đơn đã thanh toán.")

class InvoiceDetail(ValidatedModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="details")
    service = models.ForeignKey("services.Service", on_delete=models.PROTECT)
    service_name_snapshot = models.CharField(max_length=150)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)
    class Meta:
        db_table = "invoice_details"
        constraints = [models.CheckConstraint(condition=models.Q(unit_price__gte=0, quantity__gt=0, line_total__gte=0), name="detail_valid_amounts"),
            models.CheckConstraint(condition=models.Q(line_total=models.F("unit_price")*models.F("quantity")), name="detail_total_matches")]
    def clean(self):
        if self.invoice_id and self.service_id and self.invoice.appointment.service_id != self.service_id:
            raise ValidationError("Chi tiết hóa đơn chỉ chứa dịch vụ của lịch hẹn.")
        if self.invoice_id and self.invoice.payment_status == "paid":
            raise ValidationError("Không sửa chi tiết hóa đơn đã thanh toán.")

class Payment(ValidatedModel):
    class Method(models.TextChoices):
        ONLINE = "online", "payOS"
        SPA = "spa", "Tại Spa"
    class Status(models.TextChoices):
        PENDING = "pending", "Đang chờ"
        SUCCESS = "success", "Thành công"
        CANCELLED = "cancelled", "Đã hủy"
        REVIEW = "review", "Cần đối soát"
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payments")
    order_code = models.PositiveBigIntegerField(unique=True, null=True, blank=True)
    payment_link_id = models.CharField(max_length=100, blank=True, default="")
    checkout_url = models.URLField(max_length=1000, blank=True, default="")
    qr_code = models.TextField(blank=True, default="")
    provider_status = models.CharField(max_length=30, blank=True, default="")
    expires_at = models.DateTimeField(null=True, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
    requires_review = models.BooleanField(default=False)
    provider = models.CharField(max_length=30, blank=True, null=True)
    payment_method = models.CharField(max_length=30, choices=Method.choices)
    transaction_code = models.CharField(max_length=100, unique=True, blank=True, null=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.PENDING)
    paid_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = "payments"
        constraints = [models.CheckConstraint(condition=models.Q(amount__gte=0), name="payment_nonnegative"),
            models.CheckConstraint(condition=models.Q(payment_method__in=["online", "spa"]), name="payment_valid_method"),
            models.CheckConstraint(condition=models.Q(status__in=["pending", "success", "cancelled", "review"]), name="payment_valid_status")]
    def clean(self):
        if not self.transaction_code:
            self.transaction_code = None
        if self._state.adding and self.invoice_id and self.payment_method == "online":
            from datetime import datetime
            from django.utils import timezone
            appointment = self.invoice.appointment
            start = timezone.make_aware(datetime.combine(appointment.appointment_date, appointment.start_time), timezone.get_current_timezone())
            if self.invoice.payment_status != "unpaid" or timezone.now() >= start or appointment.status != "confirmed":
                raise ValidationError("Không đủ điều kiện tạo thanh toán online.")
