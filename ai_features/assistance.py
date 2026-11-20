"""FR-22/23 orchestration: constrained candidates, explicit analysis, safe fallbacks."""
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import logging
import re

from django.db import transaction
from django.db.models import Count, Max, Min
from django.utils import timezone

from products.models import CareProduct
from reviews.models import Review
from services.models import Service

from .chat import ChatError
from .config import enabled, option, time_budget
from .provider_factory import external_provider
from .models import AIRecommendation, AIReviewAnalysis
from .providers import contains_private_input, normalize

NEEDS = {
    "Dưỡng ẩm, cải thiện da khô": "face",
    "Kiểm soát dầu, chăm sóc da mụn": "face",
    "Làm sáng da, cải thiện da xỉn màu": "face",
    "Thư giãn, giảm căng thẳng": "relax",
    "Chăm sóc tóc và da đầu": "hair",
    "Chăm sóc cơ thể, giảm mệt mỏi": "body",
}
SKINS = {"", "Da thường", "Da khô", "Da dầu", "Da hỗn hợp", "Da nhạy cảm"}


def profile_inputs(customer, data):
    allowed = {"skin", "needs", "budget", "interests", "duration"}
    if set(data) - allowed:
        raise ChatError("Thông tin gợi ý không hợp lệ.")
    # Never accept a customer ID/history supplied by the browser.
    saved_needs = customer.care_needs or ""
    try:
        saved_needs = json.loads(saved_needs)
    except (TypeError, ValueError):
        saved_needs = saved_needs.splitlines()
    if not isinstance(saved_needs, list):
        saved_needs = [saved_needs]
    need_groups = {normalize(label): value for label, value in NEEDS.items()}
    group = next((need_groups[normalize(n)] for n in saved_needs
                  if isinstance(n, str) and normalize(n) in need_groups), "")
    result = {
        "skin": data.get("skin", customer.skin_type or ""), "needs": data.get("needs", group),
        "interests": data.get("interests", customer.preferences or ""), "duration": data.get("duration", ""),
    }
    if (any(not isinstance(v, str) for v in result.values()) or result["skin"] not in SKINS
            or result["needs"] not in {"", "face", "relax", "body", "hair"}
            or result["duration"] not in {"", "short", "medium", "long"} or len(result["interests"]) > 160):
        raise ChatError("Loại da, nhu cầu hoặc thời lượng không hợp lệ.")
    if contains_private_input(result["interests"]):
        raise ChatError("Vui lòng bỏ thông tin liên hệ và thông tin bí mật khỏi sở thích.")
    value = data.get("budget", customer.budget)
    try:
        budget = None if value is None or value == "" else Decimal(str(value))
        if budget is not None and (not budget.is_finite() or budget < 0 or budget > Decimal("9999999999.99")):
            raise ValueError
    except (ValueError, InvalidOperation):
        raise ChatError("Ngân sách không hợp lệ.") from None
    result["budget"] = str(budget) if budget is not None else None
    return result


def candidates(inputs):
    qs = Service.objects.filter(is_active=True, category__is_active=True)
    if inputs["needs"]:
        qs = qs.filter(care_group=inputs["needs"])
    if inputs["budget"] is not None:
        qs = qs.filter(price__lte=Decimal(inputs["budget"]))
    duration = inputs["duration"]
    if duration == "short":
        qs = qs.filter(duration_minutes__lt=60)
    elif duration == "medium":
        qs = qs.filter(duration_minutes__gte=60, duration_minutes__lte=90)
    elif duration == "long":
        qs = qs.filter(duration_minutes__gt=90)
    return list(qs.order_by("price", "pk")[:100])


def service_history(customer):
    completed = customer.appointments.filter(status="completed")
    recent = list(completed.order_by("-appointment_date", "-pk").values_list("service_id", flat=True)[:20])
    history = [{"serviceId": row["service_id"], "count": row["count"], "lastUsed": row["last_used"].isoformat(),
                "firstUsed": row["first_used"].isoformat()}
               for row in completed.values("service_id").annotate(count=Count("pk"), last_used=Max("appointment_date"), first_used=Min("appointment_date"))
               .order_by("-last_used", "service_id")[:20]]
    return recent, history


