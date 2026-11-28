from decimal import Decimal
from datetime import timedelta, datetime
import secrets
import logging
from zoneinfo import ZoneInfo
from django.conf import settings
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from .models import Invoice, InvoiceDetail, Payment
from . import gateway


def allowed(user, invoice, admin=False):
    if not user.is_authenticated or not user.is_active:raise PermissionDenied
    if admin:
        if user.role!="Admin":raise PermissionDenied
    elif user.role!="Admin" and (user.role!="User" or invoice.appointment.customer.user_id!=user.pk):raise PermissionDenied


def require_invoice_owner(user, invoice):
    if not user.is_authenticated or not user.is_active or user.role != "User":
        raise PermissionDenied
    if invoice.appointment.customer.user_id != user.pk:
        raise PermissionDenied


def online_eligible(invoice):
    if settings.PAYOS_DEMO_ONLY:
        return False
    from appointments.services import start_datetime
    a=invoice.appointment
    return payable(invoice) and a.status=="confirmed" and timezone.now()<start_datetime(a.appointment_date,a.start_time) and invoice.total_amount>0


def payable(invoice):
    return (invoice.payment_status == "unpaid" and invoice.appointment.status in ("confirmed", "completed")
            and not invoice.payments.filter(Q(requires_review=True) | Q(status="success")).exists())


def cash_timing_issue(invoice):
    appointment = invoice.appointment
    starts_at = timezone.make_aware(
        datetime.combine(appointment.appointment_date, appointment.start_time),
        ZoneInfo("Asia/Ho_Chi_Minh"),
    )
    if timezone.now() < starts_at:
        return f"Chưa đến giờ hẹn. Chỉ được ghi nhận thanh toán tại Spa từ {starts_at:%H:%M ngày %d/%m/%Y} (giờ Việt Nam)."
    return ""


def promotion_editable(invoice):
    return payable(invoice) and not invoice.payment_preference and not invoice.payments.filter(status="pending").exists()


def promotion_options(invoice):
    return promotion_choices(invoice)["items"]


def promotion_choices(invoice):
    """Explain exclusions without relaxing the same checks used when applying a code."""
    from promotions.models import Promotion
    from promotions.services import evaluate_code
    if not payable(invoice):
        if invoice.appointment.status not in ("confirmed", "completed"):
            message="Lịch hẹn chưa được xác nhận hoặc đã hủy; không được áp dụng khuyến mãi hay thanh toán."
        elif invoice.payment_status != "unpaid":
            message="Hóa đơn đã thanh toán hoặc đã hủy; không được thay đổi khuyến mãi."
        else:
            message="Hóa đơn có khoản thanh toán cần đối soát; chưa được thay đổi khuyến mãi."
        return dict(items=[],unavailable=[],message=message)
    if not promotion_editable(invoice):
        return dict(items=[],unavailable=[],message="Nhấn Đổi khuyến mãi để kiểm tra và đóng phiên thanh toán cũ an toàn trước khi chọn lại ưu đãi.")
    service=invoice.appointment.service
    service.price=invoice.subtotal
    options=[];unavailable=[]
    for promotion in Promotion.objects.filter(services=service).order_by("code"):
        try:result=evaluate_code(promotion.code,service,customer_id=invoice.appointment.customer_id,invoice_id=invoice.pk)
        except ValidationError as error:
            unavailable.append(dict(code=promotion.code,reason=" ".join(error.messages)))
            continue
        if result["eligible"]:
            options.append(dict(code=result["code"],name=promotion.name,discount=result["discount"],total=invoice.subtotal-result["discount"]))
        else:
            unavailable.append(dict(code=promotion.code,reason=result["message"]+" Điều kiện: "+"; ".join(result["conditions"])))
    return dict(items=options,unavailable=unavailable,message="")


def require_invoice_detail(invoice):
    details = list(invoice.details.all()[:2])
    if len(details) != 1:
        issue = "thiếu dòng chi tiết" if not details else "có nhiều dòng chi tiết"
        raise ValidationError(
            f"Hóa đơn HD-{invoice.pk:06d} {issue}. Cần đối soát dữ liệu trước khi tiếp tục.",
            code="invalid_invoice_details",
        )
    return details[0]


