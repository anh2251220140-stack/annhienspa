from django.core.exceptions import ValidationError
from django.db import models, transaction
from core.models import ValidatedModel

class Employee(ValidatedModel):
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True, null=True)
    specialty = models.CharField(max_length=150)
    avatar = models.ImageField(upload_to="employees/", max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    services = models.ManyToManyField("services.Service", through="EmployeeService", related_name="employees")
    class Meta:
        db_table = "employees"

class EmployeeService(ValidatedModel):
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT)
    service = models.ForeignKey("services.Service", on_delete=models.PROTECT)
    class Meta:
        db_table = "employee_services"
        constraints = [models.UniqueConstraint(fields=["employee", "service"], name="unique_employee_service")]

class EmployeeSchedule(ValidatedModel):
    class Status(models.TextChoices):
        WORKING = "working", "Làm việc"
        OFF = "off", "Nghỉ"
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="schedules")
    work_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.WORKING)
    note = models.TextField(blank=True, null=True)
    class Meta:
        db_table = "employee_schedules"
        indexes = [models.Index(fields=["employee", "work_date"], name="schedule_employee_date")]
        constraints = [models.CheckConstraint(condition=models.Q(end_time__gt=models.F("start_time")), name="schedule_positive_interval"),
                       models.CheckConstraint(condition=models.Q(status__in=["working", "off"]), name="schedule_valid_status")]
    def clean(self):
        if self.employee_id and self.work_date and self.start_time and self.end_time:
            if type(self).objects.filter(employee_id=self.employee_id, work_date=self.work_date,
                start_time__lt=self.end_time, end_time__gt=self.start_time).exclude(pk=self.pk).exists():
                raise ValidationError("Ca làm hoặc ca nghỉ bị chồng lấn.")

    def save(self, *args, **kwargs):
        with transaction.atomic():
            employee_ids = {self.employee_id}
            if self.pk:
                employee_ids.update(type(self).objects.filter(pk=self.pk).values_list("employee_id", flat=True))
            list(Employee.objects.select_for_update().filter(pk__in=employee_ids).order_by("pk"))
            return super().save(*args, **kwargs)
