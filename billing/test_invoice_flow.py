"""Invoice UI workflow, provider closure and signed late-webhook regression tests."""
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import time,timedelta
from decimal import Decimal
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import close_old_connections
from django.test import TestCase,TransactionTestCase,override_settings
from django.utils import timezone

from appointments.models import Appointment
from appointments.services import book,transition
from core.test_phase3 import Fixtures
from promotions.models import Promotion
from . import gateway,services
from .models import Invoice, InvoiceDetail, Payment
from .test_phase4 import provider_state


def created(payment):
    return SimpleNamespace(order_code=payment.order_code,amount=int(payment.amount),
        payment_link_id=f'link-{payment.order_code}',checkout_url=f'https://pay.payos.vn/web/link-{payment.order_code}',
        qr_code='mock-data-not-a-real-qr',status='PENDING')


class FlowFixtures(Fixtures):
    def flow_seed(self):
        self.seed()
        self.a=book(self.user,self.service.pk,self.employee.pk,self.day,time(10))
        transition(self.admin,self.a.pk,'confirmed');self.i=Invoice.objects.get(appointment=self.a)
        self.promo=Promotion.objects.create(name='Ưu đãi 10%',code='LIVE10',discount_type='percent',discount_value=10,
            start_date=timezone.localdate(),end_date=self.day)
        self.promo.services.add(self.service)
        self.second=Promotion.objects.create(name='Ưu đãi 20%',code='LIVE20',discount_type='percent',discount_value=20,
            start_date=timezone.localdate(),end_date=self.day)
        self.second.services.add(self.service)
        self.network=[]
        for name,fn in [('create',created),('get',provider_state),('cancel',lambda p:provider_state(p,'CANCELLED'))]:
            mock=patch('billing.gateway.'+name,side_effect=fn);self.network.append(mock.start());self.addCleanup(mock.stop)
        self.create,self.get,self.cancel=self.network
        self.client.force_login(self.user)

    def post(self,action,data=None):return self.client.post(f'/api/billing/{self.i.pk}/{action}/',data or {})

    def signed(self,p):
        from payos.types.webhooks import WebhookData
        d=WebhookData(orderCode=p.order_code,amount=int(p.amount),description='test',accountNumber='test',
            reference=f'ref-{p.order_code}',transactionDateTime=timezone.localtime().isoformat(),currency='VND',
            paymentLinkId=p.payment_link_id,code='00',desc='success')
        body=d.model_dump_camel_case()
        with gateway.client() as sdk:signature=sdk.crypto.create_signature_from_object(body,'test-checksum')
        return dict(code='00',desc='success',success=True,data=body,signature=signature)

    def deliver(self,p):return self.client.post('/api/billing/webhook/payos/',json.dumps(self.signed(p)),content_type='application/json')