def linked_care_products(service, skin):
    """Only ORM-backed links/tags; linked products are NOT a usage history."""
    from django.templatetags.static import static
    products = []
    for product in CareProduct.objects.filter(is_active=True, services=service).distinct().order_by("pk"):
        tags = {normalize(x.strip()) for x in re.split(r"[;,\n]", (product.skin_type or "") + "\n" + (product.suitable_for or "")) if x.strip()}
        if skin and normalize(skin) not in tags and (skin == "Da nhạy cảm" or "khong ap dung" not in tags):
            continue
        if product.care_group and product.care_group != service.care_group:
            continue
        if skin == "Da nhạy cảm" and "khong ap dung cho da nhay cam" in normalize(product.note):
            continue
        products.append({"id": product.pk, "serviceId": service.pk, "name": product.name,
            "category": product.product_type, "description": product.description,
            "ingredients": product.ingredients or "", "benefits": product.benefits or "",
            "usage": product.usage_instructions or "", "note": product.note,
            "image": product.image.url if product.image else static("images/" + (product.image_preset or "care-5.jpg")),
            "price": None})  # CareProduct has no structured price field; never invent one.
    return products[:3]


def recommend(customer, data):
    from .numeric_grounding import claims, numeric_claims_supported
    inputs = profile_inputs(customer, data)
    choices = candidates(inputs)
    if inputs["skin"] == "Da nhạy cảm":
        def not_contraindicated(service):
            note = normalize(service.note)
            return not any(term in note for term in ("khong ap dung cho da nhay cam", "khong danh cho da nhay cam"))
        choices = [s for s in choices if not_contraindicated(s)]
    if not choices:
        return {"mode": "rule", "label": "Đề xuất theo quy tắc", "items": [],
                "message": "Chưa có dịch vụ đáp ứng nhu cầu, ngân sách, thời lượng và lưu ý đã chọn."}
    own_history, history = service_history(customer)
    by_service = {row["serviceId"]: row for row in history}
    def numeric_facts(service):
        facts = f"{service.price} VND; {service.duration_minutes} phút; " + "; ".join(
            f"{r['count']} lượt; {r['firstUsed']}; {r['lastUsed']}" for r in history)
        return facts + (f"; {inputs['budget']} VND" if inputs["budget"] is not None else "")
    def reason_numbers_valid(reason, service):
        amounts = {service.price}
        if inputs["budget"] is not None:
            amounts.add(Decimal(inputs["budget"]))
        # A visit count/ID must not become an invented currency amount.
        money_claims = [c for c in claims(reason) if c.kind == "money"]
        for raw in re.findall(r"\bgia\s+(?:(?:la|chi|tu|khoang)\s+)?([0-9][0-9.,]*)", normalize(reason)):
            money_claims.extend(claims(raw + " VND"))
        return (all(c.value in amounts for c in money_claims)
                and numeric_claims_supported(reason, [numeric_facts(service)]))
    care = {s.pk: linked_care_products(s, inputs["skin"]) for s in choices}
    terms = set(normalize(inputs["interests"]).split())
    def score(s):
        return (bool(care[s.pk]) if inputs["skin"] else False,
                len(terms & set(normalize(s.name + " " + s.description).split())),
                -by_service.get(s.pk, {}).get("count", 0), -s.price, -s.pk)
    choices.sort(key=score, reverse=True)
    available = {s.pk: s for s in choices}
    def fallback_reason(s):
        prior = by_service.get(s.pk)
        basis = "Đáp ứng nhóm nhu cầu, ngân sách và thời lượng đã chọn. "
        basis += (f"Đã hoàn thành {prior['count']} lượt; không tự ưu tiên lặp lại chỉ vì lịch sử." if prior
                  else "Chưa xuất hiện trong phạm vi lịch sử đối chiếu; có thể trao đổi về phương án bổ sung.")
        return basis
    picked = [{"id": s.pk, "reason": fallback_reason(s)} for s in choices[:3]]
    mode = "rule"
    try:
        if (option("AI_PROVIDER", "mock") == "gemini" and enabled("AI_PERSONALIZATION_EXPORT_APPROVED")):
            with time_budget():
                proposed = external_provider().structured(
                    'Select 1–3 supplied eligible services. Return {"items":[{"id":integer,"reason":string}]}. '
                    "Consider skin, needs, per-treatment budget, interests, duration, frequency and last usage together. "
                    "Do not automatically prefer repeats. Consider complementary eligible services. "
                    "Absence from limited history does not prove a service was never used. "
                    "Explain the concrete preference/history tradeoff in Vietnamese, no medical conclusions, invented "
                    "facts or prices. Product usage is unavailable: linked products do not prove past usage. "
                    "Do not propose product names/ingredients; the server attaches verified linked products.",
                    {"preferences": inputs, "completedServiceIds": own_history, "serviceHistory": history,
                     "historyScope": "up to 20 most recently used services; counts include all completed visits",
                     "productUsageHistory": {"available": False},
                     "candidates": [{"id": s.pk, "name": s.name, "description": s.description[:500],
                                     "price": str(s.price), "minutes": s.duration_minutes,
                                     "suitable": s.suitable[:300], "method": s.steps[:300], "note": s.note[:300],
                                     "skinCareMatch": bool(care[s.pk])} for s in choices]},
                ).get("items")
            if not isinstance(proposed, list) or not 1 <= len(proposed) <= 3:
                raise ValueError
            seen = set()
            for row in proposed:
                if (not isinstance(row, dict) or set(row) != {"id", "reason"} or type(row.get("id")) is not int
                        or row["id"] not in available or row["id"] in seen or not isinstance(row.get("reason"), str)
                        or not 1 <= len(row["reason"]) <= 400 or contains_private_input(row["reason"])):
                    raise ValueError
                service = available[row["id"]]
                if (not reason_numbers_valid(row["reason"], service) or
                        re.search(r"\b(chua khoi|dieu tri|cam ket|bao dam|dam bao)\b", normalize(row["reason"]))):
                    raise ValueError
                seen.add(row["id"])
            picked, mode = proposed, "ai"
    except Exception:
        # Reject the entire invalid list. FR-22 fallback remains local, never paid retry.
        pass
    current = {s.pk: s for s in candidates(inputs)}
    if inputs["skin"] == "Da nhạy cảm":
        current = {pk: s for pk, s in current.items() if not_contraindicated(s)}
    if mode == "ai" and any(r["id"] in current and not reason_numbers_valid(
            r["reason"], current[r["id"]]) for r in picked):
        mode = "rule"
        picked = [{"id": s.pk, "reason": fallback_reason(s)} for s in current.values()][:3]
    picked = [r for r in picked if r["id"] in current]
    items = [{"id": r["id"], "name": current[r["id"]].name, "price": str(current[r["id"]].price),
              "minutes": current[r["id"]].duration_minutes, "reason": r["reason"],
              "history": by_service.get(r["id"], {"serviceId": r["id"], "count": None, "lastUsed": None,
                                                  "scope": "not-in-recent-20-service-history"}),
              "products": linked_care_products(current[r["id"]], inputs["skin"]),
              "caution": "Đối chiếu danh mục, không xác nhận phù hợp y khoa. Trao đổi với chuyên viên khi da nhạy cảm hoặc có lưu ý."}
             for r in picked]
    if items:
        AIRecommendation.objects.create(customer=customer, input_data=inputs,
            recommended_services=[r["id"] for r in items], reason=json.dumps({"mode": mode, "items": items}, ensure_ascii=False))
    else:
        return {"mode": "rule", "label": "Đề xuất theo quy tắc", "items": [], "alternatives": [],
                "message": "Dữ liệu dịch vụ vừa thay đổi hoặc không còn lựa chọn hợp lệ. Vui lòng chọn lại."}
    selected = {row["id"] for row in items}
    alternatives = [{"id": s.pk, "name": s.name, "price": str(s.price), "minutes": s.duration_minutes}
                    for s in current.values() if s.pk not in selected][:2] if items else []
    return {"mode": mode, "label": "Đề xuất bởi AI" if mode == "ai" else "Đề xuất theo quy tắc",
            "items": items, "alternatives": alternatives, "budgetScope": "per-treatment"}


