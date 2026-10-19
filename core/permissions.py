from functools import wraps
from django.http import JsonResponse

def api_role(role):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return JsonResponse({"error":"Vui lòng đăng nhập."}, status=401)
            if not request.user.is_active or request.user.role != role:
                return JsonResponse({"error":"Bạn không có quyền thực hiện thao tác này."}, status=403)
            return view(request, *args, **kwargs)
        return wrapped
    return decorator
