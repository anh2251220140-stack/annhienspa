"""Run with tools/test_blob_media.py: temporary SQLite/media and no network."""
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import ast
import os

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage, default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import path
from PIL import Image

from core.test_phase3 import Fixtures
from products.models import CareProduct
from .blob_media import (PrivateBlobStorage, MediaStorageUnavailable, blob_image,
                         BlobFailureMiddleware, image_name, MAX_UPLOAD_BYTES)

urlpatterns = [path('media/<path:path>', blob_image)]
BLOB_STORAGES = {
    'default': {'BACKEND': 'config.blob_media.PrivateBlobStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}


def picture(color='white'):
    buffer = BytesIO()
    Image.new('RGB', (32, 32), color).save(buffer, format='PNG')
    return buffer.getvalue()


class MemoryBlob:
    class BlobNotFoundError(FileNotFoundError):
        pass

    def __init__(self):
        self.files = {}
        self.calls = []
        self.fail = False

    def put_blob(self, name, body, **options):
        self.calls.append(('put', name, options))
        assert options['access'] == 'private'
        assert options['allow_overwrite'] is False
        if self.fail:
            raise RuntimeError('secret-provider-token-must-not-leak')
        assert name not in self.files
        self.files[name] = bytes(body)
        return SimpleNamespace(pathname=name)

    @contextmanager
    def stream_blob(self, name, **options):
        self.calls.append(('get', name, options))
        assert options['access'] == 'private'
        if self.fail:
            raise RuntimeError('secret-provider-token-must-not-leak')
        if name not in self.files:
            raise self.BlobNotFoundError()
        class Download:
            metadata = SimpleNamespace(size=len(self.files[name]))
            def __iter__(inner):
                return iter([self.files[name]])
        yield Download()

    def head_blob(self, name):
        if name not in self.files:
            raise self.BlobNotFoundError()
        return SimpleNamespace(size=len(self.files[name]))

    def delete_blob(self, name):
        self.files.pop(name, None)


class BlobStorageTests(SimpleTestCase):
    def setUp(self):
        self.sdk = MemoryBlob()
        self.enterContext(patch('config.blob_media.blob_sdk', return_value=self.sdk))
        self.storage = PrivateBlobStorage()

    def test_upload_private_and_preserve_relative_url(self):
        name = self.storage.save('products/example.png', ContentFile(picture()))
        self.assertTrue(name.startswith('products/'))
        self.assertEqual(self.storage.url(name), '/media/' + name)
        self.assertEqual(self.storage.open(name).read(), picture())

    def test_replacement_uses_new_key_and_keeps_old_object(self):
        a = self.storage.save('services/example.png', ContentFile(picture()))
        b = self.storage.save('services/example.png', ContentFile(picture('blue')))
        self.assertNotEqual(a, b)
        self.assertEqual(self.sdk.files[a], picture())

    def test_long_original_filename_fits_model_limit(self):
        name = self.storage.save('services/details/' + 'a' * 220 + '.png', ContentFile(picture()), max_length=255)
        self.assertLessEqual(len(name), 255)

    def test_existing_paths_work_without_database_rewrite(self):
        name = 'products/ảnh cũ.png'
        self.sdk.files[name] = picture()
        self.assertEqual(self.storage.open(name).read(), picture())
        self.assertIn('%', self.storage.url(name))

    def test_exists_size_and_explicit_delete(self):
        self.assertFalse(self.storage.exists('products/test.png'))
        name = self.storage.save('products/test.png', ContentFile(picture()))
        self.assertTrue(self.storage.exists(name))
        self.assertEqual(self.storage.size(name), len(picture()))
        self.storage.delete(name)
        self.assertFalse(self.storage.exists(name))

    def test_missing_image_has_404_semantics(self):
        with self.assertRaises(FileNotFoundError):
            self.storage.open('products/missing.png')

    def test_invalid_paths_never_reach_sdk(self):
        for name in ('../secret.png', '/products/a.png', 'products/../a.png',
                     'products//a.png', 'products/avatars/a.png', 'avatars/.hidden.png',
                     'https://example.com/a.png', 'products/a%2f.png', 'products/a.svg',
                     'products/a\\b.png', 'products/a\x00.png'):
            with self.subTest(name=name), self.assertRaises(SuspiciousFileOperation):
                self.storage.open(name)
        self.assertEqual(self.sdk.calls, [])

    def test_fake_image_and_oversized_upload_rejected(self):
        for raw in (b'not an image', b'x' * (MAX_UPLOAD_BYTES + 1)):
            with self.assertRaises(MediaStorageUnavailable):
                self.storage.save('products/test.png', ContentFile(raw))
        self.assertEqual(self.sdk.calls, [])

    def test_wrong_format_extension_rejected(self):
        with self.assertRaises(MediaStorageUnavailable):
            self.storage.save('products/test.jpg', ContentFile(picture()))
        self.assertEqual(self.sdk.calls, [])

    def test_sdk_failure_is_sanitized(self):
        self.sdk.fail = True
        with self.assertRaises(MediaStorageUnavailable) as caught:
            self.storage.save('products/test.png', ContentFile(picture()))
        self.assertNotIn('secret-provider', str(caught.exception))

    def test_no_disk_fallback(self):
        self.sdk.fail = True
        with patch.object(FileSystemStorage, '_save') as local_save:
            with self.assertRaises(MediaStorageUnavailable):
                self.storage.save('products/test.png', ContentFile(picture()))
            local_save.assert_not_called()

    def test_invalid_download_is_never_served(self):
        self.sdk.files['products/bad.png'] = b'<script>not an image</script>'
        with self.assertRaises(MediaStorageUnavailable):
            self.storage.open('products/bad.png')

    def test_missing_sdk_is_sanitized_without_local_fallback(self):
        with patch('config.blob_media.blob_sdk', side_effect=ImportError('internal detail')):
            with self.assertRaises(MediaStorageUnavailable) as caught:
                self.storage.save('products/test.png', ContentFile(picture()))
        self.assertNotIn('internal detail', str(caught.exception))

    def test_storage_activation_is_vercel_only(self):
        tree = ast.parse((settings.BASE_DIR / 'config/settings.py').read_text(encoding='utf-8'))
        node = next(n for n in tree.body if isinstance(n, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == 'BLOB_MEDIA_ENABLED' for t in n.targets))
        code = compile(ast.Expression(node.value), '<activation>', 'eval')
        for env, expected in [({}, False), ({'BLOB_READ_WRITE_TOKEN': 'fake'}, False),
                              ({'DJANGO_BLOB_MEDIA_ENABLED': 'true'}, False),
                              ({'VERCEL': '1'}, True),
                              ({'VERCEL': '1', 'DJANGO_BLOB_MEDIA_ENABLED': 'false'}, False)]:
            with self.subTest(env=env), patch.dict(os.environ, env, clear=True):
                self.assertEqual(eval(code, {'os': os}), expected)

    def test_normal_local_storage_still_filesystem(self):
        self.assertIsInstance(default_storage, FileSystemStorage)
        name = default_storage.save('products/local.png', ContentFile(picture()))
        self.assertTrue((Path(settings.MEDIA_ROOT) / name).is_file())
        self.assertEqual(default_storage.open(name).read(), picture())
        default_storage.delete(name)
        self.assertEqual(self.sdk.calls, [])

    def test_middleware_does_not_mask_other_errors(self):
        middleware = BlobFailureMiddleware(lambda request: HttpResponse())
        self.assertIsNone(middleware.process_exception(None, ValueError('unrelated')))


@override_settings(BLOB_MEDIA_ENABLED=True, STORAGES=BLOB_STORAGES,
                   ALLOWED_HOSTS=['testserver', 'annhienspa-sepia.vercel.app'],
                   CSRF_TRUSTED_ORIGINS=['https://annhienspa-sepia.vercel.app'])
class BlobApplicationTests(Fixtures, TestCase):
    def setUp(self):
        self.seed()
        self.sdk = MemoryBlob()
        self.enterContext(patch('config.blob_media.blob_sdk', return_value=self.sdk))
        self.enterContext(override_settings(MIDDLEWARE=[*settings.MIDDLEWARE, 'config.blob_media.BlobFailureMiddleware']))
        self.admin_client = self.auth_client(self.admin, '/admin-services.html')
        self.user_client = self.auth_client(self.user, '/profile.html')
        self.product = CareProduct.objects.create(name='Offline product', product_type='Serum', description='Offline')

    def auth_client(self, user, page):
        client = Client(enforce_csrf_checks=True, HTTP_HOST='annhienspa-sepia.vercel.app',
                        HTTP_ORIGIN='https://annhienspa-sepia.vercel.app')
        client.force_login(user)
        self.assertEqual(client.get(page).status_code, 200)
        return client

    def post(self, client, url, data, token=True):
        return client.post(url, data, HTTP_X_CSRFTOKEN=client.cookies[settings.CSRF_COOKIE_NAME].value if token else '')

    def upload(self):
        return SimpleUploadedFile('test.png', picture(), content_type='image/png')

    def fields(self, module):
        if module == 'services':
            return dict(name='Offline service', category=self.category.pk, price='350000',
                        duration_minutes=60, description='Offline', steps='[]')
        return dict(name='Offline product', product_type='Serum', description='Offline', services=[self.service.pk])

    def test_admin_upload_keep_replace_clear(self):
        for module, item in [('services', self.service), ('products', self.product)]:
            with self.subTest(module=module):
                url = f'/api/admin/{module}/{item.pk}/'
                for action in ('upload', 'keep', 'replace', 'clear'):
                    data = self.fields(module)
                    if action in ('upload', 'replace'):
                        data['image'] = self.upload()
                    if action == 'clear':
                        data['image-clear'] = 'on'
                    self.assertEqual(self.post(self.admin_client, url, data).status_code, 200)
                    item.refresh_from_db()
                    if action == 'clear':
                        self.assertFalse(item.image)
                    else:
                        self.assertIn(item.image.name, self.sdk.files)

    def test_service_gallery_and_employee_avatar(self):
        data = self.fields('services'); data['gallery'] = self.upload()
        self.assertEqual(self.post(self.admin_client, f'/api/admin/services/{self.service.pk}/', data).status_code, 200)
        self.service.refresh_from_db()
        self.assertTrue(self.service.gallery.name.startswith('services/details/'))
        data = dict(full_name='Offline employee', specialty='Spa', services=[self.service.pk], avatar=self.upload())
        self.assertEqual(self.post(self.admin_client, f'/api/admin/employees/{self.employee.pk}/', data).status_code, 200)
        self.employee.refresh_from_db()
        self.assertTrue(self.employee.avatar.name.startswith('employees/'))

    def test_failure_returns_503_and_rolls_back_record(self):
        self.sdk.fail = True
        before = self.service.name
        data = self.fields('services'); data['image'] = self.upload()
        response = self.post(self.admin_client, f'/api/admin/services/{self.service.pk}/', data)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['code'], 'MEDIA_STORAGE_UNAVAILABLE')
        self.assertNotIn(b'secret-provider', response.content)
        self.service.refresh_from_db()
        self.assertEqual(self.service.name, before)
        self.assertEqual(self.admin_client.get('/api/admin/services/').status_code, 200)

    def test_user_avatar_upload_and_failed_replace(self):
        data = dict(name='Offline customer', username=self.user.username, email=self.user.email, avatar=self.upload())
        self.assertEqual(self.post(self.user_client, '/api/profile/', data).status_code, 200)
        self.customer.refresh_from_db(); old = self.customer.avatar.name
        self.assertIn(old, self.sdk.files)
        self.sdk.fail = True
        data['avatar'] = self.upload(); data['name'] = 'Must roll back'
        self.assertEqual(self.post(self.user_client, '/api/profile/', data).status_code, 503)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.avatar.name, old)
        self.assertEqual(self.customer.full_name, 'Offline customer')
        self.assertEqual(self.user_client.get('/api/profile/').status_code, 200)

    def test_user_cannot_write_admin_or_bypass_csrf(self):
        url = f'/api/admin/services/{self.service.pk}/'
        for client, token in [(self.user_client, True), (self.admin_client, False)]:
            data = self.fields('services'); data['image'] = self.upload()
            self.assertEqual(self.post(client, url, data, token).status_code, 403)
        self.assertEqual(self.sdk.calls, [])

    def test_cancel_and_read_only_modal_do_not_upload(self):
        self.assertEqual(self.admin_client.get(f'/api/admin/products/{self.product.pk}/').status_code, 200)
        self.assertEqual(self.sdk.calls, [])

    @override_settings(ROOT_URLCONF=__name__)
    def test_public_catalog_image_and_private_avatar_permissions(self):
        self.sdk.files['products/existing.png'] = picture()
        self.sdk.files['avatars/existing.png'] = picture()
        self.customer.avatar = 'avatars/existing.png'; self.customer.save(update_fields=['avatar'])
        anonymous = Client()
        public = anonymous.get('/media/products/existing.png')
        self.assertEqual(public.status_code, 200)
        self.assertEqual(public.content, picture())
        self.assertEqual(public['Cache-Control'], 'private, no-store')
        self.sdk.calls.clear()
        self.assertEqual(anonymous.get('/media/avatars/existing.png').status_code, 404)
        stranger = Client(); stranger.force_login(self.other)
        self.assertEqual(stranger.get('/media/avatars/existing.png').status_code, 404)
        self.assertEqual(self.sdk.calls, [])
        self.assertEqual(self.user_client.get('/media/avatars/existing.png').status_code, 200)
        self.assertEqual(self.admin_client.get('/media/avatars/existing.png').status_code, 200)

    @override_settings(ROOT_URLCONF=__name__)
    def test_missing_blob_404_and_provider_failure_503(self):
        self.assertEqual(self.admin_client.get('/media/products/missing.png').status_code, 404)
        self.sdk.fail = True
        self.assertEqual(self.admin_client.get('/media/products/known.png').status_code, 503)

    @override_settings(ROOT_URLCONF=__name__, BLOB_MEDIA_ENABLED=False)
    def test_blob_route_disabled_locally(self):
        self.assertEqual(self.admin_client.get('/media/products/existing.png').status_code, 404)
        self.assertEqual(self.sdk.calls, [])


