from django.core.exceptions import ValidationError
from django.db import models, transaction
from core.models import TimestampedModel

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
        if not EmployeeSchedule.objects.filter(employee_id=self.employee_id, work_date=self.appointment_date,
            status="working", start_time__lte=self.start_time, end_time__gte=self.end_time).exists():
            raise ValidationError("Khung giờ phải nằm trong ca làm việc.")
        if EmployeeSchedule.objects.filter(employee_id=self.employee_id, work_date=self.appointment_date,
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
