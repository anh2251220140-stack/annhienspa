from django.http import JsonResponse
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from core.permissions import api_role
from services.models import Service
from .services import evaluate_code

@api_role('User')
@require_POST
def validate_code(request):
    try:
        pk=int(request.POST.get('service',''))
        service=get_object_or_404(Service.objects.select_related('category'),pk=pk)
        from accounts.models import Customer
        customer_id=Customer.objects.filter(user=request.user).values_list('pk',flat=True).first()
        return JsonResponse(evaluate_code(request.POST.get('code',''),service,customer_id=customer_id))
    except (ValueError,ValidationError) as e:return JsonResponse({'error':' '.join(e.messages) if isinstance(e,ValidationError) else 'Dịch vụ không hợp lệ.'},status=400)
