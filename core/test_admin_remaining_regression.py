"""Missing Admin regressions. Execute only with the guarded isolated FR-14 runner.
No test in this module has permission to run on the default production settings.
"""
import json
from contextlib import ExitStack
from datetime import datetime, time, timedelta, timezone as dt_timezone
from decimal import Decimal
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.test import Client, TestCase
from django.utils import timezone

from accounts.models import User, Customer
from appointments.models import Appointment
from appointments.services import book, transition, available_slots
from billing.models import Invoice, Payment
from core.test_phase3 import Fixtures
from employees.models import Employee, EmployeeService, EmployeeSchedule
from employees.scheduling import apply_plan
from services.models import Service, ServiceCategory


class IsolatedAdminFixtures(Fixtures):
    @classmethod
    def setUpClass(cls):
        db = settings.DATABASES['default']
        expected = dict(NAME='annhien_spa_fr14_tests', USER='annhien_fr14_tests', HOST='127.0.0.1', PORT='3306')
        if (db.get('ENGINE') != 'django.db.backends.mysql' or
                any(str(db.get(k)) != v for k, v in expected.items()) or
                db.get('TEST', {}).get('NAME') != expected['NAME']):
            raise ImproperlyConfigured('Use the guarded isolated FR-14 runner only.')
        super().setUpClass()

    def setUp(self):
        super().setUp()
        stack = self.enterContext(ExitStack())
        for name in ('create', 'get', 'cancel'):
            stack.enter_context(patch('billing.gateway.' + name, side_effect=AssertionError('External payOS forbidden')))
        self.seed()
        self.client.force_login(self.admin)

    def second_service(self, name='Service B'):
        return Service.objects.create(category=self.category, name=name, description='Test', price=400000, duration_minutes=30)

    def employee_data(self, services, **changes):
        data = dict(full_name=self.employee.full_name, specialty=self.employee.specialty,
                    email=self.employee.email, phone=self.employee.phone or '', services=list(services))
        data.update(changes)
        return data

    def plan(self, **changes):
        data = dict(mode='day', start_date=self.day.isoformat(), end_date=self.day.isoformat(),
                    work=[['09:00', '17:00']], breaks=[], note='Test plan')
        data.update(changes)
        return data

    def post_plan(self, data):
        return self.client.post(f'/api/admin/employees/{self.employee.pk}/schedules/plan/', {'plan': json.dumps(data)})

    def shifts(self):
        return list(EmployeeSchedule.objects.filter(employee=self.employee).order_by('pk').values())

    def assert_employee_services(self, ids):
        self.employee.refresh_from_db()
        self.assertSetEqual(set(self.employee.services.values_list('pk', flat=True)), set(ids))
        self.assertEqual(EmployeeService.objects.filter(employee=self.employee).count(), len(set(ids)))
        item = next(x for x in self.client.get('/api/admin/employees/').json()['items'] if x['id'] == self.employee.pk)
        self.assertSetEqual(set(item['serviceIds']), set(ids))


