from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Barrier
from datetime import time, timedelta
import json
from unittest.mock import Mock, patch

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, TransactionTestCase, Client, override_settings
from django.db import close_old_connections
from django.core.exceptions import ValidationError
from django.utils import timezone
from accounts.models import User, Customer
from services.models import ServiceCategory, Service
from products.models import CareProduct
from employees.models import Employee, EmployeeService, EmployeeSchedule
from promotions.models import Promotion
from appointments.models import Appointment
from appointments.services import book, transition
from billing.models import Invoice

class Fixtures:
    def seed(self):
        self.day=timezone.localdate()+timedelta(days=3)
        self.admin=User.objects.create_superuser("stage3admin","s3admin@example.com","StrongPassword!765")
        self.user=User.objects.create_user("stage3user","s3user@example.com","StrongPassword!765")
        self.customer=Customer.objects.create(user=self.user,full_name="Khách kiểm thử",phone="0900000000")
        self.other=User.objects.create_user("stage3other","s3other@example.com","StrongPassword!765")
        self.other_customer=Customer.objects.create(user=self.other,full_name="Khách khác",phone="0911111111")
        self.category=ServiceCategory.objects.create(name="Danh mục thật")
        self.service=Service.objects.create(category=self.category,name="Dịch vụ thật",description="Mô tả",price=500000,duration_minutes=60)
        self.employee=Employee.objects.create(full_name="Chuyên viên A",specialty="Chuyên môn")
        self.employee2=Employee.objects.create(full_name="Chuyên viên B",specialty="Chuyên môn")
        for person in (self.employee,self.employee2):
            EmployeeService.objects.create(employee=person,service=self.service)
            EmployeeSchedule.objects.create(employee=person,work_date=self.day,start_time=time(9),end_time=time(17))
    def booking_data(self,**kwargs):
        data={"service":self.service.pk,"employee":self.employee.pk,"date":self.day.isoformat(),"time":"10:00","note":"Ghi chú"};data.update(kwargs);return data