@override_settings(PAYOS_CLIENT_ID='test-client',PAYOS_API_KEY='test-api',PAYOS_CHECKSUM_KEY='test-checksum')
class InvoiceFlowTests(FlowFixtures,TestCase):
    def setUp(self):self.flow_seed()

    def test_eligible_dropdown_minimum_expiry_scope_conditions_and_snapshot_price(self):
        self.service.price=1;self.service.save()
        self.promo.min_amount=450000;self.promo.max_discount=40000;self.promo.save()
        self.second.conditions='Cần xác minh điều kiện tại Spa';self.second.save()
        Promotion.objects.create(name='Hết hạn',code='OLD',discount_type='amount',discount_value=5000,
            start_date=timezone.localdate()-timedelta(days=3),end_date=timezone.localdate()-timedelta(days=1)).services.add(self.service)
        result=self.client.get(f'/api/billing/{self.i.pk}/promotions/').json()['items']
        self.assertEqual([p['code'] for p in result],['LIVE10']);self.assertEqual(Decimal(result[0]['discount']),40000)
        self.assertEqual(self.post('promotion',{'code':'LIVE10'}).status_code,200)
        self.i.refresh_from_db();self.assertEqual(self.i.total_amount,460000)

    def test_apply_remove_and_reload_from_mysql(self):
        self.assertEqual(self.post('promotion',{'code':'LIVE10'}).status_code,200)
        self.i.refresh_from_db();self.assertEqual(self.i.total_amount,450000)
        self.assertEqual(self.post('remove-promotion').status_code,200)
        row=self.client.get(f'/api/billing/{self.i.pk}/').json()['item']
        self.assertEqual(row['promotion'],'');self.assertEqual(Decimal(row['total']),500000)
        self.i.refresh_from_db();self.assertIsNone(self.i.promotion_id);self.assertEqual(self.i.discount_amount,0)

    def test_spa_selection_is_not_payment_and_allows_explicit_edit(self):
        self.post('promotion',{'code':'LIVE10'})
        row=self.post('select-spa').json()['item'];self.assertEqual(row['paymentPreference'],'spa')
        self.assertFalse(Payment.objects.exists());self.assertEqual(row['status'],'unpaid')
        self.assertEqual(self.post('promotion',{'code':'LIVE20'}).status_code,400)
        self.assertEqual(self.post('edit-promotion').status_code,200)
        self.assertEqual(self.post('promotion',{'code':'LIVE20'}).status_code,200)
        self.post('select-spa');self.i.refresh_from_db();self.assertEqual(self.i.total_amount,400000)
        self.assertEqual(self.i.payment_preference,'spa');self.assertEqual(self.i.payment_status,'unpaid')

    def test_online_edit_closes_old_order_and_new_order_has_new_amount(self):
        self.post('promotion',{'code':'LIVE10'});self.post('online')
        old=Payment.objects.get();self.assertEqual(old.amount,450000)
        self.assertEqual(self.post('promotion',{'code':'LIVE20'}).status_code,400)
        self.assertEqual(self.post('edit-promotion').status_code,200)
        self.get.assert_called();self.cancel.assert_called_once()
        old.refresh_from_db();self.assertEqual(old.status,'cancelled')
        self.assertEqual(self.post('promotion',{'code':'LIVE20'}).status_code,200)
        self.assertEqual(self.post('online').status_code,200)
        new=Payment.objects.exclude(pk=old.pk).get();self.assertEqual(new.amount,400000)
        self.assertNotEqual(new.order_code,old.order_code)
        self.assertEqual(self.post('online').status_code,200);self.assertEqual(self.create.call_count,2)

    def test_processing_paid_unknown_partial_and_network_failure_lock_edit(self):
        self.post('online');p=Payment.objects.get()
        for state,amount_paid in [('PAID',500000),('PROCESSING',0),('UNDERPAID',100),('NEW_UNKNOWN',0)]:
            self.get.side_effect=None;self.get.return_value=provider_state(p,state,amount_paid)
            self.assertEqual(self.post('edit-promotion').status_code,400,state)
            self.i.refresh_from_db();self.assertEqual(self.i.total_amount,500000);self.assertEqual(self.i.payment_preference,'online')
        self.get.side_effect=TimeoutError
        self.assertEqual(self.post('edit-promotion').status_code,400);self.cancel.assert_not_called()

    def test_provider_mismatch_and_cancel_race_never_unlock(self):
        self.post('online');p=Payment.objects.get()
        self.get.side_effect=None;self.get.return_value=provider_state(p);self.get.return_value.amount=1
        self.assertEqual(self.post('edit-promotion').status_code,400);self.cancel.assert_not_called()
        self.get.side_effect=provider_state
        self.cancel.side_effect=lambda payment:provider_state(payment,'PAID',500000)
        self.assertEqual(self.post('edit-promotion').status_code,400)
        self.i.refresh_from_db();self.assertEqual(self.i.payment_preference,'online');self.assertEqual(self.i.total_amount,500000)

    def test_unknown_cancel_result_and_timeout_preserve_original_invoice(self):
        self.post('online')
        for result in ['PROCESSING',None]:
            self.cancel.side_effect=TimeoutError if result is None else lambda p:provider_state(p,'PROCESSING')
            self.assertEqual(self.post('edit-promotion').status_code,400)
            self.i.refresh_from_db();self.assertEqual(self.i.payment_preference,'online')
            self.assertEqual(Payment.objects.get().status,'pending')

    def test_expired_closed_order_can_edit_without_redundant_cancel(self):
        self.post('online');self.get.side_effect=lambda p:provider_state(p,'EXPIRED')
        self.assertEqual(self.post('edit-promotion').status_code,200);self.cancel.assert_not_called()
        self.assertEqual(self.post('promotion',{'code':''}).status_code,200)

    def test_expired_qr_closes_old_order_and_renews_on_same_invoice(self):
        self.assertEqual(self.post('online').status_code,200)
        old=Payment.objects.get()
        Payment.objects.filter(pk=old.pk).update(expires_at=timezone.now()-timedelta(seconds=1))
        from payos.types import PaymentLink
        self.get.side_effect=lambda p:PaymentLink.model_validate({
            'id':p.payment_link_id, 'orderCode':p.order_code, 'amount':int(p.amount),
            'amountPaid':'0', 'amountRemaining':int(p.amount), 'status':'EXPIRED',
            'transactions':[], 'createdAt':p.created_at.isoformat(),
        })
        self.assertEqual(self.post('renew-online').status_code,200)
        old.refresh_from_db();self.assertEqual(old.status,'cancelled')
        self.assertEqual(self.post('renew-online').status_code,200)
        new=Payment.objects.exclude(pk=old.pk).get()
        self.assertNotEqual(new.order_code,old.order_code)
        self.assertEqual(new.invoice_id,old.invoice_id)
        self.assertEqual(Invoice.objects.filter(appointment=self.a).count(),1)
        self.cancel.assert_not_called()

    def test_idle_timer_expires_while_provider_link_still_pending(self):
        self.post('online')
        old=Payment.objects.get()
        Payment.objects.filter(pk=old.pk).update(expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.post('renew-online').status_code,200)
        old.refresh_from_db()
        self.assertEqual(old.status,'cancelled')
        self.cancel.assert_called_once()
        self.assertNotEqual(self.i.payments.get(status='pending').order_code,old.order_code)

    def test_renewal_refuses_provider_payment_in_progress(self):
        self.assertEqual(self.post('online').status_code,200)
        old=Payment.objects.get()
        Payment.objects.filter(pk=old.pk).update(expires_at=timezone.now()-timedelta(seconds=1))
        for status,amount_paid,message in [
            ('PENDING',100,'đã ghi nhận tiền'),
            ('PAID',0,'đã thanh toán'),
            ('PROCESSING',0,'đang xử lý'),
            ('UNDERPAID',0,'thanh toán chưa đủ'),
            ('EXPIRED',-1,'chưa nhất quán'),
        ]:
            with self.subTest(status=status,amount_paid=amount_paid):
                self.get.side_effect=lambda p,s=status,a=amount_paid:provider_state(p,s,a)
                response=self.post('renew-online')
                self.assertEqual(response.status_code,400)
                self.assertIn(message,response.json()['error'])
        old.refresh_from_db();self.assertEqual(old.status,'pending')
        self.assertEqual(Payment.objects.count(),1)
        self.cancel.assert_not_called()

    def test_online_to_spa_closes_provider_and_spa_to_online_creates_new_order(self):
        self.post('online');old=Payment.objects.get()
        self.assertEqual(self.post('select-spa').status_code,200)
        old.refresh_from_db();self.assertEqual(old.status,'cancelled')
        self.i.refresh_from_db();self.assertEqual(self.i.payment_preference,'spa');self.assertEqual(self.i.payment_status,'unpaid')
        self.assertEqual(self.post('online').status_code,200)
        self.assertEqual(Payment.objects.filter(status='pending').count(),1)

    def test_signed_paid_and_duplicate_webhook_lock_all_mutations(self):
        self.post('online');p=Payment.objects.get()
        for _ in range(2):self.assertEqual(self.deliver(p).status_code,200)
        for name in ['edit-promotion','select-spa','remove-promotion','online']:
            self.assertEqual(self.post(name).status_code,400,name)
        self.assertEqual(Payment.objects.filter(status='success').count(),1)
        self.a.refresh_from_db();self.assertEqual(self.a.status,'confirmed')

    def test_late_signed_webhook_after_reprice_goes_to_review_not_invoice_paid(self):
        self.post('online');old=Payment.objects.get();self.post('edit-promotion')
        self.post('promotion',{'code':'LIVE20'});self.post('online');new=Payment.objects.exclude(pk=old.pk).get()
        for _ in range(2):self.assertEqual(self.deliver(old).status_code,200)
        old.refresh_from_db();self.i.refresh_from_db()
        self.assertEqual(old.status,'review');self.assertTrue(old.requires_review)
        self.assertEqual(self.i.payment_status,'unpaid');self.assertEqual(self.i.total_amount,400000)
        for name in ['select-spa','edit-promotion','online']:self.assertEqual(self.post(name).status_code,400)
        self.assertEqual(self.deliver(new).status_code,200)
        self.assertEqual(Payment.objects.filter(status='success').count(),0)
        self.client.force_login(self.admin)
        self.assertEqual(Decimal(self.client.get('/api/dashboard/').json()['revenue']),0)

    def test_invoice_appointment_mapping_search_filter_and_pagination(self):
        row=self.client.get(f'/api/billing/{self.i.pk}/').json()['item']
        self.assertEqual(row['id'],self.i.pk);self.assertEqual(row['appointmentId'],self.a.pk)
        for q in [f'HD-{self.i.pk}', f'LH-{self.a.pk}', f'LH-{self.a.pk:06d}']:
            self.assertEqual(self.client.get('/api/billing/',{'search':q}).json()['items'][0]['id'],self.i.pk)
        self.assertEqual(self.client.get('/api/billing/',{'status':'paid'}).json()['items'],[])
        for number in range(11):
            a=Appointment.objects.create(customer=self.customer,service=self.service,employee=self.employee,
                appointment_date=self.day+timedelta(days=number+1),start_time=time(10),end_time=time(11),status='cancelled')
            Appointment.objects.filter(pk=a.pk).update(status='completed')
            a.refresh_from_db()
            invoice = Invoice.objects.create(appointment=a, subtotal=500000, total_amount=500000,
                                             historical_basis='Fixture for pagination only')
            InvoiceDetail.objects.create(invoice=invoice, service=self.service, service_name_snapshot=self.service.name,
                                         unit_price=invoice.subtotal, line_total=invoice.subtotal)
        first=self.client.get('/api/billing/').json();second=self.client.get('/api/billing/',{'page':2}).json()
        self.assertEqual((first['total'],len(first['items']),len(second['items'])),(12,10,2))

    def test_ownership_for_options_edit_selection_and_paid_cancelled_guards(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(f'/api/billing/{self.i.pk}/promotions/').status_code,404)
        self.assertEqual(self.post('edit-promotion').status_code,404)
        self.client.force_login(self.user);Appointment.objects.filter(pk=self.a.pk).update(status='cancelled')
        self.assertEqual(self.post('online').status_code,400);self.assertEqual(self.post('select-spa').status_code,400)


