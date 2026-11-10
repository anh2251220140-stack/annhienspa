"""Reports regression tests: only disposable SQLite memory, no MySQL/network."""
import os
from pathlib import Path
import socket
import sys
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
def main():
 os.environ['DJANGO_SETTINGS_MODULE']='config.settings'
 from django.conf import settings
 settings.DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':':memory:','TEST':{'NAME':':memory:'}}}
 settings.DATABASE_ROUTERS=[];settings.SECRET_KEY='reports-isolated-contract-checks'
 settings.EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
 settings.PAYOS_CLIENT_ID=settings.PAYOS_API_KEY=settings.PAYOS_CHECKSUM_KEY=''
 from django.db.backends.base.base import BaseDatabaseWrapper
 original=BaseDatabaseWrapper.ensure_connection
 def guard(db):
  name=str(db.settings_dict['NAME'])
  if db.vendor!='sqlite' or db.alias!='default' or not(name==':memory:' or (name.startswith('file:memorydb_') and 'mode=memory' in name)):raise RuntimeError('Only SQLite memory allowed')
  return original(db)
 with patch.object(BaseDatabaseWrapper,'ensure_connection',guard),patch.object(socket.socket,'connect',side_effect=RuntimeError('Network forbidden')):
  import django
  django.setup()
  import unittest
  from django.test import TestCase
  from django.test.runner import DiscoverRunner
  from django.utils import timezone
  from datetime import datetime,timedelta,time,timezone as utc
  from core.test_phase3 import Fixtures
  from appointments.services import book,transition
  from appointments.models import Appointment
  from billing.models import Invoice,Payment
  from billing.services import cash
  from reviews.models import Review
  class ReportExtraTests(Fixtures,TestCase):
   def setUp(self):
    self.seed();self.client.force_login(self.admin)
    self.a=book(self.user,self.service.pk,self.employee.pk,self.day,time(9));transition(self.admin,self.a.pk,'confirmed')
    self.invoice=Invoice.objects.get(appointment=self.a);cash(self.admin,self.invoice.pk,self.invoice.total_amount)
    Payment.objects.update(paid_at=timezone.make_aware(datetime.combine(self.day,time(12))))
    Appointment.objects.filter(pk=self.a.pk).update(status='completed');self.a.refresh_from_db()
    self.review=Review.objects.create(appointment=self.a,customer=self.customer,service=self.service,rating=5,comment='')
    Review.objects.update(created_at=timezone.make_aware(datetime.combine(self.day,time(13))))
   def report(self,**params):
    filters={'start':self.day.isoformat(),'end':self.day.isoformat()};filters.update(params)
    r=self.client.get('/api/dashboard/',filters);self.assertEqual(r.status_code,200);return r.json()
   def test_non_success_review_retry_and_unpaid_invoice_payments_are_excluded(self):
    stamp=timezone.make_aware(datetime.combine(self.day,time(12)))
    for status in ('pending','cancelled','review'):
     Payment.objects.create(invoice=self.invoice,payment_method='spa',status=status,amount=500000,paid_at=stamp)
    Payment.objects.create(invoice=self.invoice,payment_method='spa',status='success',amount=500000,paid_at=stamp,requires_review=True)
    Payment.objects.create(invoice=self.invoice,payment_method='spa',status='success',amount=500000,paid_at=None)
    b=book(self.user,self.service.pk,self.employee.pk,self.day,time(11));transition(self.admin,b.pk,'confirmed')
    Payment.objects.create(invoice=Invoice.objects.get(appointment=b),payment_method='spa',status='success',amount=500000,paid_at=stamp)
    d=self.report();self.assertEqual(float(d['revenue']),500000);self.assertEqual(sum(float(r['total']) for r in d['daily']),500000)
   def test_distinct_service_ids_with_same_name_remain_separate(self):
    from services.models import Service
    other=Service.objects.create(category=self.category,name=self.service.name,description='Separate ID',price=500000,duration_minutes=60)
    self.employee.services.add(other)
    for hour in (11,12):
     a=book(self.user,other.pk,self.employee.pk,self.day,time(hour));Appointment.objects.filter(pk=a.pk).update(status='completed')
    d=self.report()
    for key in ('popular','services'):
     self.assertEqual(len(d[key]),2);self.assertEqual(sorted(r['count'] for r in d[key]),[1,2])
     self.assertTrue(all(set(row)=={'service__name','count'} for row in d[key]))
    self.assertEqual(len(d['report']),2);self.assertEqual(sum(row['appointments'] for row in d['report']),3)
   def test_status_filter_leaves_revenue_and_reviews_unchanged(self):
    all_rows=self.report()
    for status in ('pending','confirmed','completed','cancelled'):
     d=self.report(status=status)
     self.assertEqual((d['revenue'],d['rating'],d['reviewCount'],d['daily'],d['ratings']),(all_rows['revenue'],all_rows['rating'],all_rows['reviewCount'],all_rows['daily'],all_rows['ratings']))
     self.assertEqual(d['appointments'],1 if status=='completed' else 0)
     self.assertEqual(sum(r['appointments'] for r in d['report']),d['appointments'])
     self.assertEqual(sum(float(r['revenue']) for r in d['report']),500000)
   def test_payment_and_review_days_can_have_no_appointment_in_period(self):
    another=self.day+timedelta(days=2)
    Payment.objects.update(paid_at=timezone.make_aware(datetime.combine(another,time(12))))
    Review.objects.update(created_at=timezone.make_aware(datetime.combine(another,time(13))))
    d=self.report(start=another.isoformat(),end=another.isoformat())
    self.assertEqual((d['appointments'],d['reviewCount'],float(d['revenue'])),(0,1,500000))
    self.assertEqual((d['report'][0]['appointments'],d['report'][0]['reviews']),(0,1))
   def test_review_uses_creation_day_vietnam_and_weighted_average(self):
    b=book(self.other,self.service.pk,self.employee2.pk,self.day,time(11))
    Appointment.objects.filter(pk=b.pk).update(status='completed');b.refresh_from_db()
    review=Review.objects.create(appointment=b,customer=self.other_customer,service=self.service,rating=2,comment='Góp ý')
    day=datetime(2026,10,22).date()
    Review.objects.filter(pk=self.review.pk).update(created_at=datetime(2026,10,21,17,0,tzinfo=utc.utc))
    Review.objects.filter(pk=review.pk).update(created_at=datetime(2026,10,22,16,59,59,999999,tzinfo=utc.utc))
    d=self.report(start=day.isoformat(),end=day.isoformat());self.assertEqual((d['reviewCount'],d['rating']),(2,3.5))
    self.assertEqual(sum(r['count'] for r in d['ratings']),2)
    Review.objects.filter(pk=review.pk).update(created_at=datetime(2026,10,22,17,0,tzinfo=utc.utc))
    self.assertEqual(self.report(start=day.isoformat(),end=day.isoformat())['reviewCount'],1)
  class Runner(DiscoverRunner):
   def build_suite(self,*args,**kwargs):
    suite=super().build_suite(*args,**kwargs);suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(ReportExtraTests));print('Reports contract cases:',suite.countTestCases());return suite
  labels=['billing.test_phase4.Phase4Tests.test_signed_webhook_fake_mismatch_duplicate_and_revenue','billing.test_phase4.Phase4Tests.test_dashboard_filters_permissions_empty','billing.test_phase4.Phase4Tests.test_revenue_local_midnight_boundaries']
  print('SQLite :memory: ONLY; MySQL/network forbidden.',flush=True)
  return bool(Runner(verbosity=1,interactive=False).run_tests(labels))
if __name__=='__main__':raise SystemExit(main())
