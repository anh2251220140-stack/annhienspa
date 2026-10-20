from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.forms.models import model_to_dict
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from .permissions import api_role
from .business_layout import groups_for
from contextlib import nullcontext
from promotions.services import code_lock
from .business_forms import REGISTRY, ScheduleForm
from employees.models import Employee, EmployeeSchedule
from appointments.models import Appointment
from services.models import Service


def row(item):
    d={"id":item.pk,"name":getattr(item,"name",getattr(item,"full_name","")),"active":item.is_active,
       "description":getattr(item,"description","") or ""}
    for attr in ("price","duration_minutes","product_type","specialty","phone","code","discount_type","discount_value","start_date","end_date","category_id"):
        if hasattr(item,attr):d[attr]=getattr(item,attr)
    if hasattr(item,"category"):d["category"]=item.category.name
    if hasattr(item,"services"):d["serviceIds"]=list(item.services.values_list("pk",flat=True))
    return d

def form_html(request,form,module="schedules",detail=False):
    return render_to_string("partials/business_detail.html" if detail else "partials/business_form.html", {"form":form,"module":module,"groups":groups_for(form,module)},request=request)
def error_json(error):
    return JsonResponse({"error":" ".join(error.messages) if isinstance(error,ValidationError) else "Dữ liệu trùng hoặc có liên kết không hợp lệ."},status=400)

@never_cache
@api_role("Admin")
@require_http_methods(["GET","POST"])
def records(request,module,pk=None):
    Form=REGISTRY.get(module)
    if not Form:raise Http404
    Model=Form._meta.model
    if request.method=="GET":
        if pk==0:return JsonResponse({"html":form_html(request,Form(),module)})
        if pk:return JsonResponse({"html":form_html(request,Form(instance=get_object_or_404(Model,pk=pk)),module,request.GET.get("view")=="1")})
        return JsonResponse({"items":[row(x) for x in Model.objects.order_by("pk")]})
    try:
        with code_lock() if module=="promotions" else nullcontext(), transaction.atomic():
            item=get_object_or_404(Model.objects.select_for_update(),pk=pk) if pk else None
            if request.POST.get("_toggle") and item:
                item.is_active=not item.is_active;item.save()
                return JsonResponse({"item":row(item)})
            form=Form(request.POST,request.FILES,instance=item)
            if not form.is_valid():return JsonResponse({"errors":form.errors},status=400)
            if module=="employees" and item:
                removed=set(item.services.values_list("pk",flat=True))-set(form.cleaned_data["services"].values_list("pk",flat=True))
                if Appointment.objects.filter(employee=item,service_id__in=removed,status__in=["pending","confirmed"]).exists():
                    raise ValidationError("Không bỏ phân công dịch vụ đang có lịch hẹn chờ/đã xác nhận.")
            item=form.save()
            return JsonResponse({"item":row(item)},status=200 if pk else 201)
    except (ValidationError,IntegrityError) as error:return error_json(error)

@never_cache
@api_role("Admin")
@require_http_methods(["GET","POST"])
def schedules(request,employee_id,pk=None):
    employee=get_object_or_404(Employee,pk=employee_id)
    if request.method=="GET":
        if pk is None:
            items=employee.schedules.filter(is_active=True).order_by("work_date","start_time")
            return JsonResponse({"items":[{"id":x.pk,"date":x.work_date,"start":x.start_time.strftime("%H:%M"),"end":x.end_time.strftime("%H:%M"),"status":x.get_status_display(),"note":x.note or ""} for x in items]})
        item=get_object_or_404(EmployeeSchedule,pk=pk,employee=employee) if pk else EmployeeSchedule(employee=employee)
        return JsonResponse({"html":form_html(request,ScheduleForm(instance=item))})
    try:
        with transaction.atomic():
            Employee.objects.select_for_update().get(pk=employee.pk)
            item=get_object_or_404(EmployeeSchedule,pk=pk,employee=employee) if pk else EmployeeSchedule(employee=employee)
            if pk and Appointment.objects.filter(employee=employee,appointment_date=item.work_date,status__in=["pending","confirmed"],start_time__lt=item.end_time,end_time__gt=item.start_time).exists():
                raise ValidationError("Ca đang có lịch hẹn: không được thay đổi ca trước khi xử lý các lịch liên quan.")
            form=ScheduleForm(request.POST,instance=item)
            if not form.is_valid():return JsonResponse({"errors":form.errors},status=400)
            form.save()
            return JsonResponse({"ok":True},status=200 if pk else 201)
    except (ValidationError,IntegrityError) as error:return error_json(error)
