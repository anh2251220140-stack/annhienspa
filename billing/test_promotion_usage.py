from concurrent.futures import ThreadPoolExecutor
from datetime import time, timedelta
from decimal import Decimal
from threading import Barrier

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from appointments.services import book, transition
from promotions.services import evaluate_code, policy, usage
from . import gateway, services
from .models import Invoice, Payment
from .test_invoice_flow import FlowFixtures
from .test_phase4 import at_appointment_start, provider_state


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
        self.claim()
        with at_appointment_start(self.a):services.cash(self.admin,self.i.pk,Decimal(450000))
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
        with at_appointment_start(self.next_appointment), self.assertRaises(ValidationError):
            services.cash(self.admin,self.next_invoice.pk,Decimal(450000))
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
        with at_appointment_start(self.next_appointment):
            services.cash(self.admin,self.i.pk,Decimal(450000))
            services.cash(self.admin,self.next_invoice.pk,Decimal(450000))
        self.assertEqual(usage(self.promo,self.customer.pk),dict(used=2,reserved=0))
        self.promo.per_customer_limit=0
        with self.assertRaises(ValidationError):self.promo.save()

    def test_only_invoice_owner_can_edit_and_each_customer_has_own_limit(self):
        self.claim()
        with self.assertRaisesMessage(ValidationError, 'đang được giữ'):
            self.claim(self.next_invoice)
        for actor in (self.admin, self.other):
            with self.subTest(actor=actor.role):
                with self.assertRaises(PermissionDenied):
                    self.claim(code='', user=actor)
                with self.assertRaises(PermissionDenied):
                    services.begin_promotion_edit(actor, self.i.pk)

        other = book(self.other, self.service.pk, self.employee2.pk, self.day, time(10))
        transition(self.admin, other.pk, 'confirmed')
        self.claim(Invoice.objects.get(appointment=other), user=self.other)
        for customer in (self.customer, self.other_customer):
            self.assertEqual(usage(self.promo, customer.pk), dict(used=0, reserved=1))

    def promotion_requests(self):
        return (
            ('promotion', {'code': self.second.code}),
            ('remove-promotion', {}),
            ('edit-promotion', {}),
        )

    def billing_snapshot(self):
        return (
            Invoice.objects.filter(pk=self.i.pk).values().get(),
            list(Payment.objects.filter(invoice=self.i).order_by('pk').values()),
            list(type(self.promo).objects.order_by('pk').values()),
        )

    def test_promotion_api_owner_csrf_and_admin_cash(self):
        owner, other, admin = (Client(enforce_csrf_checks=True) for _ in range(3))
        for client, user, page in (
            (owner, self.user, '/invoice.html'),
            (other, self.other, '/invoice.html'),
            (admin, self.admin, '/admin-invoices.html'),
        ):
            client.force_login(user)
            self.assertEqual(client.get(page, secure=True).status_code, 200)

        def post(client, action, data, *, csrf=True):
            headers = {'HTTP_ORIGIN': 'https://testserver'}
            if csrf:
                headers['HTTP_X_CSRFTOKEN'] = client.cookies['csrftoken'].value
            return client.post(f'/api/billing/{self.i.pk}/{action}/', data, secure=True, **headers)

        def revenue():
            return Decimal(admin.get('/api/dashboard/', {'end':self.day.isoformat()}, secure=True).json()['revenue'])

        self.assertEqual(post(owner, 'promotion', {'code': self.promo.code}).status_code, 200)
        snapshot = self.billing_snapshot()
        self.assertEqual(snapshot[0]['total_amount'], Decimal('450000'))
        for action, data in self.promotion_requests():
            for client, csrf, expected in ((owner, False, 403), (other, True, 404), (admin, True, 403)):
                with self.subTest(action=action, expected=expected, csrf=csrf):
                    self.assertEqual(post(client, action, data, csrf=csrf).status_code, expected)
                    self.assertEqual(self.billing_snapshot(), snapshot)
        self.assertEqual(post(admin, 'promotion', {'code': 'X' * 51}).status_code, 403)
        self.assertEqual(self.billing_snapshot(), snapshot)
        self.assertEqual(admin.get(f'/api/billing/{self.i.pk}/', secure=True).status_code, 200)
        self.assertEqual(revenue(), 0)

        self.assertEqual(post(owner, 'select-spa', {}).status_code, 200)
        self.assertEqual(post(owner, 'edit-promotion', {}).status_code, 200)
        self.assertEqual(post(owner, 'remove-promotion', {}).status_code, 200)
        self.i.refresh_from_db()
        self.assertIsNone(self.i.promotion_id)
        self.assertEqual(self.i.total_amount, Decimal('500000'))
        self.assertEqual(post(owner, 'promotion', {'code': self.promo.code}).status_code, 200)
        self.assertEqual(post(owner, 'cash', {'amount': 450000}).status_code, 403)
        with at_appointment_start(self.a):
            self.assertEqual(post(admin, 'cash', {'amount': 450000}).status_code, 200)
        self.i.refresh_from_db()
        self.assertEqual(self.i.payment_status, 'paid')
        payment = self.i.payments.get(status='success', payment_method='spa')
        self.assertEqual(payment.recorded_by_id, self.admin.pk)
        self.assertEqual(payment.amount, Decimal('450000'))
        paid_snapshot = self.billing_snapshot()
        for action, data in self.promotion_requests():
            with self.subTest(paid_action=action):
                self.assertEqual(post(owner, action, data).status_code, 400)
                self.assertEqual(self.billing_snapshot(), paid_snapshot)
        self.assertEqual(paid_snapshot[2], snapshot[2])
        self.assertEqual(revenue(), Decimal('450000'))

    def test_cancelled_invoice_disallows_all_promotion_actions(self):
        self.claim()
        transition(self.admin, self.a.pk, 'cancelled', reason='Khách đề nghị hủy')
        snapshot = self.billing_snapshot()
        self.assertEqual(snapshot[0]['payment_status'], 'cancelled')
        for action, data in self.promotion_requests():
            with self.subTest(action=action):
                self.assertEqual(self.post(action, data).status_code, 400)
                self.assertEqual(self.billing_snapshot(), snapshot)

    def test_unresolved_payos_session_cannot_be_unlocked_or_repriced(self):
        self.claim()
        payment = services.online(self.user, self.i.pk)
        self.get.side_effect = TimeoutError
        snapshot = self.billing_snapshot()

        self.client.force_login(self.admin)
        for action, data in self.promotion_requests():
            with self.subTest(admin_action=action):
                self.assertEqual(self.post(action, data).status_code, 403)
                self.assertEqual(self.billing_snapshot(), snapshot)
        self.get.assert_not_called()

        self.client.force_login(self.user)
        for action, data in self.promotion_requests():
            with self.subTest(owner_action=action):
                self.assertEqual(self.post(action, data).status_code, 400)
                self.assertEqual(self.billing_snapshot(), snapshot)
        self.get.assert_called_once()
        self.cancel.assert_not_called()

        self.get.side_effect = lambda item: provider_state(item, 'EXPIRED')
        self.assertEqual(self.post('edit-promotion').status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'cancelled')
        self.assertEqual(self.post('remove-promotion').status_code, 200)
        self.i.refresh_from_db()
        self.assertIsNone(self.i.promotion_id)
        self.assertEqual(self.i.total_amount, Decimal('500000'))
        self.assertFalse(Payment.objects.filter(status='success').exists())

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
        self.get.side_effect=lambda payment:provider_state(payment,'EXPIRED')
        services.refresh_online(self.user,self.i.pk)
        with self.assertRaises(ValidationError):self.claim(self.next_invoice)
        services.begin_promotion_edit(self.user,self.i.pk);self.claim(code='')
        self.claim(self.next_invoice)

    def test_reserved_snapshot_can_settle_after_promotion_expires(self):
        self.claim()
        self.promo.start_date=timezone.localdate()-timedelta(days=2)
        self.promo.end_date=timezone.localdate()-timedelta(days=1);self.promo.save()
        with at_appointment_start(self.a):services.cash(self.admin,self.i.pk,Decimal(450000))
        self.assertEqual(usage(self.promo,self.customer.pk)['used'],1)

    def test_legacy_overallocated_invoices_cannot_both_settle(self):
        self.claim()
        # Simulate inconsistent pre-feature data; never used outside test DB.
        Invoice.objects.filter(pk=self.next_invoice.pk).update(promotion=self.promo,promotion_code_snapshot=self.promo.code,discount_amount=50000,total_amount=450000)
        with at_appointment_start(self.a), self.assertRaisesMessage(ValidationError,'đang được giữ'):
            services.cash(self.admin,self.i.pk,Decimal(450000))
        with self.assertRaises(ValidationError):services.online(self.user,self.next_invoice.pk)
        self.assertFalse(Payment.objects.exists())

    def test_late_webhook_after_releasing_code_never_consumes_reallocated_slot(self):
        self.claim();old=services.online(self.user,self.i.pk)
        services.begin_promotion_edit(self.user,self.i.pk);self.claim(code='')
        self.claim(self.next_invoice)
        self.deliver(old);self.deliver(old)
        old.refresh_from_db();self.assertEqual(old.status,'review')
        self.assertEqual(usage(self.promo,self.customer.pk),dict(used=0,reserved=1))
        with at_appointment_start(self.next_appointment):services.cash(self.admin,self.next_invoice.pk,Decimal(450000))
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
        with at_appointment_start(self.a):
            results=self.race([lambda:services.cash(self.admin,self.i.pk,Decimal(450000)),lambda:self.claim(self.next_invoice)])
        self.assertEqual(results,[True,False])
        self.assertEqual(usage(self.promo,self.customer.pk),dict(used=1,reserved=0))

    def test_webhook_and_second_claim_cannot_double_use(self):
        self.claim();p=services.online(self.user,self.i.pk)
        with gateway.client() as sdk:data=sdk.webhooks.verify(self.signed(p))
        results=self.race([lambda:services.accept_webhook(data),lambda:self.claim(self.next_invoice)])
        self.assertEqual(results,[True,False])
        self.assertEqual(usage(self.promo,self.customer.pk),dict(used=1,reserved=0))
