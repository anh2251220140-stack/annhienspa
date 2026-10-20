from django.urls import path
from . import business_views as views
from employees.views import schedule_plan
from accounts import admin_views as accounts
urlpatterns=[
 path("accounts/",accounts.accounts),path("accounts/<int:pk>/",accounts.account_detail),path("accounts/<int:pk>/status/",accounts.toggle_account),
 path("customers/",accounts.customers),path("customers/<int:pk>/",accounts.customer_detail),path("employees/<int:employee_id>/schedules/plan/",schedule_plan),path("employees/<int:employee_id>/schedules/",views.schedules),
 path("employees/<int:employee_id>/schedules/<int:pk>/",views.schedules),
 path("<str:module>/",views.records),path("<str:module>/<int:pk>/",views.records)]
