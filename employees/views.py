import json
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from core.permissions import api_role
from .models import Employee
from .scheduling import apply_plan

@api_role('Admin')
@require_POST
def schedule_plan(request,employee_id):
    get_object_or_404(Employee,pk=employee_id)
    try:
        data=json.loads(request.POST.get('plan','{}'))
        if not isinstance(data,dict):raise ValueError
        return JsonResponse(apply_plan(employee_id,data))
    except (ValueError,TypeError):return JsonResponse({'error':'Dữ liệu lịch không hợp lệ.'},status=400)
    except ValidationError as e:return JsonResponse({'error':'\n'.join(e.messages)},status=400)
