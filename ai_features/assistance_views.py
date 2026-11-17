from functools import wraps

from django.core.cache import cache
from django.http import Http404, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from accounts.models import User

from .assistance import analyze_review, recommend, serialize_analysis
from .chat import ChatError
from .config import enabled
from .models import AIReviewAnalysis
from .views import _payload


def access(*, admin=False):
    def decorate(view):
        @never_cache
        @wraps(view)
        def guarded(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                return JsonResponse({"error": "Vui lòng đăng nhập."}, status=401)
            if not user.is_active or user.role != (User.Role.ADMIN if admin else User.Role.USER):
                return JsonResponse({"error": "Bạn không có quyền thực hiện thao tác này."}, status=403)
            if admin and not enabled("AI_ASSISTANCE_ENABLED"):
                return JsonResponse({"error": "Chức năng hỗ trợ AI chưa được bật."}, status=503)
            if admin and not user.has_perm("ai_features.change_aireviewanalysis"):
                return JsonResponse({"error": "Chưa được cấp quyền phân tích đánh giá."}, status=403)
            try:
                # Limits are checked before providers; a busy/repeated click cannot trigger more calls.
                if request.method == "POST" and not cache.add(f"ai-assistance:{view.__name__}:{user.pk}", True, 5):
                    response = JsonResponse({"error": "Vui lòng chờ 5 giây trước lần phân tích tiếp theo."}, status=429)
                    response["Retry-After"] = "5"
                    return response
                return view(request, *args, **kwargs)
            except Http404:
                return JsonResponse({"error": "Không tìm thấy dữ liệu."}, status=404)
            except ChatError as error:
                return JsonResponse({"error": str(error)}, status=error.status)
        return guarded
    return decorate


@access()
@require_http_methods(["POST"])
def recommendations(request):
    if not hasattr(request.user, "customer"):
        raise ChatError("Vui lòng cập nhật hồ sơ chăm sóc trước khi nhận gợi ý.")
    return JsonResponse(recommend(request.user.customer, _payload(request)))


@access(admin=True)
@require_http_methods(["GET", "POST"])
def analysis(request, review_id):
    if request.method == "GET":
        item = AIReviewAnalysis.objects.select_related("review").filter(review_id=review_id).first()
        return JsonResponse({"analysis": serialize_analysis(item, item.review) if item else None})
    data = _payload(request)
    if data:
        raise ChatError("Yêu cầu phân tích không cần nội dung bổ sung.")
    return JsonResponse({"analysis": analyze_review(review_id)})


@access(admin=True)
@require_http_methods(["POST"])
def batch_analysis(request):
    data = _payload(request)
    ids = data.get("reviewIds")
    if (set(data) != {"reviewIds"} or not isinstance(ids, list) or not 1 <= len(ids) <= 5
            or any(type(x) is not int or not 0 < x < 2**63 for x in ids) or len(set(ids)) != len(ids)):
        raise ChatError("Chọn từ 1 đến 5 đánh giá riêng biệt để phân tích.")
    from reviews.models import Review
    if Review.objects.filter(pk__in=ids).count() != len(ids):
        raise Http404
    return JsonResponse({"items": [analyze_review(pk) for pk in ids]})
