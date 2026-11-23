import binascii
from urllib.parse import parse_qs, urlsplit
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase,override_settings
from django.utils import timezone
from .test_invoice_flow import FlowFixtures,created
from . import services,gateway
from .models import Payment
from .qr import image_data
from .gateway import create as sdk_create


def mock_payload():
    # Synthetic non-bank payload for offline tests only; never production fallback.
    data='0002010102125909TEST ONLY6304'
    return data+format(binascii.crc_hqx(data.encode(),0xffff),'04X')


@override_settings(PAYOS_CLIENT_ID='test-client',PAYOS_API_KEY='test-api',PAYOS_CHECKSUM_KEY='test-checksum')
class QrTests(FlowFixtures,TestCase):
    def setUp(self):
        self.flow_seed()
        def result(payment):
            value=created(payment);value.qr_code=mock_payload();return value
        self.create.side_effect=result

    def row(self):return self.client.get(f'/api/billing/{self.i.pk}/').json()['item']

    def test_new_ten_minutes_and_restore_without_provider_calls(self):
        now=timezone.now()
        with patch('billing.services.timezone.now',return_value=now):p=services.online(self.user,self.i.pk)
        self.assertEqual(p.expires_at,now+timedelta(seconds=600))
        self.assertEqual(p.qr_code,mock_payload())
        first=self.row()['currentOnline'];self.assertTrue(first['qrImage'].startswith('data:image/png;base64,'))
        with patch('billing.views.timezone.now',return_value=now+timedelta(seconds=123)):
            second=self.row()['currentOnline']
        self.assertEqual(second['remainingSeconds'],477)
        self.assertEqual(first['qrImage'],second['qrImage']);self.assertEqual(first['orderCode'],second['orderCode'])
        self.create.assert_called_once();self.get.assert_not_called();self.cancel.assert_not_called()
        self.i.refresh_from_db();self.assertEqual(self.i.payment_status,'unpaid')

    def test_gateway_sends_stored_expiry_and_amount(self):
        p=services.online(self.user,self.i.pk)
        with patch('billing.gateway.client') as client:
            sdk_create(p)
            request=client.return_value.__enter__.return_value.payment_requests.create.call_args.args[0]
            self.assertEqual(request.expired_at,int(p.expires_at.timestamp()))
            self.assertEqual(request.amount,int(self.i.total_amount))
            self.assertEqual(request.order_code,p.order_code)
            self.assertEqual(parse_qs(urlsplit(str(request.return_url)).query), {'invoice_id':[str(self.i.pk)]})
            self.assertEqual(parse_qs(urlsplit(str(request.cancel_url)).query), {'invoice_id':[str(self.i.pk)]})

    def test_return_url_preserves_query_fragment_without_provider_id_collision(self):
        target=gateway.invoice_return_url('https://spa.example/invoice.html?source=pay&id=old&invoice_id=2#detail',6)
        parts=urlsplit(target)
        self.assertEqual(parts.fragment,'detail')
        self.assertEqual(parse_qs(parts.query),{'source':['pay'],'invoice_id':['6']})

    def test_old_expiry_unchanged_and_missing_or_invalid_payload_fallback(self):
        p=services.online(self.user,self.i.pk);old=timezone.now()+timedelta(minutes=15)
        Payment.objects.filter(pk=p.pk).update(expires_at=old,qr_code='')
        services.online(self.user,self.i.pk)
        p.refresh_from_db();self.assertEqual(p.expires_at,old)
        row=self.row()['currentOnline'];self.assertEqual(row['qrImage'],'');self.assertTrue(row['checkoutUrl'])
        Payment.objects.filter(pk=p.pk).update(qr_code='<script>bad</script>')
        self.assertEqual(self.row()['currentOnline']['qrImage'],'')
        self.create.assert_called_once()

    def test_expiry_hides_qr_without_closing_or_releasing_coupon(self):
        services.apply_promotion(self.user,self.i.pk,self.promo.code)
        p=services.online(self.user,self.i.pk)
        Payment.objects.filter(pk=p.pk).update(expires_at=timezone.now()-timedelta(seconds=1))
        row=self.row()['currentOnline']
        self.assertTrue(row['expired']);self.assertEqual(row['remainingSeconds'],0)
        self.assertEqual(row['qrImage'],'');self.assertEqual(row['checkoutUrl'],'')
        p.refresh_from_db();self.assertEqual(p.status,'pending')
        self.i.refresh_from_db();self.assertEqual(self.i.promotion_id,self.promo.pk)
        self.get.assert_not_called();self.assertEqual(self.post('online').status_code,400)

    def test_terminal_processing_mismatch_and_other_user_never_receive_qr(self):
        p=services.online(self.user,self.i.pk)
        for state in ('PAID','PROCESSING','UNDERPAID','CANCELLED','EXPIRED','FAILED'):
            Payment.objects.filter(pk=p.pk).update(provider_status=state)
            row=self.row()['currentOnline'];self.assertEqual(row['qrImage'],'');self.assertEqual(row['checkoutUrl'],'')
        Payment.objects.filter(pk=p.pk).update(provider_status='PENDING',amount=1)
        self.assertEqual(self.row()['currentOnline']['qrImage'],'')
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(f'/api/billing/{self.i.pk}/').status_code,404)
        self.client.force_login(self.user)
        for state in ('success','cancelled','review'):
            Payment.objects.filter(pk=p.pk).update(status=state)
            self.assertIsNone(self.row()['currentOnline'])

    def test_corrupt_crc_is_not_rendered(self):
        self.assertTrue(image_data(mock_payload()))
        self.assertEqual(image_data(mock_payload()[:-4]+'FFFF'),'')
        self.assertEqual(image_data(''),'')
