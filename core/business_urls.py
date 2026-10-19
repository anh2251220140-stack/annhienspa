from django.urls import path
from . import business_views as views
urlpatterns=[path("employees/<int:employee_id>/schedules/",views.schedules),
 path("employees/<int:employee_id>/schedules/<int:pk>/",views.schedules),
 path("<str:module>/",views.records),path("<str:module>/<int:pk>/",views.records)]
