from contextlib import contextmanager
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import connection
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

def evaluate_code(code,service,day=None):
    code=code.strip().upper();day=day or timezone.localdate()
    match=next((p for p in Promotion.objects.all() if code in {p.code.upper(),*[v.strip().upper() for v in p.aliases.splitlines()]}),None)
    if not match or not match.is_active or not match.start_date<=day<=match.end_date:raise ValidationError('Mã không tồn tại hoặc không còn hiệu lực.')
    match.full_clean()
    if not service.is_active or not service.category.is_active or not match.services.filter(pk=service.pk).exists():raise ValidationError('Dịch vụ không thuộc phạm vi áp dụng.')
    subtotal=service.price
    if match.min_amount is not None and subtotal<match.min_amount:raise ValidationError('Chưa đạt giá trị tối thiểu của chương trình.')
    discount=subtotal*match.discount_value/Decimal(100) if match.discount_type=='percent' else match.discount_value
    if match.max_discount is not None:discount=min(discount,match.max_discount)
    discount=min(discount,subtotal).quantize(Decimal('0.01'))
    manual=bool(match.conditions.strip())
    return {'code':match.code,'promotionId':match.pk,'eligible':not manual,'requiresManualReview':manual,
        'conditions':match.conditions.splitlines(),'subtotal':subtotal,'discount':None if manual else discount,
        'message':'Cần Spa kiểm tra các điều kiện văn bản trước khi áp dụng.' if manual else 'Đủ các điều kiện đã cấu hình. Chưa áp dụng vào hóa đơn.'}
