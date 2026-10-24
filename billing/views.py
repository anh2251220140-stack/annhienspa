import json
import re
from decimal import Decimal
from functools import wraps
from django import forms
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q,Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET,require_POST
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import never_cache
from .models import Invoice,Payment
from .dates import boundaries
from . import services,gateway


def api(view):
    @wraps(view)
    @never_cache
    def wrapped(request,*args,**kwargs):
        if not request.user.is_authenticated:return JsonResponse({"error":"Vui lòng đăng nhập."},status=401)
        if not request.user.is_active or request.user.role not in ("User","Admin"):raise PermissionDenied
        try:return view(request,*args,**kwargs)
        except ValidationError as e:return JsonResponse({"error":" ".join(e.messages)},status=400)
    return wrapped


def payment_row(p):
    return dict(id=p.pk,invoiceId=p.invoice_id,amount=p.amount,method=p.payment_method,status=p.status,statusLabel=p.get_status_display(),createdAt=timezone.localtime(p.created_at).isoformat(),paidAt=timezone.localtime(p.paid_at).isoformat() if p.paid_at else None,reference=p.transaction_code or "",orderCode=p.order_code,providerStatus=p.provider_status,requiresReview=p.requires_review,recordedBy=p.recorded_by_id)


def invoice_row(i):
    a=i.appointment;detail=i.details.first()
    row=dict(id=i.pk,appointmentId=a.pk,customer=a.customer.full_name,service=detail.service_name_snapshot if detail else a.service.name,employee=a.employee.full_name,date=a.appointment_date.isoformat(),time=a.start_time.strftime("%H:%M"),appointmentStatus=a.status,subtotal=i.subtotal,priceSnapshot=i.subtotal,discount=i.discount_amount,total=i.total_amount,promotion=i.promotion_code_snapshot or (i.promotion.code if i.promotion else ""),status=i.payment_status,statusLabel=i.get_payment_status_display(),createdAt=timezone.localtime(i.created_at).isoformat(),onlineEligible=services.online_eligible(i),payments=[payment_row(p) for p in i.payments.all()])
    pending=next((p for p in i.payments.all() if p.status=="pending" and p.payment_method=="online"),None)
    row.update(paymentPreference="online" if pending else i.payment_preference,
        paymentAllowed=services.payable(i),promotionEditable=services.promotion_editable(i),
        needsReview=any(p.requires_review for p in i.payments.all()),currentOnline=None)
    row['promotionUsage']=None
    row['payosConfigured']=gateway.configured()
    if i.promotion_id:
        from promotions.services import policy,usage
        limit,_=policy(i.promotion)
        row['promotionUsage']=dict(limit=limit,**usage(i.promotion,a.customer_id))
    if pending:
        from .qr import image_data
        now=timezone.now()
        remaining=max(0,(pending.expires_at-now).total_seconds()) if pending.expires_at else 0
        usable=(row['onlineEligible'] and not row['needsReview'] and pending.amount==i.total_amount
            and remaining>0 and pending.provider_status=='PENDING' and bool(pending.payment_link_id))
        row["currentOnline"]=dict(orderCode=pending.order_code,amount=pending.amount,providerStatus=pending.provider_status,
            expiresAt=pending.expires_at.isoformat() if pending.expires_at else None,
            serverNow=now.isoformat(),remainingSeconds=remaining,expired=bool(pending.expires_at and remaining<=0),
            qrImage=image_data(pending.qr_code) if usable else '',
            checkoutUrl=pending.checkout_url if usable else '')
    return row


def invoices_for(user):
    qs=Invoice.objects.select_related("appointment__customer__user","appointment__service","appointment__employee","promotion").prefetch_related("details","payments").order_by("-pk")
    return qs if user.role=="Admin" else qs.filter(appointment__customer__user=user)


@api
@require_GET
def listing(request):
    qs=invoices_for(request.user)
    if request.GET.get("status"):qs=qs.filter(payment_status=request.GET["status"])
    if request.GET.get("date"):
        day=forms.DateField().clean(request.GET["date"]);lo,hi=boundaries(day,day)
        qs=qs.filter(created_at__gte=lo,created_at__lt=hi)
    if request.GET.get("search"):
        q=request.GET["search"].strip()
        number=re.fullmatch(r"(?:HD-)?(\d+)",q,re.I)
        appointment=re.fullmatch(r"LH-(\d+)",q,re.I)
        qs=qs.filter(Q(appointment__customer__full_name__icontains=q)|Q(details__service_name_snapshot__icontains=q)
            |Q(pk=int(number[1]) if number else 0)|Q(appointment_id=int(appointment[1]) if appointment else 0)).distinct()
    page=Paginator(qs,10).get_page(request.GET.get("page"))
    return JsonResponse(dict(items=[invoice_row(i) for i in page],page=page.number,pages=page.paginator.num_pages,total=page.paginator.count))


@api
@require_GET
def detail(request,pk):return JsonResponse({"item":invoice_row(get_object_or_404(invoices_for(request.user),pk=pk))})


@api
@require_GET
def promotions(request,pk):
    invoice=get_object_or_404(invoices_for(request.user),pk=pk)
    return JsonResponse(services.promotion_choices(invoice))


@api
@require_GET
def ledger(request):
    if request.user.role!="Admin":raise PermissionDenied
    return JsonResponse({"invoices":[invoice_row(i) for i in invoices_for(request.user)],"payments":[payment_row(p) for p in Payment.objects.order_by("-pk")]})


@api
@require_POST
def action(request,pk,action):
    get_object_or_404(invoices_for(request.user),pk=pk)
    if action=="cash":services.cash(request.user,pk,forms.DecimalField(max_digits=12,decimal_places=2,min_value=0).clean(request.POST.get("amount")))
    elif action=="promotion":services.apply_promotion(request.user,pk,forms.CharField(max_length=50,required=False).clean(request.POST.get("code")))
    elif action=="remove-promotion":services.apply_promotion(request.user,pk,"")
    elif action=="edit-promotion":services.begin_promotion_edit(request.user,pk)
    elif action=="select-spa":services.select_spa(request.user,pk)
    elif action=="cancel-online":services.cancel_online(request.user,pk)
    elif action=="refresh-online":services.refresh_online(request.user,pk)
    elif action=="online":
        p=services.online(request.user,pk)
        return JsonResponse({"checkoutUrl":p.checkout_url,"orderCode":p.order_code,"status":p.status})
    else:raise ValidationError("Thao tác không hợp lệ.")
    return JsonResponse({"item":invoice_row(invoices_for(request.user).get(pk=pk))})


@csrf_exempt
@require_POST
def webhook(request):
    if len(request.body)>65536:return JsonResponse({"error":"Payload too large"},status=400)
    try:data=gateway.verify(request.body)
    except Exception:return JsonResponse({"error":"Invalid signature or payload"},status=400)
    try:services.accept_webhook(data)
    except ValidationError:return JsonResponse({"error":"Transaction mismatch"},status=400)
    return JsonResponse({"code":"00","desc":"success"})