class BlobSDKContractTests(SimpleTestCase):
    def test_real_sdk_private_upload_and_download_with_mock_transport(self):
        # Optional on Windows; the deployment SDK is deliberately Linux-only.
        # This test uses fake credentials and a closed, in-memory HTTP transport.
        try:
            import httpx2 as httpx
            from vercel.api import session
            from vercel.blob.sync import BlobCredentials, CredentialKind, SyncBlobServiceOptions
        except ImportError:
            self.skipTest('Install vercel-blob in an isolated test environment for SDK contract test.')
        calls = []
        objects = {}

        def respond(request):
            calls.append(request.method)
            if request.method == 'PUT':
                self.assertEqual(request.headers['x-vercel-blob-access'], 'private')
                self.assertEqual(request.headers['x-allow-overwrite'], '0')
                name = request.url.params['pathname']
                objects[name] = request.read()
                url = 'https://offline.private.blob.vercel-storage.com/' + name
                return httpx.Response(200, json=dict(url=url, downloadUrl=url,
                    pathname=name, contentType='image/png', contentDisposition='inline', etag='offline'))
            self.assertEqual(request.method, 'GET')
            self.assertEqual(request.url.host, 'offline.private.blob.vercel-storage.com')
            self.assertTrue(request.headers.get('authorization'))
            return httpx.Response(200, content=objects[request.url.path.lstrip('/')],
                                  headers={'content-type': 'image/png'})

        options = SyncBlobServiceOptions(credentials_factory=lambda: BlobCredentials(
            token='offline-test-token', store_id='offline', kind=CredentialKind.OIDC))
        with session(service_options=[options], httpx_client_factory=lambda: httpx.Client(
                transport=httpx.MockTransport(respond), trust_env=False)):
            storage = PrivateBlobStorage()
            name = storage.save('products/test.png', ContentFile(picture()))
            self.assertEqual(storage.open(name).read(), picture())
            self.assertEqual(storage.url(name), '/media/' + name)
        self.assertEqual(calls, ['PUT', 'GET'])
