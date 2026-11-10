"""Acceptance evidence for Admin Reviews with exactly two real SQLite-memory rows.
No MySQL connections, MySQL migrations, CLEAN/FLUSH, provider calls or app edits.
The fixture uses a temporary loopback GET-only server and a test-only Admin UI
identity. API reads execute the existing Django review view against SQLite.
"""
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import threading
import uuid
from datetime import datetime, time, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlsplit, unquote
from unittest.mock import patch
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

CHECKS=r'''
(async()=>{
 const $=s=>document.querySelector(s),all=s=>[...document.querySelectorAll(s)],wait=ms=>new Promise(r=>setTimeout(r,ms||50));
 let count=Number(sessionStorage.getItem('acceptance-check-count')||0);
 const check=(v,m)=>{if(!v)throw Error(m);count++;};
 const until=async(fn,label)=>{for(let n=0;n<160;n++){if(fn())return;await wait();}throw Error('Timeout: '+label);};
 const input=e=>e.dispatchEvent(new Event('input',{bubbles:true}));
 const stats=()=>all('#quality-stats strong').map(n=>n.textContent);
 const reset=()=>$('#quality-reset').click();
 const filter=(selector,value)=>{$(selector).value=value;input($(selector));};
 async function open(id){reset();$(`[data-view-review="${id}"]`).click();await until(()=>$('#quality-dialog .reviews-thread'),'modal data');}
 async function close(){ $('#quality-dialog .admin-dialog-actions [data-close-review]').click();await until(()=>!$('#quality-dialog').open,'close');await wait();}
 function modalFits(){const r=$('#quality-dialog').getBoundingClientRect();check(r.left>=0&&r.right<=innerWidth+1&&r.top>=0&&r.bottom<=innerHeight+1,'modal contained');}
 async function shot(name,full=false){window.__reviewShot={name,full};await until(()=>!window.__reviewShot,'screenshot '+name);}
 try{
 await document.fonts.ready;await until(()=>$('#reviews-panel').getAttribute('aria-busy')==='false','API load');
 check($('#quality-api-error').hidden,'API load succeeds');
 check(JSON.stringify(stats())===JSON.stringify(['3,5','2','1','1']),'4 KPIs average3.5 / total2 / positive1 / concern1');
 check(all('#quality-rows tr').length===2,'exactly 2 reviews');
 check($('#quality-pagination').textContent.includes('1 / 1')&&all('[data-review-page]').every(b=>b.disabled),'one page for exactly2 rows');
 check(!$('.admin-quality-source'),'removed note stays removed');
 check($('#analysis-run').disabled&&$('#analysis-mode').disabled&&$('#analysis-results').textContent.includes('chưa được kết nối'),'no FR23 AI');
 if(!sessionStorage.getItem('acceptance-reloaded')){
  check(all('#quality-stats .line-icon').length===4,'4 KPI icons');
  for(const r of reviewCases){check($('#quality-rows').textContent.includes(r.customer)&&$('#quality-rows').textContent.includes(r.service),'correct customer / service '+r.id);}
  filter('#quality-stars','5');check(all('#quality-rows tr').length===1&&JSON.stringify(stats())===JSON.stringify(['5,0','1','1','0']),'5 star filter and KPIs');
  filter('#quality-stars','2');check(all('#quality-rows tr').length===1&&JSON.stringify(stats())===JSON.stringify(['2,0','1','0','1']),'2 star filter and KPIs');
  filter('#quality-search','khach kiem thu a');check(!$('#quality-empty').hidden&&all('#quality-rows tr').length===0,'combined empty search');reset();
  filter('#quality-search','yen tinh');check(all('#quality-rows tr').length===1&&$('#quality-rows').textContent.includes('Khách kiểm thử A'),'search without accents');reset();
  filter('#quality-from','10/11/2026');filter('#quality-to','10/11/2026');check(all('#quality-rows tr').length===1&&$('#quality-rows').textContent.includes('10/11/2026 00:05'),'Vietnam date boundary');
  filter('#quality-from','09/11/2026');filter('#quality-to','09/11/2026');check(all('#quality-rows tr').length===1&&$('#quality-rows').textContent.includes('Khách kiểm thử B'),'previous day filter');
  filter('#quality-from','11/11/2026');check(!$('#quality-filter-error').hidden&&all('#quality-rows tr').length===0,'invalid range no stale records');reset();
  filter('#quality-search','khong-co-ket-qua');check(!$('#quality-empty').hidden&&JSON.stringify(stats())===JSON.stringify(['—','0','0','0']),'empty filtered KPI');reset();
  for(const r of reviewCases){
   await open(r.id);modalFits();
   check($('#quality-dialog').textContent.includes(r.comment)&&$('#quality-dialog').textContent.includes(r.customer),'detail matches selected review '+r.id);
   check($('#quality-dialog .reviews-detail-banner [aria-label]').getAttribute('aria-label')===`${r.rating} trên 5 sao`,'correct stars '+r.id);
   check($('#quality-dialog').textContent.includes('LH-'+String(r.appointmentId).padStart(6,'0')),'actual appointment ID '+r.id);
   const replies=all('#quality-dialog .review-reply');
   check($('#quality-dialog-title').textContent==='Chi tiết đánh giá','B2 modal title');
   const expectedHeart=document.createElement('span');expectedHeart.innerHTML=window.spaIcon('heart');
   check($('#quality-dialog .reviews-modal-symbol path').getAttribute('d')===expectedHeart.querySelector('path').getAttribute('d'),'heart icon in header');
   check(replies.every(el=>getComputedStyle(el).backgroundColor==='rgb(255, 248, 241)'&&getComputedStyle(el).borderRadius==='12px'),'separate cream rounded reply cards');
   check(JSON.stringify(replies.map(el=>el.querySelector('strong').textContent))===JSON.stringify(r.replies.map(reply=>reply.name)),'reply sender order unchanged');
   check(JSON.stringify(replies.map(el=>el.querySelector('p').textContent))===JSON.stringify(r.replies.map(reply=>reply.content)),'reply content unchanged');
   check($('#quality-dialog label[for=review-reply-content]').textContent==='Nội dung phản hồi','B2 reply label');
   const field=$('#review-reply-content').getBoundingClientRect(),send=$('#quality-dialog [type=submit]').getBoundingClientRect();
   check(Math.abs(send.left-field.left)<2&&send.top>=field.bottom,'send button below and left aligned');
   const threadList=$('#quality-dialog .reviews-thread-list');
   check(getComputedStyle(threadList).maxHeight==='360px'&&threadList.tabIndex===0,'bounded accessible reply list');
   check(!$('#quality-dialog .admin-topic-chips')&&!$('#quality-dialog [data-review-analyze]'),'no simulated sentiment or AI action');

   check(replies.length===2&&!$('#quality-dialog .review-reply .review-reply'),'two flat replies '+r.id);
   for(const reply of r.replies){check(replies.some(el=>el.textContent.includes(reply.name)&&el.textContent.includes(reply.content)&&el.querySelector('time').textContent.includes('/2026')),'sender / content / timestamp '+reply.id);}
   check($('#review-reply-content').maxLength===2000&&$('#quality-dialog [type=submit]'),'reply form available; not submitted');
   const body=$('#quality-dialog .admin-service-modal-scroll');body.scrollTop=body.scrollHeight;await wait();
   check(body.scrollHeight<=body.clientHeight+1||body.scrollTop>0,'modal scroll works');
   check($('#quality-dialog .admin-dialog-actions').getBoundingClientRect().bottom<=innerHeight,'footer stays visible');await close();
  }
  check(document.documentElement.scrollWidth<=innerWidth,'no page horizontal overflow');
  const table=$('.admin-table-scroll');table.scrollLeft=table.scrollWidth;
  check($('#quality-rows tr .admin-row-actions button').getBoundingClientRect().right<=table.getBoundingClientRect().right+1,'table action reachable');table.scrollLeft=0;
  check(window.acceptanceErrors.length===0,'no JavaScript errors');
  sessionStorage.setItem('acceptance-check-count',String(count));sessionStorage.setItem('acceptance-reloaded','1');location.reload();return;
 }
 check($('#quality-rows').textContent.includes('2 phản hồi'),'reply counters persist after actual reload');
 check(window.acceptanceErrors.length===0,'no JavaScript error after reload');
 await shot('overview',true);
 $('#quality-table').scrollIntoView({block:'start',behavior:'instant'});await shot('list');
 for(const r of reviewCases){
  await open(r.id);modalFits();check(all('#quality-dialog .review-reply').length===2,'real SQLite replies survive F5 '+r.id);
  await shot('detail-'+r.rating+'-stars');
  if(r.rating===2){const body=$('#quality-dialog .admin-service-modal-scroll'),thread=$('#quality-dialog .reviews-thread');body.scrollTop+=thread.getBoundingClientRect().top-body.getBoundingClientRect().top;await wait();await shot('replies-user-admin');}
  await close();
 }
 check(document.documentElement.scrollWidth<=innerWidth,'no overflow after modal / reload');
 document.body.insertAdjacentHTML('beforeend',`<pre id="test-result">PASS ${count}</pre>`);
 }catch(error){document.body.insertAdjacentHTML('beforeend','<pre id="test-result">FAIL '+error.message+'</pre>');}
})();
'''


