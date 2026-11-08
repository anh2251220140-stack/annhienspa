from collections import defaultdict
from datetime import date
from decimal import Decimal

from django import forms
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Avg, Count, Q, Sum
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from accounts.admin_views import customers_qs
from appointments.models import Appointment
from billing.dates import boundaries
from billing.models import Payment
from billing.views import api
from reviews.models import Review
from services.models import Service


@api
@require_GET
def summary(request):
    if request.user.role != "Admin":
        raise PermissionDenied
    today = timezone.localdate()
    start = forms.DateField().clean(request.GET.get("start") or date(today.year, 1, 1))
    end = forms.DateField().clean(request.GET.get("end") or today)
    if end < start or (end - start).days > 3660:
        raise ValidationError("Khoảng ngày không hợp lệ (tối đa 10 năm).")
    appointments = Appointment.objects.filter(appointment_date__range=(start, end))
    status = request.GET.get("status")
    if status:
        if status not in Appointment.Status.values:
            raise ValidationError("Trạng thái lịch hẹn không hợp lệ.")
        appointments = appointments.filter(status=status)
    lo, hi = boundaries(start, end)
    paid = Payment.objects.filter(status="success", requires_review=False,
        invoice__payment_status="paid", paid_at__gte=lo, paid_at__lt=hi)
    # Windows MySQL may have no named timezone tables. Use aware UTC bounds in
    # SQL and localize the returned instants before grouping calendar days.
    months, days = defaultdict(Decimal), defaultdict(Decimal)
    for timestamp, amount in paid.values_list("paid_at", "amount"):
        local = timezone.localtime(timestamp)
        months[local.strftime("%Y-%m")] += amount
        days[local.date().isoformat()] += amount
    review = Review.objects.filter(created_at__gte=lo, created_at__lt=hi)
    counts = {x['service_id']: x for x in appointments.values('service_id').annotate(
        appointments=Count('pk'), active=Count('pk', filter=~Q(status='cancelled')),
        completed=Count('pk', filter=Q(status='completed')))}
    revenues = {x['invoice__appointment__service_id']: x['total'] for x in
        paid.values('invoice__appointment__service_id').annotate(total=Sum('amount'))}
    ratings = {x['service_id']: x for x in review.values('service_id').annotate(
        reviews=Count('pk'), rating=Avg('rating'))}
    report = []
    for service in Service.objects.filter(pk__in=set(counts) | set(revenues) | set(ratings)).order_by('pk'):
        c, r = counts.get(service.pk, {}), ratings.get(service.pk, {})
        report.append(dict(service=service.name, appointments=c.get('appointments', 0),
            active=c.get('active', 0), completed=c.get('completed', 0),
            revenue=revenues.get(service.pk, 0), reviews=r.get('reviews', 0), rating=r.get('rating', 0)))
    return JsonResponse({
        'start': start, 'end': end, 'today': today,
        'customers': customers_qs().count(), 'appointments': appointments.count(),
        'periodCustomers': appointments.order_by().values('customer_id').distinct().count(),
        'todayCount': Appointment.objects.filter(appointment_date=today).count(),
        'activeServices': Service.objects.filter(is_active=True, category__is_active=True).count(),
        'revenue': paid.aggregate(n=Sum('amount'))['n'] or 0,
        'monthly': [dict(month=k, total=v) for k, v in sorted(months.items())],
        'daily': [dict(day=k, total=v) for k, v in sorted(days.items())],
        'statuses': list(appointments.values('status').annotate(count=Count('pk'))),
        'services': list(appointments.filter(status='completed').values('service__name').annotate(count=Count('pk')).order_by('-count')[:10]),
        'popular': list(appointments.exclude(status='cancelled').values('service__name').annotate(count=Count('pk')).order_by('-count')[:10]),
        'reviewCount': review.count(), 'rating': review.aggregate(n=Avg('rating'))['n'] or 0,
        'ratings': list(review.values('rating').annotate(count=Count('pk'))), 'report': report,
        'recent': [dict(id=x.pk, customer=x.customer.full_name, service=x.service.name,
            employee=x.employee.full_name, date=x.appointment_date.isoformat(),
            time=x.start_time.strftime('%H:%M'), status=x.status)
            for x in appointments.select_related('customer', 'service', 'employee').order_by('-created_at')[:5]],
    })