def review_fingerprint(review):
    return sha256(json.dumps([review.rating, review.comment or ""], ensure_ascii=False).encode()).hexdigest()


INSUFFICIENT_REVIEW_SUMMARY = "Không đủ căn cứ phân tích văn bản: đánh giá chưa có nhận xét."
review_logger = logging.getLogger("ai_features.fr23")


def review_failure_diagnostic(error):
    """Read only error types and numeric HTTP codes, never messages or payloads.

    The shared adapter sanitizes its public exception but retains Python's
    exception context. Inspect a bounded chain without modifying that adapter.
    """
    from .integration import ProviderUnavailable
    chain, seen = [], set()
    while isinstance(error, Exception) and id(error) not in seen and len(chain) < 8:
        seen.add(id(error))
        chain.append(error)
        error = error.__cause__ if error.__cause__ is not None else error.__context__
    try:
        from google.genai.errors import APIError
    except ImportError:
        APIError = ()
    for item in chain:
        if isinstance(item, APIError) and type(item.code) is int:
            status = item.code
            if status in (401, 403):
                return {"code": "AUTHENTICATION_FAILED", "httpStatus": status}
            if status == 429:
                return {"code": "QUOTA_EXCEEDED", "httpStatus": status}
            if status in (400, 404, 408, 409, 422, 500, 502, 503, 504):
                return {"code": "PROVIDER_HTTP_ERROR", "httpStatus": status}
    if any(isinstance(item, TimeoutError) for item in chain):
        return {"code": "PROVIDER_TIMEOUT"}
    if any(isinstance(item, json.JSONDecodeError) for item in chain):
        return {"code": "RESPONSE_JSON_INVALID"}
    if any(isinstance(item, ProviderUnavailable) for item in chain):
        return {"code": "PROVIDER_UNAVAILABLE"}
    return {"code": "ANALYSIS_FAILED"}


