from django.urls import path
from . import views
app_name="appointments"
urlpatterns=[path("<int:pk>/admin-detail/",views.admin_detail,name="admin-detail"),path("",views.listing,name="list"),path("available-slots/",views.slots,name="slots"),
             path("book/",views.create,name="book"),path("<int:pk>/status/",views.update,name="status")]
