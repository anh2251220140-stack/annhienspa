from django.urls import path
from . import views
urlpatterns=[path("",views.listing),path("services/<int:pk>/",views.service_reviews),path("appointments/<int:pk>/",views.save),path("<int:pk>/replies/",views.reply,name="review-reply")]