def main():
    os.environ['DJANGO_SETTINGS_MODULE']='config.settings'
    from django.conf import settings
    memory_name='file:annhien_reviews_acceptance_'+uuid.uuid4().hex+'?mode=memory&cache=shared'
    settings.DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':memory_name,'OPTIONS':{'uri':True},'TEST':{'NAME':memory_name}}}
    settings.DATABASE_ROUTERS=[]
    settings.SECRET_KEY='isolated-reviews-acceptance-only'
    settings.EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
    settings.PAYOS_CLIENT_ID=settings.PAYOS_API_KEY=settings.PAYOS_CHECKSUM_KEY=''
    from django.db.backends.base.base import BaseDatabaseWrapper
    original=BaseDatabaseWrapper.ensure_connection
    db_attempts=[]
    def guarded(db):
        if db.alias!='default' or db.vendor!='sqlite' or db.settings_dict['NAME']!=memory_name:
            raise RuntimeError('Forbidden database connection: only named SQLite memory allowed')
        if not db_attempts:db_attempts.append('sqlite-memory')
        return original(db)
    with patch.object(BaseDatabaseWrapper,'ensure_connection',guarded),patch.object(socket.socket,'connect',side_effect=RuntimeError('Outbound Python network forbidden')):
        import django
        django.setup()
        from django.core.management import call_command
        from django.db import connection,connections
        from django.test import RequestFactory
        from django.template.loader import render_to_string
        from django.utils import timezone as dj_timezone
        from accounts.models import User,Customer
        from services.models import ServiceCategory,Service
        from employees.models import Employee,EmployeeService,EmployeeSchedule
        from appointments.models import Appointment
        from reviews.models import Review,ReviewReply
        from reviews import views
        from tools.check_admin_promotions_ui import CHROME_CHECK
        print('Creating schema in SQLite shared memory ONLY; MySQL forbidden.',flush=True)
        call_command('migrate',verbosity=0,interactive=False)
        call_command('check')
        connection.ensure_connection()
        admin=User.objects.create_superuser('admin_ui_test','admin-ui@example.test',None)
        category=ServiceCategory.objects.create(name='Danh mục kiểm thử')
        employee=Employee.objects.create(full_name='Chuyên viên kiểm thử',specialty='Dịch vụ kiểm thử')
        day=datetime(2026,11,9).date()
        EmployeeSchedule.objects.create(employee=employee,work_date=day,start_time=time(9),end_time=time(18))
        rf=RequestFactory()
        owners=[]
        for index,(rating,title,comment) in enumerate([(5,'Massage đá nóng','Không gian yên tĩnh, chuyên viên tận tâm. Tôi rất hài lòng với buổi chăm sóc.'),(2,'Chăm sóc da chuyên sâu','Tôi phải chờ lâu hơn dự kiến trước khi bắt đầu. Mong Spa cải thiện khâu đón tiếp.')]):
            user=User.objects.create_user('user_ui_'+('a' if index==0 else 'b'),'user-ui-'+str(index)+'@example.test',None)
            customer=Customer.objects.create(user=user,full_name='Khách kiểm thử '+('A' if index==0 else 'B'),phone='0000000000')
            service=Service.objects.create(category=category,name=title,description='Dữ liệu thử nghiệm cô lập',price=390000,duration_minutes=60)
            EmployeeService.objects.create(employee=employee,service=service)
            appointment=Appointment.objects.create(customer=customer,service=service,employee=employee,appointment_date=day,start_time=time(9+index*2),end_time=time(10+index*2),status='completed')
            request=rf.post('/api/reviews/appointments/'+str(appointment.pk)+'/',{'rating':rating,'comment':comment});request.user=user
            response=views.save(request,pk=appointment.pk);assert response.status_code==200
            review=Review.objects.get(appointment=appointment)
            stamp=datetime(2026,11,9,17,5,tzinfo=timezone.utc) if index==0 else datetime(2026,11,9,2,30,tzinfo=timezone.utc)
            Review.objects.filter(pk=review.pk).update(created_at=stamp)
            replies=[(admin,'Cảm ơn bạn đã chia sẻ. Spa rất vui khi bạn hài lòng.'),(user,'Cảm ơn Spa, tôi sẽ quay lại.')] if index==0 else [(user,'Tôi chờ khoảng 20 phút so với giờ hẹn.'),(admin,'Spa đã ghi nhận góp ý và sẽ rà soát việc đón tiếp.')]
            for offset,(actor,content) in enumerate(replies):
                request=rf.post('/api/reviews/'+str(review.pk)+'/replies/',{'content':content});request.user=actor
                response=views.reply(request,pk=review.pk);assert response.status_code==201
                rid=json.loads(response.content)['item']['replies'][-1]['id']
                from datetime import timedelta
                ReviewReply.objects.filter(pk=rid).update(created_at=stamp+timedelta(minutes=(offset+1)*5))
            owners.append(user)
        def api_data():
            request=rf.get('/api/reviews/');request.user=admin
            response=views.listing(request);assert response.status_code==200
            return json.loads(response.content)
        payload=api_data();assert Review.objects.count()==2 and ReviewReply.objects.count()==4
        for owner in owners:
            request=rf.get('/api/reviews/');request.user=owner
            assert len(json.loads(views.listing(request).content)['items'])==1
        cases=sorted(payload['items'],key=lambda row:-row['rating'])
        print('SQLite fixture: 2 reviews (5 and 2 stars), 4 real User/Admin replies; average 3.5.',flush=True)
        source_files=['templates/pages/admin-reviews.html','static/js/live-admin-reviews.js','static/css/admin-reviews-luxury.css','reviews/views.py','reviews/models.py']
        source_hashes={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in source_files}
        html=render_to_string('pages/admin-reviews.html',{'auth_ui':{},'live_catalog':{'services':[],'products':[],'staff':[]},'live_promotions':{'items':[]},'csrf_token':'isolated-render-token'})
        html=re.sub(r'<script src="[^\"]*/js/auth\.js"[^>]*></script>','',html)
        boot="window.acceptanceErrors=[];window.addEventListener('error',e=>acceptanceErrors.push(e.message));window.addEventListener('unhandledrejection',e=>acceptanceErrors.push(String(e.reason)));window.spaAuth={allowed:true,isAuthenticated:()=>true,getSession:()=>({role:'Admin'})};"
        html=html.replace('<script src="/static/js/admin.js"','<script>'+boot+'</script><script src="/static/js/admin.js"')
        html=html.replace('</body>','<div style="position:fixed;bottom:6px;left:8px;z-index:99999;background:#fff8f1;color:#3a2419;border:1px solid #c6a07e;padding:4px 8px;border-radius:6px;font:11px sans-serif;pointer-events:none">DỮ LIỆU KIỂM THỬ · SQLite bộ nhớ</div><script>const reviewCases='+json.dumps(cases,ensure_ascii=False)+';'+CHECKS+'</script></body>')
        requests={'api_get':0,'blocked_post':0}
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                requests['blocked_post']+=1;self.send_error(405,'Read-only test server')
            def do_GET(self):
                path=urlsplit(self.path).path
                if self.client_address[0]!='127.0.0.1' or self.headers.get('Host')!='127.0.0.1:'+str(self.server.server_port):self.send_error(403);return
                if path=='/admin-reviews.html':body=html.encode();mime='text/html; charset=utf-8'
                elif path=='/api/reviews/':
                    requests['api_get']+=1
                    body=json.dumps(api_data(),ensure_ascii=False).encode();mime='application/json; charset=utf-8'
                elif path.startswith('/static/'):
                    target=(ROOT/'static'/unquote(path[len('/static/'):])).resolve()
                    if not target.is_relative_to((ROOT/'static').resolve()) or not target.is_file():self.send_error(404);return
                    body=target.read_bytes();mime=mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
                else:self.send_error(404);return
                self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
        server=HTTPServer(('127.0.0.1',0),Handler)
        def serve():
            try:server.serve_forever(poll_interval=.1)
            finally:connections.close_all()
        thread=threading.Thread(target=serve,daemon=True);thread.start()
        output=ROOT/'docs'/('reviews-isolated-ui-'+datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).strftime('%Y%m%d-%H%M%S'))
        output.mkdir(parents=True,exist_ok=False)
        print('Evidence folder:',output,flush=True)
        # Use the existing isolated Chrome/CDP launcher, adding read-only request
        # enforcement and screenshot handshakes. All browser requests are confined
        # to this newly bound loopback port; POST requests are blocked twice.
        chrome=CHROME_CHECK.replace("for(let i=0;i<100&&!fs.existsSync(portFile);i++)await sleep(100);\n const [port,path]=fs.readFileSync(portFile,'utf8').trim().split(/\\r?\\n/);", "let portText='';for(let i=0;i<100;i++){try{portText=fs.readFileSync(portFile,'utf8').trim();if(portText.split(/\\r?\\n/).length>=2)break;}catch{}await sleep(100);}\n const [port,path]=portText.split(/\\r?\\n/);")
        chrome=chrome.replace("msg.error?reject(Error(msg.error.message)):resolve(msg.result);}};", "msg.error?reject(Error(msg.error.message)):resolve(msg.result);}if(msg.method==='Fetch.requestPaused'){const p=msg.params;const allowed=p.request.method==='GET'&&new URL(p.request.url).origin===new URL(config.url).origin;call(allowed?'Fetch.continueRequest':'Fetch.failRequest',allowed?{requestId:p.requestId}:{requestId:p.requestId,errorReason:'BlockedByClient'}).catch(()=>{});}};")
        chrome=chrome.replace("await call('Page.enable');", "await call('Fetch.enable',{patterns:[{urlPattern:'*',requestStage:'Request'}]});await call('Page.enable');")
        chrome=chrome.replace('i<160','i<600')
        chrome=chrome.replace('escape:window.__requestEscape}', 'escape:window.__requestEscape,shot:window.__reviewShot}')
        chrome=chrome.replace("if(state&&JSON.parse(state).result)break;", """if(state&&JSON.parse(state).shot){
   const shot=JSON.parse(state).shot;let opts={format:'png',captureBeyondViewport:false};
   if(shot.full){const m=await call('Page.getLayoutMetrics');opts={format:'png',captureBeyondViewport:true,clip:{x:0,y:0,width:config.width,height:m.cssContentSize.height,scale:1}};}
   const {data:shotData}=await call('Page.captureScreenshot',opts);fs.writeFileSync(config.output+'/'+shot.name+'-'+config.width+'.png',Buffer.from(shotData,'base64'));
   await call('Runtime.evaluate',{expression:'window.__reviewShot=null'});
  }
  if(state&&JSON.parse(state).result)break;""")
        results=[]
        try:
            with tempfile.TemporaryDirectory(prefix='annhien-reviews-acceptance-') as temp:
                helper=Path(temp)/'chrome.cjs';helper.write_text(chrome,encoding='utf-8')
                for width in (1440,768,500,390):
                    if any(a.startswith('--width=') for a in sys.argv) and '--width='+str(width) not in sys.argv:continue
                    config=dict(profile=str(Path(temp)/str(width)),width=width,url=f'http://127.0.0.1:{server.server_port}/admin-reviews.html',output=str(output),screenshot=str(output/f'final-{width}.png'),dom=str(Path(temp)/f'{width}.html'))
                    result=subprocess.run([r'D:\node\node.exe',str(helper)],input=json.dumps(config),capture_output=True,encoding='utf-8',errors='replace',timeout=100)
                    print(width,result.stdout.strip() or 'NO RESULT',flush=True)
                    state=json.loads(result.stdout.strip()) if result.stdout.strip().startswith('{') else {'result':'NO RESULT'}
                    results.append({'width':width,**state})
                    if result.returncode:print(result.stderr[-1400:]);raise RuntimeError('Chrome acceptance checks failed')
            assert Review.objects.count()==2 and ReviewReply.objects.count()==4
            assert api_data()==payload,'Unexpected fixture data change'
            assert requests['blocked_post']==0
            for f,digest in source_hashes.items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==digest
            evidence=[]
            for file in sorted(output.glob('*.png')):
                raw=file.read_bytes();assert raw.startswith(b'\x89PNG\r\n\x1a\n')
                evidence.append({'file':file.name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
            report={'environment':'SQLite shared in-memory only; temporary loopback GET-only server','database_after_checks':{'reviews':2,'review_replies':4},'expected_kpis':{'average':3.5,'total':2,'rating_4_5':1,'rating_1_2':1},'results':results,'http':requests,'source_unchanged':True,'mysql_connections':0,'evidence':evidence}
            (output/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            print('PASS: 2 reviews / 4 replies unchanged; no MySQL; no UI POST; source unchanged.',flush=True)
            print('Report:',output/'results.json',flush=True)
            return 0
        finally:
            server.shutdown();thread.join(timeout=5);server.server_close();connections.close_all()

if __name__=='__main__':raise SystemExit(main())
