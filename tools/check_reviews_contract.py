"""Review contract checks on disposable SQLite memory ONLY, never on MySQL.
Does not use the FR-14 runner, credentials, CLEAN, or any payOS request.
"""
import os
import socket
import sys
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def main():
    os.environ['DJANGO_SETTINGS_MODULE']='config.settings'
    from django.conf import settings
    settings.DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':':memory:','TEST':{'NAME':':memory:'}}}
    settings.DATABASE_ROUTERS=[]
    settings.SECRET_KEY='isolated-review-contract-checks-only'
    settings.EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
    settings.PAYOS_CLIENT_ID=settings.PAYOS_API_KEY=settings.PAYOS_CHECKSUM_KEY=''
    from django.db.backends.base.base import BaseDatabaseWrapper
    original=BaseDatabaseWrapper.ensure_connection
    def guarded(db):
        name=str(db.settings_dict['NAME'])
        if db.alias!='default' or db.vendor!='sqlite' or not(name==':memory:' or (name.startswith('file:memorydb_') and 'mode=memory' in name)):
            raise RuntimeError('Only SQLite in-memory connections are allowed')
        return original(db)
    with patch.object(BaseDatabaseWrapper,'ensure_connection',guarded),patch.object(socket.socket,'connect',side_effect=RuntimeError('Network forbidden in review checks')):
        import django
        django.setup()
        import unittest
        from django.test import TestCase,Client
        from django.test.runner import DiscoverRunner
        from core.test_phase3 import Fixtures
        from appointments.models import Appointment
        from reviews.models import Review,ReviewReply
        from datetime import time
        class ReviewAdditionalTests(Fixtures,TestCase):
            def setUp(self):
                self.seed()
                self.a=Appointment.objects.create(customer=self.customer,service=self.service,employee=self.employee,appointment_date=self.day,start_time=time(9),end_time=time(10),status='completed')
                self.url=f'/api/reviews/appointments/{self.a.pk}/'
                self.client.force_login(self.user)
            def test_blank_comment_boundaries_and_invalid_inputs_leave_stored_review_unchanged(self):
                for rating in (1,5):
                    response=self.client.post(self.url,{'rating':rating,'comment':''})
                    self.assertEqual(response.status_code,200)
                    r=Review.objects.get();self.assertEqual(r.rating,rating);self.assertFalse(r.comment)
                    item=self.client.get('/api/reviews/').json()['items'][0]
                    self.assertEqual(item['rating'],rating);self.assertEqual(item['comment'],'')
                self.assertEqual(self.client.post(self.url,{'rating':4,'comment':'a'*2000}).status_code,200)
                original=Review.objects.get()
                for payload in ({'rating':0},{'rating':6},{'rating':'x'},{'comment':'missing stars'},{'rating':3,'comment':'x'*2001}):
                    with self.subTest(payload_length=len(payload.get('comment',''))):
                        self.assertEqual(self.client.post(self.url,payload).status_code,400)
                        r=Review.objects.get();self.assertEqual((r.pk,r.rating,r.comment),(original.pk,4,'a'*2000))
            def test_http_csrf_anonymous_admin_and_locked_account_cannot_write(self):
                anonymous=Client();self.assertEqual(anonymous.post(self.url,{'rating':5}).status_code,401)
                secure=Client(enforce_csrf_checks=True);secure.force_login(self.user)
                self.assertEqual(secure.post(self.url,{'rating':5}).status_code,403)
                self.client.force_login(self.admin);self.assertEqual(self.client.post(self.url,{'rating':5}).status_code,403)
                self.user.is_active=False;self.user.save();self.client.force_login(self.user)
                self.assertIn(self.client.post(self.url,{'rating':5}).status_code,(401,403))
                self.assertFalse(Review.objects.exists())
            def test_reply_validation_csrf_owner_admin_and_flat_history_survive_reads(self):
                self.client.post(self.url,{'rating':5});r=Review.objects.get();url=f'/api/reviews/{r.pk}/replies/'
                for content in ('','   ','x'*2001):
                    self.assertEqual(self.client.post(url,{'content':content}).status_code,400)
                secure=Client(enforce_csrf_checks=True);secure.force_login(self.user)
                self.assertEqual(secure.post(url,{'content':'CSRF denied'}).status_code,403)
                self.assertEqual(ReviewReply.objects.count(),0)
                self.assertEqual(self.client.post(url,{'content':'u'*2000}).status_code,201)
                self.client.force_login(self.admin)
                self.assertEqual(self.client.post(url,{'content':'Admin feedback','parent_id':1}).status_code,201)
                item=self.client.get('/api/reviews/').json()['items'][0]
                self.assertEqual([x['role'] for x in item['replies']],['User','Admin'])
                self.assertTrue(all(x['name'] and x['createdAt'] and 'parent_id' not in x for x in item['replies']))
                self.client.force_login(self.other)
                self.assertEqual(self.client.post(url,{'content':'not owner'}).status_code,404)
                self.assertEqual(self.client.get('/api/reviews/').json()['items'],[])
                self.client.force_login(self.user)
                self.assertEqual(len(self.client.get('/api/reviews/').json()['items'][0]['replies']),2)
                self.assertEqual(self.client.delete(url).status_code,405)
                self.assertEqual(ReviewReply.objects.count(),2)
            def test_public_blank_review_and_replies_persist_and_have_no_private_ids(self):
                self.client.post(self.url,{'rating':1,'comment':''});r=Review.objects.get()
                self.client.post(f'/api/reviews/{r.pk}/replies/',{'content':'Owner feedback'})
                self.client.force_login(self.admin)
                self.client.post(f'/api/reviews/{r.pk}/replies/',{'content':'Spa feedback'})
                d=Client().get(f'/api/reviews/services/{self.service.pk}/').json()
                self.assertEqual((d['total'],d['average']),(1,1))
                item=d['items'][0];self.assertEqual(item['comment'],'');self.assertEqual(item['rating'],1)
                self.assertEqual([x['content'] for x in item['replies']],['Owner feedback','Spa feedback'])
                self.assertFalse({'id','appointmentId','email','customerId'} & item.keys())
                self.assertEqual(Review.objects.count(),1)
        class Runner(DiscoverRunner):
            def build_suite(self,*args,**kwargs):
                suite=super().build_suite(*args,**kwargs)
                suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(ReviewAdditionalTests))
                return suite
        labels=['billing.test_phase4.Phase4Tests.test_reviews_ownership_completion_edit_reply','billing.test_phase4.Phase4Tests.test_public_service_reviews_do_not_expose_private_identifiers','core.test_models.ModelTests.test_review_requires_completed_owner_and_single_review','core.test_models.ModelTests.test_cross_customer_review_rejected']
        print('Database: SQLite :memory: ONLY; MySQL/network forbidden; 4 existing + 4 additional tests',flush=True)
        return bool(Runner(verbosity=2,interactive=False).run_tests(labels))

if __name__=='__main__':raise SystemExit(main())
