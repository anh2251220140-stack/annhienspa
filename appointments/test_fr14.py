"""Run only in an explicitly approved isolated test database; never against production."""
from datetime import time, timedelta
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.test import TestCase, TransactionTestCase
from django.db import close_old_connections
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from core.test_phase3 import Fixtures
from accounts.models import User
from employees.models import EmployeeService, EmployeeSchedule
from billing.models import Invoice
from appointments.models import Appointment, AppointmentReassignment
from appointments.services import book, transition, start_datetime


class FR14Tests(Fixtures, TestCase):
    def setUp(self):
        self.seed()
        self.a = book(self.user, self.service.pk, self.employee.pk, self.day, time(10), note="Legacy note")

    def consent(self):
        return dict(employee_id=self.employee2.pk, consent=True, reason="Chuyên viên không thể phục vụ",
                    expected_employee=self.a.employee_id, expected_updated_at=self.a.updated_at,
                    consent_method="phone", consent_note="Đã thông báo, khách đồng ý",
                    consent_at=timezone.now())

    def test_user_cancel_audit_and_repeated_request(self):
        transition(self.user, self.a.pk, "cancelled")
        self.a.refresh_from_db()
        self.assertEqual(self.a.cancelled_by_id, self.user.pk)
        self.assertEqual(self.a.cancel_reason, "Khách hàng tự hủy")
        timestamp = self.a.cancelled_at
        with self.assertRaises(ValidationError):
            transition(self.admin, self.a.pk, "cancelled", reason="Repeat")
        self.a.refresh_from_db()
        self.assertEqual(self.a.cancelled_at, timestamp)
        self.assertEqual(self.a.note, "Legacy note")

    def test_admin_reason_and_ownership(self):
        with self.assertRaises(ValidationError): transition(self.admin, self.a.pk, "cancelled")
        with self.assertRaises(PermissionDenied): transition(self.other, self.a.pk, "cancelled")
        transition(self.admin, self.a.pk, "cancelled", reason="Khách yêu cầu")
        self.a.refresh_from_db()
        self.assertEqual(self.a.cancelled_by_id, self.admin.pk)

    def test_no_show_strictly_after_start_confirmed_only(self):
        start = start_datetime(self.day, time(10))
        with patch("appointments.services.timezone.now", return_value=start + timedelta(seconds=1)):
            with self.assertRaises(ValidationError): transition(self.admin, self.a.pk, "cancelled", no_show=True)
        transition(self.admin, self.a.pk, "confirmed")
        for now in (start - timedelta(seconds=1), start):
            with patch("appointments.services.timezone.now", return_value=now):
                with self.assertRaises(ValidationError): transition(self.admin, self.a.pk, "cancelled", reason="Khách không đến")
        with patch("appointments.services.timezone.now", return_value=start + timedelta(seconds=1)):
            transition(self.admin, self.a.pk, "cancelled", no_show=True)
        self.a.refresh_from_db()
        self.assertEqual(self.a.cancel_reason, "Khách không đến")
        self.assertEqual(Invoice.objects.get(appointment=self.a).payment_status, "cancelled")

    def test_paid_no_show_remains_unchanged(self):
        transition(self.admin, self.a.pk, "confirmed")
        invoice = Invoice.objects.get(appointment=self.a)
        invoice.payment_status = "paid"; invoice.save()
        with patch("appointments.services.timezone.now", return_value=start_datetime(self.day,time(11))):
            with self.assertRaises(ValidationError): transition(self.admin,self.a.pk,"cancelled",no_show=True)
        self.a.refresh_from_db(); invoice.refresh_from_db()
        self.assertEqual(self.a.status,"confirmed")
        self.assertIsNone(self.a.cancelled_at)
        self.assertEqual(invoice.payment_status,"paid")

    def test_history_atomic_unchanged_note_and_duplicate(self):
        args = self.consent()
        transition(self.admin,self.a.pk,"pending",**args)
        self.a.refresh_from_db()
        h = self.a.reassignments.get()
        self.assertEqual((h.previous_employee_id,h.new_employee_id,h.changed_by_id),
                         (self.employee.pk,self.employee2.pk,self.admin.pk))
        self.assertTrue(h.customer_consent)
        self.assertEqual(self.a.note,"Legacy note")
        with self.assertRaises(ValidationError): transition(self.admin,self.a.pk,"pending",**args)
        self.assertEqual(self.a.reassignments.count(),1)
        h.reason="Overwrite"
        with self.assertRaises(ValidationError): h.save()

    def test_reassignment_chain_and_aba_stale_request(self):
        initial=self.consent()
        transition(self.admin,self.a.pk,'pending',**initial)
        self.a.refresh_from_db()
        back=self.consent();back['employee_id']=self.employee.pk
        transition(self.admin,self.a.pk,'pending',**back)
        self.a.refresh_from_db()
        self.assertEqual(list(self.a.reassignments.values_list('previous_employee_id','new_employee_id')),
                         [(self.employee.pk,self.employee2.pk),(self.employee2.pk,self.employee.pk)])
        with self.assertRaises(ValidationError): transition(self.admin,self.a.pk,'pending',**initial)
        self.assertEqual(self.a.reassignments.count(),2)

    def test_history_failure_rolls_back_employee(self):
        with patch.object(AppointmentReassignment,"save",side_effect=RuntimeError("audit failure")):
            with self.assertRaises(RuntimeError): transition(self.admin,self.a.pk,"pending",**self.consent())
        self.a.refresh_from_db()
        self.assertEqual(self.a.employee_id,self.employee.pk)
        self.assertFalse(self.a.reassignments.exists())

    def test_missing_consent_and_stale_version(self):
        for invalid in (dict(consent=False),dict(reason=""),dict(consent_method=""),dict(consent_note=""),
                        dict(consent_at=None),dict(consent_at=timezone.now()+timedelta(days=1)),
                        dict(expected_updated_at=None),dict(expected_employee=self.employee2.pk)):
            with self.subTest(invalid=invalid):
                args=self.consent();args.update(invalid)
                with self.assertRaises(ValidationError): transition(self.admin,self.a.pk,"pending",**args)
        self.assertFalse(self.a.reassignments.exists())

    def test_reassignment_requires_specialty_shift_and_no_conflict(self):
        EmployeeService.objects.filter(employee=self.employee2).delete()
        with self.assertRaises(ValidationError): transition(self.admin,self.a.pk,"pending",**self.consent())
        EmployeeService.objects.create(employee=self.employee2,service=self.service)
        EmployeeSchedule.objects.filter(employee=self.employee2).update(status="off")
        with self.assertRaises(ValidationError): transition(self.admin,self.a.pk,"pending",**self.consent())
        EmployeeSchedule.objects.filter(employee=self.employee2).update(status="working")
        book(self.other,self.service.pk,self.employee2.pk,self.day,time(10))
        with self.assertRaises(ValidationError): transition(self.admin,self.a.pk,"pending",**self.consent())
        self.assertFalse(self.a.reassignments.exists())

    def test_reassignment_time_terminal_and_user_permissions(self):
        with self.assertRaises(PermissionDenied): transition(self.user,self.a.pk,"pending",**self.consent())
        args=self.consent()
        with patch("appointments.services.timezone.now",return_value=start_datetime(self.day,time(10))):
            with self.assertRaises(ValidationError): transition(self.admin,self.a.pk,"pending",**args)
        transition(self.user,self.a.pk,"cancelled")
        with self.assertRaises(ValidationError): transition(self.admin,self.a.pk,"pending",**args)

    def test_api_new_fields_and_no_internal_audit_in_user_response(self):
        self.client.force_login(self.admin)
        args=self.consent();args['employee']=args.pop('employee_id');args['status']='pending'
        args['expected_updated_at']=args['expected_updated_at'].isoformat()
        args['consent_at']=args['consent_at'].isoformat()
        response=self.client.post(f"/api/appointments/{self.a.pk}/status/",args)
        self.assertEqual(response.status_code,200,response.content)
        self.assertIn('updatedAt',response.json()['item'])
        self.client.force_login(self.user)
        row=self.client.get('/api/appointments/').json()['items'][0]
        self.assertNotIn('consent_note',row)
        self.assertNotIn('reassignments',row)

    def test_unresolved_payment_prevents_cancel_audit(self):
        transition(self.admin,self.a.pk,'confirmed')
        with patch('billing.services.stop_pending',side_effect=ValidationError('Unresolved')):
            with self.assertRaises(ValidationError): transition(self.admin,self.a.pk,'cancelled',reason='Khách yêu cầu')
        self.a.refresh_from_db()
        self.assertEqual(self.a.status,'confirmed')
        self.assertIsNone(self.a.cancelled_at)

    def test_admin_detail_permissions_and_readonly(self):
        url=f'/api/appointments/{self.a.pk}/admin-detail/'
        self.assertEqual(self.client.get(url).status_code,401)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(url).status_code,403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(url).status_code,200)
        self.assertEqual(self.client.post(url,{}).status_code,405)
        self.assertEqual(self.client.get('/api/appointments/999999/admin-detail/').status_code,404)
        self.assertFalse(self.a.reassignments.exists())

    def test_admin_detail_audit_and_cancellation(self):
        transition(self.admin,self.a.pk,'pending',**self.consent())
        transition(self.admin,self.a.pk,'cancelled',reason='Khách yêu cầu')
        self.client.force_login(self.admin)
        data=self.client.get(f'/api/appointments/{self.a.pk}/admin-detail/').json()
        self.assertEqual(data['item']['cancelledBy'],self.admin.username)
        self.assertEqual(data['item']['cancelReason'],'Khách yêu cầu')
        self.assertEqual(len(data['history']),1)
        self.assertEqual(data['history'][0]['consentMethod'],'Điện thoại')
        self.assertFalse(data['item']['canReassign'])
        self.assertFalse(data['item']['canCancel'])

    def test_admin_detail_action_boundaries(self):
        transition(self.admin,self.a.pk,'confirmed')
        self.client.force_login(self.admin)
        url=f'/api/appointments/{self.a.pk}/admin-detail/'
        start=start_datetime(self.day,time(10))
        with patch('appointments.views.timezone.now',return_value=start):
            row=self.client.get(url).json()['item']
            self.assertFalse(row['canNoShow']);self.assertFalse(row['canReassign'])
        with patch('appointments.views.timezone.now',return_value=start+timedelta(seconds=1)):
            self.assertTrue(self.client.get(url).json()['item']['canNoShow'])
        invoice=Invoice.objects.get(appointment=self.a);invoice.payment_status='paid';invoice.save()
        with patch('appointments.views.timezone.now',return_value=start+timedelta(seconds=1)):
            row=self.client.get(url).json()['item']
            self.assertFalse(row['canNoShow']);self.assertFalse(row['canCancel'])

    def test_admin_form_missing_fields_and_stale_request(self):
        self.client.force_login(self.admin)
        url=f'/api/appointments/{self.a.pk}/status/'
        args=self.consent();args['employee']=args.pop('employee_id');args['status']='pending'
        args['expected_updated_at']=args['expected_updated_at'].isoformat()
        args['consent_at']=args['consent_at'].isoformat()
        invalid=dict(args);invalid['consent_method']=''
        self.assertEqual(self.client.post(url,invalid).status_code,400)
        self.assertEqual(self.client.post(url,args).status_code,200)
        self.assertEqual(self.client.post(url,args).status_code,400)
        self.assertEqual(self.a.reassignments.count(),1)


class FR14ConcurrentTests(Fixtures, TransactionTestCase):
    def setUp(self): self.seed()

    def test_duplicate_concurrent_reassignment_creates_one_history(self):
        a=book(self.user,self.service.pk,self.employee.pk,self.day,time(10))
        barrier=Barrier(2)
        def attempt(_):
            close_old_connections()
            try:
                admin=User.objects.get(pk=self.admin.pk)
                barrier.wait(timeout=10)
                transition(admin,a.pk,'pending',employee_id=self.employee2.pk,consent=True,reason='Ngoại lệ',
                           expected_employee=a.employee_id,expected_updated_at=a.updated_at,
                           consent_method='phone',consent_note='Khách đồng ý',consent_at=timezone.now())
                return 'saved'
            except ValidationError: return 'stale'
            finally: close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(attempt,range(2)))
        self.assertCountEqual(results,['saved','stale'])
        self.assertEqual(AppointmentReassignment.objects.filter(appointment=a).count(),1)