class Phase3Tests(Fixtures,TestCase):
    def setUp(self):self.seed()
    def login_admin(self):self.client.force_login(self.admin)
    def login_user(self):self.client.force_login(self.user)
    def test_admin_crud_all_four_modules_and_relations(self):
        self.login_admin()
        cases={"services":dict(name="DV mới",category=self.category.pk,description="Mô tả",price="450000",duration_minutes=45,is_active="on"),
          "products":dict(name="SP mới",product_type="Serum",description="Mô tả",services=[self.service.pk],is_active="on"),
          "employees":dict(full_name="Nhân viên mới",specialty="Spa",services=[self.service.pk],is_active="on"),
          "promotions":dict(name="Ưu đãi",code="REAL10",discount_type="percent",discount_value=10,start_date=timezone.localdate(),end_date=self.day,services=[self.service.pk],is_active="on")}
        for module,data in cases.items():
            with self.subTest(module=module):
                result=self.client.post(f"/api/admin/{module}/",data)
                self.assertEqual(result.status_code,201,result.content)
                pk=result.json()["item"]["id"]
                key="full_name" if module=="employees" else "name";data[key]="Đã sửa"
                self.assertEqual(self.client.post(f"/api/admin/{module}/{pk}/",data).status_code,200)
                self.assertEqual(self.client.get(f"/api/admin/{module}/{pk}/").status_code,200)
                self.assertEqual(self.client.post(f"/api/admin/{module}/{pk}/",{"_toggle":"1"}).json()["item"]["active"],False)
                self.assertEqual(self.client.delete(f"/api/admin/{module}/{pk}/").status_code,405)
        self.assertEqual(CareProduct.objects.get(name="Đã sửa").services.get(),self.service)
        self.assertEqual(Promotion.objects.get(code="REAL10").services.get(),self.service)

    def test_validation_and_admin_permission(self):
        self.assertEqual(self.client.get("/api/admin/services/").status_code,401)
        self.login_user()
        for module in ("categories","services","products","employees","promotions"):
            self.assertEqual(self.client.get(f"/api/admin/{module}/").status_code,403)
            self.assertEqual(self.client.post(f"/api/admin/{module}/",{}).status_code,403)
        self.login_admin()
        self.assertEqual(self.client.post("/api/admin/services/",dict(name="Sai",category=self.category.pk,description="M",price=-1,duration_minutes=0)).status_code,400)
        self.assertEqual(self.client.post("/api/admin/promotions/",dict(name="Sai",code="BAD",discount_type="percent",discount_value=101,start_date=self.day,end_date=timezone.localdate())).status_code,400)

    def test_csrf_mutations(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.admin)
        self.assertEqual(client.post("/api/admin/services/",{}).status_code,403)
        client.force_login(self.user)
        self.assertEqual(client.post("/api/appointments/book/",self.booking_data()).status_code,403)

    def test_catalog_real_active_and_category_hidden(self):
        response=self.client.get("/services.html")
        self.assertEqual(response.context["live_catalog"]["services"][0]["id"],self.service.pk)
        self.category.is_active=False;self.category.save()
        self.assertEqual(self.client.get("/services.html").context["live_catalog"]["services"],[])
        self.assertNotContains(self.client.get("/index.html"),"WELCOME10")

    def test_promotion_validity_and_relations(self):
        today=timezone.localdate()
        for code,start,end in (("VALID",today,self.day),("FUTURE",self.day,self.day),("EXPIRED",today-timedelta(days=3),today-timedelta(days=1))):
            Promotion.objects.create(code=code,name=code,discount_type="amount",discount_value=10000,start_date=start,end_date=end)
        self.assertEqual([p["code"] for p in self.client.get("/promotions.html").context["live_promotions"]["items"]],["VALID"])

    def test_public_catalog_relations_use_bounded_queries_and_filter_hidden_services(self):
        from .catalog_data import catalog, promotions
        hidden = Service.objects.create(category=self.category, name='Đã ẩn', description='Mô tả',
                                        price=300000, duration_minutes=30, is_active=False)
        EmployeeService.objects.create(employee=self.employee, service=hidden)
        promo = Promotion.objects.create(code='PUBLIC20', name='Ưu đãi', discount_type='percent',
                                         discount_value=20, start_date=timezone.localdate(), end_date=self.day)
        promo.services.add(self.service, hidden)
        product = CareProduct.objects.create(name='Sản phẩm', product_type='Chăm sóc', description='Mô tả')
        product.services.add(self.service)
        with self.assertNumQueries(5):
            data = catalog()
        self.assertEqual([person['serviceIds'] for person in data['staff']], [[self.service.pk]] * 2)
        with self.assertNumQueries(2):
            offer = promotions()['items'][0]
        self.assertEqual(offer['serviceIds'], [self.service.pk])

    @override_settings(PUBLIC_CATALOG_CACHE_SECONDS=45)
    def test_guest_pages_share_only_public_data_and_keep_csrf_private(self):
        key = f"frontend-public-catalog:{timezone.localdate().isoformat()}"
        cache.delete(key)
        self.addCleanup(cache.delete, key)
        Promotion.objects.create(code="CACHE20", name="Ưu đãi kiểm thử",
                                 discount_type="percent", discount_value=20,
                                 start_date=timezone.localdate(), end_date=self.day)
        with patch.object(cache, "set", wraps=cache.set) as store:
            home = self.client.get("/")
            self.assertIn('desc="miss"', home["Server-Timing"])
            self.assertEqual(store.call_args.args[2], 45)
        with self.assertNumQueries(0):
            offer_page = Client().get("/promotions.html")
        self.assertIn('desc="hit"', offer_page["Server-Timing"])
        self.assertIn("no-store", offer_page["Cache-Control"])
        cookie_name = settings.CSRF_COOKIE_NAME
        self.assertNotEqual(home.cookies[cookie_name].value, offer_page.cookies[cookie_name].value)
        self.assertNotIn("discountType", home.context["live_promotions"]["items"][0])
        self.assertEqual(offer_page.context["live_promotions"]["items"][0]["discountType"], "percent")

        self.category.is_active = False
        self.category.save()
        self.login_user()
        authenticated = self.client.get("/services.html")
        self.assertNotIn("Server-Timing", authenticated)
        self.assertEqual(authenticated.context["live_catalog"]["services"], [])
        self.assertEqual(self.client.get("/")["Location"], "/home.html")

    @override_settings(PUBLIC_CATALOG_CACHE_SECONDS=45)
    def test_snapshot_does_not_keep_yesterdays_offers(self):
        today = timezone.localdate()
        tomorrow = today + timedelta(days=1)
        for day in (today, tomorrow):
            key = f"frontend-public-catalog:{day.isoformat()}"
            cache.delete(key)
            self.addCleanup(cache.delete, key)
        Promotion.objects.create(code="ONEDAY", name="Ưu đãi trong ngày",
                                 discount_type="percent", discount_value=20,
                                 start_date=today, end_date=today)
        self.assertContains(self.client.get("/promotions.html"), "ONEDAY")
        with patch("core.catalog_data.timezone.localdate", return_value=tomorrow):
            page = self.client.get("/promotions.html")
        self.assertIn('desc="miss"', page["Server-Timing"])
        self.assertNotContains(page, "ONEDAY")

    @override_settings(PUBLIC_CATALOG_CACHE_SECONDS=45, PUBLIC_CATALOG_BLOB_ENABLED=True)
    def test_shared_catalog_serves_guest_without_mysql_after_local_cache_eviction(self):
        from .catalog_blob import _build, PATH

        today = timezone.localdate()
        tomorrow = today + timedelta(days=1)
        for code, day in (("TODAY", today), ("TOMORROW", tomorrow)):
            Promotion.objects.create(code=code, name=code, discount_type="percent",
                                     discount_value=20, start_date=day, end_date=day)
        snapshot = _build()
        self.assertEqual({item["code"] for item in snapshot[1]["items"]}, {"TODAY", "TOMORROW"})

        @contextmanager
        def stream(path, *, access):
            self.assertEqual((path, access), (PATH, "private"))
            yield iter([json.dumps(snapshot).encode()])

        for page, day, expected in (("/", today, "TODAY"), ("/promotions.html", today, "TODAY"),
                                    ("/service-detail.html?id=1", tomorrow, "TOMORROW")):
            key = f"frontend-public-catalog:{day.isoformat()}"
            cache.delete(key)
            self.addCleanup(cache.delete, key)
            with patch("core.catalog_blob.blob_sdk", return_value=Mock(stream_blob=stream)), \
                    patch("core.catalog_data.timezone.localdate", return_value=day), self.assertNumQueries(0):
                response = Client().get(page)
            self.assertEqual(response.status_code, 200)
            self.assertIn('public-catalog-source;desc="blob"', response["Server-Timing"])
            self.assertEqual([p["code"] for p in response.context["live_promotions"]["items"]], [expected])
            self.assertNotIn("email", response.context["live_catalog"]["staff"][0])

    @override_settings(PUBLIC_CATALOG_BLOB_ENABLED=True)
    def test_shared_catalog_initializes_only_missing_objects_and_publishes_on_admin_save(self):
        from .catalog_blob import load_or_initialize, PATH

        class MissingBlob(Exception):
            pass

        sdk = Mock(BlobNotFoundError=MissingBlob)
        sdk.stream_blob.side_effect = MissingBlob
        with patch("core.catalog_blob.blob_sdk", return_value=sdk):
            data, _, source = load_or_initialize()
        self.assertEqual(source, "mysql")
        self.assertEqual(data["services"][0]["id"], self.service.pk)
        self.assertEqual(sdk.put_blob.call_args.args[0], PATH)
        self.assertEqual(sdk.put_blob.call_args.kwargs["access"], "private")
        self.assertFalse(sdk.put_blob.call_args.kwargs["allow_overwrite"])

        self.login_admin()
        with patch("core.catalog_blob._publish") as publish, self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(f"/api/admin/services/{self.service.pk}/", {"_toggle": "1"})
            self.assertEqual(response.status_code, 200)
            publish.assert_not_called()
        publish.assert_called_once_with()

    def test_schedule_crud_and_overlap(self):
        self.login_admin();path=f"/api/admin/employees/{self.employee.pk}/schedules/"
        self.assertEqual(self.client.get(path+"0/").status_code,200)
        self.assertEqual(self.client.post(path+"0/",dict(work_date=self.day,start_time="10:00",end_time="12:00",status="working")).status_code,400)
        nextday=self.day+timedelta(days=1)
        self.assertEqual(self.client.post(path+"0/",dict(work_date=nextday,start_time="09:00",end_time="17:00",status="working")).status_code,201)
        appointment=book(self.user,self.service.pk,self.employee.pk,self.day,time(10))
        shift=self.employee.schedules.get(work_date=self.day)
        self.assertEqual(self.client.post(path+str(shift.pk)+"/",dict(work_date=self.day,start_time="11:00",end_time="17:00",status="working")).status_code,400)

    def test_booking_requires_employee_and_valid_slots(self):
        self.login_user()
        self.assertEqual(self.client.post("/api/appointments/book/",self.booking_data(employee="")).status_code,400)
        self.assertEqual(self.client.get("/api/appointments/available-slots/",{"service":self.service.pk,"date":self.day}).status_code,400)
        result=self.client.get("/api/appointments/available-slots/",{"service":self.service.pk,"employee":self.employee.pk,"date":self.day})
        self.assertIn("16:00",result.json()["slots"]);self.assertNotIn("16:01",result.json()["slots"])
        result=self.client.post("/api/appointments/book/",self.booking_data())
        self.assertEqual(result.status_code,201,result.content)
        item=Appointment.objects.get();self.assertEqual(item.employee,self.employee);self.assertEqual(item.end_time,time(11))
        self.assertEqual(item.customer,self.customer)
        self.assertEqual(self.client.post("/api/appointments/book/",self.booking_data(time="10:30")).status_code,400)
        self.assertEqual(self.client.post("/api/appointments/book/",self.booking_data(employee=self.employee2.pk,time="10:30")).status_code,400)
        self.assertEqual(self.client.post("/api/appointments/book/",self.booking_data(time="11:00")).status_code,201)

    def test_past_unassigned_inactive_and_duration_rejected(self):
        self.login_user()
        self.assertEqual(self.client.post("/api/appointments/book/",self.booking_data(date=timezone.localdate()-timedelta(days=1))).status_code,400)
        self.assertEqual(self.client.post("/api/appointments/book/",self.booking_data(time="16:30")).status_code,400)
        EmployeeService.objects.filter(employee=self.employee,service=self.service).delete()
        self.assertEqual(self.client.post("/api/appointments/book/",self.booking_data()).status_code,400)
        self.employee2.is_active=False;self.employee2.save()
        self.assertEqual(self.client.post("/api/appointments/book/",self.booking_data(employee=self.employee2.pk)).status_code,400)

    def test_user_scope_and_cancel_invoice(self):
        item=book(self.user,self.service.pk,self.employee.pk,self.day,time(10))
        transition(self.admin,item.pk,"confirmed")
        item.refresh_from_db();invoice=Invoice.objects.get(appointment=item)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get("/api/appointments/").json()["items"],[])
        self.assertEqual(self.client.post(f"/api/appointments/{item.pk}/status/",{"status":"cancelled"}).status_code,403)
        self.login_user()
        self.assertEqual(self.client.post(f"/api/appointments/{item.pk}/status/",{"status":"cancelled"}).status_code,200)
        invoice.refresh_from_db();self.assertEqual(invoice.payment_status,"cancelled")
        self.assertEqual(self.client.post("/api/appointments/book/",self.booking_data()).status_code,201)

    def test_admin_confirmation_keeps_employee_terminal_and_time_rules(self):
        item=book(self.user,self.service.pk,self.employee.pk,self.day,time(10))
        self.login_admin();path=f"/api/appointments/{item.pk}/status/"
        self.assertEqual(self.client.post(path,{"status":"completed"}).status_code,400)
        self.assertEqual(self.client.post(path,{"status":"confirmed"}).status_code,200)
        item.refresh_from_db();self.assertEqual(item.employee,self.employee)
        self.assertEqual(self.client.post(path,{"status":"completed"}).status_code,400)
        self.assertEqual(self.client.post(path,{"status":"cancelled","reason":"Khách đề nghị hủy"}).status_code,200)
        self.assertEqual(self.client.post(path,{"status":"confirmed"}).status_code,400)

    def test_reassignment_requires_consent_checks_conflict_and_records_notice(self):
        item=book(self.user,self.service.pk,self.employee.pk,self.day,time(10))
        self.login_admin();path=f"/api/appointments/{item.pk}/status/"
        data={"status":"confirmed","employee":self.employee2.pk,"reason":"Khách đồng ý thay thế"}
        self.assertEqual(self.client.post(path,data).status_code,400)
        data.update(consent="on", expected_employee=item.employee_id, expected_updated_at=item.updated_at.isoformat(),
                    consent_method="phone", consent_note="Đã thông báo và khách đồng ý", consent_at=timezone.now().isoformat())
        self.assertEqual(self.client.post(path,data).status_code,200)
        item.refresh_from_db();self.assertEqual(item.employee,self.employee2);self.assertEqual(item.reassignments.get().previous_employee_id,self.employee.pk)
        data.update(expected_employee=item.employee_id, expected_updated_at=item.updated_at.isoformat())
        second=book(self.other,self.service.pk,self.employee.pk,self.day,time(10))
        self.assertEqual(self.client.post(path,{**data,"employee":self.employee.pk}).status_code,400)

    def test_paid_cancellation_rejected(self):
        item=book(self.user,self.service.pk,self.employee.pk,self.day,time(10));transition(self.admin,item.pk,"confirmed");item.refresh_from_db()
        invoice=Invoice.objects.get(appointment=item);invoice.payment_status="paid";invoice.save()
        self.login_user();self.assertEqual(self.client.post(f"/api/appointments/{item.pk}/status/",{"status":"cancelled"}).status_code,400)

    def test_admin_filters(self):
        item=book(self.user,self.service.pk,self.employee.pk,self.day,time(10));self.login_admin()
        self.assertEqual(len(self.client.get("/api/appointments/",{"employee":self.employee.pk,"date":self.day,"status":"pending"}).json()["items"]),1)
        self.assertEqual(self.client.get("/api/appointments/",{"employee":self.employee2.pk}).json()["items"],[])

    def test_completion_after_end_and_terminal_immutability(self):
        item=book(self.user,self.service.pk,self.employee.pk,self.day,time(10))
        transition(self.admin,item.pk,"confirmed")
        Appointment.objects.filter(pk=item.pk).update(appointment_date=timezone.localdate()-timedelta(days=1))
        self.login_admin();path=f"/api/appointments/{item.pk}/status/"
        self.assertEqual(self.client.post(path,{"status":"completed"}).status_code,200)
        item.refresh_from_db();self.assertEqual(item.status,"completed")
        self.assertEqual(self.client.post(path,{"status":"cancelled"}).status_code,400)

    def test_assignment_removal_and_inactive_records_preserve_appointments(self):
        item=book(self.user,self.service.pk,self.employee.pk,self.day,time(10))
        self.login_admin()
        self.assertEqual(self.client.post(f"/api/admin/employees/{self.employee.pk}/",{
            "full_name":self.employee.full_name,"specialty":"Spa","is_active":"on","services":[]}).status_code,400)
        self.assertEqual(self.client.post(f"/api/admin/services/{self.service.pk}/",{"_toggle":"1"}).status_code,200)
        item.refresh_from_db();self.assertEqual(item.service_id,self.service.pk)
        self.login_user()
        self.assertEqual(self.client.post("/api/appointments/book/",self.booking_data(time="12:00")).status_code,400)