class EmployeeMissingRegressionTests(IsolatedAdminFixtures, TestCase):
    def test_multiple_services_http_create_read_and_preselect(self):
        from html.parser import HTMLParser
        b = self.second_service()
        response = self.client.post('/api/admin/employees/', dict(full_name='Multi staff', specialty='Spa', services=[self.service.pk, b.pk]))
        self.assertEqual(response.status_code, 201, response.content)
        employee = Employee.objects.get(pk=response.json()['item']['id'])
        self.assertSetEqual(set(employee.services.values_list('pk', flat=True)), {self.service.pk, b.pk})
        class Selected(HTMLParser):
            def __init__(self): super().__init__(); self.ids = set()
            def handle_starttag(self, tag, attrs):
                a = dict(attrs)
                if tag == 'input' and a.get('name') == 'services' and 'checked' in a: self.ids.add(int(a['value']))
        selected = Selected(); selected.feed(self.client.get(f'/api/admin/employees/{employee.pk}/').json()['html'])
        self.assertSetEqual(selected.ids, {self.service.pk, b.pk})

    def test_reassign_service_set_and_remove_all_without_live_appointments(self):
        b, c = self.second_service(), self.second_service('Service C')
        path = f'/api/admin/employees/{self.employee.pk}/'
        for ids in ([self.service.pk, b.pk], [b.pk, c.pk], []):
            r = self.client.post(path, self.employee_data(ids))
            self.assertEqual(r.status_code, 200, r.content); self.assert_employee_services(ids)

    def test_pending_and_confirmed_appointments_block_partial_assignment_edit(self):
        b = self.second_service(); self.employee.services.add(b)
        appointment = book(self.user, self.service.pk, self.employee.pk, self.day, time(10))
        for status in ('pending', 'confirmed'):
            with self.subTest(status=status):
                if status == 'confirmed': transition(self.admin, appointment.pk, status)
                before = Employee.objects.filter(pk=self.employee.pk).values().get()
                links = list(EmployeeService.objects.filter(employee=self.employee).order_by('pk').values())
                r = self.client.post(f'/api/admin/employees/{self.employee.pk}/', self.employee_data([b.pk], full_name='Must not persist'))
                self.assertEqual(r.status_code, 400, r.content)
                self.assertEqual(Employee.objects.filter(pk=self.employee.pk).values().get(), before)
                self.assertEqual(list(EmployeeService.objects.filter(employee=self.employee).order_by('pk').values()), links)
                appointment.refresh_from_db(); self.assertEqual(appointment.status, status)

    def test_invalid_service_does_not_partially_save_employee(self):
        b = self.second_service()
        missing = b.pk + 10000
        r = self.client.post(f'/api/admin/employees/{self.employee.pk}/', self.employee_data([b.pk, missing], full_name='Invalid edit'))
        self.assertEqual(r.status_code, 400); self.assertIn('services', r.json()['errors'])
        self.assert_employee_services([self.service.pk]); self.assertNotEqual(self.employee.full_name, 'Invalid edit')

    def test_adjacent_shifts_and_adjacent_appointments_are_allowed(self):
        r = self.post_plan(self.plan(work=[['09:00', '10:00'], ['10:00', '11:00']]))
        self.assertEqual(r.status_code, 200, r.content)
        first = book(self.user, self.service.pk, self.employee.pk, self.day, time(9))
        second = book(self.user, self.service.pk, self.employee.pk, self.day, time(10))
        self.assertEqual(first.end_time, second.start_time)
        self.assertEqual(self.employee.schedules.filter(is_active=True).count(), 2)

    def test_schedule_rejections_and_mid_insert_failure_roll_back_all_changes(self):
        before = self.shifts()
        for changes in (dict(work=[['09:00', '12:00'], ['11:00', '17:00']]),
                        dict(breaks=[['12:00', '13:00'], ['12:30', '14:00']]),
                        dict(breaks=[['08:00', '09:30']])):
            with self.subTest(changes=changes):
                r = self.post_plan(self.plan(**changes))
                self.assertEqual(r.status_code, 400, r.content); self.assertEqual(self.shifts(), before)

        # Failure after deactivation + first INSERT must roll back both operations.
        original_save = EmployeeSchedule.save
        inserts = []
        def fail_second_insert(instance, *args, **kwargs):
            if instance.employee_id == self.employee.pk and instance._state.adding:
                inserts.append(instance)
                if len(inserts) == 2: raise ValidationError('Injected second shift failure')
            return original_save(instance, *args, **kwargs)
        with patch.object(EmployeeSchedule, 'save', new=fail_second_insert):
            r = self.post_plan(self.plan(work=[['09:00', '12:00'], ['13:00', '17:00']]))
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(len(inserts), 2)
        self.assertEqual(self.shifts(), before)

    def test_break_boundaries_and_changed_day_preserve_history(self):
        self.service.duration_minutes = 30; self.service.save()
        old = self.employee.schedules.get()
        r = self.post_plan(self.plan(work=[['09:00', '12:00']], breaks=[['09:00', '09:15'], ['10:00', '10:15'], ['11:45', '12:00']]))
        self.assertEqual(r.status_code, 200, r.content)
        old.refresh_from_db(); self.assertFalse(old.is_active)
        slots = available_slots(self.user, self.service.pk, self.employee.pk, self.day)
        self.assertIn('09:30', slots); self.assertIn('10:15', slots); self.assertIn('11:15', slots)
        self.assertNotIn('09:00', slots); self.assertNotIn('09:45', slots); self.assertNotIn('11:30', slots)
        self.assertEqual(book(self.user, self.service.pk, self.employee.pk, self.day, time(9, 30)).end_time, time(10))

    def test_weekly_plan_only_selected_days_and_leave_only_requested_day(self):
        end = self.day + timedelta(days=8)
        r = self.post_plan(self.plan(mode='weekly', end_date=end.isoformat(), weekdays=[self.day.weekday()]))
        self.assertEqual(r.status_code, 200, r.content)
        expected = {self.day, self.day + timedelta(days=7)}
        self.assertSetEqual(set(self.employee.schedules.filter(is_active=True).values_list('work_date', flat=True)), expected)
        before_other = list(self.employee2.schedules.order_by('pk').values())
        r = self.post_plan(self.plan(mode='leave'))
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(available_slots(self.user, self.service.pk, self.employee.pk, self.day), [])
        self.assertTrue(self.employee.schedules.filter(is_active=True, work_date=self.day + timedelta(days=7), status='working').exists())
        self.assertEqual(list(self.employee2.schedules.order_by('pk').values()), before_other)

    def test_pending_and_confirmed_appointments_block_day_change_and_leave_atomically(self):
        appointment = book(self.user, self.service.pk, self.employee.pk, self.day, time(10))
        for status in ('pending', 'confirmed'):
            if status == 'confirmed': transition(self.admin, appointment.pk, status)
            for plan in (self.plan(work=[['13:00', '17:00']]), self.plan(mode='leave')):
                with self.subTest(status=status, plan=plan):
                    before = self.shifts()
                    r = self.post_plan(plan)
                    self.assertEqual(r.status_code, 400, r.content); self.assertIn(f'LH-{appointment.pk}', r.json()['error'])
                    self.assertEqual(self.shifts(), before)
                    appointment.refresh_from_db(); self.assertEqual(appointment.status, status)
                    self.assertEqual((appointment.start_time, appointment.end_time, appointment.employee_id), (time(10), time(11), self.employee.pk))

    def test_employee_and_schedule_endpoint_permission_csrf_matrix(self):
        paths = ['/api/admin/employees/', f'/api/admin/employees/{self.employee.pk}/',
                 f'/api/admin/employees/{self.employee.pk}/schedules/', f'/api/admin/employees/{self.employee.pk}/schedules/0/',
                 f'/api/admin/employees/{self.employee.pk}/schedules/plan/']
        before = self.shifts()
        anonymous, regular = Client(), Client(); regular.force_login(self.user)
        for path in paths:
            for client, expected in ((anonymous, 401), (regular, 403)):
                self.assertEqual(client.post(path, {}).status_code, expected)
            csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.admin)
            self.assertEqual(csrf.post(path, {}).status_code, 403)
        self.assertEqual(self.shifts(), before)