def serialize_analysis(analysis, review):
    insufficient = analysis.mode == "rule" and analysis.summary == INSUFFICIENT_REVIEW_SUMMARY
    return {"reviewId": review.pk, "sentiment": None if insufficient else analysis.sentiment, "themes": analysis.themes,
            "summary": analysis.summary, "priority": None if insufficient else analysis.priority, "actions": analysis.actions,
            "mode": analysis.mode, "stale": analysis.source_hash != review_fingerprint(review),
            "analysisState": "insufficient_text" if insufficient else "available",
            "analyzedAt": analysis.analyzed_at.isoformat()}


FR23_REVIEW_PROMPT = (
    "Bạn là chuyên gia phân tích phản hồi khách hàng của Spa. "
    "Phân tích bằng tiếng Việt, chỉ dựa trên nội dung nhận xét và dữ liệu được cung cấp. "
    "Trả về JSON hợp lệ gồm sentiment, themes, summary, priority, actions. "

    "QUY TẮC CẢM XÚC: "
    "positive khi khách hàng thể hiện hài lòng và không có phàn nàn đáng kể. "
    "negative khi có sự không hài lòng, phàn nàn, thất vọng hoặc ý định không quay lại. "
    "neutral khi nhận xét khách quan, chưa thể hiện cảm xúc rõ ràng, "
    "hoặc có cả điểm tốt và điểm cần cải thiện mà không bên nào chiếm ưu thế. "
    "Không được phân loại positive chỉ vì câu có chứa lời khen "
    "nếu đồng thời có một vấn đề cần cải thiện đáng kể. "

    "QUY TẮC MỨC ƯU TIÊN: "
    "high: vấn đề vệ sinh, an toàn, nguy cơ ảnh hưởng sức khỏe; "
    "không minh bạch giá hoặc phụ phí; khiếu nại nghiêm trọng chưa được hỗ trợ. "
    "medium: chờ đợi, trễ lịch, tiếng ồn, thao tác gây khó chịu nhưng "
    "không có dấu hiệu tổn thương, tư vấn bán thêm gây áp lực, "
    "trải nghiệm không tốt, nguy cơ mất khách hoặc cần cải thiện giờ hẹn. "
    "low: phản hồi tích cực hoặc nhận xét trung tính không có vấn đề "
    "cần xử lý đáng kể. "

    "Không tự động đánh giá high chỉ vì khách dùng từ rất tệ, "
    "rất thất vọng hoặc không quay lại. "
    "Không đánh đồng mọi phản ánh tiêu cực với mức ưu tiên high. "
    "Rating chỉ là thông tin tham khảo, không được quyết định mức ưu tiên "
    "nếu nội dung nhận xét không hỗ trợ kết luận đó. "

    "themes: từ 1 đến 5 chủ đề ngắn. "
    "summary: tóm tắt trung thực, tối đa 1000 ký tự. "
    "actions: từ 1 đến 5 đề xuất cải thiện cụ thể, không bịa sự kiện. "
    "Không tự tạo thông tin khách hàng, không gửi phản hồi, "
    "không sửa đánh giá gốc. "
    "sentiment chỉ nhận positive, neutral, negative. "
    "priority chỉ nhận low, medium, high."
)


