from django.urls import path
from .pages import PAGES
from .views import FrontendView
from accounts.views import login_view, register_view
app_name = "core"
urlpatterns = [path("", FrontendView.as_view(template_name="pages/index.html"), name="landing")]
for page in PAGES:
    view = {"login.html": login_view, "register.html": register_view}.get(page)
    urlpatterns.append(path(page, view or FrontendView.as_view(template_name="pages/" + page), name=page[:-5]))
