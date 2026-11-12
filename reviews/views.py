from django import forms
from django.utils import timezone
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_GET,require_POST
from django.views.decorators.cache import never_cache
from django.db.models import Avg, Prefetch
from django.core.paginator import Paginator
from billing.views import api
from appointments.models import Appointment
from .models import Review,ReviewReply

class ReviewForm(forms.Form):
    rating=forms.IntegerField(min_value=1,max_value=5)
    comment=forms.CharField(required=False,max_length=2000)

def row(r):
    return dict(id=r.pk,appointmentId=r.appointment_id,customer=r.customer.full_name,service=r.service.name,serviceId=r.service_id,rating=r.rating,comment=r.comment or "",createdAt=timezone.localtime(r.created_at).isoformat(),replies=[dict(id=x.pk,name=x.user.username,role=x.user.role,content=x.content,createdAt=timezone.localtime(x.created_at).isoformat()) for x in r.replies.select_related("user").order_by("pk")])

def scoped(user):
    q=Review.objects.select_related("customer","service","appointment").order_by("-pk")
    return q if user.role=="Admin" else q.filter(customer__user=user)

@api
@require_GET
def listing(request):
    q=scoped(request.user)
    eligible=Appointment.objects.filter(customer__user=request.user,status="completed").select_related("service") if request.user.role=="User" else []
    return JsonResponse({"items":[row(r) for r in q],"eligible":[dict(id=a.pk,service=a.service.name,serviceId=a.service_id,date=a.appointment_date.isoformat()) for a in eligible]})


@never_cache
@require_GET
def service_reviews(request,pk):
    from services.models import Service
    get_object_or_404(Service,pk=pk,is_active=True,category__is_active=True)
    replies=ReviewReply.objects.select_related('user').order_by('pk')
    qs=Review.objects.filter(service_id=pk).select_related('customer').prefetch_related(
        Prefetch('replies',queryset=replies)
    ).order_by('-pk')
    page=Paginator(qs,10).get_page(request.GET.get('page'))
    user=request.user
    active_account=user.is_authenticated and user.is_active
    items=[]
    for review in page:
        item=dict(rating=review.rating,comment=review.comment or '',name=review.customer.full_name,
            createdAt=timezone.localtime(review.created_at).isoformat(),replies=[
                dict(name='An Nhiên Spa' if reply.user.role=='Admin' else review.customer.full_name,
                     role=reply.user.role,content=reply.content,createdAt=timezone.localtime(reply.created_at).isoformat())
                for reply in review.replies.all()
            ])
        if active_account and (user.role=='Admin' or (user.role=='User' and review.customer.user_id==user.pk)):
            item['replyUrl']=reverse('review-reply',kwargs={'pk':review.pk})
        items.append(item)
    return JsonResponse(dict(items=items,total=page.paginator.count,page=page.number,pages=page.paginator.num_pages,average=qs.aggregate(n=Avg('rating'))['n'] or 0))

@api
@require_POST
@transaction.atomic
def save(request,pk):
    if request.user.role!="User":raise PermissionDenied
    a=get_object_or_404(Appointment.objects.select_for_update(),pk=pk,customer__user=request.user)
    if a.status!="completed":raise ValidationError("Chỉ đánh giá lịch đã hoàn thành.")
    form=ReviewForm(request.POST)
    if not form.is_valid():return JsonResponse({"errors":form.errors},status=400)
    r=Review.objects.filter(appointment=a).first() or Review(appointment=a,customer=a.customer,service=a.service)
    r.rating=form.cleaned_data["rating"];r.comment=form.cleaned_data["comment"];r.save()
    return JsonResponse({"item":row(r)})

@api
@require_POST
def reply(request,pk):
    r=get_object_or_404(scoped(request.user),pk=pk)
    content=forms.CharField(max_length=2000).clean(request.POST.get("content"))
    ReviewReply.objects.create(review=r,user=request.user,content=content)
    return JsonResponse({"item":row(r)},status=201)
