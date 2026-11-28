"""FR-21 replies based on structured public catalog data."""

from dataclasses import replace
import re

from django.utils import timezone
from django.utils.html import strip_tags

from core.catalog_data import _promotion_discount_label, lines, money
from products.models import CareProduct
from promotions.models import Promotion
from promotions.services import policy
from services.models import Service

from .catalog_queries import booking_guidance, general_relaxation_question, product_list_question, promotion_question
from .chat_intents import is_service_list_question, normalize
from .numeric_grounding import claims


_DISCOUNT_IN_PROSE = re.compile(
    r"\bgiảm(?:\s+(?:giá|ngay|trực tiếp))*\s+"
    r"(\d[\d.,]*\s*(?:%|phần\s+trăm|vnd\b|vnđ\b|đồng\b|₫|đ\b))", re.I,
)
_UNSAFE_CATALOG_TEXT = re.compile(
    r"\b(?:chua khoi|chan doan|dieu tri|nguyen chat|tre em|tre so sinh|"
    r"boi truc tiep|thoa truc tiep|uong|cam ket|bao dam|dam bao)\b",
)


def unsupported_guidance(question):
    q = f" {normalize(question)} "
    if " huy lich " in q:
        return "Bạn có thể xem và hủy lịch đủ điều kiện tại Lịch hẹn của tôi (appointments.html)."
    if " thanh toan " in q or " chuyen khoan " in q:
        return "Bạn có thể mở Hóa đơn (invoice.html) để kiểm tra trạng thái hoặc thanh toán theo hướng dẫn."
    if " dat lich " in q and not booking_guidance(question):
        return "Bạn có thể tự chọn dịch vụ, nhân viên và giờ tại trang Đặt lịch (booking.html)."
    return ""


def _with_sources(text, names):
    return text.strip()[:1150] + "\nNguồn: " + "; ".join(dict.fromkeys(names))


def _safe_excerpt(value, *, limit=220):
    for line in lines(strip_tags(value or "")):
        if not _UNSAFE_CATALOG_TEXT.search(normalize(line)) and len(line) <= limit:
            return line
    return ""


def _promotion_rows(sources):
    today = timezone.localdate()
    ids = [source.object_id for source in sources if source.kind == "promotion"]
    if not ids:
        return {}
    return {
        item.pk: item for item in Promotion.objects.filter(
            pk__in=ids, is_active=True, start_date__lte=today, end_date__gte=today
        ).prefetch_related("services__category")
    }


def _promotion_facts(item):
    expected = "percent" if item.discount_type == Promotion.DiscountType.PERCENT else "money"
    prose_parts = (item.description, item.detail, item.conditions, item.note, item.scope_note)
    discounts = (
        claim for part in prose_parts for match in _DISCOUNT_IN_PROSE.finditer(part or "")
        for claim in claims(match[1])
    )
    conflict = any(claim.kind != expected or claim.value != item.discount_value for claim in discounts)
    if conflict:
        return (f"{item.code} ({item.name}): mức giảm trong dữ liệu và nội dung công bố không khớp. "
                "Bạn nên xác nhận với Spa trước khi sử dụng mã.")
    facts = [_promotion_discount_label(item.discount_type, item.discount_value)]
    if item.min_amount is not None:
        facts.append(f"giá trị tối thiểu {money(item.min_amount)}")
    if item.max_discount is not None:
        facts.append(f"giảm tối đa {money(item.max_discount)}")
    limit, _ = policy(item)
    if limit is not None:
        facts.append(f"tối đa {limit} lượt mỗi khách")
    service_names = [service.name for service in item.services.all()
                     if service.is_active and service.category.is_active]
    if service_names:
        facts.append(f"áp dụng cho {', '.join(service_names)}")
    facts.append(f"đến {item.end_date:%d/%m/%Y}")
    for condition in lines(strip_tags(item.conditions)):
        if not any(claims(condition)) and _safe_excerpt(condition):
            facts.append(condition)
    return f"{item.code} ({item.name}): {', '.join(facts)}."


def _oil_summary(source):
    return source.name + " là sản phẩm tạo hương thơm."


