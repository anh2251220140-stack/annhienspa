"""No-database checks for Products presentation and preserved form/security contracts."""
import os,sys,io,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from django.test import Client,RequestFactory,override_settings
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.loader import render_to_string
from PIL import Image
from products.models import CareProduct
from core.business_forms import ProductForm,CategoryForm
from core.business_views import row,records
from core.business_layout import groups_for
from types import SimpleNamespace
class ProductSafeChecks(unittest.TestCase):
 def setUp(self):
  self.block=patch('django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection',side_effect=RuntimeError('DB forbidden'));self.block.start();self.addCleanup(self.block.stop)
 def test_image_urls_and_no_demo_fallback(self):
  p=CareProduct(id=12,name='Product')
  with patch.object(type(p.services),'values_list',return_value=[]):
   self.assertEqual(row(p)['image_url'],'');p.image_preset='../private.png';self.assertEqual(row(p)['image_url'],'');p.image='products/current.jpg';self.assertTrue(row(p)['image_url'].endswith('/products/current.jpg'))
 def test_upload_verification_and_keep_existing(self):
  f=ProductForm();field=f.fields['image'];self.assertEqual(field.clean(None,'products/old.jpg'),'products/old.jpg');self.assertIs(field.clean(False,'products/old.jpg'),False)
  with self.assertRaises(ValidationError):field.clean(SimpleUploadedFile('fake.png',b'not an image',content_type='image/png'))
  buf=io.BytesIO();Image.new('RGB',(2,2)).save(buf,format='PNG');self.assertIsNotNone(field.clean(SimpleUploadedFile('real.png',buf.getvalue(),content_type='image/png')))
 def test_product_form_render_and_labels(self):
  f=ProductForm();f.fields['services'].choices=[(1,'Dịch vụ thật')];f.initial['image']='products/current.jpg'
  html=render_to_string('partials/business_form.html',{'form':f,'module':'products','groups':groups_for(f,'products')})
  self.assertIn('image-clear',html);self.assertNotIn('Currently:',html);self.assertIn('>Lưu</button>',html);self.assertIn('Nhóm hiển thị trên trang khách hàng',html)
  other=render_to_string('partials/business_form.html',{'module':'employees','groups':[]});self.assertIn('Lưu thay đổi',other)
 def test_permissions_and_csrf(self):
  rf=RequestFactory();r=rf.get('/api/admin/products/');r.user=AnonymousUser();self.assertEqual(records(r,'products').status_code,401)
  r.user=SimpleNamespace(is_authenticated=True,is_active=True,role='User');self.assertEqual(records(r,'products').status_code,403)
  with override_settings(ALLOWED_HOSTS=['testserver']):self.assertEqual(Client(enforce_csrf_checks=True).post('/api/admin/products/',{'name':'blocked'}).status_code,403)
if __name__=='__main__':unittest.main()