@transaction.atomic
def ensure_invoice(appointment):
    # Caller holds appointment lock; OneToOne also enforces uniqueness in MySQL.
    invoice=Invoice.objects.filter(appointment=appointment).first()
    if invoice:
        require_invoice_detail(invoice)
        return invoice
    if appointment.status!="confirmed":raise ValidationError("Chỉ lập hóa đơn sau khi xác nhận lịch.")
    price=appointment.service.price
    invoice=Invoice.objects.create(appointment=appointment,subtotal=price,total_amount=price)
    InvoiceDetail.objects.create(invoice=invoice,service=appointment.service,service_name_snapshot=appointment.service.name,unit_price=price,line_total=price)
    return invoice


def lock_invoice(pk):
    from appointments.models import Appointment
    item=Invoice.objects.get(pk=pk)
    Appointment.objects.select_for_update().get(pk=item.appointment_id)
    # Do not lock joined Service/Customer rows after Appointment: transitions lock
    # those parents first, so a joined FOR UPDATE could invert the lock order.
    return Invoice.objects.select_for_update().get(pk=pk)


@transaction.atomic
def apply_promotion(user,pk,code):
    from promotions.services import evaluate_code
    invoice = lock_invoice(pk)
    require_invoice_owner(user, invoice)
    require_invoice_detail(invoice)
    if not promotion_editable(invoice):raise ValidationError("Chọn Đổi khuyến mãi và đóng phiên thanh toán cũ an toàn trước khi sửa ưu đãi. Hóa đơn đã trả/hủy hoặc cần đối soát không được thay đổi.")
    if not code.strip():
        invoice.promotion=None;invoice.promotion_code_snapshot=""
        invoice.discount_amount=Decimal(0);invoice.total_amount=invoice.subtotal;invoice.save()
        return invoice
    service=invoice.appointment.service;service.price=invoice.subtotal
    result=evaluate_code(code,service,customer_id=invoice.appointment.customer_id,invoice_id=invoice.pk,lock=True)
    if not result["eligible"]:raise ValidationError(result["message"])
    invoice.promotion_id=result["promotionId"];invoice.promotion_code_snapshot=result["code"]
    invoice.discount_amount=result["discount"];invoice.total_amount=invoice.subtotal-invoice.discount_amount;invoice.save()
    return invoice


def check_link_funds(invoice, link):
    # payOS returns amounts in integer VND. A contradictory balance is
    # insufficient evidence either to collect again or to tell the user they paid.
    paid = link.amount_paid
    remaining = getattr(link, "amount_remaining", None)
    transactions = getattr(link, "transactions", ())
    if (type(paid) is not int or paid < 0 or
            (remaining is not None and remaining != link.amount - paid) or
            (transactions and paid == 0)):
        logging.getLogger(__name__).warning(
            "payOS inconsistent balance invoice=%s status=%s", invoice.pk, link.status
        )
        raise ValidationError("Dữ liệu số dư của phiên QR chưa nhất quán. Vui lòng kiểm tra trạng thái phiên.")
    if paid > 0:
        logging.getLogger(__name__).warning(
            "payOS renewal blocked invoice=%s status=%s has_transactions=%s",
            invoice.pk, link.status, bool(transactions)
        )
        raise ValidationError("payOS đã ghi nhận tiền ở phiên cũ. Vui lòng liên hệ Spa để đối soát trước khi tạo mã QR mới.")


def stop_pending(invoice):
    for p in invoice.payments.select_for_update().filter(status="pending",payment_method="online"):
        try:
            current=gateway.get(p)
            validate_provider(p,current)
            check_link_funds(invoice, current)
            if current.status=="PAID":
                raise ValidationError("payOS báo phiên cũ đã thanh toán. Vui lòng liên hệ Spa để đối soát trước khi tạo mã QR mới.")
            if current.status=="PROCESSING":
                raise ValidationError("payOS đang xử lý phiên cũ. Vui lòng kiểm tra lại trạng thái sau; chưa thể tạo mã QR mới.")
            if current.status=="UNDERPAID":
                raise ValidationError("payOS báo phiên cũ thanh toán chưa đủ. Vui lòng liên hệ Spa để đối soát trước khi tạo mã QR mới.")
            if current.status in ("CANCELLED","EXPIRED","FAILED"):
                result=current
            elif current.status=="PENDING":
                result=gateway.cancel(p)
                validate_provider(p,result)
                check_link_funds(invoice, result)
            else:
                raise ValidationError("Không xác định được trạng thái payOS; cần đối soát.")
        except ValidationError:raise
        except Exception:raise ValidationError("Chưa xác minh được phiên payOS đã đóng. Thử lại hoặc liên hệ Spa; chưa ghi nhận thanh toán/hủy lịch.")
        if result.status not in ("CANCELLED","EXPIRED","FAILED"):raise ValidationError("payOS chưa xác nhận hủy; cần chờ webhook hoặc đối soát.")
        p.status="cancelled";p.provider_status=result.status;p.save()


