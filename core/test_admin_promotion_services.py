"""Promotion-service HTTP/ORM regressions for the isolated FR-14 MySQL runner.

Discovery does not connect to a database. Execution writes fixtures and requires
the guarded runner, test credentials and explicit cleanup consent. Never run
this module using the default project database configuration.
"""
from contextlib import ExitStack
from html.parser import HTMLParser
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.test import Client, TestCase
from django.utils import timezone

from core.test_phase3 import Fixtures
from promotions.models import Promotion, PromotionService
from promotions.services import evaluate_code
from services.models import Service


class ServiceCheckboxes(HTMLParser):
    def __init__(self):
        super().__init__()
        self.checked = set()
        self.available = set()
        self.cancel_buttons = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'input' and attrs.get('name') == 'services':
            self.available.add(int(attrs['value']))
            if 'checked' in attrs:
                self.checked.add(int(attrs['value']))
        if tag == 'button' and 'data-close' in attrs:
            self.cancel_buttons.append(attrs)


class AdminPromotionServicesTests(Fixtures, TestCase):
    @classmethod
    def setUpClass(cls):
        db = settings.DATABASES['default']
        expected = dict(NAME='annhien_spa_fr14_tests', USER='annhien_fr14_tests',
                        HOST='127.0.0.1', PORT='3306')
        if (db.get('ENGINE') != 'django.db.backends.mysql' or
                any(str(db.get(key)) != value for key, value in expected.items()) or
                db.get('TEST', {}).get('NAME') != expected['NAME']):
            raise ImproperlyConfigured('Promotion tests require the guarded isolated FR-14 runner.')
        super().setUpClass()

    def setUp(self):
        super().setUp()
        stack = self.enterContext(ExitStack())
        for operation in ('create', 'get', 'cancel'):
            stack.enter_context(patch('billing.gateway.' + operation,
                                      side_effect=AssertionError('External payOS forbidden')))
        self.seed()
        self.b = Service.objects.create(category=self.category, name='Promotion service B',
                                        description='Isolated fixture', price=400000, duration_minutes=45)
        self.c = Service.objects.create(category=self.category, name='Promotion service C',
                                        description='Isolated fixture', price=300000, duration_minutes=30)
        self.client.force_login(self.admin)
        self.user_client = Client()
        self.user_client.force_login(self.user)

    def payload(self, ids=None, **changes):
        data = dict(name='Multi-service promotion', code='MULTI10', discount_type='percent',
                    discount_value='10.00', start_date=timezone.localdate().isoformat(),
                    end_date=self.day.isoformat(), description='Isolated promotion',
                    conditions='', note='', accent='champagne',
                    services=[self.service.pk, self.b.pk] if ids is None else ids)
        data.update(changes)
        return data

    def create_promotion(self, ids=None):
        response = self.client.post('/api/admin/promotions/', self.payload(ids))
        self.assertEqual(response.status_code, 201, response.content)
        return Promotion.objects.get(pk=response.json()['item']['id'])

    def assert_links(self, promotion, ids):
        expected = sorted(set(ids))
        fresh = Promotion.objects.get(pk=promotion.pk)
        self.assertEqual(list(fresh.services.order_by('pk').values_list('pk', flat=True)), expected)
        self.assertEqual(list(PromotionService.objects.filter(promotion=fresh)
                              .order_by('service_id').values_list('service_id', flat=True)), expected)
        response = self.client.get('/api/admin/promotions/')
        self.assertEqual(response.status_code, 200)
        item = next(row for row in response.json()['items'] if row['id'] == promotion.pk)
        self.assertEqual(sorted(item['serviceIds']), expected)

    def edit_form(self, promotion):
        response = self.client.get(f'/api/admin/promotions/{promotion.pk}/')
        self.assertEqual(response.status_code, 200)
        parser = ServiceCheckboxes()
        parser.feed(response.json()['html'])
        return parser, response.json()['html']

    def snapshot(self, promotion):
        return (Promotion.objects.filter(pk=promotion.pk).values().get(),
                list(PromotionService.objects.filter(promotion=promotion).order_by('pk').values()))

    def user_service_ids(self, promotion):
        response = self.user_client.get('/promotions.html')
        self.assertEqual(response.status_code, 200)
        item = next(row for row in response.context['live_promotions']['items']
                    if row['id'] == promotion.pk)
        return item['serviceIds']

    def test_create_two_services_readback_and_edit_preselection(self):
        promotion = self.create_promotion()
        self.assert_links(promotion, [self.service.pk, self.b.pk])
        form, _ = self.edit_form(promotion)
        self.assertSetEqual(form.available, {self.service.pk, self.b.pk, self.c.pk})
        self.assertSetEqual(form.checked, {self.service.pk, self.b.pk})
        self.assertSetEqual(set(self.user_service_ids(promotion)), {self.service.pk, self.b.pk})

    def test_replace_ab_with_bc_and_reopen_exact_selection(self):
        promotion = self.create_promotion()
        response = self.client.post(f'/api/admin/promotions/{promotion.pk}/',
                                    self.payload([self.b.pk, self.c.pk]))
        self.assertEqual(response.status_code, 200, response.content)
        self.assert_links(promotion, [self.b.pk, self.c.pk])
        form, _ = self.edit_form(promotion)
        self.assertSetEqual(form.checked, {self.b.pk, self.c.pk})
        self.assertSetEqual(set(self.user_service_ids(promotion)), {self.b.pk, self.c.pk})

    def test_remove_all_links_leaves_no_selection_and_no_implicit_scope(self):
        promotion = self.create_promotion()
        response = self.client.post(f'/api/admin/promotions/{promotion.pk}/', self.payload([]))
        self.assertEqual(response.status_code, 200, response.content)
        self.assert_links(promotion, [])
        form, _ = self.edit_form(promotion)
        self.assertSetEqual(form.checked, set())
        self.assertEqual(self.user_service_ids(promotion), [])
        # An empty selection is accepted by CRUD, but does not mean "all services".
        with self.assertRaisesMessage(ValidationError, 'Dịch vụ không thuộc phạm vi áp dụng.'):
            evaluate_code(promotion.code, self.service)

    def test_invalid_service_ids_reject_create_and_edit_without_partial_changes(self):
        promotion = self.create_promotion()
        before = self.snapshot(promotion)
        total = Promotion.objects.count()
        total_links = PromotionService.objects.count()
        missing = Service.objects.order_by('-pk').first().pk + 1000
        for invalid in (missing, 'not-a-service-id'):
            with self.subTest(invalid=invalid, operation='create'):
                response = self.client.post('/api/admin/promotions/',
                                            self.payload([self.b.pk, invalid], code='INVALID10'))
                self.assertEqual(response.status_code, 400, response.content)
                self.assertIn('services', response.json()['errors'])
                self.assertEqual(Promotion.objects.count(), total)
                self.assertEqual(PromotionService.objects.count(), total_links)
            with self.subTest(invalid=invalid, operation='edit'):
                response = self.client.post(f'/api/admin/promotions/{promotion.pk}/',
                                            self.payload([self.b.pk, invalid], name='Must not persist'))
                self.assertEqual(response.status_code, 400, response.content)
                self.assertIn('services', response.json()['errors'])
                self.assertEqual(self.snapshot(promotion), before)

    def test_duplicate_posted_ids_never_duplicate_links(self):
        promotion = self.create_promotion([self.service.pk, self.service.pk, self.b.pk])
        self.assert_links(promotion, [self.service.pk, self.b.pk])
        response = self.client.post(f'/api/admin/promotions/{promotion.pk}/',
                                    self.payload([self.b.pk, self.c.pk, self.b.pk, self.c.pk]))
        self.assertEqual(response.status_code, 200, response.content)
        self.assert_links(promotion, [self.b.pk, self.c.pk])

    def test_inactive_service_links_saved_but_unavailable_to_user(self):
        self.b.is_active = False
        self.b.save()
        promotion = self.create_promotion()
        self.assert_links(promotion, [self.service.pk, self.b.pk])
        form, html = self.edit_form(promotion)
        self.assertSetEqual(form.checked, {self.service.pk, self.b.pk})
        self.assertIn('Promotion service B (Tạm ngừng)', html)
        self.assertEqual(self.user_service_ids(promotion), [self.service.pk])
        self.assertTrue(evaluate_code(promotion.code, self.service)['eligible'])
        with self.assertRaisesMessage(ValidationError, 'Dịch vụ không thuộc phạm vi áp dụng.'):
            evaluate_code(promotion.code, self.b)
        response = self.client.post(f'/api/admin/promotions/{promotion.pk}/',
                                    self.payload([self.b.pk, self.c.pk]))
        self.assertEqual(response.status_code, 200, response.content)
        self.assert_links(promotion, [self.b.pk, self.c.pk])
        self.assertEqual(self.user_service_ids(promotion), [self.c.pk])
        self.assertTrue(evaluate_code(promotion.code, self.c)['eligible'])
        self.category.is_active = False
        self.category.save()
        self.assertEqual(self.user_service_ids(promotion), [])
        self.assert_links(promotion, [self.b.pk, self.c.pk])
        with self.assertRaisesMessage(ValidationError, 'Dịch vụ không thuộc phạm vi áp dụng.'):
            evaluate_code(promotion.code, self.c)

    def test_open_and_abandon_edit_does_not_persist_changes(self):
        promotion = self.create_promotion()
        before = self.snapshot(promotion)
        form, _ = self.edit_form(promotion)
        self.assertTrue(form.cancel_buttons)
        self.assertTrue(all(button.get('type') == 'button' for button in form.cancel_buttons))
        # Cancel has no write endpoint. Opening/abandoning uses GET only; the
        # isolated Chrome UI tool separately checks changing checkboxes + Cancel
        # sends no POST. This database test verifies the persisted state remains.
        response = self.client.get(f'/api/admin/promotions/{promotion.pk}/?view=1')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('<input', response.json()['html'])
        reopened, _ = self.edit_form(promotion)
        self.assertSetEqual(reopened.checked, {self.service.pk, self.b.pk})
        self.assertEqual(self.snapshot(promotion), before)
