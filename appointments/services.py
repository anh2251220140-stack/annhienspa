from datetime import datetime, timedelta
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from accounts.models import Customer
from employees.models import Employee, EmployeeService, EmployeeSchedule
from services.models import Service
from billing.models import Invoice
from .models import Appointment, AppointmentReassignment

LIVE = ["pending", "confirmed"]

def start_datetime(day, clock):
    return timezone.make_aware(datetime.combine(day, clock), timezone.get_current_timezone())

def customer_for(user):
    if not user.is_authenticated or not user.is_active or user.role != "User":
        raise PermissionDenied
    try: return user.customer
    except Customer.DoesNotExist: raise ValidationError("Vui lòng cập nhật hồ sơ khách hàng trước khi đặt lịch.")

def available_slots(user, service_id, employee_id, day):
    customer = customer_for(user)
    service = Service.objects.filter(pk=service_id, is_active=True, category__is_active=True).first()
    employee = Employee.objects.filter(pk=employee_id, is_active=True).first()
    if not service or not employee or not EmployeeService.objects.filter(employee=employee,service=service).exists():
        raise ValidationError("Dịch vụ hoặc chuyên viên không khả dụng / chưa được phân công.")
    if day < timezone.localdate(): return []
    shifts = EmployeeSchedule.objects.filter(is_active=True, employee=employee,work_date=day)
    busy = list(Appointment.objects.filter(appointment_date=day).exclude(status="cancelled").filter(
        Q(employee=employee) | Q(customer=customer)))
    result = set()
    # Offer every valid minute: SRS does not specify a fixed slot increment.
    for shift in shifts.filter(status="working"):
        current = start_datetime(day,shift.start_time)
        end = start_datetime(day,shift.end_time)
        while current + timedelta(minutes=service.duration_minutes) <= end:
            finish = current + timedelta(minutes=service.duration_minutes)
            if current > timezone.now() and not any(current.time() < a.end_time and finish.time() > a.start_time for a in busy) and not any(
                current.time() < rest.end_time and finish.time() > rest.start_time for rest in shifts if rest.status == "off"):
                result.add(current.strftime("%H:%M"))
            current += timedelta(minutes=1)
    return sorted(result)

@transaction.atomic
def book(user, service_id, employee_id, day, clock, note=""):
    customer = customer_for(user)
    service = Service.objects.select_for_update().filter(pk=service_id, is_active=True, category__is_active=True).first()
    employee = Employee.objects.select_for_update().filter(pk=employee_id,is_active=True).first()
    Customer.objects.select_for_update().get(pk=customer.pk)
    if not service or not employee:
        raise ValidationError("Dịch vụ hoặc chuyên viên không khả dụng.")
    start = start_datetime(day,clock)
    if start <= timezone.now(): raise ValidationError("Vui lòng chọn thời gian trong tương lai.")
    if clock.second or clock.microsecond: raise ValidationError("Giờ đặt lịch phải theo phút.")
    finish = start + timedelta(minutes=service.duration_minutes)
    if finish.date() != day: raise ValidationError("Liệu trình phải kết thúc trong ngày làm việc.")
    return Appointment.objects.create(customer=customer,service=service,employee=employee,appointment_date=day,
        start_time=clock,end_time=finish.time(),note=note,status="pending")

