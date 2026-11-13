from contextlib import contextmanager
from decimal import Decimal
import re
import unicodedata
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.models import Q
from django.utils import timezone
from .models import Promotion

@contextmanager
def code_lock():
    # Serializes code + alias edits across administrators, including an empty table.
    with connection.cursor() as cursor:
        cursor.execute('SELECT GET_LOCK(%s, 10)', ['annhien_promotion_codes'])
        if cursor.fetchone()[0]!=1:raise ValidationError('Chương trình đang được cập nhật. Vui lòng thử lại.')
    try:yield
    finally:
        with connection.cursor() as cursor:cursor.execute('SELECT RELEASE_LOCK(%s)', ['annhien_promotion_codes'])

def policy(promotion):
    """Check conditions and legacy notes without inferring rules from arbitrary prose."""
    limit=promotion.per_customer_limit
    manual=[]
    text = promotion.conditions
    if not promotion.note_is_informational:
        text += '\n' + promotion.note
    for clause in re.split(r'[.;\n]+', text):
        clause=clause.strip()
        if not clause:continue
        normalized=' '.join(unicodedata.normalize('NFC',clause).casefold().split())
        if normalized=='mỗi khách hàng chỉ sử dụng mã một lần':
            limit=min(limit,1) if limit else 1
        elif normalized not in ('áp dụng cho dịch vụ được chọn','không áp dụng đồng thời với chương trình khác'):
            manual.append(clause)
    return limit,manual


def usage(promotion,customer_id,exclude_invoice=None):
    from billing.models import Invoice
    # Count invoices, not payment attempts: repeated webhooks cannot consume twice.
    rows=Invoice.objects.filter(promotion=promotion,appointment__customer_id=customer_id)
    if exclude_invoice:rows=rows.exclude(pk=exclude_invoice)
    used=rows.filter(payment_status='paid').count()
    reserved=rows.exclude(payment_status='paid').filter(
        Q(payment_status='unpaid') | Q(payments__status__in=['pending','success','review']) |
        Q(payments__requires_review=True)).distinct().count()
    return dict(used=used,reserved=reserved)


def check_usage(promotion,customer_id,exclude_invoice=None):
    limit,_=policy(promotion)
    if limit is None:return dict(limit=None,used=0,reserved=0)
    if customer_id is None:raise ValidationError('Cần xác định khách hàng để kiểm tra giới hạn lượt sử dụng.')
    counts=usage(promotion,customer_id,exclude_invoice)
    if counts['used']>=limit:raise ValidationError('Khách hàng đã sử dụng hết lượt của khuyến mãi này trên hóa đơn đã thanh toán.')
    if counts['used']+counts['reserved']>=limit:raise ValidationError('Lượt khuyến mãi đang được giữ ở hóa đơn khác chưa thanh toán hoặc cần đối soát. Vui lòng xử lý hóa đơn đó trước.')
    return dict(limit=limit,**counts)


def validate_invoice_usage(invoice):
    # All writers lock Appointment -> Invoice -> Promotion. The promotion row
    # serializes claims across invoices/customers without locking other invoices.
    if invoice.promotion_id:
        promotion=Promotion.objects.select_for_update().get(pk=invoice.promotion_id)
        check_usage(promotion,invoice.appointment.customer_id,invoice.pk)


def evaluate_code(code,service,day=None,*,customer_id=None,invoice_id=None,lock=False):
    code=code.strip().upper();day=day or timezone.localdate()
    match=next((p for p in Promotion.objects.all() if code in {p.code.upper(),*[v.strip().upper() for v in p.aliases.splitlines()]}),None)
    if match and lock:
        match=Promotion.objects.select_for_update().get(pk=match.pk)
        if code not in {match.code.upper(),*[v.strip().upper() for v in match.aliases.splitlines()]}:match=None
    if not match or not match.is_active or not match.start_date<=day<=match.end_date:raise ValidationError('Mã không tồn tại hoặc không còn hiệu lực.')
    match.full_clean()
    if not service.is_active or not service.category.is_active or not match.services.filter(pk=service.pk).exists():raise ValidationError('Dịch vụ không thuộc phạm vi áp dụng.')
    subtotal=service.price
    if match.min_amount is not None and subtotal<match.min_amount:raise ValidationError('Chưa đạt giá trị tối thiểu của chương trình.')
    discount=subtotal*match.discount_value/Decimal(100) if match.discount_type=='percent' else match.discount_value
    if match.max_discount is not None:discount=min(discount,match.max_discount)
    discount=min(discount,subtotal).quantize(Decimal('0.01'))
    limit,conditions=policy(match)
    counts=check_usage(match,customer_id,invoice_id)
    manual=bool(conditions)
    return {'code':match.code,'promotionId':match.pk,'eligible':not manual,'requiresManualReview':manual,
        'conditions':conditions,'usage':counts,'subtotal':subtotal,'discount':None if manual else discount,
        'message':'Cần Spa kiểm tra các điều kiện văn bản trước khi áp dụng.' if manual else 'Đủ các điều kiện đã cấu hình. Chưa áp dụng vào hóa đơn.'}