@override_settings(PAYOS_CLIENT_ID='test-client',PAYOS_API_KEY='test-api',PAYOS_CHECKSUM_KEY='test-checksum')
class ConcurrentInvoiceFlowTests(FlowFixtures,TransactionTestCase):
    def setUp(self):self.flow_seed()

    def test_simultaneous_online_creates_one_order(self):
        barrier=Barrier(2)
        def attempt(_):
            close_old_connections()
            try:barrier.wait(timeout=15);return services.online(self.user,self.i.pk).order_code
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:orders=list(pool.map(attempt,range(2)))
        self.assertEqual(len(set(orders)),1);self.assertEqual(Payment.objects.count(),1);self.assertEqual(self.create.call_count,1)

    def test_edit_and_signed_webhook_race_preserves_amount_and_one_effect(self):
        p=services.online(self.user,self.i.pk)
        with gateway.client() as sdk:data=sdk.webhooks.verify(self.signed(p))
        barrier=Barrier(2)
        def attempt(kind):
            close_old_connections()
            try:
                barrier.wait(timeout=15)
                if kind=='edit':services.begin_promotion_edit(self.user,self.i.pk)
                else:services.accept_webhook(data)
            except ValidationError:pass
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(attempt,['edit','webhook']))
        self.i.refresh_from_db();p.refresh_from_db()
        self.assertEqual(self.i.total_amount,500000);self.assertEqual(Payment.objects.count(),1)
        self.assertIn((self.i.payment_status,p.status),[('paid','success'),('unpaid','review')])
