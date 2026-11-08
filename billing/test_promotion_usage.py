from concurrent.futures import ThreadPoolExecutor
from datetime import time, timedelta
from decimal import Decimal
from threading import Barrier

from django.core.exceptions import ValidationError
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from appointments.services import book, transition
from promotions.services import evaluate_code, policy, usage
from . import gateway, services
from .models import Invoice, Payment
from .test_invoice_flow import FlowFixtures


class UsageFixtures(FlowFixtures):
    def usage_seed(self):
        self.flow_seed()
        self.promo.code='TESTSPA10'
        self.promo.aliases='SPA10'
        self.promo.conditions='Áp dụng cho dịch vụ được chọn'
        self.promo.note='Mỗi khách hàng chỉ sử dụng mã một lần. Không áp dụng đồng thời với chương trình khác.'
        self.promo.max_discount=50000
        self.promo.save()
        self.next_appointment=book(self.user,self.service.pk,self.employee.pk,self.day,time(11))
        transition(self.admin,self.next_appointment.pk,'confirmed')
        self.next_invoice=Invoice.objects.get(appointment=self.next_appointment)

    def claim(self,invoice=None,code='TESTSPA10',user=None):
        return services.apply_promotion(user or self.user,(invoice or self.i).pk,code)


@override_settings(PAYOS_CLIENT_ID='test-client',PAYOS_API_KEY='test-api',PAYOS_CHECKSUM_KEY='test-checksum')
class PromotionUsageTests(UsageFixtures,TestCase):
    def setUp(self):self.usage_seed()

    def test_exact_legacy_policy_automatically_eligible_without_changing_promotion(self):
        before=type(self.promo).objects.filter(pk=self.promo.pk).values().get()
        result=self.client.get(f'/api/billing/{self.i.pk}/promotions/').json()
        self.assertIn('TESTSPA10',[p['code'] for p in result['items']])
        self.claim()
        self.assertEqual(type(self.promo).objects.filter(pk=self.promo.pk).values().get(),before)
        self.i.refresh_from_db();self.assertEqual(self.i.total_amount,450000)
        self.assertEqual(usage(self.promo,self.customer.pk),dict(used=0,reserved=1))
        row=self.client.get(f'/api/billing/{self.i.pk}/').json()['item']
        self.assertEqual(row['promotionUsage'],dict(limit=1,used=0,reserved=1))

    def test_alias_and_repeated_same_invoice_cannot_bypass_reserved_limit(self):
        self.claim();self.claim(code='spa10')
        with self.assertRaisesMessage(ValidationError,'đang được giữ'):self.claim(self.next_invoice,code='SPA10')
        result=self.client.get(f'/api/billing/{self.next_invoice.pk}/promotions/').json()
        self.assertIn('đang được giữ',next(p['reason'] for p in result['unavailable'] if p['code']=='TESTSPA10'))
        self.assertEqual(Invoice.objects.filter(promotion=self.promo).count(),1)

    def test_cash_consumes_once_and_paid_invoice_cannot_release(self):
        self.claim();services.cash(self.admin,self.i.pk,Decimal(450000))
        self.assertEqual(usage(self.promo,self.customer.pk),dict(used=1,reserved=0))
        with self.assertRaisesMessage(ValidationError,'đã sử dụng hết'):self.claim(self.next_invoice)
        with self.assertRaises(ValidationError):self.claim(code='')
        with self.assertRaises(ValidationError):services.cash(self.admin,self.i.pk,Decimal(450000))
        self.assertEqual(Payment.objects.filter(status='success').count(),1)

    def test_signed_webhook_duplicate_consumes_one_invoice_once(self):
        self.claim();p=services.online(self.user,self.i.pk)
        self.assertEqual(usage(self.promo,self.customer.pk),dict(used=0,reserved=1))
        for _ in range(2):self.assertEqual(self.deliver(p).status_code,200)
        self.assertEqual(usage(self.promo,self.customer.pk),dict(used=1,reserved=0))
        with self.assertRaises(ValidationError):self.claim(self.next_invoice)
        self.assertEqual(Payment.objects.filter(status='success').count(),1)

    def test_remove_or_replace_code_releases_reservation(self):
        self.claim();self.claim(code='')
        self.assertEqual(usage(self.promo,self.customer.pk),dict(used=0,reserved=0))
        self.claim(self.next_invoice)
        self.claim(self.next_invoice,code='LIVE20')
        self.claim()
        self.assertEqual(usage(self.promo,self.customer.pk),dict(used=0,reserved=1))

    def test_valid_cancellation_releases_but_late_payment_needs_review(self):
        self.claim();old=services.online(self.user,self.i.pk)
        transition(self.admin,self.a.pk,'cancelled',reason='Khách đề nghị hủy')
        self.assertEqual(usage(self.promo,self.customer.pk),dict(used=0,reserved=0))
        self.claim(self.next_invoice)
        self.assertEqual(self.deliver(old).status_code,200)
        old.refresh_from_db();self.assertEqual(old.status,'review')
        # Disputed money is never a successful use and prevents another settlement.
        self.assertEqual(usage(self.promo,self.customer.pk),dict(used=0,reserved=2))
        with self.assertRaises(ValidationError):services.cash(self.admin,self.next_invoice.pk,Decimal(450000))
        self.assertFalse(Payment.objects.filter(status='success').exists())

    def test_unknown_conditions_and_notes_are_never_ignored(self):
        for field in ('conditions','note'):
            original=getattr(self.promo,field)
            setattr(self.promo,field,original+'\nKhách cần giấy xác nhận')
            self.promo.save()
            with self.assertRaisesMessage(ValidationError,'Cần Spa kiểm tra'):self.claim()
            setattr(self.promo,field,original)
        self.promo.save()
        self.assertEqual(policy(self.promo),(1,[]))

    def test_numeric_limit_and_legacy_one_use_cannot_be_weakened_accidentally(self):
        self.promo.per_customer_limit=2;self.promo.save()
        self.assertEqual(policy(self.promo)[0],1)
        self.promo.note='';self.promo.save()
        self.claim();self.claim(self.next_invoice)
        services.cash(self.admin,self.i.pk,Decimal(450000))
        services.cash(self.admin,self.next_invoice.pk,Decimal(450000))
        self.assertEqual(usage(self.promo,self.customer.pk),dict(used=2,reserved=0))
        self.promo.per_customer_limit=0
        with self.assertRaises(ValidationError):self.promo.save()

    def test_admin_applies_for_invoice_customer_and_other_customer_has_own_limit(self):
        self.claim(user=self.admin)
        with self.assertRaises(ValidationError):self.claim(self.next_invoice,user=self.admin)
        other=book(self.other,self.service.pk,self.employee2.pk,self.day,time(10))
        transition(self.admin,other.pk,'confirmed')
        self.claim(Invoice.objects.get(appointment=other),user=self.admin)
        self.assertEqual(usage(self.promo,self.other_customer.pk),dict(used=0,reserved=1))

    def test_online_timeout_keeps_reservation_until_verified_close_and_remove(self):
        self.claim();self.create.side_effect=TimeoutError
        with self.assertRaises(ValidationError):services.online(self.user,self.i.pk)
        with self.assertRaises(ValidationError):self.claim(self.next_invoice)
        with self.assertRaises(ValidationError):self.claim(code='')
        self.get.side_effect=TimeoutError
        with self.assertRaises(ValidationError):services.begin_promotion_edit(self.user,self.i.pk)
        self.assertEqual(usage(self.promo,self.customer.pk),dict(used=0,reserved=1))

    def test_expired_link_or_spa_selection_does_not_release_invoice_reservation(self):
        self.claim();services.select_spa(self.user,self.i.pk)
        with self.assertRaises(ValidationError):self.claim(self.next_invoice)
        services.begin_promotion_edit(self.user,self.i.pk)
        p=services.online(self.user,self.i.pk)
        from .test_phase4 import provider_state
        self.get.side_effect=lambda payment:provider_state(payment,'EXPIRED')
        services.refresh_online(self.user,self.i.pk)
        with self.assertRaises(ValidationError):self.claim(self.next_invoice)
        services.begin_promotion_edit(self.user,self.i.pk);self.claim(code='')
        self.claim(self.next_invoice)

    def test_reserved_snapshot_can_settle_after_promotion_expires(self):
        self.claim()
        self.promo.start_date=timezone.localdate()-timedelta(days=2)
        self.promo.end_date=timezone.localdate()-timedelta(days=1);self.promo.save()
        services.cash(self.admin,self.i.pk,Decimal(450000))
        self.assertEqual(usage(self.promo,self.customer.pk)['used'],1)

    def test_legacy_overallocated_invoices_cannot_both_settle(self):
        self.claim()
        # Simulate inconsistent pre-feature data; never used outside test DB.
        Invoice.objects.filter(pk=self.next_invoice.pk).update(promotion=self.promo,promotion_code_snapshot=self.promo.code,discount_amount=50000,total_amount=450000)
        with self.assertRaises(ValidationError):services.cash(self.admin,self.i.pk,Decimal(450000))
        with self.assertRaises(ValidationError):services.online(self.user,self.next_invoice.pk)
        self.assertFalse(Payment.objects.exists())

    def test_late_webhook_after_releasing_code_never_consumes_reallocated_slot(self):
        self.claim();old=services.online(self.user,self.i.pk)
        services.begin_promotion_edit(self.user,self.i.pk);self.claim(code='')
        self.claim(self.next_invoice)
        self.deliver(old);self.deliver(old)
        old.refresh_from_db();self.assertEqual(old.status,'review')
        self.assertEqual(usage(self.promo,self.customer.pk),dict(used=0,reserved=1))
        services.cash(self.admin,self.next_invoice.pk,Decimal(450000))
        self.assertEqual(usage(self.promo,self.customer.pk),dict(used=1,reserved=0))

    def test_minimum_cap_service_and_customer_context_still_required(self):
        with self.assertRaisesMessage(ValidationError,'khách hàng'):evaluate_code('TESTSPA10',self.service)
        self.promo.min_amount=600000;self.promo.save()
        with self.assertRaisesMessage(ValidationError,'tối thiểu'):self.claim()
        self.promo.min_amount=0;self.promo.max_discount=20000;self.promo.save()
        self.assertEqual(self.claim().total_amount,480000)
        self.claim(code='');self.promo.services.clear()
        with self.assertRaisesMessage(ValidationError,'phạm vi'):self.claim()