class PeopleMissingFixtures(IsolatedAdminFixtures):
    def setUp(self):
        super().setUp()
        self.audit_users = []
        for i in range(12):
            user = User.objects.create_user(f'audit{i:02}', f'audit{i:02}@example.invalid', 'TestOnly!765', is_active=i < 8)
            Customer.objects.create(user=user, full_name=f'Audit customer {i:02}', phone=f'09000000{i:02}')
            self.audit_users.append(user)

    def get_ok(self, path, **params):
        r = self.client.get(path, params); self.assertEqual(r.status_code, 200, r.content); return r.json()


class AccountMissingRegressionTests(PeopleMissingFixtures, TestCase):
    def test_accounts_three_pages_have_no_gaps_or_duplicates(self):
        expected = list(User.objects.order_by('pk').values_list('pk', flat=True))
        ids = []
        first = self.get_ok('/api/admin/accounts/')
        self.assertGreater(first['pages'], 2)
        for page in range(1, first['pages'] + 1): ids.extend(x['id'] for x in self.get_ok('/api/admin/accounts/', page=page)['items'])
        self.assertEqual(ids, expected); self.assertEqual(len(set(ids)), len(ids))

    def test_combined_account_filters_cross_pages_and_global_statistics(self):
        data = self.get_ok('/api/admin/accounts/', search='audit', role='User', status='active')
        self.assertEqual((data['total'], data['pages'], len(data['items'])), (8, 2, 5))
        second = self.get_ok('/api/admin/accounts/', search='audit', role='User', status='active', page=2)
        self.assertEqual(len(second['items']), 3)
        self.assertSetEqual({x['id'] for x in data['items'] + second['items']}, {u.pk for u in self.audit_users[:8]})
        self.assertEqual(data['stats']['total'], User.objects.count())
        self.assertEqual(data['stats']['locked'], 4)

    def test_account_email_search_empty_and_invalid_pages(self):
        data = self.get_ok('/api/admin/accounts/', search=self.audit_users[9].email, role='User', status='locked')
        self.assertEqual([x['id'] for x in data['items']], [self.audit_users[9].pk])
        empty = self.get_ok('/api/admin/accounts/', search='no-match', page=99)
        self.assertEqual((empty['items'], empty['total'], empty['page']), ([], 0, 1))
        self.assertEqual(self.get_ok('/api/admin/accounts/', page='bad')['page'], 1)
        last = self.get_ok('/api/admin/accounts/', page=999); self.assertEqual(last['page'], last['pages'])

    def test_lock_actions_idempotent_and_admin_staff_self_protection(self):
        path = f'/api/admin/accounts/{self.user.pk}/status/'
        for action in ('lock', 'lock', 'unlock', 'unlock'):
            self.assertEqual(self.client.post(path, {'action': action}).status_code, 200)
            self.user.refresh_from_db(); self.assertEqual(self.user.is_active, action == 'unlock')
        self.assertEqual(self.client.post(path, {'action': 'delete'}).status_code, 400)
        staff = User.objects.create_user('staffprotected', 'staff@example.invalid', 'TestOnly!765', is_staff=True)
        other_admin = User.objects.create_user('otheradmin', 'otheradmin@example.invalid', 'TestOnly!765', role='Admin')
        for user in (self.admin, staff, other_admin):
            self.assertEqual(self.client.post(f'/api/admin/accounts/{user.pk}/status/', {'action': 'lock'}).status_code, 403)
            user.refresh_from_db(); self.assertTrue(user.is_active)
        self.assertTrue(Customer.objects.filter(user=self.user).exists()); self.assertEqual(self.user.role, 'User')

    def test_account_endpoints_permissions_csrf_and_methods(self):
        endpoints = ['/api/admin/accounts/', f'/api/admin/accounts/{self.user.pk}/']
        for client, expected in ((Client(), 401), (self.client, 200)):
            for path in endpoints: self.assertEqual(client.get(path).status_code, expected)
        regular = Client(); regular.force_login(self.user)
        for path in endpoints: self.assertEqual(regular.get(path).status_code, 403)
        status_path = f'/api/admin/accounts/{self.user.pk}/status/'
        self.assertEqual(regular.post(status_path, {'action': 'lock'}).status_code, 403)
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.admin)
        self.assertEqual(csrf.post(status_path, {'action': 'lock'}).status_code, 403)
        self.assertEqual(self.client.get(status_path).status_code, 405)
        for path in endpoints + [status_path]: self.assertEqual(self.client.delete(path).status_code, 405)


