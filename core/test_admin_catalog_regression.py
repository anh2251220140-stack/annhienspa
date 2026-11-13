"""FR-07/FR-09 database regression tests.

Run only through the guarded FR-14 runner after approval of test-schema cleanup.
Discovery is read-only; these tests themselves perform writes when executed.
Never use manage.py test with the default project database configuration.
"""
import io
import tempfile
from contextlib import ExitStack
from datetime import time
from decimal import Decimal
from unittest.mock import patch

from PIL import Image
from django.core.exceptions import ValidationError
from config.fr14_test_guard import require_isolated_database
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings

from core.test_phase3 import Fixtures
from services.models import Service, ServiceCategory
from products.models import CareProduct, ServiceProduct
from appointments.services import book
from billing.models import Invoice


class AdminCatalogRegressionTests(Fixtures, TestCase):
    """Actual HTTP + ORM checks, not mocked persistence or frontend fixtures."""

    @classmethod
    def setUpClass(cls):
        require_isolated_database()
        super().setUpClass()

    def setUp(self):
        stack = self.enterContext(ExitStack())
        for operation in ('create', 'get', 'cancel'):
            stack.enter_context(patch('billing.gateway.' + operation,
                                     side_effect=AssertionError('Real payOS access forbidden')))
        self.media = stack.enter_context(tempfile.TemporaryDirectory(prefix='annhien-catalog-test-'))
        stack.enter_context(override_settings(MEDIA_ROOT=self.media, FILE_UPLOAD_TEMP_DIR=self.media))
        self.seed()
        self.client.force_login(self.admin)
        self.user_client = Client(); self.user_client.force_login(self.user)
        self.b = Service.objects.create(category=self.category, name='Service B', description='B', price=400000, duration_minutes=45)
        self.c = Service.objects.create(category=self.category, name='Service C', description='C', price=300000, duration_minutes=30)

    def service_data(self, **changes):
        data = dict(name='Service A edited', category=self.category.pk, description='Real description',
                    price='500000.00', duration_minutes=60, care_group='relax', image_preset='', gallery_preset='')
        data.update(changes)
        return data

    def product_data(self, **changes):
        data = dict(name='Test product', product_type='Serum', description='Real description',
                    care_group='face', image_preset='', services=[self.service.pk, self.b.pk])
        data.update(changes)
        return data

    def post_ok(self, path, data, status=200):
        response = self.client.post(path, data)
        self.assertEqual(response.status_code, status, response.content)
        return response.json()

    def create_product(self, **changes):
        result = self.post_ok('/api/admin/products/', self.product_data(**changes), 201)
        return CareProduct.objects.get(pk=result['item']['id'])

    def assert_links(self, product, ids):
        product.refresh_from_db()
        self.assertSetEqual(set(product.services.values_list('pk', flat=True)), set(ids))
        self.assertEqual(ServiceProduct.objects.filter(product=product).count(), len(set(ids)))
        result = self.client.get('/api/admin/products/').json()
        row = next(row for row in result['items'] if row['id'] == product.pk)
        self.assertSetEqual(set(row['serviceIds']), set(ids))

    def test_category_http_create_edit_toggle_and_readback(self):
        result = self.post_ok('/api/admin/categories/', {'name': 'New category', 'description': 'First'}, 201)
        category = ServiceCategory.objects.get(pk=result['item']['id'])
        self.assertTrue(category.is_active)
        path = f'/api/admin/categories/{category.pk}/'
        self.post_ok(path, {'name': 'Updated category', 'description': 'Updated'})
        category.refresh_from_db()
        self.assertEqual((category.name, category.description), ('Updated category', 'Updated'))
        for expected in (False, True):
            self.post_ok(path, {'_toggle': '1'})
            category.refresh_from_db()
            self.assertEqual(category.is_active, expected)
            row = next(x for x in self.client.get('/api/admin/categories/').json()['items'] if x['id'] == category.pk)
            self.assertEqual((row['name'], row['description'], row['active']), ('Updated category', 'Updated', expected))
        self.assertContains(self.client.get(path), 'Updated category')
        self.assertEqual(self.client.delete(path).status_code, 405)

    def test_service_edit_and_hide_preserve_confirmed_appointment_and_invoice_snapshot(self):
        appointment = book(self.user, self.service.pk, self.employee.pk, self.day, time(10))
        self.post_ok(f'/api/appointments/{appointment.pk}/status/', {'status': 'confirmed'})
        invoice = Invoice.objects.get(appointment=appointment)
        detail = invoice.details.get()
        before = (appointment.appointment_date, appointment.start_time, appointment.end_time, appointment.employee_id)
        snapshot = (detail.service_name_snapshot, detail.unit_price, detail.line_total)
        self.post_ok(f'/api/admin/services/{self.service.pk}/', self.service_data(price='650000.00', duration_minutes=90))
        self.service.refresh_from_db()
        self.assertEqual((self.service.price, self.service.duration_minutes), (Decimal('650000'), 90))
        newer = book(self.user, self.service.pk, self.employee.pk, self.day, time(13))
        self.assertEqual(newer.end_time, time(14, 30))
        self.post_ok(f'/api/admin/services/{self.service.pk}/', {'_toggle': '1'})
        appointment.refresh_from_db(); invoice.refresh_from_db(); detail.refresh_from_db()
        self.assertEqual(appointment.status, 'confirmed')
        self.assertEqual((appointment.appointment_date, appointment.start_time, appointment.end_time, appointment.employee_id), before)
        self.assertEqual((detail.service_name_snapshot, detail.unit_price, detail.line_total), snapshot)
        self.assertEqual((invoice.subtotal, invoice.total_amount, invoice.payment_status), (Decimal('500000'), Decimal('500000'), 'unpaid'))
        self.assertEqual(Invoice.objects.filter(appointment=appointment).count(), 1)
        self.assertFalse(appointment.cancel_reason)
        self.assertIsNone(appointment.cancelled_at)
        catalog = self.client.get('/services.html').context['live_catalog']
        self.assertFalse(any(x['id'] == self.service.pk for x in catalog['services']))
        newer.refresh_from_db(); self.assertEqual(newer.status, 'pending')
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/api/appointments/available-slots/', {'service': self.service.pk, 'employee': self.employee.pk, 'date': self.day.isoformat()}).status_code, 400)

    def test_service_changes_do_not_cancel_pending_appointment_or_create_invoice(self):
        appointment = book(self.user, self.service.pk, self.employee.pk, self.day, time(10))
        end = appointment.end_time
        self.post_ok(f'/api/admin/services/{self.service.pk}/', self.service_data(price='700000', duration_minutes=30))
        self.post_ok(f'/api/admin/services/{self.service.pk}/', {'_toggle': '1'})
        appointment.refresh_from_db()
        self.assertEqual((appointment.status, appointment.end_time), ('pending', end))
        self.assertFalse(Invoice.objects.filter(appointment=appointment).exists())

    def test_product_multiple_links_create_and_edit_form_preselection(self):
        product = self.create_product()
        self.assert_links(product, [self.service.pk, self.b.pk])
        response = self.client.get(f'/api/admin/products/{product.pk}/')
        from html.parser import HTMLParser
        class CheckedServices(HTMLParser):
            def __init__(self):
                super().__init__(); self.ids = set()
            def handle_starttag(self, tag, attrs):
                values = dict(attrs)
                if tag == 'input' and values.get('name') == 'services' and 'checked' in values:
                    self.ids.add(int(values['value']))
        parser = CheckedServices(); parser.feed(response.json()['html'])
        self.assertSetEqual(parser.ids, {self.service.pk, self.b.pk})

    def test_product_replace_ab_with_bc_and_readback(self):
        product = self.create_product()
        self.post_ok(f'/api/admin/products/{product.pk}/', self.product_data(services=[self.b.pk, self.c.pk]))
        self.assert_links(product, [self.b.pk, self.c.pk])
        self.assertEqual(product.care_group, 'face')

    def test_product_remove_all_links(self):
        product = self.create_product()
        self.post_ok(f'/api/admin/products/{product.pk}/', self.product_data(services=[]))
        self.assert_links(product, [])

    def test_product_open_edit_or_view_without_post_does_not_save(self):
        product = self.create_product()
        before = list(ServiceProduct.objects.filter(product=product).order_by('pk').values())
        for suffix in ('', '?view=1'):
            self.assertEqual(self.client.get(f'/api/admin/products/{product.pk}/' + suffix).status_code, 200)
        product.refresh_from_db()
        self.assertEqual(product.name, 'Test product')
        self.assertEqual(list(ServiceProduct.objects.filter(product=product).order_by('pk').values()), before)
        # Browser Cancel is separately covered by the isolated UI tool (no POST).

    def test_product_invalid_service_id_rejected_without_partial_edit(self):
        product = self.create_product()
        missing = max(Service.objects.values_list('pk', flat=True)) + 1000
        response = self.client.post(f'/api/admin/products/{product.pk}/', self.product_data(name='Must not persist', services=[self.b.pk, missing]))
        self.assertEqual(response.status_code, 400)
        self.assertIn('services', response.json()['errors'])
        product.refresh_from_db(); self.assertEqual(product.name, 'Test product')
        self.assert_links(product, [self.service.pk, self.b.pk])

    def test_product_duplicate_posted_ids_do_not_duplicate_relations(self):
        product = self.create_product(services=[self.service.pk, self.service.pk, self.b.pk])
        self.assert_links(product, [self.service.pk, self.b.pk])
        self.post_ok(f'/api/admin/products/{product.pk}/', self.product_data(services=[self.b.pk, self.b.pk, self.c.pk]))
        self.assert_links(product, [self.b.pk, self.c.pk])

    def test_product_relation_unique_constraint_even_when_bulk_validation_bypassed(self):
        product = self.create_product()
        with self.assertRaises(ValidationError):
            ServiceProduct.objects.create(product=product, service=self.service)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ServiceProduct.objects.bulk_create([ServiceProduct(product=product, service=self.service)])
        self.assert_links(product, [self.service.pk, self.b.pk])

    def test_product_inactive_service_link_allowed_but_not_in_user_catalog(self):
        self.b.is_active = False; self.b.save()
        product = self.create_product()
        self.assert_links(product, [self.service.pk, self.b.pk])
        self.assertIn('Tạm ngừng', self.client.get(f'/api/admin/products/{product.pk}/').json()['html'])
        catalog = self.user_client.get('/products.html').context['live_catalog']
        links = {x['serviceId'] for x in catalog['relations'] if x['productId'] == product.pk}
        self.assertSetEqual(links, {self.service.pk})
        self.post_ok(f'/api/admin/products/{product.pk}/', self.product_data(services=[self.b.pk, self.c.pk]))
        self.assert_links(product, [self.b.pk, self.c.pk])

    def test_product_hidden_category_hides_relation_without_deleting_it(self):
        product = self.create_product()
        self.post_ok(f'/api/admin/categories/{self.category.pk}/', {'_toggle': '1'})
        self.assert_links(product, [self.service.pk, self.b.pk])
        catalog = self.user_client.get('/products.html').context['live_catalog']
        self.assertFalse(any(x['productId'] == product.pk for x in catalog['relations']))
        self.assertTrue(any(x['id'] == product.pk for x in catalog['products']))

    @staticmethod
    def upload(name='photo.png', color='white', oversized=False, content_type='image/png'):
        buf = io.BytesIO(); Image.new('RGB', (8, 8), color).save(buf, format='PNG')
        content = buf.getvalue()
        if oversized:
            content += b'\0' * (5 * 1024 * 1024 + 1 - len(content))
        return SimpleUploadedFile(name, content, content_type=content_type)

    def image_lifecycle(self, module, field='image'):
        data = self.service_data if module == 'services' else self.product_data
        Model = Service if module == 'services' else CareProduct
        created = self.post_ok(f'/api/admin/{module}/', data(**{field: self.upload()}), 201)
        pk = created['item']['id']; path = f'/api/admin/{module}/{pk}/'
        obj = Model.objects.get(pk=pk); original = getattr(obj, field).name
        self.assertTrue(getattr(obj, field).storage.exists(original))
        self.assertIn(getattr(obj, field).url, self.client.get(path + '?view=1').json()['html'])
        self.post_ok(path, data())
        obj.refresh_from_db(); self.assertEqual(getattr(obj, field).name, original)
        self.post_ok(path, data(**{field: self.upload('replacement.png', 'blue')}))
        obj.refresh_from_db(); replacement = getattr(obj, field).name
        self.assertNotEqual(replacement, original); self.assertTrue(getattr(obj, field).storage.exists(replacement))
        self.post_ok(path, data(**{field + '-clear': 'on'}))
        obj.refresh_from_db(); self.assertFalse(getattr(obj, field))
        self.assertTrue(getattr(obj, field).storage.exists(original))
        self.assertTrue(getattr(obj, field).storage.exists(replacement))
        self.assertEqual(getattr(obj, field + '_preset'), '')
        self.assertEqual(obj.care_group, 'relax' if module == 'services' else 'face')
        if module == 'products': self.assert_links(obj, [self.service.pk, self.b.pk])

    def test_service_upload_keep_replace_and_clear_image_http(self):
        self.image_lifecycle('services')

    def test_product_upload_keep_replace_and_clear_image_http(self):
        self.image_lifecycle('products')

    def invalid_uploads(self, module, field='image'):
        data = self.service_data if module == 'services' else self.product_data
        Model = Service if module == 'services' else CareProduct
        # subTest does not roll back requests: every case gets its own record/image.
        for kind in ('wrong-mime', 'fake-image', 'unsupported-format', 'over-5mb', 'clear-and-upload'):
            with self.subTest(module=module, field=field, kind=kind):
                result = self.post_ok(f'/api/admin/{module}/', data(**{field: self.upload()}), 201)
                obj = Model.objects.get(pk=result['item']['id'])
                original = getattr(obj, field).name
                before = Model.objects.filter(pk=obj.pk).values().get()
                with getattr(obj, field).storage.open(original, 'rb') as saved:
                    original_bytes = saved.read()
                if kind == 'fake-image':
                    upload = SimpleUploadedFile('fake.png', b'not an image', content_type='image/png')
                elif kind == 'wrong-mime':
                    # The bytes are PNG; Django/Pillow replaces the untrusted declaration.
                    upload = self.upload(content_type='text/plain')
                elif kind == 'unsupported-format':
                    buf = io.BytesIO()
                    Image.new('RGB', (8, 8), 'white').save(buf, format='GIF')
                    upload = SimpleUploadedFile('photo.gif', buf.getvalue(), content_type='image/png')
                else:
                    upload = self.upload(oversized=kind == 'over-5mb')
                payload = data(**{field: upload})
                if kind == 'clear-and-upload':
                    payload[field + '-clear'] = 'on'
                response = self.client.post(f'/api/admin/{module}/{obj.pk}/', payload)
                if kind == 'wrong-mime':
                    self.assertEqual(response.status_code, 200, response.content)
                    self.assertEqual(response.wsgi_request.FILES[field].content_type, 'image/png')
                    obj.refresh_from_db()
                    self.assertNotEqual(getattr(obj, field).name, original)
                    with getattr(obj, field).open('rb') as saved:
                        image = Image.open(saved)
                        self.assertEqual(image.format, 'PNG')
                        image.verify()
                else:
                    self.assertEqual(response.status_code, 400, response.content)
                    errors = response.json()['errors']
                    self.assertIn(field, errors)
                    self.assertTrue(errors[field])
                    if kind == 'over-5mb':
                        self.assertIn('5 MB', ' '.join(errors[field]))
                    self.assertEqual(Model.objects.filter(pk=obj.pk).values().get(), before)
                    obj.refresh_from_db()
                    self.assertEqual(getattr(obj, field).name, original)
                with getattr(obj, field).storage.open(original, 'rb') as saved:
                    self.assertEqual(saved.read(), original_bytes)
                if module == 'products':
                    self.assert_links(obj, [self.service.pk, self.b.pk])

    def test_service_invalid_oversized_and_conflicting_uploads_rejected(self):
        self.invalid_uploads('services')

    def test_product_invalid_oversized_and_conflicting_uploads_rejected(self):
        self.invalid_uploads('products')

    def test_service_gallery_upload_keep_replace_and_clear_http(self):
        self.image_lifecycle('services', 'gallery')

    def test_service_gallery_invalid_oversized_and_conflicting_uploads(self):
        self.invalid_uploads('services', 'gallery')

    def test_product_hidden_excluded_from_user_catalog_without_deleting_links(self):
        product = self.create_product()
        self.post_ok(f'/api/admin/products/{product.pk}/', {'_toggle': '1'})
        self.assert_links(product, [self.service.pk, self.b.pk])
        catalog = self.user_client.get('/products.html').context['live_catalog']
        self.assertFalse(any(x['id'] == product.pk for x in catalog['products']))
        self.assertFalse(any(x['productId'] == product.pk for x in catalog['relations']))
