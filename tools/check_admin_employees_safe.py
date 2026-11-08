"""No-database checks for Employees presentation and preserved form/security contracts."""
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
from employees.models import Employee
from core.business_forms import EmployeeForm,CategoryForm
from core.business_views import row,records
from core.business_layout import groups_for
from types import SimpleNamespace
class EmployeeSafeChecks(unittest.TestCase):
 def setUp(self):
  self.block=patch('django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection',side_effect=RuntimeError('DB forbidden'));self.block.start();self.addCleanup(self.block.stop)
 def test_image_urls_and_no_demo_fallback(self):
  p=Employee(id=12,full_name='Employee')
  with patch.object(type(p.services),'values_list',return_value=[]):
   self.assertEqual(row(p)['image_url'],'');p.avatar_preset='../private.png';self.assertEqual(row(p)['image_url'],'');p.avatar='employees/current.jpg';self.assertTrue(row(p)['image_url'].endswith('/employees/current.jpg'))
 def test_upload_verification_and_keep_existing(self):
  f=EmployeeForm();field=f.fields['avatar'];self.assertEqual(field.clean(None,'employees/old.jpg'),'employees/old.jpg');self.assertIs(field.clean(False,'employees/old.jpg'),False)
  with self.assertRaises(ValidationError):field.clean(SimpleUploadedFile('fake.png',b'not an image',content_type='image/png'))
  buf=io.BytesIO();Image.new('RGB',(2,2)).save(buf,format='PNG');self.assertIsNotNone(field.clean(SimpleUploadedFile('real.png',buf.getvalue(),content_type='image/png')))
 def test_product_form_render_and_labels(self):
  f=EmployeeForm();f.fields['services'].choices=[(1,'Dịch vụ thật')];f.initial['avatar']='employees/current.jpg'
  html=render_to_string('partials/business_form.html',{'form':f,'module':'employees','groups':groups_for(f,'employees')})
  self.assertIn('avatar-clear',html);self.assertNotIn('Currently:',html);self.assertIn('>Lưu</button>',html);self.assertIn('Dịch vụ có thể phụ trách',html)
  other=render_to_string('partials/business_form.html',{'module':'promotions','groups':[]});self.assertIn('Lưu thay đổi',other)
 def test_multiple_services_pass_to_relation_manager(self):
  from employees.models import EmployeeService
  instance=Employee(id=10,full_name='Staff',specialty='Spa')
  from services.models import Service
  with patch.object(type(instance.services),'all',return_value=[Service(id=1),Service(id=2)]):
   form=EmployeeForm(instance=instance)
  self.assertEqual([s.pk for s in form.initial['services']],[1,2])
  form.cleaned_data={'services':[1,2]}
  manager=type(instance.services)
  with patch.object(manager,'set') as save:
   form._save_m2m()
   save.assert_called_once_with([1,2])
  self.assertTrue(any(tuple(c.fields)==('employee','service') for c in EmployeeService._meta.constraints))
 def test_phone_validation(self):
  f=EmployeeForm();f.cleaned_data={'phone':'abc'}
  with self.assertRaises(ValidationError):f.clean_phone()
 def test_permissions_and_csrf(self):
  rf=RequestFactory();r=rf.get('/api/admin/employees/');r.user=AnonymousUser();self.assertEqual(records(r,'employees').status_code,401)
  r.user=SimpleNamespace(is_authenticated=True,is_active=True,role='User');self.assertEqual(records(r,'employees').status_code,403)
  with override_settings(ALLOWED_HOSTS=['testserver']):self.assertEqual(Client(enforce_csrf_checks=True).post('/api/admin/employees/',{'name':'blocked'}).status_code,403)
if __name__=='__main__':unittest.main()