@transaction.atomic
def transition(user, appointment_id, status, employee_id=None, consent=False, reason="", *, expected_employee=None, expected_updated_at=None,
               consent_method="", consent_note="", consent_at=None, no_show=False):
    if not user.is_authenticated or not user.is_active: raise PermissionDenied
    # Serialize status changes and reassignment using the same parent lock order as booking.
    current = Appointment.objects.get(pk=appointment_id)
    Service.objects.select_for_update().get(pk=current.service_id)
    current = Appointment.objects.get(pk=appointment_id)
    ids = {current.employee_id}
    if employee_id: ids.add(employee_id)
    locked_employees = {e.pk:e for e in Employee.objects.select_for_update().filter(pk__in=ids).order_by("pk")}
    Customer.objects.select_for_update().get(pk=current.customer_id)
    item = Appointment.objects.select_for_update().get(pk=appointment_id)
    invoice = Invoice.objects.select_for_update().filter(appointment=item).first()
    if user.role == "Admin" and item.status == "confirmed" and status == "confirmed" and not employee_id:
        if not invoice:
            raise ValidationError("Lịch cũ thiếu hóa đơn: Admin cần đối soát giá lịch sử trước khi bổ sung hóa đơn.")
        return item
    if item.status not in LIVE: raise ValidationError("Lịch đã hoàn thành hoặc đã hủy không được thay đổi.")
    if user.role == "User":
        if item.customer.user_id != user.pk: raise PermissionDenied
        if status != "cancelled" or employee_id: raise PermissionDenied
        if start_datetime(item.appointment_date,item.start_time) <= timezone.now() or (invoice and invoice.payment_status == "paid"):
            raise ValidationError("Không thể tự hủy lịch đã tới giờ hoặc đã thanh toán. Vui lòng liên hệ Spa.")
    elif user.role != "Admin": raise PermissionDenied
    now = timezone.now()
    reason = reason.strip()
    if len(reason) > 500:
        raise ValidationError("Lý do tối đa 500 ký tự.")
    if no_show or reason.casefold() == "khách không đến":
        if user.role != "Admin" or status != "cancelled" or item.status != "confirmed" or now <= start_datetime(item.appointment_date, item.start_time):
            raise ValidationError("Chỉ Admin xác nhận khách không đến sau giờ bắt đầu của lịch đã xác nhận.")
        reason = "Khách không đến"
    if status == "cancelled" and user.role == "Admin" and not reason:
        raise ValidationError("Admin phải ghi lý do hủy lịch.")
    history = None
    if employee_id:
        if expected_employee != item.employee_id or expected_updated_at != item.updated_at:
            raise ValidationError("Lịch đã thay đổi hoặc thiếu phiên bản đối chiếu. Vui lòng tải lại.")
        if employee_id == item.employee_id:
            raise ValidationError("Chuyên viên mới phải khác chuyên viên hiện tại.")
    allowed = {"pending":{"confirmed","cancelled"}, "confirmed":{"completed","cancelled"}}
    changing_employee = employee_id and employee_id != item.employee_id
    if changing_employee:
        if user.role != "Admin" or not consent or not reason.strip():
            raise ValidationError("Đổi chuyên viên cần xác nhận đã được khách đồng ý và ghi rõ lý do/thông báo cho khách.")
        if start_datetime(item.appointment_date,item.start_time) <= timezone.now() or status in ("completed","cancelled"):
            raise ValidationError("Chỉ đổi chuyên viên trước giờ hẹn, khi lịch còn hiệu lực.")
        employee = locked_employees.get(employee_id)
        if not employee or not employee.is_active: raise ValidationError("Chuyên viên không khả dụng.")
        if consent_at is None or timezone.is_naive(consent_at) or consent_at > now:
            raise ValidationError("Thời điểm khách đồng ý phải hợp lệ và không ở tương lai.")
        history = AppointmentReassignment(
            appointment=item, previous_employee_id=item.employee_id, new_employee=employee,
            reason=reason, changed_by=user, changed_at=now, customer_consent=consent,
            consent_method=consent_method, consent_note=consent_note, consent_at=consent_at)
        history.full_clean()
        item.employee = employee
        item.full_clean()  # assignment, working hours and employee/customer overlaps
        # Keep legacy notes unchanged; new audit data is stored separately.
    if status not in allowed[item.status] and not (changing_employee and status == item.status):
        raise ValidationError("Chuyển trạng thái không hợp lệ.")
    if status == "completed" and start_datetime(item.appointment_date,item.end_time) > timezone.now():
        raise ValidationError("Chưa đến thời điểm kết thúc liệu trình.")
    if status == "cancelled" and invoice and invoice.payment_status == "paid":
        raise ValidationError("Hóa đơn đã thanh toán: cần xử lý thủ công với khách; không hoàn tiền tự động.")
    if status == "cancelled" and invoice:
        from billing.services import stop_pending
        stop_pending(invoice)
    if status == "confirmed" and not invoice and item.status != "pending":
        raise ValidationError("Lịch cũ thiếu hóa đơn: cần đối soát giá lịch sử, kể cả khi đổi chuyên viên.")
    if status == "cancelled":
        item.cancel_reason = reason or "Khách hàng tự hủy"
        item.cancelled_by = user
        item.cancelled_at = now
    item.status = status
    # Existing historical schedule/assignment may be inactive; status changes do not rebook.
    Appointment.objects.filter(pk=item.pk).update(status=status,employee_id=item.employee_id,note=item.note,updated_at=now,
        cancel_reason=item.cancel_reason,cancelled_by_id=item.cancelled_by_id,cancelled_at=item.cancelled_at)
    item.updated_at = now
    if history:
        history.save()
    if status == "confirmed":
        from billing.services import ensure_invoice
        ensure_invoice(item)
    if status == "cancelled" and invoice:
        invoice.payment_status = "cancelled"; invoice.save()
    return item