def validate_provider(payment, result):
    if (result.order_code!=payment.order_code or Decimal(result.amount)!=payment.amount
            or (payment.payment_link_id and result.id!=payment.payment_link_id)):
        raise ValidationError("Phản hồi payOS không khớp giao dịch. Chưa thay đổi hóa đơn.")


@transaction.atomic
def begin_promotion_edit(user,pk):
    invoice = lock_invoice(pk)
    require_invoice_owner(user, invoice)
    require_invoice_detail(invoice)
    if not payable(invoice):raise ValidationError("Hóa đơn không còn được đổi ưu đãi hoặc đang cần đối soát.")
    stop_pending(invoice)
    invoice.payment_preference="";invoice.save()
    return invoice


@transaction.atomic
def select_spa(user,pk):
    invoice=lock_invoice(pk);allowed(user,invoice)
    require_invoice_detail(invoice)
    if not payable(invoice):raise ValidationError("Hóa đơn không đủ điều kiện chọn thanh toán tại Spa.")
    stop_pending(invoice)
    invoice.payment_preference="spa";invoice.save()
    return invoice


@transaction.atomic
def cash(user,pk,amount):
    from promotions.services import validate_invoice_usage
    invoice=lock_invoice(pk);allowed(user,invoice,admin=True)
    require_invoice_detail(invoice)
    if not payable(invoice):raise ValidationError("Hóa đơn không đủ điều kiện thu tiền hoặc cần đối soát.")
    if issue := cash_timing_issue(invoice):
        raise ValidationError(issue)
    if amount!=invoice.total_amount:raise ValidationError("Số tiền phải khớp tổng hóa đơn.")
    stop_pending(invoice)
    validate_invoice_usage(invoice)
    Payment.objects.create(invoice=invoice,payment_method="spa",amount=invoice.total_amount,status="success",paid_at=timezone.now(),recorded_by=user,transaction_code="SPA-"+secrets.token_hex(16))
    invoice.payment_status="paid";invoice.payment_preference="spa";invoice.save();return invoice


def online(user,pk, *, renew_expired=False):
    if settings.PAYOS_DEMO_ONLY:
        raise PermissionDenied("Thanh toán thử nghiệm của đồ án, không chuyển tiền.")
    from promotions.services import validate_invoice_usage
    # Commit reservation before the network call: a timeout never loses orderCode.
    from appointments.services import start_datetime
    gateway.client().close()
    with transaction.atomic():
        invoice=lock_invoice(pk);allowed(user,invoice)
        if user.role!="User" or not online_eligible(invoice):raise ValidationError("Chỉ thanh toán online trước giờ bắt đầu, với hóa đơn chưa thanh toán.")
        require_invoice_detail(invoice)
        if invoice.total_amount!=invoice.total_amount.to_integral_value():raise ValidationError("payOS yêu cầu số tiền nguyên VND. Vui lòng thanh toán tại Spa.")
        validate_invoice_usage(invoice)
        p=invoice.payments.filter(status="pending",payment_method="online").first()
        if renew_expired and p and p.expires_at and p.expires_at <= timezone.now():
            stop_pending(invoice)
            p = None
        if not p:
            p=Payment.objects.create(invoice=invoice,payment_method="online",provider="payOS",amount=invoice.total_amount,order_code=secrets.randbelow(8_000_000_000_000_000)+1,
                expires_at=min(timezone.now()+timedelta(seconds=600),start_datetime(invoice.appointment.appointment_date,invoice.appointment.start_time)))
        invoice.payment_preference="online";invoice.save()
    with transaction.atomic():
        invoice=lock_invoice(pk);allowed(user,invoice)
        require_invoice_detail(invoice)
        p=Payment.objects.select_for_update().get(pk=p.pk)
        if p.status!="pending" or not online_eligible(invoice):raise ValidationError("Hóa đơn/phiên thanh toán đã thay đổi.")
        validate_invoice_usage(invoice)
        if p.expires_at<=timezone.now():raise ValidationError("Phiên đã hết thời gian. Chọn đóng phiên payOS trước khi tạo lại.")
        if p.checkout_url:return p
        try:result=gateway.create(p)
        except Exception:
            # Same order must be retried; never reserve another after ambiguous timeout.
            raise ValidationError("Không thể lấy liên kết payOS. Mã giao dịch đã được giữ để thử lại an toàn; chưa ghi nhận đã thanh toán.")
        if result.order_code!=p.order_code or Decimal(result.amount)!=p.amount:raise ValidationError("Phản hồi payOS không khớp giao dịch.")
        p.payment_link_id=result.payment_link_id;p.checkout_url=result.checkout_url;p.qr_code=result.qr_code;p.provider_status=result.status;p.save();return p


