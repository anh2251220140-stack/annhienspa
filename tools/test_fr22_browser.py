"""Offline browser-environment tests; no server sockets or migration commands."""
from contextlib import ExitStack
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch


class BrowserEnvironmentTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from tools import fr22_browser_test as preview
        cls.stack=ExitStack()
        cls.folder=cls.stack.enter_context(TemporaryDirectory(prefix='fr22-browser-offline-'))
        preview.configure_preview(cls.stack,Path(cls.folder))
        preview.create_fixture_schema()
        preview.seed_preview()

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()
        super().tearDownClass()

    def setUp(self):
        from django.test import Client
        from django.core.cache import cache
        cache.clear()
        self.client=Client(enforce_csrf_checks=True, HTTP_HOST='127.0.0.1')

    def enter(self,scenario='ai'):
        response=self.client.get('/acceptance/fr22/?scenario='+scenario)
        self.assertEqual(response.status_code,302)
        page=self.client.get('/services.html')
        self.assertEqual(page.status_code,200)
        return page

    def post(self,**values):
        from django.conf import settings
        payload={'skin':'Da khô','needs':'face','budget':'600000','interests':'Dịu nhẹ','duration':''}
        payload.update(values)
        token=self.client.cookies[settings.CSRF_COOKIE_NAME].value
        return self.client.post('/api/ai/recommendations/',payload,content_type='application/json',HTTP_X_CSRFTOKEN=token)

    def test_schema_is_sqlite_without_migration_history_and_catalog_is_seven(self):
        from django.db import connection
        from services.models import Service
        from products.models import CareProduct,ServiceProduct
        self.assertEqual(connection.vendor,'sqlite')
        self.assertNotIn('django_migrations',connection.introspection.table_names())
        self.assertEqual(Service.objects.filter(is_active=True).count(),9)
        self.assertEqual(CareProduct.objects.count(),5)
        self.assertEqual(ServiceProduct.objects.count(),8)

    def test_real_template_and_api_ai_mode_persist(self):
        page=self.enter()
        self.assertIn(b'data-recommendation-form',page.content)
        self.assertIn(b'HTTP mock',page.content)
        result=self.post().json()
        self.assertEqual(result['mode'],'ai')
        self.assertTrue(1<=len(result['items'])<=3)
        self.assertTrue(all(float(r['price'])<=600000 for r in result['items']))
        self.assertIn('giả lập',result['items'][0]['reason'])
        state=self.client.get('/acceptance/fr22/state/').json()
        self.assertEqual(state['latest']['mode'],'ai')

    def test_timeout_and_quota_and_invalid_json_are_rule_not_ai(self):
        from django.core.cache import cache
        for scenario in ('fallback','quota','invalid'):
            cache.clear();self.enter(scenario)
            result=self.post().json()
            self.assertEqual(result['mode'],'rule')
            self.assertEqual(result['label'],'Đề xuất theo quy tắc')

    def test_page_get_and_reload_do_not_call_sdk(self):
        from tools.fr22_browser_test import COUNTERS
        before=COUNTERS['mock_http_requests']
        self.enter()
        self.client.get('/services.html')
        self.assertEqual(COUNTERS['mock_http_requests'],before)

    def test_csrf_and_cooldown_stay_active(self):
        self.enter()
        self.assertEqual(self.client.post('/api/ai/recommendations/',{},content_type='application/json').status_code,403)
        self.assertEqual(self.post().status_code,200)
        self.assertEqual(self.post().status_code,429)

    def test_no_matching_budget_does_not_call_sdk(self):
        from tools.fr22_browser_test import COUNTERS
        self.enter();before=COUNTERS['mock_http_requests']
        result=self.post(budget='1').json()
        self.assertEqual(result['items'],[])
        self.assertEqual(result['mode'],'rule')
        self.assertEqual(COUNTERS['mock_http_requests'],before)

    def test_cookie_names_are_distinct_and_real_network_is_blocked(self):
        import socket
        from django.conf import settings
        self.assertEqual(settings.SESSION_COOKIE_NAME,'annhien_fr22_preview_session')
        self.assertEqual(settings.CSRF_COOKIE_NAME,'annhien_fr22_preview_csrf')
        self.assertFalse(settings.AI_REVIEW_EXPORT_APPROVED)
        self.assertFalse(settings.AI_PAID_CALLS_APPROVED)
        with socket.socket() as sock,self.assertRaises(RuntimeError):
            sock.connect(('127.0.0.1',3306))

    def test_unknown_mock_target_cannot_reach_network(self):
        import httpx
        with self.assertRaises(RuntimeError):
            httpx.Client().get('https://api.openai.com/')

    def test_three_profiles_personalize_real_api_and_export_only_own_history(self):
        from django.core.cache import cache
        from django.conf import settings
        from tools.fr22_browser_test import PROFILES
        from accounts.models import Customer
        from ai_features.gemini import GeminiProvider
        original=GeminiProvider.structured
        captured=[]
        def capture(provider,instruction,data):
            captured.append(data)
            return original(provider,instruction,data)
        recommendations=[]
        with patch.object(GeminiProvider,'structured',capture):
            for profile,group in [('KH-01','body'),('KH-02','face'),('KH-03','relax')]:
                cache.clear()
                self.client.get('/acceptance/fr22/?profile='+profile)
                self.client.get('/services.html')
                token=self.client.cookies[settings.CSRF_COOKIE_NAME].value
                customer=Customer.objects.get(user_id=PROFILES[profile])
                result=self.client.post('/api/ai/recommendations/',{},content_type='application/json',HTTP_X_CSRFTOKEN=token).json()
                self.assertEqual(result['mode'],'ai')
                self.assertTrue(all(float(row['price'])<=float(customer.budget) for row in result['items']))
                if profile=='KH-01':
                    self.assertEqual(len(result['items']),2)
                    self.assertEqual(result['budgetScope'],'per-treatment')
                self.assertEqual(captured[-1]['preferences']['needs'],group)
                self.assertFalse(captured[-1]['productUsageHistory']['available'])
                history=captured[-1]['serviceHistory']
                self.assertEqual(len(history),1)
                self.assertIn(history[0]['count'],(3,4))
                self.assertRegex(history[0]['lastUsed'],r'^\d{4}-\d{2}-\d{2}$')
                self.assertNotEqual(result['items'][0]['id'],history[0]['serviceId'])
                self.assertNotIn(customer.full_name,json.dumps(captured[-1],ensure_ascii=False))
                recommendations.append({row['id'] for row in result['items']})
        self.assertFalse(recommendations[0]&recommendations[1])
        self.assertFalse(recommendations[1]&recommendations[2])

    def test_sensitive_skin_blocks_known_caution_and_only_verified_product_links(self):
        from services.models import Service
        from products.models import ServiceProduct,CareProduct
        self.enter()
        result=self.post(skin='Da nhạy cảm',needs='face',budget='500000').json()
        self.assertEqual(result['mode'],'ai')
        blocked=Service.objects.get(name__startswith='Chăm sóc da chuyên sâu')
        self.assertNotIn(blocked.pk,[row['id'] for row in result['items']])
        for row in result['items']:
            self.assertIn('không xác nhận',row['caution'])
            for product in row['products']:
                self.assertTrue(ServiceProduct.objects.filter(service_id=row['id'],product_id=product['id']).exists())
                source=CareProduct.objects.get(pk=product['id'])
                self.assertEqual(product['ingredients'],source.ingredients)
                self.assertIn('Da nhạy cảm',source.skin_type)

    def test_unlinked_service_has_no_product_recommendation(self):
        self.enter()
        result=self.post(budget='180000',duration='short').json()
        self.assertEqual(result['mode'],'ai')
        self.assertTrue(result['items'])
        self.assertTrue(all(row['products']==[] for row in result['items']))

    def test_alternatives_never_duplicate_selected_services(self):
        from django.core.cache import cache
        self.enter()
        result=self.post().json()
        selected={row['id'] for row in result['items']}
        self.assertFalse(selected&{row['id'] for row in result['alternatives']})
        self.assertEqual(result['budgetScope'],'per-treatment')