class CustomerMissingRegressionTests(PeopleMissingFixtures, TestCase):
    def test_customer_search_pagination_and_contact_searches(self):
        first = self.get_ok('/api/admin/customers/', search='Audit customer')
        ids = [x['id'] for p in range(1, first['pages'] + 1) for x in self.get_ok('/api/admin/customers/', search='Audit customer', page=p)['items']]
        self.assertEqual(len(ids), 12); self.assertEqual(len(set(ids)), 12)
        for term in (self.audit_users[4].username, self.audit_users[4].email, self.audit_users[4].customer.phone):
            result = self.get_ok('/api/admin/customers/', search=term)
            self.assertEqual([x['id'] for x in result['items']], [self.audit_users[4].customer.pk])

    def test_customer_empty_and_out_of_range_pagination(self):
        result = self.get_ok('/api/admin/customers/', search='absent', page=99)
        self.assertEqual((result['items'], result['total'], result['page']), ([], 0, 1))
        last = self.get_ok('/api/admin/customers/', page=999); self.assertEqual(last['page'], last['pages'])
        self.assertEqual(self.get_ok('/api/admin/customers/', page='invalid')['page'], 1)

    def test_hidden_admin_superuser_profiles_not_in_any_page_or_detail(self):
        hidden = self.audit_users[-2:]
        User.objects.filter(pk=hidden[0].pk).update(role='Admin')
        User.objects.filter(pk=hidden[1].pk).update(is_superuser=True)
        hidden_ids = {u.customer.pk for u in hidden}
        first = self.get_ok('/api/admin/customers/')
        ids = {x['id'] for p in range(1, first['pages'] + 1) for x in self.get_ok('/api/admin/customers/', page=p)['items']}
        self.assertTrue(ids.isdisjoint(hidden_ids))
        for pk in hidden_ids: self.assertEqual(self.client.get(f'/api/admin/customers/{pk}/').status_code, 404)

    def test_admin_detail_matches_all_user_profile_fields_after_update(self):
        user_client = Client(); user_client.force_login(self.user)
        payload = dict(name='Profile updated', username=self.user.username, email=self.user.email, phone='0901234567',
                       skin='Da khô', needs=['Thư giãn', 'Da mặt'], interests=['Nhẹ nhàng'], budget='450000')
        self.assertEqual(user_client.post('/api/profile/', payload).status_code, 200)
        profile = user_client.get('/api/profile/').json()['item']
        detail = self.get_ok(f'/api/admin/customers/{self.customer.pk}/')['item']
        self.assertEqual(detail, profile)
        listed = self.get_ok('/api/admin/customers/', search=self.user.username)['items']
        self.assertEqual(listed, [profile])

    def test_customer_readonly_and_detail_permissions_without_changes(self):
        path = f'/api/admin/customers/{self.customer.pk}/'
        before = Customer.objects.filter(pk=self.customer.pk).values().get()
        for method in ('post', 'put', 'patch', 'delete'):
            self.assertEqual(getattr(self.client, method)(path, {'full_name': 'Do not save'}).status_code, 405)
        anon, regular, other = Client(), Client(), Client()
        regular.force_login(self.user); other.force_login(self.other)
        for client, expected in ((anon, 401), (regular, 403), (other, 403)):
            for url in ('/api/admin/customers/', path): self.assertEqual(client.get(url).status_code, expected)
        self.assertEqual(self.client.get('/api/admin/customers/999999999/').status_code, 404)
        self.assertEqual(Customer.objects.filter(pk=self.customer.pk).values().get(), before)


