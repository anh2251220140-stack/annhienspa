from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import models, transaction
from core.models import TimestampedModel, ValidatedModel

class Appointment(TimestampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Chờ xác nhận"
        CONFIRMED = "confirmed", "Đã xác nhận"
        COMPLETED = "completed", "Đã hoàn thành"
        CANCELLED = "cancelled", "Đã hủy"
    customer = models.ForeignKey("accounts.Customer", on_delete=models.PROTECT, related_name="appointments")
    service = models.ForeignKey("services.Service", on_delete=models.PROTECT, related_name="appointments")
    employee = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="appointments")
    appointment_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.PENDING)
    note = models.TextField(blank=True, null=True)
    cancel_reason = models.CharField(max_length=500, blank=True, null=True)
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="cancelled_appointments")
    cancelled_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        db_table = "appointments"
        indexes = [models.Index(fields=["employee", "appointment_date"], name="appointment_employee_date"),
                   models.Index(fields=["customer", "appointment_date"], name="appointment_customer_date")]
        constraints = [models.CheckConstraint(condition=models.Q(end_time__gt=models.F("start_time")), name="appointment_positive_interval"),
            models.CheckConstraint(condition=models.Q(status__in=["pending", "confirmed", "completed", "cancelled"]), name="appointment_valid_status")]
    def clean(self):
        if self.status == self.Status.CANCELLED:
            return
        if not all([self.employee_id, self.customer_id, self.service_id, self.appointment_date, self.start_time, self.end_time]):
            return
        from employees.models import EmployeeService, EmployeeSchedule
        if not EmployeeService.objects.filter(employee_id=self.employee_id, service_id=self.service_id).exists():
            raise ValidationError("Nhân viên chưa được phân công dịch vụ này.")
        if not EmployeeSchedule.objects.filter(is_active=True, employee_id=self.employee_id, work_date=self.appointment_date,
            status="working", start_time__lte=self.start_time, end_time__gte=self.end_time).exists():
            raise ValidationError("Khung giờ phải nằm trong ca làm việc.")
        if EmployeeSchedule.objects.filter(is_active=True, employee_id=self.employee_id, work_date=self.appointment_date,
            status="off", start_time__lt=self.end_time, end_time__gt=self.start_time).exists():
            raise ValidationError("Khung giờ trùng ca nghỉ.")
        conflicts = type(self).objects.filter(appointment_date=self.appointment_date,
            start_time__lt=self.end_time, end_time__gt=self.start_time).exclude(pk=self.pk).exclude(status="cancelled")
        if conflicts.filter(models.Q(employee_id=self.employee_id) | models.Q(customer_id=self.customer_id)).exists():
            raise ValidationError("Trùng lịch của nhân viên hoặc khách hàng.")

    def save(self, *args, **kwargs):
        # Lock stable parent rows even when no appointments exist yet.
        from employees.models import Employee
        from accounts.models import Customer
        with transaction.atomic():
            employee_ids, customer_ids = {self.employee_id}, {self.customer_id}
            if self.pk:
                previous = type(self).objects.filter(pk=self.pk).values("employee_id", "customer_id").first()
                if previous:
                    employee_ids.add(previous["employee_id"])
                    customer_ids.add(previous["customer_id"])
            list(Employee.objects.select_for_update().filter(pk__in=employee_ids).order_by("pk"))
            list(Customer.objects.select_for_update().filter(pk__in=customer_ids).order_by("pk"))
            return super().save(*args, **kwargs)


class AppointmentReassignment(ValidatedModel):
    appointment = models.ForeignKey(Appointment, on_delete=models.PROTECT, related_name="reassignments")
    previous_employee = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="reassignments_from")
    new_employee = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="reassignments_to")
    reason = models.CharField(max_length=500)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="appointment_reassignments")
    changed_at = models.DateTimeField(default=timezone.now, editable=False)
    customer_consent = models.BooleanField()
    consent_method = models.CharField(max_length=20, choices=[("in_person", "Trực tiếp"), ("phone", "Điện thoại"), ("other", "Kênh khác")])
    consent_note = models.CharField(max_length=500)
    consent_at = models.DateTimeField()

    class Meta:
        db_table = "appointment_reassignments"
        ordering = ["changed_at", "pk"]
        indexes = [models.Index(fields=["appointment", "changed_at"], name="reassign_appointment_time")]
        constraints = [
            models.CheckConstraint(condition=~models.Q(previous_employee=models.F("new_employee")), name="reassign_different_employee"),
            models.CheckConstraint(condition=models.Q(customer_consent=True), name="reassign_consent_required"),
            models.CheckConstraint(condition=models.Q(consent_at__lte=models.F("changed_at")), name="reassign_consent_before_change"),
        ]

    def clean(self):
        if self.pk:
            raise ValidationError("Không được sửa lịch sử phân công lại.")
        if self.changed_by_id and self.changed_by.role != "Admin":
            raise ValidationError("Chỉ Admin được phân công lại.")
        if not self.reason.strip() or not self.consent_note.strip():
            raise ValidationError("Cần lý do và thông tin xác nhận đồng ý.")
