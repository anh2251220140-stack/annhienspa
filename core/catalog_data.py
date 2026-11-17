from django.templatetags.static import static
from django.utils import timezone
from services.models import Service, ServiceCategory
from products.models import CareProduct, ServiceProduct
from employees.models import Employee
from promotions.models import Promotion


def image(field,fallback,preset=""):return field.url if field else static("images/"+(preset or fallback))
def money(value):return f"{value:,.0f}".replace(",",".")+" VND"
def lines(value):return [s.strip() for s in (value or "").splitlines() if s.strip()]

def _promotion_discount_label(discount_type, value):
    percent = discount_type == Promotion.DiscountType.PERCENT
    whole, _, fraction = format(value, "f" if percent else ",f").partition(".")
    whole = whole.replace(",", ".")
    fraction = fraction.rstrip("0")
    separator = "." if percent else ","
    number = f"{whole}{separator}{fraction}" if fraction else whole
    suffix = "%" if percent else " VND"
    return f"Giảm {number}{suffix}"


def catalog():
    services=[]
    for x in Service.objects.filter(is_active=True,category__is_active=True).select_related("category"):
        services.append({"id":x.pk,"active":True,"name":x.name,"category":x.category.name,"description":x.description,
            "price":money(x.price),"priceValue":float(x.price),"minutes":x.duration_minutes,"duration":f"{x.duration_minutes} phút",
            "image":image(x.image,"facial.jpg",x.image_preset),"gallery":image(x.gallery,"facial.jpg",x.gallery_preset) if x.gallery or x.gallery_preset else image(x.image,"facial.jpg",x.image_preset),"introduction":x.introduction or x.description,
            "benefits":lines(x.benefits),"steps":lines(x.steps),"suitable":x.suitable,"note":x.note,"careGroup":x.care_group})
    products=[]
    for x in CareProduct.objects.filter(is_active=True):
        products.append({"id":x.pk,"active":True,"name":x.name,"category":x.product_type,"description":x.description,
            "skins":lines(x.skin_type),"audiences":lines(x.suitable_for),"ingredients":x.ingredients or "",
            "usage":x.usage_instructions or "","note":x.note,"benefits":lines(x.benefits),"careGroup":x.care_group,
            "image":image(x.image,"care-5.jpg",x.image_preset)})
    staff=[{"id":x.pk,"active":True,"name":x.full_name,"specialty":x.specialty,"image":image(x.avatar,"specialist-mai-anh.jpg",x.avatar_preset),
        "serviceIds":list(x.services.filter(is_active=True,category__is_active=True).values_list("pk",flat=True))} for x in Employee.objects.filter(is_active=True).prefetch_related("services")]
    ids={s["id"] for s in services};products_ids={p["id"] for p in products}
    relations=[{"serviceId":r.service_id,"productId":r.product_id} for r in ServiceProduct.objects.filter(service_id__in=ids,product_id__in=products_ids)]
    return {"services":services,"products":products,"staff":staff,"relations":relations}

def promotions(*, promotion_page=False):
    today=timezone.localdate();items=[]
    for x in Promotion.objects.filter(is_active=True,start_date__lte=today,end_date__gte=today).prefetch_related("services"):
        conditions=lines(x.conditions)
        from promotions.services import policy
        limit,_=policy(x)
        if limit is not None:conditions.append(f'Mỗi khách hàng được sử dụng tối đa {limit} lần; hóa đơn chưa thanh toán giữ lượt cho đến khi xóa mã hoặc hủy hợp lệ.')
        if x.min_amount is not None:conditions.append("Giá trị tối thiểu: "+money(x.min_amount))
        if x.max_discount is not None:conditions.append("Giảm tối đa: "+money(x.max_discount))
        discount = _promotion_discount_label(x.discount_type, x.discount_value)
        item={"id":x.pk,"code":x.code,"aliases":lines(x.aliases),"active":True,"name":x.name,
            "discount":discount,
            "description":x.description or "","detail":x.detail or x.description or "","conditions":conditions,
            "startDate":x.start_date.isoformat(),"endDate":x.end_date.isoformat(),"badge":x.badge or "Ưu đãi", "accent":x.accent,
            "serviceIds":list(x.services.filter(is_active=True,category__is_active=True).values_list("pk",flat=True)),"note":x.note,"scopeNote":x.scope_note}
        if promotion_page:
            item["discountType"] = x.discount_type
        items.append(item)
    return {"referenceDate":today.isoformat(),"expiringWithinDays":7,"items":items}
