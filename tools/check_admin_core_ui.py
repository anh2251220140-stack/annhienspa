"""Core UI checks with synthetic API responses; no database connections."""
import os,sys,re,tempfile,subprocess
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from django.template.loader import render_to_string
mock=r'''
window.spaAuth={allowed:true,isAuthenticated:()=>true,getSession:()=>({role:'Admin'})};window.spaCatalog={services:[],staff:[]};
let writes=0,failNextWrite=false;
const accounts=Array.from({length:7},(_,i)=>({id:i+1,username:'account'+i,email:'test'+i+'@example.invalid',role:i?'User':'Admin',active:true,joined:'2026-11-07',canToggle:!!i}));
const customers=accounts.slice(1).map(a=>({...a,name:'Khách thử '+a.id,phone:'',skin:'',needs:[],interests:[],budget:null,avatar:''}));
const dashboard={today:'2026-11-07',customers:6,periodCustomers:2,appointments:4,revenue:'351000',todayCount:2,activeServices:3,monthly:[{month:'2026-11',total:'351000'}],statuses:[{status:'completed',count:4}],popular:[{service__name:'Dịch vụ thử',count:4}],recent:[{id:4,customer:'Khách thử',service:'Dịch vụ thử',employee:'Chuyên viên thử',date:'2026-11-07',time:'08:00',status:'completed'}]};
window.fetch=async(path,options)=>{const u=new URL(path,'http://fixture.invalid');let data;
if(u.pathname==='/api/dashboard/'){const start=u.searchParams.get('start'),end=u.searchParams.get('end');data={...dashboard,start,end};if(start==='2000-01-01')data={...data,periodCustomers:0,appointments:0,revenue:0,monthly:[],statuses:[],popular:[],recent:[]};}
else if(options?.method==='POST'){if(failNextWrite){failNextWrite=false;return {ok:false,json:async()=>({error:'Lỗi giả lập an toàn'})};}writes++;const a=accounts.find(a=>a.id===Number(u.pathname.split('/')[4]));if(!a?.canToggle)throw Error('protected');a.active=options.body.get('action')==='unlock';data={item:a};}
else if(/accounts\/\d+\//.test(u.pathname))data={item:accounts.find(a=>a.id===Number(u.pathname.split('/')[4]))};
else {const isAccount=u.pathname.includes('accounts'),all=isAccount?accounts:customers;
const q=u.searchParams.get('search')||'',role=u.searchParams.get('role'),status=u.searchParams.get('status');const filtered=all.filter(a=>JSON.stringify(a).includes(q)&&(!role||a.role===role)&&(!status||a.active===(status==='active')));const pages=Math.max(1,Math.ceil(filtered.length/5)),page=Math.min(Number(u.searchParams.get('page')||1),pages);data={items:filtered.slice((page-1)*5,page*5),page,pages,total:filtered.length,stats:{total:accounts.length,active:accounts.filter(a=>a.active).length,locked:accounts.filter(a=>!a.active).length}};}
return {ok:true,json:async()=>JSON.parse(JSON.stringify(data))};};
window.spaLive={api:async path=>(await fetch(path)).json()};
'''
tests=r'''
(async()=>{let count=0;const wait=()=>new Promise(r=>setTimeout(r,70));const check=(ok,msg)=>{if(!ok)throw Error(msg);count++;};try{await wait();await wait();
const $=s=>document.querySelector(s),kind=document.body.dataset.fixture;
if(kind==='accounts'){
check($('#accounts-rows').children.length===5,'page size');check($('#accounts-rows').textContent.includes('TK-001'),'code');check($('#accounts-rows').textContent.includes('07/11/2026'),'date');check(!$('[data-toggle="1"]'),'admin protected');
$('[data-view="1"]').click();await wait();
check($('dialog [data-error]').hidden,'view has no empty error frame');
const modal=$('dialog'),rect=modal.getBoundingClientRect();check(rect.top>=0&&rect.bottom<=innerHeight,'view modal fits viewport');
const body=modal.querySelector('.admin-dialog-body');const long=document.createElement('p');long.textContent='Nội dung dài thử cuộn. '.repeat(300);body.append(long);
check(body.scrollHeight>body.clientHeight,'long details scroll');check(modal.querySelector('.admin-dialog-actions').getBoundingClientRect().bottom<=innerHeight,'footer visible');modal.close();

$('[data-toggle="2"]').click();await wait();check(document.querySelector('dialog').open&&writes===0,'confirmation required');check($('dialog [data-error]').hidden,'confirmation has no empty frame');failNextWrite=true;$('[data-confirm]').click();await wait();check(!$('dialog [data-error]').hidden&&writes===0&&!$('[data-confirm]').disabled,'failed request visible and retry allowed');$('[data-confirm]').click();await wait();check(writes===1&&!accounts[1].active,'mock lock');
$('[data-toggle="2"]').click();await wait();$('[data-confirm]').click();await wait();check(writes===2&&accounts[1].active,'mock unlock');
$('#accounts-search').value='missing';$('#accounts-search').dispatchEvent(new Event('input'));await wait();check(!$('#accounts-empty').hidden,'empty');$('#accounts-search').value='';$('#accounts-search').dispatchEvent(new Event('input'));await wait();$('#accounts-pagination [data-page="2"]').click();await wait();check($('#accounts-rows').children.length===2,'page two');
const cells=$('#accounts-rows tr').children,roleBadge=cells[3].firstElementChild.getBoundingClientRect(),statusBadge=cells[4].firstElementChild.getBoundingClientRect();check(roleBadge.right<statusBadge.left,'role status badges separated');}
if(kind==='customers'){
check($('#customers-rows').children.length===5,'customer page size');check(!$('#customer-profile input, #customer-profile button'),'readonly');check($('#customer-profile .admin-care-facts'),'care layout');check($('#customer-profile').textContent.includes('07/11/2026'),'profile date');
const second=document.querySelectorAll('[data-customer]')[1];second.click();check($('#customer-profile h2').textContent==='Khách thử 3','selection');check($('#customer-profile .admin-customer-initials').textContent===document.querySelector('[aria-pressed=true] .admin-customer-initials').textContent,'avatar consistency');
$('#customers-search').value='missing';$('#customers-search').dispatchEvent(new Event('input'));await wait();check(!$('#customers-empty').hidden&&!$('#customer-profile h2'),'empty clears profile');check(writes===0,'no customer write');$('#customers-search').value='';$('#customers-search').dispatchEvent(new Event('input'));await wait();check($('#customer-profile h2'),'restore profile after filter');$('#customers-pagination [data-page="2"]').click();await wait();check($('#customers-rows').children.length===1&&$('#customer-profile h2').textContent==='Khách thử 7','customer page two details');$('#customers-search').value='missing';$('#customers-search').dispatchEvent(new Event('input'));await wait();check($('#customers-pagination').textContent.includes('0 / 0')&&[...document.querySelectorAll('#customers-pagination button')].every(b=>b.disabled),'empty pager disabled');$('#customers-search').value='';$('#customers-search').dispatchEvent(new Event('input'));await wait();
check(!$('#customers-tier'),'tier removed');check($('#customers-rows .admin-customer-skin').textContent==='Chưa xác định','skin retained');
$('[data-customer-tab=chat]').click();check(!$('#admin-chat').hidden&&$('#customer-profile-panel').hidden,'chat tab');check($('#admin-chat').textContent.includes('Chưa kết nối backend'),'honest FR24 placeholder');$('[data-customer-tab=profile]').click();check($('#admin-chat').hidden&&!$('#customer-profile-panel').hidden,'profile tab restored');}
if(kind==='dashboard'){
check(document.querySelectorAll('.admin-stat-card').length===4,'four KPIs');check($('[data-stat-customers]').textContent==='2','unique owners API KPI');check($('[data-stat-revenue]').textContent.includes('351'),'API revenue');check($('#admin-revenue-chart svg')&&$('#admin-status-chart svg')&&$('#admin-services-chart li'),'three charts');check($('#admin-recent-appointments').children.length===1,'real recent count');check($('#admin-recent-appointments').textContent.includes('LH-000004'),'recent code');check($('#admin-recent-appointments').textContent.includes('07/11/2026'),'recent date');check(writes===0,'dashboard read only');
const originalChart=$('#admin-revenue-chart').innerHTML;
$('#dashboard-from').value='2000-01-01';$('#dashboard-to').value='2000-01-02';$('#dashboard-filters').requestSubmit();await wait();
check($('[data-stat-customers]').textContent==='0'&&$('[data-stat-today]').textContent==='0','period KPIs');check(!$('#admin-appointments-empty').hidden,'period empty');check($('#admin-revenue-chart').innerHTML===originalChart,'year chart independent');check($('[data-period-status]').textContent.includes('01/01/2000'),'period caption');
$('#dashboard-from').value='2000-02-01';$('#dashboard-to').value='2000-01-01';$('#dashboard-filters').requestSubmit();await wait();check(!$('#dashboard-error').hidden,'invalid period');$('#dashboard-reset').click();await wait();check($('[data-stat-today]').textContent==='4','reset month');}
check(document.documentElement.scrollWidth<=innerWidth,'no page horizontal overflow');check(!document.body.innerText.includes('Bản mẫu'),'no demo banner');document.body.insertAdjacentHTML('beforeend',`<pre id="test-result">PASS ${count}</pre>`);
}catch(e){document.body.insertAdjacentHTML('beforeend','<pre id="test-result">FAIL '+e.message+'</pre>');}})();
'''
with tempfile.TemporaryDirectory(prefix='core-ui-',dir=ROOT/'staticfiles') as temp:
 for kind in (('accounts',) if '--accounts-modal' in sys.argv else ('dashboard','accounts','customers')):
  with patch('django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection',side_effect=RuntimeError('DB forbidden')):
   html=render_to_string('pages/admin-'+kind+'.html',{'auth_ui':{},'live_catalog':{},'live_promotions':{}})
  html=re.sub(r'<script\b[^>]*>.*?</script>','',html,flags=re.S).replace('/static/',(ROOT/'static').as_uri()+'/').replace('<body class=',f'<body data-fixture="{kind}" class=')
  scripts=(ROOT/'static/js/ui.js').read_text(encoding='utf-8')+'\n;'+mock+'\n;'+(ROOT/'static/js/admin.js').read_text(encoding='utf-8')+'\n;'
  if kind!='dashboard':scripts+=(ROOT/'static/js/live-people.js').read_text(encoding='utf-8')+'\n;'
  active_tests=tests.replace("check(document.documentElement.scrollWidth<=innerWidth", "$('[data-view]').click();await wait();check(document.documentElement.scrollWidth<=innerWidth") if '--accounts-modal' in sys.argv else tests
  html=html.replace('</body>','<input type="hidden" name="csrfmiddlewaretoken" value="mock-token"><script>'+scripts+active_tests+'</script></body>')
  fixture=Path(temp)/('admin-'+kind+'.html');fixture.write_text(html,encoding='utf-8')
  for width in (1440,768,500):
   r=subprocess.run([r'C:\Program Files\Google\Chrome\Application\chrome.exe','--headless','--disable-gpu','--force-device-scale-factor=1','--disable-smooth-scrolling','--no-first-run','--no-default-browser-check','--allow-file-access-from-files','--user-data-dir='+str(Path(temp)/(kind+str(width))),f'--window-size={width},1000','--virtual-time-budget=3000','--screenshot='+str(ROOT/'staticfiles'/f'core-{kind}-{width}.png'),'--dump-dom',fixture.as_uri()],capture_output=True,encoding='utf-8',errors='replace',timeout=35)
   dom=re.sub(r'<script\b[^>]*>.*?</script>','',r.stdout,flags=re.S);found=re.search(r'<pre id="test-result">(PASS \d+|FAIL [^<]+)</pre>',dom)
   print(kind,width,found.group(1) if found else 'NO RESULT',flush=True)
   if not found or not found.group(1).startswith('PASS'):raise SystemExit(1)