@transaction.atomic
def cancel_online(user,pk):
    invoice=lock_invoice(pk);allowed(user,invoice)
    require_invoice_detail(invoice)
    if invoice.payment_status!="unpaid":raise ValidationError("Hóa đơn không còn chờ thanh toán.")
    if not payable(invoice):raise ValidationError("Hóa đơn cần đối soát trước khi đóng phiên.")
    stop_pending(invoice);invoice.payment_preference="";invoice.save();return invoice


@transaction.atomic
def refresh_online(user, pk):
    invoice=lock_invoice(pk);allowed(user,invoice)
    require_invoice_detail(invoice)
    for p in invoice.payments.select_for_update().filter(payment_method="online",status="pending"):
        try: result=gateway.get(p)
        except Exception: raise ValidationError("Chưa thể đối chiếu trạng thái payOS. Vui lòng thử lại; hóa đơn chưa được đổi trạng thái.")
        validate_provider(p,result)
        p.provider_status=result.status
        p.payment_link_id=result.id
        if result.status in ("CANCELLED","EXPIRED","FAILED") and result.amount_paid==0:
            p.status="cancelled"
        # Even PAID from a status request is not a substitute for a signed webhook.
        p.save()
    return invoice


@transaction.atomic
def accept_webhook(data):
    from promotions.services import validate_invoice_usage
    p=Payment.objects.filter(order_code=data.order_code,payment_method="online").first()
    if not p:return False  # Signed provider probe/unknown code: no mutation.
    invoice=lock_invoice(p.invoice_id);p=Payment.objects.select_for_update().get(pk=p.pk)
    if Decimal(data.amount)!=p.amount or data.currency!="VND" or (p.payment_link_id and p.payment_link_id!=data.payment_link_id):raise ValidationError("Webhook không khớp giao dịch.")
    if data.code!="00":return False
    require_invoice_detail(invoice)
    if p.status in ("success","review"):return True
    try:
        paid_at=datetime.fromisoformat(data.transaction_date_time)
        if timezone.is_naive(paid_at):paid_at=timezone.make_aware(paid_at)
    except (TypeError,ValueError):raise ValidationError("Thời gian giao dịch không hợp lệ.")
    was_closed=p.status=="cancelled"
    p.paid_at=paid_at;p.provider_status="PAID";p.transaction_code=data.reference
    p.requires_review=(was_closed or invoice.payment_status!="unpaid" or invoice.appointment.status not in ("confirmed","completed")
        or invoice.total_amount!=p.amount or invoice.payments.exclude(pk=p.pk).filter(Q(status="success")|Q(requires_review=True)).exists())
    if not p.requires_review:
        try:validate_invoice_usage(invoice)
        except ValidationError:p.requires_review=True
    p.status="review" if p.requires_review else "success"
    p.save()
    if not p.requires_review:invoice.payment_status="paid";invoice.payment_preference="online";invoice.save()
    return True