def provider_sources(sources):
    """Keep citations stable while withholding conflicting or unsafe prose from Gemini."""
    promotions = _promotion_rows(sources)
    output = []
    for source in sources:
        if source.kind == "promotion":
            promotion = promotions.get(source.object_id)
            if promotion is not None:
                output.append(replace(source, text=_promotion_facts(promotion)))
        elif source.kind == "product" and " tinh dau " in f" {normalize(source.name)} ":
            output.append(replace(source, text=_oil_summary(source)))
        else:
            output.append(source)
    return output


def catalog_answer(question, sources, *, recover=False):
    """Use only retrieved, current records. Empty means let Gemini handle the question."""
    q = f" {normalize(question)} "
    kinds = {source.kind for source in sources}
    if recover:
        if kinds == {"service"} and is_service_list_question(q):
            return _with_sources(
                "Một số liệu trình của Spa gồm " + ", ".join(s.name for s in sources)
                + ". Xem thêm tại trang Dịch vụ.", [s.name for s in sources],
            )
        if len(sources) == 1 and kinds == {"spa"} and (
            booking_guidance(q) or re.search(r"\b(?:gio mo cua|may gio|mo cua|dia chi|o dau|lien he|dien thoai)\b", q)
        ):
            source = sources[0]
            return _with_sources(source.text, [source.name])
        return ""

    if kinds == {"promotion"} and (
        promotion_question(q) or any(f" {normalize(s.name.split(' · ')[0])} " in q for s in sources)
    ):
        promotions = _promotion_rows(sources)
        found = [source for source in sources if source.object_id in promotions]
        if not found:
            return ""
        facts = "\n".join(_promotion_facts(promotions[source.object_id]) for source in found)
        return _with_sources(facts + "\nKiểm tra điều kiện áp dụng tại trang Hóa đơn.", [s.name for s in found])

    if kinds == {"product"} and product_list_question(q):
        return _with_sources("Một số sản phẩm chăm sóc của Spa gồm " + ", ".join(s.name for s in sources)
                             + ". Xem thêm tại trang Sản phẩm chăm sóc.", [s.name for s in sources])

    if kinds == {"service"} and general_relaxation_question(q):
        return _with_sources(
            "Bạn có thể tham khảo " + ", ".join(s.name for s in sources) + ".",
            [s.name for s in sources],
        )

    if len(sources) == 1 and kinds == {"product"}:
        source = sources[0]
        oil = " tinh dau " in f" {normalize(source.name)} "
        if oil and re.search(r"\b(?:huong dan|su dung|dung the nao|thoa|boi|uong|cho tre)\b", q):
            return _with_sources(
                f"Với {source.name}, bạn hãy xem hướng dẫn an toàn trên nhãn và hỏi Spa trước khi dùng.",
                [source.name],
            )
        if re.search(r"\b(?:cong dung|loi ich|tac dung)\b", q):
            if oil:
                return _with_sources(_oil_summary(source), [source.name])
            item = CareProduct.objects.filter(pk=source.object_id, is_active=True).first()
            if item:
                excerpt = _safe_excerpt(item.benefits) or _safe_excerpt(item.description)
                if excerpt:
                    return _with_sources(f"{item.name}: {excerpt}", [source.name])

    service_fact = re.search(
        r"\b(?:gia bao nhieu|chi phi|bao lau|thoi luong|loi ich|cong dung|da am|"
        r"(?:cap|duong) am da mat)\b", q
    )
    if len(sources) == 1 and kinds == {"service"} and service_fact:
        source = sources[0]
        item = Service.objects.filter(pk=source.object_id, is_active=True, category__is_active=True).first()
        if item:
            text = f"{item.name}: {money(item.price)}, {item.duration_minutes} phút."
            if re.search(r"\b(?:loi ich|cong dung|tu van|(?:cap|duong) am da mat)\b", q):
                excerpt = _safe_excerpt(item.benefits) or _safe_excerpt(item.description)
                if excerpt:
                    text += f" {excerpt}"
            return _with_sources(text, [source.name])
    return ""