@override_settings(PAYOS_CLIENT_ID='test-client',PAYOS_API_KEY='test-api',PAYOS_CHECKSUM_KEY='test-checksum')
class ConcurrentPromotionUsageTests(UsageFixtures,TransactionTestCase):
    def setUp(self):self.usage_seed()

    def race(self,actions):
        barrier=Barrier(len(actions))
        def attempt(action):
            close_old_connections()
            try:
                barrier.wait(timeout=15);action();return True
            except ValidationError:return False
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=len(actions)) as pool:return list(pool.map(attempt,actions))

    def test_two_simultaneous_invoices_only_one_claims_last_slot(self):
        results=self.race([lambda:self.claim(),lambda:self.claim(self.next_invoice,code='SPA10')])
        self.assertEqual(sorted(results),[False,True])
        self.assertEqual(Invoice.objects.filter(promotion=self.promo).count(),1)
        self.assertEqual(usage(self.promo,self.customer.pk),dict(used=0,reserved=1))

    def test_cash_and_second_claim_cannot_double_use(self):
        self.claim()
        results=self.race([lambda:services.cash(self.admin,self.i.pk,Decimal(450000)),lambda:self.claim(self.next_invoice)])
        self.assertEqual(results,[True,False])
        self.assertEqual(usage(self.promo,self.customer.pk),dict(used=1,reserved=0))

    def test_webhook_and_second_claim_cannot_double_use(self):
        self.claim();p=services.online(self.user,self.i.pk)
        with gateway.client() as sdk:data=sdk.webhooks.verify(self.signed(p))
        results=self.race([lambda:services.accept_webhook(data),lambda:self.claim(self.next_invoice)])
        self.assertEqual(results,[True,False])
        self.assertEqual(usage(self.promo,self.customer.pk),dict(used=1,reserved=0))