def analyze_review(review_id):
    review = Review.objects.filter(pk=review_id).first()
    if review is None:
        from django.http import Http404
        raise Http404
    fingerprint = review_fingerprint(review)
    # Honest fallback: rating statistics, never presented as AI language understanding.
    result = {"sentiment": "positive" if review.rating >= 4 else "negative" if review.rating <= 2 else "neutral",
              "themes": ["Theo số sao; chưa phân tích nội dung"],
              "summary": "Chưa có phân tích AI. Quản trị viên cần đọc nhận xét gốc.",
              "priority": "high" if review.rating <= 2 else "low",
              "actions": ["Đọc đánh giá gốc và xác minh trước khi phản hồi."], "mode": "rule", "model_name": ""}
    # Existing DB constraints require a sentiment/priority. Neutral/low here are
    # storage placeholders, NOT text classifications; the API exposes null and
    # an explicit insufficient_text state on both POST and GET, without migration.
    if not (review.comment or "").strip():
        result.update(sentiment="neutral", priority="low", themes=[], summary=INSUFFICIENT_REVIEW_SUMMARY)
    provider_name = option("AI_PROVIDER", "mock")
    provider_name = provider_name if provider_name in {"gemini", "mock"} else "unavailable"
    diagnostic = {"code": "PROVIDER_NOT_SELECTED"}
    output_received = False
    try:
        if not (review.comment or "").strip():
            diagnostic = {"code": "INSUFFICIENT_TEXT"}
        elif not enabled("AI_REVIEW_EXPORT_APPROVED"):
            diagnostic = {"code": "REVIEW_EXPORT_NOT_APPROVED"}
        elif contains_private_input(review.comment):
            diagnostic = {"code": "PRIVATE_INPUT_BLOCKED"}
        elif provider_name == "gemini":
            with time_budget():
                provider = external_provider()
                output = provider.structured(
                    FR23_REVIEW_PROMPT,
                    {"rating": review.rating, "comment": review.comment},
                )
            output_received = True
            if not isinstance(output, dict) or output.get("sentiment") not in AIReviewAnalysis.Sentiment.values:
                raise ValueError
            if output.get("priority") not in {"low", "medium", "high"}:
                raise ValueError
            if not isinstance(output.get("summary"), str) or not 1 <= len(output["summary"]) <= 1000:
                raise ValueError
            for field, length in (("themes", 100), ("actions", 300)):
                values = output.get(field)
                if not isinstance(values, list) or not 1 <= len(values) <= 5 or any(
                        not isinstance(x, str) or not 1 <= len(x) <= length for x in values):
                    raise ValueError
            if contains_private_input(" ".join([output["summary"], *output["themes"], *output["actions"]])):
                diagnostic = {"code": "PRIVATE_OUTPUT_BLOCKED"}
                raise ValueError
            result = {k: output[k] for k in ("sentiment", "themes", "summary", "priority", "actions")}
            result.update(mode="ai", model_name=provider.name)
            diagnostic = {"code": "AI_ANALYSIS_VALIDATED"}
    except Exception as error:
        if diagnostic["code"] != "PRIVATE_OUTPUT_BLOCKED":
            diagnostic = {"code": "OUTPUT_VALIDATION_FAILED"} if output_received else review_failure_diagnostic(error)
        # Fixed codes/provider labels only. No exc_info, raw exception, review ID,
        # comment, key, prompt, response body or SDK headers are logged.
        review_logger.warning("FR23 fallback code=%s provider=%s", diagnostic["code"], provider_name)
    with transaction.atomic():
        current = Review.objects.select_for_update().get(pk=review_id)
        if review_fingerprint(current) != fingerprint:
            raise ChatError("Đánh giá vừa thay đổi. Vui lòng phân tích lại.", 409)
        analysis, _ = AIReviewAnalysis.objects.update_or_create(review=current, defaults={
            **result, "source_hash": fingerprint, "analyzed_at": timezone.now()})
    response = serialize_analysis(analysis, current)
    response["diagnostics"] = {**diagnostic, "provider": provider_name}
    return response
