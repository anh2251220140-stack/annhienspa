"""Read-only presentation regressions; no database or external provider required."""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.contrib.staticfiles import finders
from django.contrib.staticfiles.handlers import StaticFilesHandler
from django.core.wsgi import get_wsgi_application
from django.test import SimpleTestCase,RequestFactory

from core.catalog_data import _promotion_discount_label,promotions
from core.views import FrontendView


class PromotionPresentationTests(SimpleTestCase):
    def promotion(self,value,kind='percent'):
        return SimpleNamespace(pk=1,code='DISPLAYTEST',aliases='',name='Ưu đãi kiểm thử',discount_type=kind,
            discount_value=Decimal(value),per_customer_limit=None,conditions='',note='',note_is_informational=False,
            min_amount=None,max_discount=None,description='',detail='',start_date=SimpleNamespace(isoformat=lambda:'2026-01-01'),
            end_date=SimpleNamespace(isoformat=lambda:'2030-12-31'),badge='',accent='champagne',public_services=[],scope_note='')

    def test_percent_removes_only_insignificant_zeroes(self):
        for value,label in [('10.00','10%'),('15.00','15%'),('12.50','12.5%'),('7.25','7.25%'),('12.500001','12.500001%')]:
            with self.subTest(value=value):
                self.assertEqual(_promotion_discount_label('percent',Decimal(value)),'Giảm '+label)

    def test_currency_type_and_thousands_separator_are_preserved(self):
        for value,label in [('50000.00','50.000 VND'),('50000.50','50.000,5 VND')]:
            with self.subTest(value=value):
                self.assertEqual(_promotion_discount_label('amount',Decimal(value)),'Giảm '+label)

    def test_home_list_and_detail_contexts_use_the_same_formatter_without_mutation(self):
        for kind,value,expected in [('percent','10.00','Giảm 10%'),('percent','12.50','Giảm 12.5%'),('amount','50000.00','Giảm 50.000 VND')]:
            item=self.promotion(value,kind)
            with self.subTest(kind=kind,value=value),patch('core.catalog_data.Promotion.objects.filter') as query:
                query.return_value.prefetch_related.return_value=[item]
                home=promotions()['items'][0]
                detail=promotions(promotion_page=True)['items'][0]
                self.assertEqual(home['discount'],expected)
                self.assertEqual(detail['discount'],expected)
                self.assertEqual(detail['discountType'],kind)
                self.assertEqual(item.discount_value,Decimal(value))

    def test_four_real_templates_render_consistent_discount_labels(self):
        factory=RequestFactory()
        user=SimpleNamespace(is_authenticated=True,is_active=True,role='User',pk=1,id=1,
            username='presentation_fixture',email='fixture@example.test',customer=None)
        for page in ('index.html','home.html','promotions.html','promotion-detail.html'):
            request=factory.get('/'+page,HTTP_HOST='127.0.0.1')
            request.user=user if page=='home.html' else AnonymousUser()
            with self.subTest(page=page),patch('core.catalog_data.catalog',return_value={'services':[],'products':[],'staff':[],'relations':[]}), \
                    patch('core.catalog_data.Promotion.objects.filter') as query:
                query.return_value.prefetch_related.return_value=[self.promotion('10.00')]
                response=FrontendView.as_view(template_name='pages/'+page)(request)
                response.render()
                self.assertEqual(response.status_code,200)
                html=response.content.decode()
                self.assertIn('Giảm 10%',html)
                self.assertNotIn('Giảm 10.00%',html)


class FaviconPresentationTests(SimpleTestCase):
    def test_favicon_redirects_to_existing_local_logo(self):
        response=self.client.get('/favicon.ico',HTTP_HOST='127.0.0.1')
        self.assertEqual(response.status_code,302)
        self.assertEqual(response['Location'],'/static/images/an-nhien-logo.png')
        self.assertIsNotNone(finders.find('images/an-nhien-logo.png'))

    def test_redirect_destination_serves_png_bytes(self):
        request=RequestFactory().get('/static/images/an-nhien-logo.png',HTTP_HOST='127.0.0.1')
        response=StaticFilesHandler(get_wsgi_application()).serve(request)
        try:
            self.assertEqual(response.status_code,200)
            self.assertEqual(response['Content-Type'],'image/png')
            self.assertTrue(b''.join(response.streaming_content).startswith(b'\x89PNG\r\n\x1a\n'))
        finally:response.close()
