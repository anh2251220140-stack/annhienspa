from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods, require_GET, require_POST
from django.views.decorators.cache import never_cache
from core.permissions import api_role
from .models import User, Customer
from .profile_forms import CustomerProfileForm, IdentityForm


def account_row(user,actor):
    return {'id':user.pk,'username':user.username,'email':user.email,'role':user.role,'active':user.is_active,
        'joined':user.date_joined.isoformat()[:10],'canToggle':user.pk!=actor.pk and user.role=='User' and not user.is_superuser and not user.is_staff}

def page_result(request,qs,serialize):
    page=Paginator(qs,5).get_page(request.GET.get('page',1))
    return {'items':[serialize(x) for x in page], 'page':page.number,'pages':page.paginator.num_pages,'total':page.paginator.count}

@never_cache
@api_role('Admin')
@require_GET
def accounts(request):
    qs=User.objects.order_by('pk');stats={'total':qs.count(),'active':qs.filter(is_active=True).count(),'locked':qs.filter(is_active=False).count()}
    query=request.GET.get('search','').strip()
    if query:qs=qs.filter(Q(username__icontains=query)|Q(email__icontains=query))
    if request.GET.get('role'):qs=qs.filter(role=request.GET['role'])
    if request.GET.get('status') in ('active','locked'):qs=qs.filter(is_active=request.GET['status']=='active')
    data=page_result(request,qs,lambda u:account_row(u,request.user));data['stats']=stats;return JsonResponse(data)

@never_cache
@api_role('Admin')
@require_GET
def account_detail(request,pk):return JsonResponse({'item':account_row(get_object_or_404(User,pk=pk),request.user)})

@api_role('Admin')
@require_POST
def toggle_account(request,pk):
    with transaction.atomic():
        target=get_object_or_404(User.objects.select_for_update(),pk=pk)
        if not account_row(target,request.user)['canToggle']:raise PermissionDenied('Không được khóa chính mình hoặc tài khoản quản trị.')
        action=request.POST.get('action')
        if action not in ('lock','unlock'):return JsonResponse({'error':'Thao tác không hợp lệ.'},status=400)
        target.is_active=action=='unlock';target.save(update_fields=['is_active'])
        return JsonResponse({'item':account_row(target,request.user)})

def customers_qs():return Customer.objects.filter(user__role='User',user__is_superuser=False).select_related('user').order_by('pk')
def customer_row(c):
    return {'id':c.pk,'name':c.full_name,'username':c.user.username,'email':c.user.email,'phone':c.phone,'joined':c.user.date_joined.isoformat()[:10],
        'avatar':c.avatar.url if c.avatar else '', 'skin':c.skin_type or '', 'needs':(c.care_needs or '').splitlines(), 'interests':(c.preferences or '').splitlines(), 'budget':c.budget,'tier':None}

@never_cache
@api_role('Admin')
@require_GET
def customers(request):
    qs=customers_qs();query=request.GET.get('search','').strip()
    if query:qs=qs.filter(Q(full_name__icontains=query)|Q(user__username__icontains=query)|Q(user__email__icontains=query)|Q(phone__icontains=query))
    if request.GET.get('tier') not in (None,'','unset'):qs=qs.none()
    return JsonResponse(page_result(request,qs,customer_row))

@never_cache
@api_role('Admin')
@require_GET
def customer_detail(request,pk):return JsonResponse({'item':customer_row(get_object_or_404(customers_qs(),pk=pk))})

@never_cache
@api_role('User')
@require_http_methods(['GET','POST'])
def profile(request):
    if request.user.is_superuser:raise PermissionDenied
    customer=get_object_or_404(customers_qs(),user=request.user)
    if request.method=='GET':return JsonResponse({'item':customer_row(customer)})
    try:
        with transaction.atomic():
            user=User.objects.select_for_update().get(pk=request.user.pk)
            customer=Customer.objects.select_for_update().get(pk=customer.pk)
            data=request.POST.copy();data['full_name']=data.get('name','');data['skin_type']=data.get('skin','');data['care_needs']='\n'.join(data.getlist('needs'));data['preferences']='\n'.join(data.getlist('interests'))
            form=CustomerProfileForm(data,request.FILES,instance=customer);identity=IdentityForm(data,instance=user)
            valid=form.is_valid();valid_identity=identity.is_valid()
            if not valid or not valid_identity:return JsonResponse({'errors':{**form.errors,**identity.errors}},status=400)
            identity.save();customer=form.save();customer.user=user
            return JsonResponse({'item':customer_row(customer)})
    except IntegrityError:return JsonResponse({'error':'Username hoặc email đã được sử dụng.'},status=400)