class ConcurrentBookingTests(Fixtures,TransactionTestCase):
    def setUp(self):self.seed()
    def test_two_simultaneous_requests_only_one_succeeds(self):
        barrier=Barrier(2)
        def attempt(user_id):
            close_old_connections()
            try:
                user=User.objects.get(pk=user_id);barrier.wait(timeout=10)
                book(user,self.service.pk,self.employee.pk,self.day,time(10));return "saved"
            except ValidationError:return "conflict"
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(attempt,[self.user.pk,self.other.pk]))
        self.assertCountEqual(results,["saved","conflict"])
        self.assertEqual(Appointment.objects.count(),1)

    def test_same_customer_parallel_different_services_and_employees(self):
        second_service=Service.objects.create(category=self.category,name="Dịch vụ thứ hai",description="Mô tả",price=400000,duration_minutes=60)
        EmployeeService.objects.create(employee=self.employee2,service=second_service)
        barrier=Barrier(2)
        def attempt(pair):
            close_old_connections()
            try:
                user=User.objects.get(pk=self.user.pk);barrier.wait(timeout=10)
                book(user,pair[0],pair[1],self.day,time(10));return "saved"
            except ValidationError:return "conflict"
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(attempt,[(self.service.pk,self.employee.pk),(second_service.pk,self.employee2.pk)]))
        self.assertCountEqual(results,["saved","conflict"])
        self.assertEqual(Appointment.objects.count(),1)
