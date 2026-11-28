from django.conf import settings
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
        from .catalog_data import catalog, promotions, public_catalog_snapshot
        page = self.template_name.rsplit("/", 1)[-1]
        promotion_page = self.template_name in (
            "pages/promotions.html", "pages/promotion-detail.html",
        )
        if (settings.PUBLIC_CATALOG_CACHE_SECONDS and page in PUBLIC_PAGES
                and not self.request.user.is_authenticated):
            (context["live_catalog"], offers), self.catalog_source = public_catalog_snapshot()
            if not promotion_page:
                offers = {
                    **offers,
                    "items": [{k: v for k, v in item.items() if k != "discountType"}
                              for item in offers["items"]],
                }
            context["live_promotions"] = offers
        else:
            context["live_catalog"] = catalog()
            context["live_promotions"] = promotions(promotion_page=promotion_page)
        if self.template_name == "pages/invoice.html":
            context["payos_demo_only"] = settings.PAYOS_DEMO_ONLY
        return context

    http_method_names = ["get", "head", "options"]
    def dispatch(self, request, *args, **kwargs):
        page = self.template_name.rsplit("/", 1)[-1]
        user = request.user
        if page == "index.html" and user.is_authenticated:
            return redirect(landing(user))
        if page not in PUBLIC_PAGES:
            if not user.is_authenticated:
                response = redirect_to_login(request.get_full_path())
                if page == "invoice.html" and settings.PAYOS_DEMO_ONLY:
                    response["X-AnNhien-Payment-Mode"] = "demo-only"
                return response
            role = "Admin" if page.startswith("admin-") else "User"
            if not user.is_active or user.role != role:
                raise PermissionDenied("Bạn không có quyền truy cập trang này.")
        response = super().dispatch(request, *args, **kwargs)
        if hasattr(self, "catalog_source"):
            result = "miss" if self.catalog_source == "mysql" else "hit"
            response["Server-Timing"] = (
                f'public-catalog-cache;desc="{result}", public-catalog-source;desc="{self.catalog_source}"'
            )
        return response

class LegacyImageView(RedirectView):
    url = "/static/images/%(path)s"
    permanent = False
