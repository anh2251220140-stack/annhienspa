"""Coupon exclusions must be explained, without bypassing manual conditions."""
from datetime import time, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from appointments.services import book, transition
from core.business_forms import PromotionForm
from promotions.services import policy
from . import services
from .models import Invoice, Payment
from .test_invoice_flow import FlowFixtures
from .test_phase4 import at_appointment_start


class PromotionDiagnosticTests(FlowFixtures, TestCase):
    def setUp(self):
        self.flow_seed()
        self.second.services.clear()
        self.i.subtotal = self.i.total_amount = Decimal('390000')
        self.i.save()
        self.promo.code = 'TESTSPA10'
        self.promo.min_amount = 0
        self.promo.max_discount = 50000
        self.promo.conditions = 'Áp dụng cho dịch vụ được chọn'
        self.promo.note = 'Mỗi khách hàng chỉ sử dụng mã một lần.'
        self.promo.save()

    def choices(self):
        return self.client.get(f'/api/billing/{self.i.pk}/promotions/')

    def test_annhien10_accepts_informational_note_and_reserves_one_use(self):
        self.i.subtotal = self.i.total_amount = Decimal('300000')
        self.i.save()
        self.promo.code = 'ANNHIEN10'
        self.promo.min_amount = Decimal('300000')
        self.promo.max_discount = Decimal('30000')
        self.promo.per_customer_limit = 1
        self.promo.conditions = ''
        self.promo.note = 'Vui lòng liên hệ Spa nếu cần tư vấn.'
        self.promo.note_is_informational = True
        self.promo.save()
        self.assertEqual(self.choices().json()['items'][0]['code'], 'ANNHIEN10')
        self.assertEqual(self.post('promotion', {'code': 'ANNHIEN10'}).status_code, 200)
        self.i.refresh_from_db()
        self.assertEqual(self.i.discount_amount, Decimal('30000'))
        self.assertEqual(self.i.total_amount, Decimal('270000'))
        self.assertFalse(Payment.objects.exists())

        other_appointment = book(self.user, self.service.pk, self.employee.pk, self.day, time(11))
        transition(self.admin, other_appointment.pk, 'confirmed')
        other_invoice = Invoice.objects.get(appointment=other_appointment)
        response = self.client.post(f'/api/billing/{other_invoice.pk}/promotion/', {'code': 'ANNHIEN10'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('đang được giữ', response.json()['error'])
        other_invoice.refresh_from_db()
        self.assertIsNone(other_invoice.promotion_id)
        self.assertEqual(other_invoice.total_amount, other_invoice.subtotal)

    def test_legacy_admin_edit_requires_explicit_conversion_and_preserves_limit(self):
        # This test targets the Admin form/save contract. GET_LOCK itself has separate MySQL coverage.
        self.promo.note += '\nXuất trình giấy xác nhận.'
        self.promo.save()
        self.client.force_login(self.admin)
        url = f'/api/admin/promotions/{self.promo.pk}/'
        self.assertFalse(PromotionForm(instance=self.promo)['note_is_informational'].value())
        self.assertTrue(PromotionForm()['note_is_informational'].value())
        self.assertContains(self.client.get(url), 'id_note_is_informational')
        data = dict(name=self.promo.name, code=self.promo.code, discount_type='percent',
                    discount_value='10', start_date=self.promo.start_date, end_date=self.promo.end_date,
                    note=self.promo.note, conditions=self.promo.conditions, services=[self.service.pk])
        with patch('core.business_views.code_lock'):
            self.assertEqual(self.client.post(url, data).status_code, 200)
            self.promo.refresh_from_db()
            self.assertEqual(policy(self.promo), (1, ['Xuất trình giấy xác nhận']))

            data['note_is_informational'] = 'on'
            response = self.client.post(url, data)
            self.assertEqual(response.status_code, 400)
            self.assertIn('per_customer_limit', response.json()['errors'])
            self.promo.refresh_from_db()
            self.assertFalse(self.promo.note_is_informational)

            data.update(per_customer_limit=1, conditions='Xuất trình giấy xác nhận',
                        note='Vui lòng liên hệ Spa nếu cần tư vấn.')
            self.assertEqual(self.client.post(url, data).status_code, 200)
        self.promo.refresh_from_db()
        self.assertTrue(self.promo.note_is_informational)
        self.assertEqual(self.promo.note, data['note'])
        self.assertEqual(policy(self.promo), (1, ['Xuất trình giấy xác nhận']))
        self.client.force_login(self.user)
        self.assertIn('Xuất trình giấy xác nhận', self.choices().json()['unavailable'][0]['reason'])
        self.assertEqual(self.post('promotion', {'code': self.promo.code}).status_code, 400)
        self.i.refresh_from_db()
        self.assertIsNone(self.i.promotion_id)
        self.assertEqual(self.i.total_amount, self.i.subtotal)

    def test_scope_only_text_still_requires_review_and_explains_exclusion_after_reload(self):
        self.promo.conditions='Cần giấy xác nhận tại Spa'
        self.promo.save()
        for _ in range(2):
            data = self.choices().json()
            self.assertEqual(data['items'], [])
            self.assertEqual(data['unavailable'][0]['code'], 'TESTSPA10')
            self.assertIn('Cần Spa kiểm tra', data['unavailable'][0]['reason'])
            self.assertIn(self.promo.conditions, data['unavailable'][0]['reason'])
        self.assertEqual(self.post('promotion', {'code': 'TESTSPA10'}).status_code, 400)
        self.i.refresh_from_db()
        self.assertEqual(self.i.total_amount, 390000)
        self.assertIsNone(self.i.promotion_id)
        self.assertFalse(Payment.objects.exists())

    def test_fully_structured_test_coupon_apply_remove_and_reload_snapshot_amounts(self):
        # Test-only control: no unsupported manual conditions or usage-limit promise.
        self.promo.conditions = self.promo.note = ''
        self.promo.save()
        self.service.price = 900000
        self.service.save()
        choice = self.choices().json()['items'][0]
        self.assertEqual(Decimal(choice['discount']), 39000)
        self.assertEqual(Decimal(choice['total']), 351000)
        self.assertEqual(self.post('promotion', {'code': 'TESTSPA10'}).status_code, 200)
        for _ in range(2):
            row = self.client.get(f'/api/billing/{self.i.pk}/').json()['item']
            self.assertEqual(row['promotion'], 'TESTSPA10')
            self.assertEqual(Decimal(row['discount']), 39000)
            self.assertEqual(Decimal(row['total']), 351000)
        self.assertEqual(self.post('remove-promotion').status_code, 200)
        self.i.refresh_from_db()
        self.assertEqual(self.i.total_amount, 390000)
        self.assertEqual(self.i.discount_amount, 0)
        self.assertIsNone(self.i.promotion_id)
        self.assertEqual(self.client.get(f'/api/billing/{self.i.pk}/').json()['item']['promotion'], '')

    def test_minimum_date_and_inactive_reasons_without_exposing_unrelated_codes(self):
        self.promo.min_amount = 400000
        self.promo.save()
        self.assertIn('tối thiểu', self.choices().json()['unavailable'][0]['reason'])
        self.promo.min_amount = 0
        self.promo.start_date = timezone.localdate() - timedelta(days=2)
        self.promo.end_date = timezone.localdate() - timedelta(days=1)
        self.promo.save()
        self.assertIn('hiệu lực', self.choices().json()['unavailable'][0]['reason'])
        self.promo.end_date = self.day
        self.promo.is_active = False
        self.promo.save()
        data = self.choices().json()
        self.assertEqual(data['items'], [])
        self.assertEqual([p['code'] for p in data['unavailable']], ['TESTSPA10'])
        self.promo.services.clear()
        self.assertEqual(self.choices().json()['unavailable'], [])
        self.assertEqual(self.post('promotion', {'code': 'TESTSPA10'}).status_code, 400)

    def test_pending_appointment_has_explicit_reason_and_cannot_apply(self):
        self.a.status = 'pending'
        self.a.save()
        data = self.choices().json()
        self.assertEqual(data['items'], [])
        self.assertIn('chưa được xác nhận', data['message'])
        self.assertEqual(self.post('promotion', {'code': 'TESTSPA10'}).status_code, 400)

    def test_payment_preference_requires_explicit_edit_and_paid_invoice_stays_immutable(self):
        self.post('select-spa')
        self.assertIn('Đổi khuyến mãi', self.choices().json()['message'])
        with at_appointment_start(self.a):
            services.cash(self.admin, self.i.pk, Decimal('390000'))
        self.assertIn('đã thanh toán', self.choices().json()['message'])
        self.assertEqual(self.post('promotion', {'code': 'TESTSPA10'}).status_code, 400)
        self.assertEqual(self.post('remove-promotion').status_code, 400)
        self.i.refresh_from_db()
        self.assertEqual(self.i.total_amount, 390000)
        self.assertEqual(self.i.payment_status, 'paid')

    def test_other_customer_cannot_read_exclusion_or_change_invoice(self):
        self.client.force_login(self.other)
        self.assertEqual(self.choices().status_code, 404)
        self.assertEqual(self.post('promotion', {'code': 'TESTSPA10'}).status_code, 404)
        self.client.logout()
        self.assertEqual(self.choices().status_code, 401)
