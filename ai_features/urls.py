from django.urls import path
from . import views

app_name = "ai_features"
urlpatterns = [
    path("chat/", views.chat, name="chat"),
    path("chat/sessions/", views.sessions, name="sessions"),
    path("chat/sessions/<int:session_id>/", views.detail, name="detail"),
    path("admin/chat/sessions/", views.admin_sessions, name="admin-sessions"),
    path("admin/chat/sessions/<int:session_id>/", views.admin_detail, name="admin-detail"),
]