class DashboardMissingRegressionTests(IsolatedAdminFixtures, TestCase):
    def dashboard(self, **params):
        defaults = dict(start=self.day.isoformat(), end=self.day.isoformat()); defaults.update(params)
        r = self.client.get('/api/dashboard/', defaults); self.assertEqual(r.status_code, 200, r.content); return r.json()

    def confirmed_invoice(self, hour, day=None):
        appointment = book(self.user, self.service.pk, self.employee.pk, day or self.day, time(hour))
        transition(self.admin, appointment.pk, 'confirmed')
        return Invoice.objects.get(appointment=appointment)

    def payment(self, invoice, **changes):
        data = dict(invoice=invoice, payment_method='spa', status='success', amount=invoice.total_amount, paid_at=timezone.now())
        data.update(changes); return Payment.objects.create(**data)

    def test_period_kpis_unique_customers_statuses_recent_and_active_services(self):
        b = self.second_service(); self.employee.services.add(b)
        a = book(self.user, self.service.pk, self.employee.pk, self.day, time(9))
        b_app = book(self.user, b.pk, self.employee.pk, self.day, time(11))
        c = book(self.other, self.service.pk, self.employee2.pk, self.day, time(13))
        # Synthetic status fixtures exercise aggregation, not transition rules.
        Appointment.objects.filter(pk=b_app.pk).update(status='cancelled')
        Appointment.objects.filter(pk=c.pk).update(status='completed')
        outside = book(self.user, self.service.pk, self.employee.pk, self.day, time(15))
        Appointment.objects.filter(pk=outside.pk).update(appointment_date=self.day + timedelta(days=1))
        hidden = ServiceCategory.objects.create(name='Hidden', is_active=False)
        Service.objects.create(category=hidden, name='Hidden service', description='X', price=1, duration_minutes=1)
        data = self.dashboard()
        self.assertEqual((data['appointments'], data['periodCustomers'], data['activeServices']), (3, 2, 2))
        self.assertEqual({r['status']: r['count'] for r in data['statuses']}, {'pending': 1, 'cancelled': 1, 'completed': 1})
        self.assertEqual(sum(r['count'] for r in data['popular']), 2)
        self.assertSetEqual({r['id'] for r in data['recent']}, {a.pk, b_app.pk, c.pk})
        self.assertEqual(self.dashboard(start=(self.day + timedelta(days=1)).isoformat(), end=(self.day + timedelta(days=1)).isoformat())['appointments'], 1)

    def test_duplicate_service_names_must_remain_distinct_in_statistics(self):
        # Known backend defect: values('service__name') merges these IDs.
        b = self.second_service(self.service.name); self.employee.services.add(b)
        appointments = [book(self.user, self.service.pk, self.employee.pk, self.day, time(9)),
                        book(self.user, b.pk, self.employee.pk, self.day, time(11)),
                        book(self.user, b.pk, self.employee.pk, self.day, time(12))]
        Appointment.objects.filter(pk__in=[a.pk for a in appointments]).update(status='completed')
        data = self.dashboard()
        for key in ('popular', 'services'):
            with self.subTest(metric=key):
                self.assertEqual(len(data[key]), 2, 'Different service IDs must not be merged by display name')
                self.assertEqual(sorted(x['count'] for x in data[key]), [1, 2])

    def test_revenue_excludes_retry_review_pending_and_unpaid_invoice_rows(self):
        invoice = self.confirmed_invoice(9)
        Invoice.objects.filter(pk=invoice.pk).update(payment_status='paid')
        invoice.refresh_from_db()
        paid_at = timezone.make_aware(datetime.combine(self.day, time(12)))
        self.payment(invoice, paid_at=paid_at)
        for status in ('pending', 'cancelled', 'review'):
            self.payment(invoice, status=status, paid_at=paid_at)
        self.payment(invoice, requires_review=True, paid_at=paid_at)
        self.payment(invoice, paid_at=None)
        unpaid = self.confirmed_invoice(11)
        self.payment(unpaid, paid_at=paid_at)
        data = self.dashboard()
        self.assertEqual(Decimal(data['revenue']), invoice.total_amount)
        self.assertEqual(sum(Decimal(x['total']) for x in data['daily']), invoice.total_amount)
        self.assertEqual(sum(Decimal(x['total']) for x in data['monthly']), invoice.total_amount)

    def test_vietnam_day_includes_start_and_excludes_next_midnight(self):
        moments = [datetime(2026, 10, 21, 16, 59, 59, 999999, tzinfo=dt_timezone.utc),
                   datetime(2026, 10, 21, 17, 0, tzinfo=dt_timezone.utc),
                   datetime(2026, 10, 22, 16, 59, 59, 999999, tzinfo=dt_timezone.utc),
                   datetime(2026, 10, 22, 17, 0, tzinfo=dt_timezone.utc)]
        for hour, moment in zip((9, 10, 11, 12), moments):
            invoice = self.confirmed_invoice(hour)
            Invoice.objects.filter(pk=invoice.pk).update(payment_status='paid'); invoice.refresh_from_db()
            self.payment(invoice, paid_at=moment)
        data = self.dashboard(start='2026-10-22', end='2026-10-22')
        self.assertEqual(Decimal(data['revenue']), Decimal('1000000'))
        self.assertEqual(data['daily'], [{'day': '2026-10-22', 'total': '1000000.00'}])

    def test_empty_invalid_periods_and_permission_matrix(self):
        data = self.dashboard(start='2000-01-01', end='2000-01-02')
        self.assertEqual((data['appointments'], data['periodCustomers'], Decimal(data['revenue'])), (0, 0, 0))
        self.assertEqual((data['recent'], data['statuses'], data['popular']), ([], [], []))
        for params in (dict(start='bad'), dict(start='2026-02-02', end='2026-02-01'),
                       dict(start='2000-01-01', end='2030-01-01'), dict(status='unknown')):
            self.assertEqual(self.client.get('/api/dashboard/', params).status_code, 400)
        self.assertEqual(Client().get('/api/dashboard/').status_code, 401)
        regular = Client(); regular.force_login(self.user)
        self.assertEqual(regular.get('/api/dashboard/').status_code, 403)
