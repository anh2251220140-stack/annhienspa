"""Real MySQL transaction races; run only after explicit isolated-test cleanup consent.
Unexpected database errors are NOT treated as a valid business conflict.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import time
from threading import Barrier

from django.core.exceptions import ValidationError
from django.db import close_old_connections
from django.test import Client, TransactionTestCase

from accounts.models import User
from appointments.models import Appointment
from appointments.services import book
from employees.models import Employee, EmployeeService, EmployeeSchedule
from employees.scheduling import apply_plan
from core import test_admin_remaining_regression as helpers


class EmployeeConcurrentRegressionTests(helpers.IsolatedAdminFixtures, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.b = self.second_service()
        self.employee.services.add(self.b)

    def race(self, operations):
        barrier = Barrier(len(operations))
        def attempt(operation):
            close_old_connections()
            try:
                barrier.wait(timeout=15)
                if operation == 'book':
                    book(User.objects.get(pk=self.user.pk), self.service.pk, self.employee.pk, self.day, time(10))
                elif operation == 'leave':
                    apply_plan(self.employee.pk, self.plan(mode='leave'))
                else:
                    client = Client(); client.force_login(User.objects.get(pk=self.admin.pk))
                    result = client.post(f'/api/admin/employees/{self.employee.pk}/',
                                         self.employee_data([self.b.pk], full_name='Reassigned service set'))
                    if result.status_code == 400:
                        self.assertIn('Không bỏ phân công dịch vụ', result.json()['error'])
                        return operation, 'conflict'
                    if result.status_code != 200:
                        raise AssertionError(f'Unexpected assignment response: {result.status_code}: {result.content!r}')
                return operation, 'saved'
            except ValidationError as error:
                message = ' '.join(error.messages)
                allowed = ('ảnh hưởng',) if operation == 'leave' else (
                    'Nhân viên chưa được phân công dịch vụ', 'Khung giờ phải nằm trong ca làm việc', 'Khung giờ trùng ca nghỉ')
                self.assertTrue(any(text in message for text in allowed), message)
                return operation, 'conflict'
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=len(operations)) as pool:
            futures = [pool.submit(attempt, op) for op in operations]
            return dict(future.result(timeout=40) for future in futures)

    def assert_consistent_final_state(self, results, before_shifts):
        appointments = Appointment.objects.filter(employee=self.employee, appointment_date=self.day)
        links = set(EmployeeService.objects.filter(employee=self.employee).values_list('service_id', flat=True))
        self.employee.refresh_from_db()
        if results['book'] == 'saved':
            self.assertEqual(appointments.count(), 1)
            self.assertEqual(appointments.get().status, 'pending')
            self.assertIn(self.service.pk, links)
            self.assertTrue(EmployeeSchedule.objects.filter(employee=self.employee, is_active=True, work_date=self.day,
                            status='working', start_time__lte=time(10), end_time__gte=time(11)).exists())
            if 'leave' in results: self.assertEqual(results['leave'], 'conflict')
            if 'unassign' in results:
                self.assertEqual(results['unassign'], 'conflict')
                self.assertNotEqual(self.employee.full_name, 'Reassigned service set')
        else:
            self.assertEqual(appointments.count(), 0)
            self.assertTrue(any(v == 'saved' for k, v in results.items() if k != 'book'))
        if results.get('leave') == 'conflict':
            self.assertEqual(self.shifts(), before_shifts)
        elif results.get('leave') == 'saved':
            self.assertFalse(EmployeeSchedule.objects.filter(employee=self.employee, work_date=self.day, is_active=True, status='working').exists())
        if results.get('unassign') == 'saved':
            self.assertSetEqual(links, {self.b.pk})
            self.assertEqual(self.employee.full_name, 'Reassigned service set')
        elif results.get('unassign') == 'conflict':
            self.assertSetEqual(links, {self.service.pk, self.b.pk})
        self.assertEqual(EmployeeService.objects.filter(employee=self.employee).count(), len(links))

    def test_booking_against_day_off_serializes_without_partial_shift_updates(self):
        before = self.shifts()
        results = self.race(['book', 'leave'])
        self.assertCountEqual(results.values(), ['saved', 'conflict'])
        self.assert_consistent_final_state(results, before)

    def test_booking_against_service_unassignment_preserves_valid_assignment(self):
        before = self.shifts()
        results = self.race(['book', 'unassign'])
        self.assertCountEqual(results.values(), ['saved', 'conflict'])
        self.assert_consistent_final_state(results, before)

    def test_booking_day_off_and_unassignment_three_way_race(self):
        before = self.shifts()
        results = self.race(['book', 'leave', 'unassign'])
        # Two administrative edits may both succeed if booking is rejected.
        self.assert_consistent_final_state(results, before)
