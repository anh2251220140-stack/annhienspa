from decimal import Decimal
from unittest.mock import patch

from django.test import Client,TestCase,override_settings
from promotions.services import usage
from .models import Payment
from . import services
from .test_invoice_flow import FlowFixtures


@override_settings(PAYOS_CLIENT_ID='test-client',PAYOS_API_KEY='test-api',PAYOS_CHECKSUM_KEY='test-checksum')
class PayosFeedbackTests(FlowFixtures,TestCase):
    def setUp(self):
        self.flow_seed()
        self.i.subtotal=self.i.total_amount=Decimal('390000');self.i.save()
        self.i.details.update(unit_price=390000,line_total=390000)
        self.promo.code='TESTSPA10';self.promo.per_customer_limit=1;self.promo.save()
        services.apply_promotion(self.user,self.i.pk,'TESTSPA10')

    def test_missing_each_key_returns_clear_error_without_payment_or_sdk(self):
        for name in ('PAYOS_CLIENT_ID','PAYOS_API_KEY','PAYOS_CHECKSUM_KEY'):
            with self.subTest(name=name),override_settings(**{name:''}),patch('billing.gateway.PayOS') as sdk:
                response=self.post('online')
                self.assertEqual(response.status_code,400)
                self.assertIn('Thanh toán payOS chưa được cấu hình',response.json()['error'])
                sdk.assert_not_called();self.create.assert_not_called()
                self.assertFalse(Payment.objects.exists())
                row=self.client.get(f'/api/billing/{self.i.pk}/').json()['item']
                self.assertFalse(row['payosConfigured'])
        self.i.refresh_from_db()
        self.assertEqual(self.i.payment_status,'unpaid');self.assertEqual(self.i.payment_preference,'')
        self.assertEqual(self.i.total_amount,351000)
        self.assertEqual(usage(self.promo,self.customer.pk),dict(used=0,reserved=1))

    def test_success_uses_server_amount_ignores_tampered_frontend_and_reuses_order(self):
        first=self.post('online',{'amount':'1','total':'1','promotion':'BOGUS'})
        second=self.post('online',{'amount':'999999'})
        self.assertEqual(first.status_code,200);self.assertEqual(second.status_code,200)
        self.assertEqual(first.json()['orderCode'],second.json()['orderCode'])
        self.create.assert_called_once()
        self.assertEqual(self.create.call_args.args[0].amount,351000)
        p=Payment.objects.get();self.assertEqual(p.amount,351000);self.assertEqual(p.status,'pending')
        self.i.refresh_from_db();self.assertEqual(self.i.payment_status,'unpaid')
        row=self.client.get(f'/api/billing/{self.i.pk}/').json()['item']
        self.assertTrue(row['payosConfigured']);self.assertEqual(Decimal(row['currentOnline']['amount']),351000)
        self.assertEqual(usage(self.promo,self.customer.pk),dict(used=0,reserved=1))

    def test_api_error_is_sanitized_and_keeps_same_reservation_on_retry(self):
        self.create.side_effect=RuntimeError('private-provider-response-do-not-display')
        for _ in range(2):
            response=self.post('online')
            self.assertEqual(response.status_code,400)
            self.assertIn('Không thể lấy liên kết payOS',response.json()['error'])
            self.assertNotContains(response,'private-provider-response',status_code=400)
        self.assertEqual(Payment.objects.count(),1)
        p=Payment.objects.get();self.assertEqual(p.amount,351000);self.assertEqual(p.status,'pending')
        self.assertEqual(self.post('remove-promotion').status_code,400)
        self.i.refresh_from_db();self.assertEqual(self.i.payment_status,'unpaid')
        self.assertEqual(usage(self.promo,self.customer.pk),dict(used=0,reserved=1))

    def test_csrf_missing_denied_valid_token_reaches_config_validation_without_writes(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.user)
        url=f'/api/billing/{self.i.pk}/online/'
        self.assertEqual(client.post(url).status_code,403)
        self.assertEqual(client.get('/invoice.html').status_code,200)
        with override_settings(PAYOS_CLIENT_ID=''):
            result=client.post(url,HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)
        self.assertEqual(result.status_code,400)
        self.assertIn('chưa được cấu hình',result.json()['error'])
        self.assertFalse(Payment.objects.exists())

    @override_settings(PAYOS_CLIENT_ID='   ')
    def test_whitespace_key_is_missing(self):
        self.assertEqual(self.post('online').status_code,400)
        self.assertFalse(Payment.objects.exists())
