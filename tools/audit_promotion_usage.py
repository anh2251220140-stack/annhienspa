"""Read-only audit of TESTSPA10/HD-2. Never logs credentials or creates sessions."""
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection
from django.test import RequestFactory
from django.utils import timezone
from billing.models import Invoice
from billing.views import promotions as promotion_view
from promotions.models import Promotion
from promotions.services import policy,usage


def read_only(execute,sql,params,many,context):
    if sql.lstrip().split()[0].upper() not in ('SELECT','SHOW','SET'):
        raise RuntimeError('Audit permits read-only SQL only')
    return execute(sql,params,many,context)


def audit():
    assert connection.settings_dict['NAME']=='annhien_spa'
    with connection.execute_wrapper(read_only):
        p=Promotion.objects.get(code='TESTSPA10')
        invoice=Invoice.objects.select_related('appointment__customer__user').get(pk=2)
        request=RequestFactory().get('/api/billing/2/promotions/')
        request.user=invoice.appointment.customer.user
        response=promotion_view(request,2)
        limit,manual=policy(p)
        report=dict(checkedAt=timezone.localtime().isoformat(),database=connection.settings_dict['NAME'],
            promotion=dict(id=p.pk,code=p.code,configuredLimit=p.per_customer_limit,effectiveLimit=limit,
                conditions=p.conditions,note=p.note,manualConditions=manual,start=p.start_date,end=p.end_date,
                active=p.is_active,minAmount=p.min_amount,maxDiscount=p.max_discount,
                serviceIds=list(p.services.values_list('pk',flat=True))),
            invoice=dict(id=invoice.pk,appointmentId=invoice.appointment_id,status=invoice.payment_status,
                appointmentStatus=invoice.appointment.status,date=invoice.appointment.appointment_date,
                subtotal=invoice.subtotal,total=invoice.total_amount,promotionId=invoice.promotion_id),
            usage=usage(p,invoice.appointment.customer_id),apiStatus=response.status_code,
            dropdown=json.loads(response.content),fingerprints={})
        # Compare only hashes/counts, never export account/password/customer fields.
        for table in ('users','customers','appointments','invoices','invoice_details','payments','promotions','promotion_services'):
            with connection.cursor() as cursor:
                cursor.execute('SELECT * FROM '+connection.ops.quote_name(table)+' ORDER BY id')
                rows=cursor.fetchall()
            report['fingerprints'][table]=dict(rows=len(rows),sha256=hashlib.sha256(repr(rows).encode()).hexdigest())
    path=settings.BASE_DIR/'docs/promotion-usage-audit.json'
    if path.exists():
        before=json.loads(path.read_text(encoding='utf-8'))
        report['sameBusinessDataAsPreviousAudit']=before['fingerprints']==report['fingerprints']
    path.write_text(json.dumps(report,cls=DjangoJSONEncoder,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(apiStatus=response.status_code,effectiveLimit=limit,manualConditions=len(manual),
        availableCodes=[x['code'] for x in report['dropdown']['items']],
        unchanged=report.get('sameBusinessDataAsPreviousAudit')),ensure_ascii=True))


if __name__=='__main__':audit()
