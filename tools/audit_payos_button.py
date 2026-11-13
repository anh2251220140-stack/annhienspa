"""HD-3 read-only audit. No provider calls, session writes or secret values."""
import hashlib,json,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.audit_promotion_usage import read_only
from django.conf import settings
from django.db import connection
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
from billing.models import Invoice
from billing import services

assert connection.settings_dict['NAME']=='annhien_spa'
names=['PAYOS_CLIENT_ID','PAYOS_API_KEY','PAYOS_CHECKSUM_KEY','PAYOS_RETURN_URL','PAYOS_CANCEL_URL']
report=dict(checkedAt=timezone.localtime().isoformat(),configuration={name:dict(environmentPresent=bool(os.getenv(name,'')),effectivePresent=bool(getattr(settings,name,''))) for name in names})
with connection.execute_wrapper(read_only):
    i=Invoice.objects.select_related('appointment__customer__user').get(pk=3)
    report['invoice']=dict(id=i.pk,appointmentId=i.appointment_id,date=i.appointment.appointment_date,time=i.appointment.start_time,
        appointmentStatus=i.appointment.status,status=i.payment_status,total=i.total_amount,promotion=i.promotion_code_snapshot,
        onlineEligible=services.online_eligible(i),preference=i.payment_preference,
        payments=[dict(id=p.pk,status=p.status,amount=p.amount,provider_status=p.provider_status,
            requires_review=p.requires_review,expiresAt=p.expires_at,hasStoredQr=bool(p.qr_code),hasCheckout=bool(p.checkout_url)) for p in i.payments.all()])
    report['fingerprints']={}
    for table in ('users','customers','appointments','invoices','invoice_details','payments','promotions','promotion_services'):
        with connection.cursor() as c:
            c.execute('SELECT * FROM '+connection.ops.quote_name(table)+' ORDER BY id');rows=c.fetchall()
        report['fingerprints'][table]=dict(rows=len(rows),sha256=hashlib.sha256(repr(rows).encode()).hexdigest())
path=settings.BASE_DIR/'docs/payos-button-audit.json'
if path.exists():report['sameBusinessDataAsPreviousAudit']=json.loads(path.read_text(encoding='utf-8'))['fingerprints']==report['fingerprints']
path.write_text(json.dumps(report,cls=DjangoJSONEncoder,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='fingerprints'},cls=DjangoJSONEncoder,ensure_ascii=True))
