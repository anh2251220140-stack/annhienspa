from django.conf import settings
from .local_media import local_image
from django.urls import include, path, re_path
from core.views import LegacyImageView
from promotions.views import validate_code
from dashboard.views import summary
from accounts.admin_views import profile

urlpatterns = [path("api/dashboard/",summary),path("api/billing/",include("billing.urls")),path("api/reviews/",include("reviews.urls")),path("api/profile/",profile),
    path("api/ai/", include("ai_features.urls")),
    path("api/promotions/validate/",validate_code),path("api/admin/", include("core.business_urls")), path("api/appointments/", include("appointments.urls")), path("accounts/", include("accounts.urls")), path("", include("core.urls")),
    re_path(r"^images/(?P<path>.+)$", LegacyImageView.as_view())]
if settings.LOCAL_MEDIA_ENABLED:
    urlpatterns += [path("media/<path:path>", local_image, name="local-media-image")]
