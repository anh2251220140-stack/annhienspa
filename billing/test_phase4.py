import json
from datetime import timedelta,time,datetime,date,timezone as dt_timezone
from decimal import Decimal
from unittest.mock import patch
from types import SimpleNamespace
from django.test import TestCase,Client,override_settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from core.test_phase3 import Fixtures
from appointments.services import book,transition
from appointments.models import Appointment
from .models import Invoice,Payment
from .services import cash,online,accept_webhook,apply_promotion
from . import gateway
from promotions.models import Promotion
from reviews.models import Review

def provider_state(p,status='PENDING',amount_paid=0):
    return SimpleNamespace(order_code=p.order_code,amount=int(p.amount),id=p.payment_link_id or 'test-link',status=status,amount_paid=amount_paid)

@override_settings(PAYOS_CLIENT_ID="test-client",PAYOS_API_KEY="test-api",PAYOS_CHECKSUM_KEY="test-checksum")
class Phase4Tests(Fixtures,TestCase):
    def setUp(self):
        get=patch('billing.gateway.get',side_effect=provider_state);get.start();self.addCleanup(get.stop)
        self.seed();self.a=book(self.user,self.service.pk,self.employee.pk,self.day,time(10));transition(self.admin,self.a.pk,"confirmed");self.i=Invoice.objects.get(appointment=self.a)
    def test_invoice_once_snapshot(self):
        transition(self.admin,self.a.pk,"confirmed");self.assertEqual(Invoice.objects.count(),1)
        self.service.price=900000;self.service.save();self.i.refresh_from_db();self.assertEqual(self.i.total_amount,Decimal(500000));self.assertEqual(self.i.details.get().unit_price,Decimal(500000))
    def test_promotion_snapshot(self):
        p=Promotion.objects.create(name="Test",code="TEST10",discount_type="percent",discount_value=10,start_date=timezone.localdate(),end_date=self.day);p.services.add(self.service)
        apply_promotion(self.user,self.i.pk,"TEST10");self.i.refresh_from_db();self.assertEqual(self.i.total_amount,Decimal(450000));self.assertEqual(self.i.promotion_code_snapshot,"TEST10")
    def test_cash_once_and_amount(self):
        with self.assertRaises(ValidationError):cash(self.admin,self.i.pk,Decimal(1))
        cash(self.admin,self.i.pk,Decimal(500000));self.assertEqual(Payment.objects.get().recorded_by,self.admin)
        with self.assertRaises(ValidationError):cash(self.admin,self.i.pk,Decimal(500000))
        self.i.refresh_from_db();self.assertEqual(self.i.payment_status,"paid")
    def test_invoice_ownership_and_csrf(self):
        self.client.force_login(self.other);self.assertEqual(self.client.get(f"/api/billing/{self.i.pk}/").status_code,404)
        self.client.force_login(self.user);self.assertEqual(self.client.post(f"/api/billing/{self.i.pk}/cash/",{"amount":500000}).status_code,403)
        c=Client(enforce_csrf_checks=True);c.force_login(self.admin);self.assertEqual(c.post(f"/api/billing/{self.i.pk}/cash/",{"amount":500000}).status_code,403)
    def mock_create(self,p):return SimpleNamespace(order_code=p.order_code,amount=int(p.amount),payment_link_id="test-link",checkout_url="https://pay.payos.vn/web/test-link",qr_code="test-qr",status="PENDING")
    @patch("billing.gateway.create")
    def test_online_reuse_and_start_cutoff(self,create):
        create.side_effect=self.mock_create
        p=online(self.user,self.i.pk);self.assertEqual(online(self.user,self.i.pk).pk,p.pk);self.assertEqual(create.call_count,1)
        Appointment.objects.filter(pk=self.a.pk).update(appointment_date=timezone.localdate()-timedelta(days=1))
        with self.assertRaises(ValidationError):online(self.user,self.i.pk)
    @patch("billing.gateway.create",side_effect=TimeoutError)
    def test_timeout_keeps_order_and_unpaid(self,create):
        for _ in range(2):
            with self.assertRaises(ValidationError):online(self.user,self.i.pk)
        self.assertEqual(Payment.objects.count(),1);self.i.refresh_from_db();self.assertEqual(self.i.payment_status,"unpaid")
    def signed(self,p,amount=None):
        from payos.types.webhooks import WebhookData
        d=WebhookData(orderCode=p.order_code,amount=amount or int(p.amount),description="test",accountNumber="test",reference="test-reference",transactionDateTime=timezone.localtime().strftime("%Y-%m-%d %H:%M:%S"),currency="VND",paymentLinkId="test-link",code="00",desc="success")
        with gateway.client() as sdk:sig=sdk.crypto.create_signature_from_object(d.model_dump_camel_case(),"test-checksum")
        return dict(code="00",desc="success",success=True,data=d.model_dump_camel_case(),signature=sig)
    @patch("billing.gateway.create")
    def test_signed_webhook_fake_mismatch_duplicate_and_revenue(self,create):
        create.side_effect=self.mock_create;p=online(self.user,self.i.pk)
        data=self.signed(p);bad={**data,"signature":"fake"}
        url="/api/billing/webhook/payos/"
        self.assertEqual(self.client.post(url,json.dumps(bad),content_type="application/json").status_code,400)
        self.assertEqual(self.client.post(url,json.dumps(self.signed(p,1)),content_type="application/json").status_code,400)
        for _ in range(2):self.assertEqual(self.client.post(url,json.dumps(data),content_type="application/json").status_code,200)
        self.i.refresh_from_db();self.assertEqual(self.i.payment_status,"paid");self.assertEqual(Payment.objects.filter(status="success").count(),1)
        self.client.force_login(self.admin);r=self.client.get("/api/dashboard/").json();self.assertEqual(Decimal(r["revenue"]),Decimal(500000));self.assertEqual(r["customers"],2)
    @patch("billing.gateway.cancel")
    @patch("billing.gateway.create")
    def test_cash_closes_pending_online(self,create,cancel):
        create.side_effect=self.mock_create;p=online(self.user,self.i.pk)
        cancel.side_effect=TimeoutError
        with self.assertRaises(ValidationError):cash(self.admin,self.i.pk,Decimal(500000))
        cancel.side_effect=None;cancel.return_value=provider_state(p,"CANCELLED",10000)
        with self.assertRaises(ValidationError):cash(self.admin,self.i.pk,Decimal(500000))
        self.i.refresh_from_db();self.assertEqual(self.i.payment_status,'unpaid')
        cancel.return_value=provider_state(p,"CANCELLED")
        cash(self.admin,self.i.pk,Decimal(500000));self.assertEqual(Payment.objects.filter(status="success").count(),1)
    def test_reviews_ownership_completion_edit_reply(self):
        self.client.force_login(self.user);url=f"/api/reviews/appointments/{self.a.pk}/"
        self.assertEqual(self.client.post(url,{"rating":5}).status_code,400)
        Appointment.objects.filter(pk=self.a.pk).update(appointment_date=timezone.localdate()-timedelta(days=1));transition(self.admin,self.a.pk,"completed")
        self.assertEqual(self.client.post(url,{"rating":6}).status_code,400)
        self.assertEqual(self.client.post(url,{"rating":5,"comment":"A"}).status_code,200)
        self.assertEqual(self.client.post(url,{"rating":4,"comment":"B"}).status_code,200);self.assertEqual(Review.objects.count(),1)
        r=Review.objects.get();reply=f"/api/reviews/{r.pk}/replies/"
        self.assertEqual(self.client.post(reply,{"content":"User reply"}).status_code,201)
        self.client.force_login(self.other);self.assertEqual(self.client.post(url,{"rating":5}).status_code,404);self.assertEqual(self.client.post(reply,{"content":"Other"}).status_code,404)
        self.client.force_login(self.admin);self.assertEqual(self.client.post(reply,{"content":"Admin reply"}).status_code,201)
        self.assertEqual(r.replies.count(),2);self.assertEqual(self.client.delete(reply).status_code,405)
    def test_dashboard_filters_permissions_empty(self):
        self.client.force_login(self.user);self.assertEqual(self.client.get("/api/dashboard/").status_code,403)
        self.client.force_login(self.admin);r=self.client.get("/api/dashboard/",{"start":"2000-01-01","end":"2000-01-02"}).json();self.assertEqual(r["appointments"],0);self.assertEqual(r["revenue"],0)
        self.assertEqual(self.client.get("/api/dashboard/",{"start":"bad"}).status_code,400)
        self.assertEqual(r["periodCustomers"],0)
        duplicate=book(self.user,self.service.pk,self.employee.pk,self.day,time(13))
        Appointment.objects.filter(pk=duplicate.pk).update(status="cancelled")
        period=self.client.get("/api/dashboard/",{"start":self.day.isoformat(),"end":self.day.isoformat()}).json()
        self.assertEqual(period["appointments"],2)
        self.assertEqual(period["periodCustomers"],1)  # Same owner, two appointments.
        self.assertEqual(sum(row["count"] for row in period["popular"]),1)
        self.assertEqual(sum(row["count"] for row in period["statuses"]),2)
        self.assertTrue(all(row["date"]==self.day.isoformat() for row in period["recent"]))


    def test_pending_has_no_invoice_then_confirmed_and_completed_keep_same_invoice(self):
        a=book(self.user,self.service.pk,self.employee.pk,self.day,time(13))
        self.client.force_login(self.user)
        def row():return next(x for x in self.client.get('/api/appointments/').json()['items'] if x['id']==a.pk)
        self.assertIsNone(row()['invoiceId']);self.assertFalse(Invoice.objects.filter(appointment=a).exists())
        transition(self.admin,a.pk,'confirmed');i=Invoice.objects.get(appointment=a)
        self.assertEqual(row()['invoiceId'],i.pk)
        cash(self.admin,i.pk,Decimal(500000));a.refresh_from_db();self.assertEqual(a.status,'confirmed')
        Appointment.objects.filter(pk=a.pk).update(appointment_date=timezone.localdate()-timedelta(days=1))
        transition(self.admin,a.pk,'completed')
        self.assertEqual(row()['invoiceId'],i.pk)
        result=self.client.get(f'/api/billing/{i.pk}/').json()['item']
        self.assertEqual(result['status'],'paid');self.assertEqual(result['payments'][0]['method'],'spa')
        self.assertEqual(self.client.post(f'/api/billing/{i.pk}/online/').status_code,400)

    def test_inconsistent_pending_invoice_cannot_take_payment(self):
        Appointment.objects.filter(pk=self.a.pk).update(status='pending')
        with self.assertRaises(ValidationError):cash(self.admin,self.i.pk,Decimal(500000))
        with self.assertRaises(ValidationError):online(self.user,self.i.pk)
        self.assertFalse(Payment.objects.exists())

    def test_historical_reconciliation_requires_prices_evidence_and_is_repeatable(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from io import StringIO
        a=book(self.user,self.service.pk,self.employee.pk,self.day,time(13))
        Appointment.objects.filter(pk=a.pk).update(status='completed',appointment_date=timezone.localdate()-timedelta(days=1))
        with TemporaryDirectory() as directory:
            path=Path(directory)/'plan.json'
            plan=[dict(appointment_id=a.pk,service_name='Tên theo chứng từ',subtotal='400000',discount='20000',promotion_code='OLD',evidence='Admin verified original signed quotation.')]
            path.write_text(json.dumps(plan),encoding='utf-8')
            call_command('reconcile_invoices',plan=str(path),stdout=StringIO())
            self.assertFalse(Invoice.objects.filter(appointment=a).exists())
            with self.assertRaises(CommandError):call_command('reconcile_invoices',plan=str(path),apply=True,stdout=StringIO())
            for _ in range(2):call_command('reconcile_invoices',plan=str(path),apply=True,admin_id=self.admin.pk,acknowledge_historical_prices=True,stdout=StringIO())
            i=Invoice.objects.get(appointment=a);self.assertEqual(i.total_amount,380000);self.assertEqual(i.payment_status,'unpaid')
            self.assertEqual(i.details.get().unit_price,400000);self.assertTrue(i.historical_basis)
            a.refresh_from_db();self.assertEqual(a.status,'completed');self.assertFalse(i.payments.exists())
            self.client.force_login(self.user);self.assertEqual(self.client.get(f'/api/billing/{i.pk}/').status_code,200)

    def test_legacy_confirmed_reconfirmation_does_not_guess_price(self):
        a=book(self.user,self.service.pk,self.employee.pk,self.day,time(13))
        Appointment.objects.filter(pk=a.pk).update(status='confirmed')
        with self.assertRaises(ValidationError):transition(self.admin,a.pk,'confirmed')
        with self.assertRaises(ValidationError):transition(self.admin,a.pk,'confirmed',employee_id=self.employee2.pk,consent=True,reason='Khách đã đồng ý thay thế')
        self.assertFalse(Invoice.objects.filter(appointment=a).exists())

    def test_public_service_reviews_do_not_expose_private_identifiers(self):
        Appointment.objects.filter(pk=self.a.pk).update(status='completed')
        self.a.refresh_from_db()
        Review.objects.create(appointment=self.a,customer=self.customer,service=self.service,rating=5,comment='Verified review')
        result=self.client.get(f'/api/reviews/services/{self.service.pk}/').json()
        self.assertEqual(result['total'],1);self.assertEqual(result['items'][0]['comment'],'Verified review')
        self.assertNotIn('appointmentId',result['items'][0]);self.assertNotIn('email',result['items'][0])

    def test_revenue_local_midnight_boundaries(self):
        cash(self.admin,self.i.pk,Decimal(500000))
        # 17:00 UTC is exactly midnight of the following Vietnamese calendar day.
        Payment.objects.update(paid_at=datetime(2026,10,21,17,0,tzinfo=dt_timezone.utc))
        self.client.force_login(self.admin)
        for day,expected in (("2026-10-21",0),("2026-10-22",500000)):
            result=self.client.get('/api/dashboard/',{'start':day,'end':day}).json()
            self.assertEqual(Decimal(result['revenue']),Decimal(expected))
            if expected:self.assertEqual(result['daily'],[{'day':day,'total':'500000.00'}])

    @patch('billing.gateway.get')
    @patch('billing.gateway.create')
    def test_provider_expiry_and_paid_status_never_substitute_webhook(self,create,get):
        create.side_effect=self.mock_create;p=online(self.user,self.i.pk)
        self.client.force_login(self.user)
        get.return_value=SimpleNamespace(order_code=p.order_code,amount=500000,id='test-link',status='PAID',amount_paid=500000)
        self.assertEqual(self.client.post(f'/api/billing/{self.i.pk}/refresh-online/').status_code,200)
        self.i.refresh_from_db();self.assertEqual(self.i.payment_status,'unpaid')
        get.return_value.status='EXPIRED';get.return_value.amount_paid=0
        self.assertEqual(self.client.post(f'/api/billing/{self.i.pk}/refresh-online/').status_code,200)
        p.refresh_from_db();self.assertEqual(p.status,'cancelled');self.assertEqual(p.provider_status,'EXPIRED')

    @patch('billing.gateway.cancel')
    @patch('billing.gateway.create')
    def test_late_webhook_after_cash_requires_review_not_double_revenue(self,create,cancel):
        create.side_effect=self.mock_create;p=online(self.user,self.i.pk)
        cancel.side_effect=lambda payment:provider_state(payment,"CANCELLED")
        cash(self.admin,self.i.pk,Decimal(500000))
        with gateway.client() as sdk:data=sdk.webhooks.verify(self.signed(p))
        accept_webhook(data);p.refresh_from_db();self.assertTrue(p.requires_review)
        self.client.force_login(self.admin)
        self.assertEqual(Decimal(self.client.get('/api/dashboard/').json()['revenue']),500000)


from django.test import TransactionTestCase
from django.db import close_old_connections
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier


class ConcurrentPaymentTests(Fixtures,TransactionTestCase):
    def setUp(self):
        get=patch('billing.gateway.get',side_effect=provider_state);get.start();self.addCleanup(get.stop)
        self.seed();a=book(self.user,self.service.pk,self.employee.pk,self.day,time(10))
        transition(self.admin,a.pk,'confirmed');self.invoice=Invoice.objects.get(appointment=a)

    def test_simultaneous_cash_only_one_payment(self):
        barrier=Barrier(2)
        def attempt(_):
            close_old_connections()
            try:
                barrier.wait(timeout=15);cash(self.admin,self.invoice.pk,Decimal(500000));return 'saved'
            except ValidationError:return 'conflict'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,range(2)))
        self.assertCountEqual(results,['saved','conflict'])
        self.assertEqual(Payment.objects.filter(status='success').count(),1)

    @patch('billing.gateway.cancel')
    def test_cash_and_webhook_race_counts_revenue_once(self,cancel):
        cancel.side_effect=lambda payment:provider_state(payment,'CANCELLED')
        p=Payment.objects.create(invoice=self.invoice,payment_method='online',amount=500000,order_code=424242,payment_link_id='test-link')
        data=SimpleNamespace(order_code=p.order_code,amount=500000,currency='VND',payment_link_id='test-link',code='00',reference='race-reference',transaction_date_time=timezone.localtime().isoformat())
        barrier=Barrier(2)
        def attempt(kind):
            close_old_connections()
            try:
                barrier.wait(timeout=15)
                if kind=='cash':cash(self.admin,self.invoice.pk,Decimal(500000))
                else:accept_webhook(data)
                return 'saved'
            except ValidationError:return 'conflict'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(attempt,['cash','webhook']))
        self.invoice.refresh_from_db();self.assertEqual(self.invoice.payment_status,'paid')
        self.assertEqual(Payment.objects.filter(status='success',requires_review=False).count(),1)
        self.assertIn(Payment.objects.get(pk=p.pk).status,('success','review'))
