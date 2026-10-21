from django.urls import path
from . import views
from .password_reset import ResetView, ConfirmView, TEMPLATE
from django.contrib.auth import views as auth_views
app_name = "accounts"
urlpatterns = [
    path("password-reset/", ResetView.as_view(), name="password_reset"),
    path("password-reset/done/", auth_views.PasswordResetDoneView.as_view(template_name=TEMPLATE, title="Kiểm tra email", extra_context={"reset_stage":"done"}), name="password_reset_done"),
    path("reset/<uidb64>/<token>/", ConfirmView.as_view(), name="password_reset_confirm"),
    path("reset/complete/", auth_views.PasswordResetCompleteView.as_view(template_name=TEMPLATE, title="Đặt lại thành công", extra_context={"reset_stage":"complete"}), name="password_reset_complete"),
path("login/", views.login_view, name="login"),
               path("register/", views.register_view, name="register"),
               path("logout/", views.logout_view, name="logout")]
