import io,json,tempfile
from datetime import time,timedelta
from decimal import Decimal
from PIL import Image
from django.test import TestCase,Client,override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.utils import timezone
from core.test_phase3 import Fixtures
from core.business_forms import ServiceForm,ProductForm,EmployeeForm,PromotionForm,CategoryForm
from services.models import Service
from employees.models import Employee,EmployeeSchedule
from products.models import CareProduct
from promotions.models import Promotion
from promotions.services import evaluate_code
from employees.scheduling import apply_plan
from appointments.services import book,available_slots
from accounts.models import User,Customer

class Phase3CompletionTests(Fixtures,TestCase):
    def setUp(self):self.seed();self.client.force_login(self.admin)
    def service_data(self):return dict(name='DV đầy đủ',category=self.category.pk,description='Mô tả',price=350000,duration_minutes=45,introduction='Giới thiệu thật',benefits='Lợi ích 1\nLợi ích 2',steps='Bước 1\nBước 2',suitable='Khách phù hợp',note='Lưu ý thật',care_group='face',image_preset='facial.jpg',gallery_preset='facial.jpg')
    def promotion_data(self):return dict(name='CT đầy đủ',code='FULL10',discount_type='percent',discount_value=10,start_date=timezone.localdate(),end_date=self.day,detail='Chi tiết thật',conditions='',note='Lưu ý CT',badge='Đặc biệt',accent='caramel',aliases='ALT10\nALT11',scope_note='Phạm vi thật',services=[self.service.pk],min_amount=100000,max_discount=40000)
    def test_complete_service_roundtrip_and_modal_groups(self):
        d=self.service_data();r=self.client.post('/api/admin/services/',d);self.assertEqual(r.status_code,201,r.content);pk=r.json()['item']['id']
        for key in ('introduction','benefits','steps','suitable','note','care_group','image_preset','gallery_preset'):self.assertEqual(getattr(Service.objects.get(pk=pk),key),d[key])
        html=self.client.get(f'/api/admin/services/{pk}/').json()['html'];self.assertIn('Nội dung chi tiết liệu trình',html);self.assertIn('<details',html);self.assertNotIn('name="is_active"',html)
        d['introduction']='Đã sửa';self.assertEqual(self.client.post(f'/api/admin/services/{pk}/',d).status_code,200)
        self.client.logout();catalog=self.client.get('/service-detail.html').context['live_catalog'];item=next(x for x in catalog['services'] if x['id']==pk)
        self.assertEqual(item['introduction'],'Đã sửa');self.assertEqual(item['steps'],['Bước 1','Bước 2']);self.assertEqual(item['image'],'/static/images/facial.jpg')
    def test_complete_product_employee_promotion_roundtrip(self):
        cases={'products':dict(name='SP đầy đủ',product_type='Serum',description='Mô tả',skin_type='Da khô\nDa thường',suitable_for='Người 1\nNgười 2',benefits='Công dụng',ingredients='Thành phần',usage_instructions='Cách dùng',note='Lưu ý',care_group='face',services=[self.service.pk]),'employees':dict(full_name='NV đầy đủ',email='staff@example.com',phone='0901111222',specialty='Dòng 1\nDòng 2',description='Mô tả NV',services=[self.service.pk]),'promotions':self.promotion_data()}
        for module,d in cases.items():
            r=self.client.post('/api/admin/'+module+'/',d);self.assertEqual(r.status_code,201,r.content);pk=r.json()['item']['id']
            self.assertEqual(self.client.post(f'/api/admin/{module}/{pk}/',d).status_code,200)
            view=self.client.get(f'/api/admin/{module}/{pk}/?view=1');self.assertEqual(view.status_code,200);self.assertNotIn('<input',view.json()['html'])
        self.assertEqual(CareProduct.objects.get(name='SP đầy đủ').skin_type,'Da khô\nDa thường')
        self.assertEqual(Employee.objects.get(email='staff@example.com').specialty,'Dòng 1\nDòng 2')
        self.client.logout();p=self.client.get('/promotions.html').context['live_promotions']['items'][0];self.assertEqual(p['aliases'],['ALT10','ALT11']);self.assertEqual(p['scopeNote'],'Phạm vi thật');self.assertEqual(p['accent'],'caramel')
    def test_state_only_through_toggle_all_forms(self):
        for Form in (ServiceForm,ProductForm,EmployeeForm,PromotionForm,CategoryForm):self.assertNotIn('is_active',Form().fields)
        self.service.is_active=False;self.service.save()
        r=self.client.post(f'/api/admin/services/{self.service.pk}/',{**self.service_data(),'is_active':'on'});self.assertEqual(r.status_code,200)
        self.service.refresh_from_db();self.assertFalse(self.service.is_active)
    def test_image_upload_validation_and_existing_image_preserved(self):
        with tempfile.TemporaryDirectory() as directory,override_settings(MEDIA_ROOT=directory):
            content=io.BytesIO();Image.new('RGB',(8,8),'white').save(content,format='PNG')
            d=self.service_data();d['image']=SimpleUploadedFile('photo.png',content.getvalue(),content_type='image/png')
            r=self.client.post('/api/admin/services/',d);self.assertEqual(r.status_code,201,r.content);pk=r.json()['item']['id'];s=Service.objects.get(pk=pk);self.assertTrue(s.image.storage.exists(s.image.name));name=s.image.name
            d=self.service_data();d['image_preset']='';self.assertEqual(self.client.post(f'/api/admin/services/{pk}/',d).status_code,200);s.refresh_from_db();self.assertEqual(s.image.name,name)
            d['image']=SimpleUploadedFile('fake.png',b'not an image',content_type='image/png');self.assertEqual(self.client.post('/api/admin/services/',d).status_code,400)
            d=self.service_data();d['image_preset']='../../.env';self.assertEqual(self.client.post('/api/admin/services/',d).status_code,400)
    def plan(self,**kw):
        d={'mode':'day','start_date':self.day.isoformat(),'end_date':self.day.isoformat(),'work':[['09:00','17:00']],'breaks':[['12:00','13:00']]};d.update(kw);return d
    def test_schedule_breaks_and_preserves_old_rows(self):
        old=self.employee.schedules.get();result=apply_plan(self.employee.pk,self.plan());self.assertEqual(result['shifts'],3);old.refresh_from_db();self.assertFalse(old.is_active)
        slots=available_slots(self.user,self.service.pk,self.employee.pk,self.day);self.assertIn('11:00',slots);self.assertNotIn('11:01',slots);self.assertNotIn('12:00',slots);self.assertIn('13:00',slots)
        with self.assertRaises(ValidationError):book(self.user,self.service.pk,self.employee.pk,self.day,time(12))
    def test_weekly_plan_and_leave_range(self):
        end=self.day+timedelta(days=7)
        r=apply_plan(self.employee.pk,self.plan(mode='weekly',end_date=end.isoformat(),weekdays=[self.day.weekday()]));self.assertEqual(r['days'],2)
        apply_plan(self.employee.pk,self.plan(mode='leave',end_date=end.isoformat()));self.assertEqual(available_slots(self.user,self.service.pk,self.employee.pk,self.day),[])
    def test_schedule_warns_affected_appointments_without_changes(self):
        a=book(self.user,self.service.pk,self.employee.pk,self.day,time(10));before=list(self.employee.schedules.values())
        with self.assertRaisesMessage(ValidationError,f'LH-{a.pk}'):
            apply_plan(self.employee.pk,self.plan(mode='leave'))
        self.assertEqual(list(self.employee.schedules.values()),before);a.refresh_from_db();self.assertEqual(a.status,'pending')
        apply_plan(self.employee.pk,self.plan());a.refresh_from_db();self.assertEqual(a.employee,self.employee)
    def test_invalid_schedule_and_permissions(self):
        for data in (self.plan(work=[['17:00','09:00']]),self.plan(breaks=[['08:00','09:30']]),self.plan(breaks=[['12:00','13:00'],['12:30','14:00']]),self.plan(mode='weekly',weekdays=[])):
            with self.assertRaises(ValidationError):apply_plan(self.employee.pk,data)
        self.client.force_login(self.user);self.assertEqual(self.client.post(f'/api/admin/employees/{self.employee.pk}/schedules/plan/',{'plan':json.dumps(self.plan())}).status_code,403)
    def test_account_lock_login_session_and_unlock(self):
        user_client=Client();user_client.force_login(self.user)
        path=f'/api/admin/accounts/{self.user.pk}/status/'
        self.assertEqual(self.client.post(path,{'action':'lock'}).status_code,200)
        self.assertEqual(user_client.get('/api/appointments/').status_code,401)
        self.assertFalse(Client().login(username=self.user.username,password='StrongPassword!765'))
        self.assertEqual(self.client.post(path,{'action':'unlock'}).status_code,200)
        self.assertTrue(Client().login(username=self.user.username,password='StrongPassword!765'))
        self.user.refresh_from_db();self.assertEqual(self.user.role,'User');self.assertTrue(Customer.objects.filter(user=self.user).exists())
    def test_admin_accounts_protected_and_role_permissions(self):
        second=User.objects.create_user('admin2','admin2@example.com','Strong!765',role='Admin')
        for user in (self.admin,second):self.assertEqual(self.client.post(f'/api/admin/accounts/{user.pk}/status/',{'action':'lock'}).status_code,403)
        self.client.force_login(self.user);self.assertEqual(self.client.get('/api/admin/accounts/').status_code,403)
    def test_account_search_filters_stats_pagination(self):
        data=self.client.get('/api/admin/accounts/',{'search':self.user.username,'role':'User','status':'active'}).json();self.assertEqual(len(data['items']),1);self.assertEqual(data['stats']['total'],3)
        self.assertEqual(data['items'][0]['id'],self.user.pk);self.assertNotIn('password',data['items'][0])
    def test_customers_exclude_admin_superuser_in_all_routes(self):
        User.objects.filter(pk=self.other.pk).update(role='Admin')
        data=self.client.get('/api/admin/customers/').json();self.assertEqual(data['total'],1);self.assertEqual(data['items'][0]['id'],self.customer.pk);self.assertIsNone(data['items'][0]['tier'])
        self.assertEqual(self.client.get(f'/api/admin/customers/{self.other_customer.pk}/').status_code,404)
        User.objects.filter(pk=self.other.pk).update(role='User',is_superuser=True)
        self.assertEqual(self.client.get('/api/admin/customers/',{'search':self.other.email}).json()['total'],0)
        self.assertEqual(self.client.get('/api/admin/customers/',{'tier':'Bạc'}).json()['total'],0)
    def test_profile_user_updates_and_admin_readonly(self):
        self.client.force_login(self.user)
        data={'name':'Tên mới','username':self.user.username,'email':self.user.email,'phone':'0901111222','skin':'Da khô','needs':['Chăm sóc da','Thư giãn'],'interests':['Nhẹ nhàng'],'budget':'500000'}
        r=self.client.post('/api/profile/',data);self.assertEqual(r.status_code,200,r.content)
        self.assertEqual(self.client.get('/api/profile/').json()['item']['needs'],data['needs'])
        self.customer.refresh_from_db();self.assertEqual(self.customer.full_name,'Tên mới')
        self.client.force_login(self.admin);self.assertEqual(self.client.get(f'/api/admin/customers/{self.customer.pk}/').json()['item']['budget'],'500000.00')
        self.assertEqual(self.client.post(f'/api/admin/customers/{self.customer.pk}/',data).status_code,405)
        self.assertEqual(self.client.post('/api/profile/',data).status_code,403)
    def test_promotion_backend_rules_aliases_and_manual_conditions(self):
        data=self.promotion_data();data['note']=''
        r=self.client.post('/api/admin/promotions/',data);self.assertEqual(r.status_code,201,r.content)
        p=Promotion.objects.get(pk=r.json()['item']['id']);self.assertEqual(evaluate_code('alt10',self.service)['discount'],Decimal('40000'))
        duplicate={**self.promotion_data(),'code':'ANOTHER','aliases':'ALT10'};self.assertEqual(self.client.post('/api/admin/promotions/',duplicate).status_code,400)
        p.conditions='Khách cần giấy xác nhận';p.save();result=evaluate_code(p.code,self.service);self.assertTrue(result['requiresManualReview']);self.assertFalse(result['eligible']);self.assertIsNone(result['discount'])
        p.conditions='';p.min_amount=600000;p.save()
        with self.assertRaises(ValidationError):evaluate_code(p.code,self.service)
        p.min_amount=None;p.is_active=False;p.save()
        with self.assertRaises(ValidationError):evaluate_code(p.code,self.service)
    def test_new_endpoints_csrf(self):
        c=Client(enforce_csrf_checks=True);c.force_login(self.admin)
        for path in (f'/api/admin/accounts/{self.user.pk}/status/',f'/api/admin/employees/{self.employee.pk}/schedules/plan/'):
            self.assertEqual(c.post(path,{}).status_code,403)
        c.force_login(self.user);self.assertEqual(c.post('/api/profile/',{}).status_code,403)
