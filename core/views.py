from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic import TemplateView, RedirectView
from accounts.views import landing

PUBLIC_PAGES = {"index.html", "services.html", "service-detail.html", "promotions.html", "promotion-detail.html"}

@method_decorator(never_cache, name="dispatch")
class FrontendView(TemplateView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .catalog_data import catalog, promotions
        context["live_catalog"] = catalog()
        context["live_promotions"] = promotions()
        return context

    http_method_names = ["get", "head", "options"]
    def dispatch(self, request, *args, **kwargs):
        page = self.template_name.rsplit("/", 1)[-1]
        user = request.user
        if page == "index.html" and user.is_authenticated:
            return redirect(landing(user))
        if page not in PUBLIC_PAGES:
            if not user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            role = "Admin" if page.startswith("admin-") else "User"
            if not user.is_active or user.role != role:
                raise PermissionDenied("Bạn không có quyền truy cập trang này.")
        return super().dispatch(request, *args, **kwargs)

class LegacyImageView(RedirectView):
    url = "/static/images/%(path)s"
    permanent = False
