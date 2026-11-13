"""Admin Reports browser acceptance against original API + SQLite shared memory.
Temporary GET-only loopback server. MySQL and outbound network are forbidden.
No production source changes, CLEAN/FLUSH or external payment operations.
"""
import hashlib,json,mimetypes,os,re,socket,subprocess,sys,tempfile,threading,uuid
from datetime import date,datetime,time,timedelta,timezone
from pathlib import Path
from http.server import HTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlsplit,parse_qs,unquote
from unittest.mock import patch
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
CHECKS=r'''
(async()=>{
 const $=s=>document.querySelector(s),all=s=>[...document.querySelectorAll(s)],wait=ms=>new Promise(r=>setTimeout(r,ms||40));
 let count=Number(sessionStorage.getItem('report-checks')||0);
 const check=(v,m)=>{if(!v)throw Error(m);count++;},until=async(fn,label)=>{for(let n=0;n<180;n++){if(fn())return;await wait();}throw Error('Timeout '+label);};
 const ready=()=>until(()=>document.querySelector('[data-live-reports]').getAttribute('aria-busy')==='false','report load');
 const stats=()=>all('#report-stats strong').map(e=>e.textContent),input=e=>e.dispatchEvent(new Event('input',{bubbles:true}));
 async function apply(from,to,status=''){$('#report-from-display').value=from;input($('#report-from-display'));$('#report-to-display').value=to;input($('#report-to-display'));$('#report-status-filter').value=status;$('#report-filters').requestSubmit();await wait();await ready();}
 async function shot(name){window.__reportShot={name};await until(()=>!window.__reportShot,'screenshot');}
 function totals(){const c=all('#report-total tr > *').map(n=>n.textContent);return c;}
 function consistent(){
  const rows=all('#report-rows tr').filter(r=>r.children.length===7),sum=col=>rows.reduce((n,r)=>n+Number(r.children[col].textContent.replaceAll('.','').replace(',','.').replace(' VND','')),0),t=totals();
  for(const col of [1,2,3,5])check(sum(col)===Number(t[col]),'table totals column '+col);
  check(sum(4)===Number(t[4].replaceAll('.','').replace(' VND','')),'table revenue total');
 }
 try{
 await document.fonts.ready;await ready();check($('#report-api-error').hidden&&!$('#report-content').hidden,'API connected');
 if(sessionStorage.getItem('report-reloaded')){
  check(JSON.stringify(stats())===JSON.stringify(['351.000 VND','4','4','—']),'F5 restores October data');
  check($('#report-from-display').value==='01/10/2026'&&$('#report-to-display').value==='31/10/2026'&&$('#report-status-filter').value==='completed','F5 restores period / status');consistent();
  await shot('october');await apply('01/11/2026','10/11/2026');await shot('november-empty');
  await apply('01/09/2026','30/09/2026');await shot('with-reviews');
  check(reportErrors.length===0,'no JS errors');document.body.insertAdjacentHTML('beforeend',`<pre id="test-result">PASS ${count}</pre>`);return;
 }
 check(JSON.stringify(stats())===JSON.stringify(['1.000.000 VND','5','4','3,5 / 5']),'rich period KPI');consistent();
 check(all('#report-stats .line-icon').length===4,'4 KPI icons');const receipt=document.createElement('span');receipt.innerHTML=window.spaIcon('note');check($('#report-stats article:first-child .line-icon path').getAttribute('d')===receipt.querySelector('path').getAttribute('d'),'receipt icon for valid revenue');
 check(!/Admin Core|Admin Operations|Finance & Quality|Dashboard/.test($('.admin-sidebar').textContent),'Vietnamese sidebar');
 check(all('#report-services .admin-analytics-bar').length===2,'same-name distinct service groups not merged');
 check(all('#report-ratings .admin-analytics-bar').length===5&&$('#report-ratings').textContent.includes('5 sao'),'actual star distribution including real zero buckets');
 check($('#report-insights').textContent.includes('1 / 2')&&all('#report-insights article > .line-icon').length===3,'insights real ratings and icons');
 check($('#report-period').textContent.includes('01/09/2026 — 30/09/2026'),'Vietnamese period label');
 check($('#report-revenue').textContent.includes('20/09/2026')&&!$('#report-revenue').textContent.includes('2026-09-20'),'Vietnamese chart dates');
 await apply('01/09/2026','30/09/2026','cancelled');
 check(JSON.stringify(stats())===JSON.stringify(['1.000.000 VND','1','0','3,5 / 5']),'status changes appointments only');consistent();
 check($('#report-services .report-chart-empty')&&all('#report-ratings .admin-analytics-bar').length===5,'no active bookings but actual reviews retained');
 await apply('20/09/2026','20/09/2026');check(JSON.stringify(stats())===JSON.stringify(['300.000 VND','0','0','—']),'Vietnam midnight inclusion and no appointment day');consistent();
 check(!$('#report-empty').hidden===false&&$('#report-status .report-chart-empty'),'revenue-only period not globally empty');
 await apply('01/08/2026','31/08/2026');check(stats()[0]==='0 VND'&&$('#report-empty').hidden&&all('#report-revenue .admin-revenue-day').length===1,'valid zero-value receipt is not absence of transactions');check(all('#report-rows tr')[0].children.length===7,'zero-value service group retained');consistent();
 await apply('01/10/2026','31/10/2026');check(JSON.stringify(stats())===JSON.stringify(['351.000 VND','4','4','—']),'October mirrors observed totals');consistent();
 check($('#report-revenue').textContent.includes('24/10/2026')&&$('#report-status').textContent.includes('Đã hoàn thành'),'October daily and actual status');
 check($('#report-ratings').textContent.includes('Chưa có đánh giá'),'no fake rating');
 await apply('01/10/2026','31/10/2026','cancelled');check(JSON.stringify(stats())===JSON.stringify(['351.000 VND','0','0','—']),'October no cancelled appointments keeps paid revenue');consistent();
 await apply('01/11/2026','10/11/2026');check(JSON.stringify(stats())===JSON.stringify(['0 VND','0','0','—']),'November empty accurate KPI');consistent();
 check(!$('#report-empty').hidden&&all('.report-chart-empty').length===4&&!$('#report-content').textContent.includes('Không có dữ liệu trong kỳ'),'compact distinct empty states');
 check($('#report-revenue').textContent.includes('Chưa có doanh thu trong kỳ.')&&$('#report-status').textContent.includes('Chưa có lịch hẹn')&&$('#report-ratings').textContent.includes('Chưa có đánh giá'),'separate payment / appointment / review absence');
 const revenue=$('#report-revenue'),emptyRevenue=$('#report-revenue .report-chart-empty'),emptyIcon=emptyRevenue.querySelector('svg'),emptyText=emptyRevenue.querySelector('p');
 const hostBox=revenue.getBoundingClientRect(),emptyBox=emptyRevenue.getBoundingClientRect(),iconBox=emptyIcon.getBoundingClientRect(),textBox=emptyText.getBoundingClientRect();
 check(iconBox.width===30&&getComputedStyle(emptyIcon).minWidth==='0px','empty receipt icon overrides chart SVG minimum width');
 check(revenue.scrollWidth<=revenue.clientWidth&&emptyRevenue.scrollWidth<=emptyRevenue.clientWidth,'empty revenue has no horizontal scrolling');
 check(textBox.left>=hostBox.left&&textBox.right<=hostBox.right&&textBox.width>0&&textBox.height>0,'empty revenue message fully visible without clipping');
 check(Math.abs((textBox.left+textBox.right-hostBox.left-hostBox.right)/2)<2&&Math.abs((iconBox.left+iconBox.right-hostBox.left-hostBox.right)/2)<2,'empty revenue icon and message horizontally centered');
 check(Math.abs((iconBox.top+textBox.bottom-emptyBox.top-emptyBox.bottom)/2)<2,'empty revenue content vertically centered');
 check(all('#report-insights article').length===0&&$('.admin-report-insights').hidden,'empty period has no fake insights');
 $('#report-reset').click();await wait();await ready();check($('#report-from').value===serverToday.slice(0,8)+'01'&&$('#report-to').value===serverToday&&!$('#report-status-filter').value,'current month uses server Vietnam day');
 const requestsBefore=reportRequests.length;
 $('#report-from-display').value='31/02/2026';$('#report-filters').requestSubmit();await wait(100);
 check(!$('#report-filter-error').hidden&&reportRequests.length===requestsBefore,'invalid date never queried');
 $('#report-from-display').value='30/11/2026';$('#report-to-display').value='01/11/2026';$('#report-filters').requestSubmit();await wait(100);check(!$('#report-filter-error').hidden&&reportRequests.length===requestsBefore,'reversed range never queried');
 $('#report-from').value='2026-10-01';$('#report-from').dispatchEvent(new Event('change'));check($('#report-from-display').value==='01/10/2026','native picker to Vietnamese input');
 reportFailNext=true;await apply('01/10/2026','31/10/2026');check(!$('#report-api-error').hidden&&$('#report-content').hidden,'API error never exposes stale charts');
 $('#report-retry').click();await wait();await ready();check($('#report-api-error').hidden&&stats()[0]==='351.000 VND','retry same captured period');
 const n=reportRequests.length;$('#report-filters').requestSubmit();$('#report-filters').requestSubmit();await wait();await ready();check(reportRequests.length===n+1,'double apply request blocked');
 const last=new URL(reportRequests.at(-1),location.href);check(last.searchParams.get('start')==='2026-10-01'&&last.searchParams.get('end')==='2026-10-31','API dates ISO unchanged');
 const table=$('.admin-table-scroll');table.scrollLeft=table.scrollWidth;const edge=$('#report-total td:last-child').getBoundingClientRect();check(edge.right<=table.getBoundingClientRect().right+1,'last table column reachable');table.scrollLeft=0;
 check(document.documentElement.scrollWidth<=innerWidth,'no page horizontal overflow');
 check(reportErrors.length===0,'no JavaScript errors');
 await apply('01/10/2026','31/10/2026','completed');
 sessionStorage.setItem('report-checks',count);sessionStorage.setItem('report-reloaded','1');location.reload();
 }catch(ex){document.body.insertAdjacentHTML('beforeend','<pre id="test-result">FAIL '+ex.message+'</pre>');}
})();
'''

