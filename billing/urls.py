from django.urls import path
from . import views
urlpatterns=[path("",views.listing),path("ledger/",views.ledger),path("webhook/payos/",views.webhook),path("<int:pk>/",views.detail),path("<int:pk>/promotions/",views.promotions),path("<int:pk>/<str:action>/",views.action)]
