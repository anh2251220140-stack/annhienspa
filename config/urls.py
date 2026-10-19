from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path, re_path
from core.views import LegacyImageView
urlpatterns = [path("api/admin/", include("core.business_urls")), path("api/appointments/", include("appointments.urls")), path("accounts/", include("accounts.urls")), path("", include("core.urls")),
    re_path(r"^images/(?P<path>.+)$", LegacyImageView.as_view())]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
