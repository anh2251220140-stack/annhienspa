from django.core.exceptions import ValidationError, PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.cache import never_cache
from django import forms
from core.permissions import api_role
from .forms import BookingForm, TransitionForm
from .models import Appointment
from .services import available_slots, book, transition, start_datetime


def serialize(item):
    invoice = getattr(item,"invoice",None)
    return {"id":item.pk,"service":item.service.name,"serviceId":item.service_id,"employee":item.employee.full_name,
        "employeeId":item.employee_id,"customer":item.customer.full_name,"date":item.appointment_date.isoformat(),
        "time":item.start_time.strftime("%H:%M"),"end":item.end_time.strftime("%H:%M"),"status":item.status,
        "statusLabel":item.get_status_display(),"note":item.note or "","invoiceStatus":invoice.get_payment_status_display() if invoice else None,"invoiceId":invoice.pk if invoice else None,
        "cancellable":item.status in ("pending","confirmed") and start_datetime(item.appointment_date,item.start_time)>timezone.now() and (not invoice or invoice.payment_status!="paid")}

def failure(error):
    return JsonResponse({"error":" ".join(error.messages)},status=400)

@never_cache
@api_role("User")
@require_GET
def slots(request):
    try:
        service = forms.IntegerField(min_value=1).clean(request.GET.get("service"))
        employee = forms.IntegerField(min_value=1).clean(request.GET.get("employee"))
        day = forms.DateField().clean(request.GET.get("date"))
        return JsonResponse({"slots":available_slots(request.user,service,employee,day)})
    except ValidationError as error: return failure(error)

@api_role("User")
@require_POST
def create(request):
    form = BookingForm(request.POST)
    if not form.is_valid(): return JsonResponse({"errors":form.errors},status=400)
    try:
        d=form.cleaned_data
        item=book(request.user,d["service"],d["employee"],d["date"],d["time"],d["note"])
        return JsonResponse({"item":serialize(item)},status=201)
    except ValidationError as error: return failure(error)

@never_cache
@require_GET
def listing(request):
    if not request.user.is_authenticated:return JsonResponse({"error":"Vui lòng đăng nhập."},status=401)
    if request.user.role not in ("User","Admin"):raise PermissionDenied
    items=Appointment.objects.select_related("service","employee","customer__user","invoice").order_by("-appointment_date","-start_time")
    if request.user.role=="User":items=items.filter(customer__user=request.user)
    try:
        if request.GET.get("date"):items=items.filter(appointment_date=forms.DateField().clean(request.GET["date"]))
        if request.GET.get("employee"):items=items.filter(employee_id=forms.IntegerField(min_value=1).clean(request.GET["employee"]))
        if request.GET.get("status"):items=items.filter(status=request.GET["status"])
    except ValidationError as error:return failure(error)
    return JsonResponse({"items":[serialize(i) for i in items]})

@require_POST
def update(request,pk):
    if not request.user.is_authenticated:return JsonResponse({"error":"Vui lòng đăng nhập."},status=401)
    get_object_or_404(Appointment,pk=pk)
    form=TransitionForm(request.POST)
    if not form.is_valid():return JsonResponse({"errors":form.errors},status=400)
    try:
        d=form.cleaned_data
        item=transition(request.user,pk,d["status"],d["employee"],d["consent"],d["reason"])
        return JsonResponse({"item":serialize(item)})
    except ValidationError as error:return failure(error)