def main():
 os.environ['DJANGO_SETTINGS_MODULE']='config.settings'
 from django.conf import settings
 memory='file:annhien_reports_'+uuid.uuid4().hex+'?mode=memory&cache=shared'
 settings.DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':memory,'OPTIONS':{'uri':True}}};settings.DATABASE_ROUTERS=[]
 settings.SECRET_KEY='isolated-report-ui-only';settings.EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
 settings.PAYOS_CLIENT_ID=settings.PAYOS_API_KEY=settings.PAYOS_CHECKSUM_KEY=''
 from django.db.backends.base.base import BaseDatabaseWrapper
 original=BaseDatabaseWrapper.ensure_connection
 def guard(db):
  if db.vendor!='sqlite' or db.alias!='default' or db.settings_dict['NAME']!=memory:raise RuntimeError('Only this SQLite memory database allowed')
  return original(db)
 with patch.object(BaseDatabaseWrapper,'ensure_connection',guard),patch.object(socket.socket,'connect',side_effect=RuntimeError('Python network forbidden')):
  import django
  django.setup()
  from django.core.management import call_command
  from django.db import connections
  from django.test import RequestFactory
  from django.template.loader import render_to_string
  from django.utils import timezone as tz
  from accounts.models import User,Customer
  from services.models import ServiceCategory,Service
  from employees.models import Employee,EmployeeService,EmployeeSchedule
  from appointments.models import Appointment
  from billing.models import Invoice,InvoiceDetail,Payment
  from reviews.models import Review
  from dashboard.views import summary
  from tools.check_admin_promotions_ui import CHROME_CHECK
  call_command('migrate',verbosity=0,interactive=False);call_command('check')
  admin=User.objects.create_superuser('reports_admin','reports-admin@example.test',None)
  user=User.objects.create_user('reports_customer','reports-customer@example.test',None)
  customer=Customer.objects.create(user=user,full_name='Khách kiểm thử báo cáo',phone='0000000000')
  category=ServiceCategory.objects.create(name='Danh mục kiểm thử')
  services=[Service.objects.create(category=category,name=n,description='Fixture cô lập',price=390000,duration_minutes=60) for n in ['Massage đá nóng thư giãn toàn thân','Chăm sóc da chuyên sâu','Chăm sóc da chuyên sâu']]
  employee=Employee.objects.create(full_name='Chuyên viên kiểm thử',specialty='Kiểm thử')
  for s in services:EmployeeService.objects.create(employee=employee,service=s)
  def appointment(day,hour,service,status='confirmed'):
   day=date.fromisoformat(day)
   if not EmployeeSchedule.objects.filter(employee=employee,work_date=day).exists():EmployeeSchedule.objects.create(employee=employee,work_date=day,start_time=time(8),end_time=time(20))
   return Appointment.objects.create(customer=customer,employee=employee,service=service,appointment_date=day,start_time=time(hour),end_time=time(hour+1),status=status)
  def invoice(a,amount=390000,discount=0):
   i=Invoice.objects.create(appointment=a,subtotal=amount,discount_amount=discount,total_amount=amount-discount)
   InvoiceDetail.objects.create(invoice=i,service=a.service,service_name_snapshot=a.service.name,unit_price=amount,line_total=amount)
   return i
  def pay(i,amount,paid_at):
   p=Payment.objects.create(invoice=i,payment_method='spa',status='success',amount=amount,paid_at=paid_at)
   i.payment_status='paid';i.save();return p
  zone=ZoneInfo('Asia/Ho_Chi_Minh')
  october=[]
  for day,hour in [('2026-10-21',8),('2026-10-23',14),('2026-10-23',16),('2026-10-26',8)]:october.append(appointment(day,hour,services[0]))
  invoice(october[1]);invoice(october[2]);i=invoice(october[3],390000,39000);pay(i,351000,datetime(2026,10,24,0,5,tzinfo=zone))
  for status in ('cancelled','cancelled'):Payment.objects.create(invoice=i,payment_method='spa',status=status,amount=351000)
  Appointment.objects.filter(pk__in=[a.pk for a in october]).update(status='completed')
  rich=[appointment('2026-09-15',9+n,services[1] if n<3 else services[2]) for n in range(5)]
  for a,amount,stamp in zip(rich[:4],[100000,200000,300000,400000],[datetime(2026,9,20,0,0,tzinfo=zone),datetime(2026,9,20,23,59,59,999999,tzinfo=zone),datetime(2026,9,21,0,0,tzinfo=zone),datetime(2026,9,19,23,59,59,999999,tzinfo=zone)]):pay(invoice(a,amount),amount,stamp)
  for status in ('pending','cancelled','review'):Payment.objects.create(invoice=Invoice.objects.get(appointment=rich[0]),payment_method='spa',amount=100000,status=status,paid_at=datetime(2026,9,20,12,tzinfo=zone))
  Payment.objects.create(invoice=Invoice.objects.get(appointment=rich[0]),payment_method='spa',amount=100000,status='success',requires_review=True,paid_at=datetime(2026,9,20,12,tzinfo=zone))
  Appointment.objects.filter(pk__in=[a.pk for a in rich[:2]]).update(status='completed');Appointment.objects.filter(pk=rich[4].pk).update(status='cancelled')
  for a,rating in zip(rich[:2],[5,2]):
   a.refresh_from_db();r=Review.objects.create(appointment=a,customer=customer,service=a.service,rating=rating,comment='Đánh giá kiểm thử')
   Review.objects.filter(pk=r.pk).update(created_at=datetime(2026,9,15,12,tzinfo=zone))
  rf=RequestFactory();serverToday=tz.localdate().isoformat()
  def data(params):
   req=rf.get('/api/dashboard/',params);req.user=admin;response=summary(req)
   return response.status_code,json.loads(response.content)
  snapshots={}
  for key,params,expected in [('october',{'start':'2026-10-01','end':'2026-10-31'},(351000,4,0)),('november',{'start':'2026-11-01','end':'2026-11-10'},(0,0,0)),('rich',{'start':'2026-09-01','end':'2026-09-30'},(1000000,5,2)),('midnight',{'start':'2026-09-20','end':'2026-09-20'},(300000,0,0))]:
   status,d=data(params);assert status==200 and (float(d['revenue']),d['appointments'],d['reviewCount'])==expected
   assert sum(float(r['revenue']) for r in d['report'])==float(d['revenue'])
   assert sum(r['count'] for r in d['statuses'])==d['appointments']
   snapshots[key]=d
  free=Service.objects.create(category=category,name='Dịch vụ tặng trải nghiệm',description='Fixture zero-value receipt',price=0,duration_minutes=60)
  EmployeeService.objects.create(employee=employee,service=free)
  free_app=appointment('2026-07-31',9,free);pay(invoice(free_app,0),0,datetime(2026,8,15,10,tzinfo=zone))
  status,zero=data({'start':'2026-08-01','end':'2026-08-31'})
  assert status==200 and len(zero['daily'])==1 and float(zero['revenue'])==0 and len(zero['report'])==1
  snapshots['zero-value-valid-receipt']=zero
  baseline=(Appointment.objects.count(),Invoice.objects.count(),Payment.objects.count(),Review.objects.count())
  tracked=['templates/pages/admin-reports.html','static/js/live-reports.js','static/css/admin-reports-luxury.css','dashboard/views.py','templates/pages/admin-reviews.html','static/js/live-admin-reviews.js']
  hashes={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in tracked}
  html=render_to_string('pages/admin-reports.html',{'auth_ui':{},'live_catalog':{'services':[],'products':[],'staff':[]},'live_promotions':{'items':[]},'csrf_token':'test-token'})
  html=re.sub(r'<script src="[^\"]*/js/auth\.js"[^>]*></script>','',html)
  boot="window.reportErrors=[];window.reportRequests=[];window.reportFailNext=false;window.addEventListener('error',e=>reportErrors.push(e.message));window.addEventListener('unhandledrejection',e=>reportErrors.push(String(e.reason)));window.spaAuth={allowed:true,isAuthenticated:()=>true,getSession:()=>({role:'Admin'})};const nativeFetch=window.fetch;window.fetch=(url,opt)=>{reportRequests.push(String(url));if(reportFailNext){reportFailNext=false;return Promise.resolve(new Response(JSON.stringify({error:'Lỗi tải báo cáo kiểm thử.'}),{status:503,headers:{'Content-Type':'application/json'}}));}return nativeFetch(url,opt);};"
  html=html.replace('<script src="/static/js/admin.js"','<script>'+boot+'</script><script src="/static/js/admin.js"')
  html=html.replace('</body>','<div style="position:fixed;left:8px;bottom:6px;z-index:99999;background:#fff8f1;color:#3a2419;border:1px solid #c6a07e;border-radius:6px;padding:4px 8px;font:11px sans-serif">DỮ LIỆU KIỂM THỬ · SQLite bộ nhớ</div><script>const serverToday='+json.dumps(serverToday)+';'+CHECKS+'</script></body>')
  requests={'api_get':0,'post':0}
  class Handler(BaseHTTPRequestHandler):
   def log_message(self,*args):pass
   def do_POST(self):requests['post']+=1;self.send_error(405)
   def do_GET(self):
    if self.client_address[0]!='127.0.0.1' or self.headers.get('Host')!='127.0.0.1:'+str(self.server.server_port):self.send_error(403);return
    url=urlsplit(self.path);code=200
    if url.path=='/admin-reports.html':body=html.encode();mime='text/html; charset=utf-8'
    elif url.path=='/api/dashboard/':
     requests['api_get']+=1;code,payload=data({k:v[0] for k,v in parse_qs(url.query).items()});body=json.dumps(payload,ensure_ascii=False).encode();mime='application/json; charset=utf-8'
    elif url.path.startswith('/static/'):
     path=(ROOT/'static'/unquote(url.path[len('/static/'):])).resolve()
     if not path.is_relative_to((ROOT/'static').resolve()) or not path.is_file():self.send_error(404);return
     body=path.read_bytes();mime=mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
    else:self.send_error(404);return
    self.send_response(code);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
  server=HTTPServer(('127.0.0.1',0),Handler)
  def serve():
   try:server.serve_forever(poll_interval=.1)
   finally:connections.close_all()
  worker=threading.Thread(target=serve,daemon=True);worker.start()
  output=ROOT/'docs'/('reports-isolated-ui-'+datetime.now(zone).strftime('%Y%m%d-%H%M%S'));output.mkdir(parents=True,exist_ok=False)
  print('SQLite Reports fixture ready; MySQL forbidden. Evidence:',output,flush=True)
  chrome=CHROME_CHECK.replace("for(let i=0;i<100&&!fs.existsSync(portFile);i++)await sleep(100);\n const [port,path]=fs.readFileSync(portFile,'utf8').trim().split(/\\r?\\n/);", "let portText='';for(let i=0;i<100;i++){try{portText=fs.readFileSync(portFile,'utf8').trim();if(portText.split(/\\r?\\n/).length>=2)break;}catch{}await sleep(100);}\n const [port,path]=portText.split(/\\r?\\n/);")
  chrome=chrome.replace("msg.error?reject(Error(msg.error.message)):resolve(msg.result);}};", "msg.error?reject(Error(msg.error.message)):resolve(msg.result);}if(msg.method==='Fetch.requestPaused'){const p=msg.params;const allowed=p.request.method==='GET'&&new URL(p.request.url).origin===new URL(config.url).origin;call(allowed?'Fetch.continueRequest':'Fetch.failRequest',allowed?{requestId:p.requestId}:{requestId:p.requestId,errorReason:'BlockedByClient'}).catch(()=>{});}};")
  chrome=chrome.replace("await call('Page.enable');", "await call('Fetch.enable',{patterns:[{urlPattern:'*',requestStage:'Request'}]});await call('Page.enable');").replace('i<160','i<600').replace('escape:window.__requestEscape}', 'escape:window.__requestEscape,shot:window.__reportShot}')
  chrome=chrome.replace("if(state&&JSON.parse(state).result)break;", """if(state&&JSON.parse(state).shot){const s=JSON.parse(state).shot,m=await call('Page.getLayoutMetrics');const {data:png}=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip:{x:0,y:0,width:config.width,height:m.cssContentSize.height,scale:1}});fs.writeFileSync(config.output+'/'+s.name+'-'+config.width+'.png',Buffer.from(png,'base64'));await call('Runtime.evaluate',{expression:'window.__reportShot=null'});}if(state&&JSON.parse(state).result)break;""")
  results=[]
  try:
   with tempfile.TemporaryDirectory(prefix='annhien-reports-ui-') as temp:
    helper=Path(temp)/'chrome.cjs';helper.write_text(chrome,encoding='utf-8')
    for width in (1440,768,500,390):
     if any(a.startswith('--width=') for a in sys.argv) and '--width='+str(width) not in sys.argv:continue
     cfg=dict(profile=str(Path(temp)/str(width)),width=width,url=f'http://127.0.0.1:{server.server_port}/admin-reports.html?start=2026-09-01&end=2026-09-30',output=str(output),screenshot=str(output/f'final-{width}.png'),dom=str(Path(temp)/f'{width}.html'))
     r=subprocess.run([r'D:\node\node.exe',str(helper)],input=json.dumps(cfg),capture_output=True,encoding='utf-8',errors='replace',timeout=100)
     print(width,r.stdout.strip() or 'NO RESULT',flush=True)
     if r.returncode:print(r.stderr[-1500:]);raise RuntimeError('Reports UI failed')
     results.append(json.loads(r.stdout.strip()))
   assert baseline==(Appointment.objects.count(),Invoice.objects.count(),Payment.objects.count(),Review.objects.count()) and requests['post']==0
   assert all(hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==digest for f,digest in hashes.items())
   (output/'results.json').write_text(json.dumps({'database':'SQLite shared memory ONLY','results':results,'read_only_http':requests,'fixture_unchanged':True,'source_unchanged':True,'api_snapshots':snapshots},ensure_ascii=False,indent=2),encoding='utf-8')
   print('PASS: GET-only UI, fixture/source unchanged, no MySQL. Report:',output/'results.json',flush=True)
   return 0
  finally:server.shutdown();worker.join(5);server.server_close();connections.close_all()
if __name__=='__main__':raise SystemExit(main())
