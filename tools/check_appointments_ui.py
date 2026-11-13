"""Isolated browser smoke test: no database, all API requests mocked."""
import os, re, subprocess, tempfile, sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.template.loader import render_to_string
ROOT=Path(__file__).resolve().parents[1]
with patch('django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection', side_effect=RuntimeError('DB forbidden')):
    html=render_to_string('pages/admin-appointments.html', {'auth_ui':{},'live_catalog':{},'live_promotions':{}})
html=html.replace('</body>', '<input type="hidden" name="csrfmiddlewaretoken" value="isolated-test-token"></body>')
html=re.sub(r'<script\b[^>]*>.*?</script>', '', html, flags=re.S)
html=html.replace('/static/',(ROOT/'static').as_uri()+'/')
mock='''
window.spaAuth={allowed:true,isAuthenticated:()=>true,getSession:()=>({role:'Admin'})};
window.spaCatalog={staff:[{id:2,name:'Chuyên viên thử',serviceIds:[1]}]};
let writes=0;const posted=[];
const item={id:4,customer:'Khách thử',service:'Dịch vụ thử',serviceId:1,employee:'Chuyên viên',employeeId:1,date:'2026-11-20',time:'08:00',end:'09:00',status:'confirmed',statusLabel:'Đã xác nhận',updatedAt:'v1',canConfirm:false,canComplete:false,canCancel:true,canNoShow:false,canReassign:true};
window.fetch=async(path,options)=>{if(options?.method==='POST'){writes++;posted.push(Object.fromEntries(options.body));item.updatedAt='v'+(writes+1);return {ok:true,json:async()=>({item})};}return {ok:true,json:async()=>path.includes('admin-detail')?{item:{...item},history:[]}:path.includes('/admin/employees')?{items:[{id:1,name:'Chuyên viên'}]}:{items:Array.from({length:6},(_,i)=>({...item,id:i+1}))}}};
'''
tests='''
(async()=>{const wait=()=>new Promise(r=>setTimeout(r,50));await wait();
let checks=0;const check=(ok,msg)=>{if(!ok)throw Error(msg);checks++;};
try{
check(document.querySelectorAll('#ops-rows tr').length===5,'page size');
check(document.querySelector('#ops-rows').textContent.includes('LH-000004'),'code');
check(document.querySelector('#ops-rows').textContent.includes('20/11/2026'),'date');
document.querySelector('[data-appointment-page="2"]').click();check(document.querySelectorAll('#ops-rows tr').length===1,'page 2');
const search=document.querySelector('#ops-search');search.value='LH-000004';search.dispatchEvent(new Event('input',{bubbles:true}));check(document.querySelectorAll('#ops-rows tr').length===1,'search');
search.value='missing';search.dispatchEvent(new Event('input',{bubbles:true}));check(!document.querySelector('#ops-empty').hidden,'empty');
document.querySelector('#ops-reset').click();check(document.querySelectorAll('#ops-rows tr').length===5,'reset');
const date=document.querySelector('.appointment-date-control input[type=text]');date.value='31/02/2026';date.dispatchEvent(new Event('input',{bubbles:true}));check(document.querySelectorAll('#ops-rows tr').length===0,'invalid date');document.querySelector('#ops-reset').click();
document.querySelector('[data-appointment]:not([data-readonly])').click();await wait();
const form=document.querySelector('#ops-dialog form');check(!!form,'modal');check(!form.querySelector('option[value=no_show]'),'permissions');
const change=(el,value)=>{el.value=value;el.dispatchEvent(new Event('change',{bubbles:true}));};
const cancel=(f,value='other')=>{change(f.elements.action,'cancel');change(f.elements.cancel_reason,value);};
const typeReason=(f,value)=>{f.elements.reason.value=value;f.elements.reason.dispatchEvent(new Event('input',{bubbles:true}));};
check(form.querySelector('[data-current-employee] select').disabled&&form.querySelector('[data-reason]').hidden,'initial employee and cancellation controls');
check(!document.querySelector('#ops-dialog').textContent.includes('Ghi chú và hóa đơn'),'processing omits supplemental accordion');
const assignment=form.querySelector('.appointment-assignment');
const current=form.querySelector('[data-current-employee]').getBoundingClientRect();
const status=form.elements.action.closest('label').getBoundingClientRect();
check(innerWidth>700?Math.abs(current.top-status.top)<2:current.bottom<=status.top,'responsive employee and status grid');
const toggle=form.querySelector('[data-reassign-toggle]');toggle.click();check(!form.querySelector('[data-reassign-fields]').disabled,'consent fields');
check(form.elements.action.disabled&&!form.elements.employee.disabled,'reassignment keeps status');
check(form.elements.consent_at.getBoundingClientRect().width>100,'consent date input width');
const scroll=document.querySelector('#ops-dialog .admin-service-modal-scroll');
check(scroll.scrollWidth<=scroll.clientWidth+1&&assignment.scrollWidth<=assignment.clientWidth+1,'modal has no horizontal overflow');
check(!form.elements.consent.checked,'consent not automatic');check(!form.checkValidity(),'incomplete consent blocked');
form.elements.employee.value='2';form.elements.consent.checked=true;form.elements.consent_method.value='phone';form.elements.consent_note.value='Khách đồng ý';form.elements.consent_at.value='2026-11-19T08:00';form.elements.reassign_reason.value='Lý do thử';
toggle.click();check(form.querySelector('[data-reassign-fields]').disabled,'unchecked disables fields');check(!new FormData(form).has('employee')&&!new FormData(form).has('consent'),'unchecked omits fields');check(!form.elements.consent.checked&&!form.elements.consent_note.value,'unchecked clears consent');
cancel(form,'');check(!form.querySelector('[data-reason]').hidden&&toggle.disabled,'cancellation disallows reassignment');
check(form.elements.reason.getBoundingClientRect().height>0&&!form.elements.reason.required,'detail visible before selecting a reason');
change(form.elements.cancel_reason,'customer');check(form.checkValidity()&&!form.elements.reason.disabled&&!form.elements.reason.required,'preset detail optional');
typeReason(form,'a'.repeat(500));check(!form.checkValidity(),'combined cancellation reason respects limit');
change(form.elements.cancel_reason,'other');check(form.elements.reason.required&&!form.checkValidity(),'other cancellation reason required');
typeReason(form,'Khách không đến');check(!form.checkValidity(),'no-show cannot bypass verification');typeReason(form,'Lý do thử');form.requestSubmit();check(!form.querySelector('[data-confirm]').hidden,'confirmation');check(writes===0,'no writes');await wait();const rect=document.querySelector('#ops-dialog').getBoundingClientRect();check(rect.width<=innerWidth&&rect.height<=innerHeight&&rect.top>=0&&rect.bottom<=innerHeight,'modal viewport');document.documentElement.style.scrollBehavior='auto';window.scrollTo(0,0);
check(!document.querySelector('#ops-employee'),'no employee filter');
form.querySelector('[data-commit]').click();form.querySelector('[data-commit]').click();await wait();await wait();
check(writes===1,'duplicate click guarded');check(posted[0].status==='cancelled'&&posted[0].reason==='Lý do thử'&&!('employee' in posted[0])&&!('consent' in posted[0]),'cancel payload');
let f=document.querySelector('#ops-dialog form');f.querySelector('[data-reassign-toggle]').click();
f.elements.employee.value='2';f.elements.consent.checked=true;f.elements.consent_method.value='phone';f.elements.consent_note.value='Khách đồng ý';f.elements.consent_at.value='2026-11-19T08:00';f.elements.reassign_reason.value='Ngoại lệ';
f.requestSubmit();f.querySelector('[data-commit]').click();await wait();await wait();
check(writes===2,'reassignment sent once');check(posted[1].employee==='2'&&posted[1].status==='confirmed'&&posted[1].expected_employee==='1'&&posted[1].expected_updated_at==='v2'&&posted[1].consent==='on'&&posted[1].consent_method==='phone'&&posted[1].consent_note==='Khách đồng ý'&&posted[1].consent_at==='2026-11-19T08:00:00+07:00'&&posted[1].reason==='Ngoại lệ','reassignment contract');
f=document.querySelector('#ops-dialog form');cancel(f);typeReason(f,'Thử xung đột');f.requestSubmit();item.updatedAt='conflict';f.querySelector('[data-commit]').click();await wait();await wait();
check(writes===2,'stale version no POST');check(document.querySelector('.appointment-feedback').textContent.includes('Lịch đã thay đổi'),'conflict visible');check(document.querySelector('#ops-dialog form').elements.action.value==='','fresh confirmation required');
const openProcess=async()=>{document.querySelector('#ops-dialog').close();document.querySelector('[data-appointment]:not([data-readonly])').click();await wait();return document.querySelector('#ops-dialog form');};
item.status='pending';item.statusLabel='Chờ xác nhận';item.canConfirm=true;item.canCancel=true;item.canReassign=false;
f=await openProcess();check(f.querySelector('[data-reassign-toggle]').disabled,'reassignment permission');
check(f.elements.action.value===''&&[...f.elements.action.options].map(x=>x.textContent).join('|')==='Chờ xác nhận|Đã xác nhận|Đã hủy','pending status labels and default');
cancel(f,'customer');typeReason(f,'Khách đã gọi');f.requestSubmit();f.querySelector('[data-commit]').click();await wait();await wait();
check(posted.at(-1).status==='cancelled'&&posted.at(-1).reason==='Khách yêu cầu hủy: Khách đã gọi'&&!('cancel_reason' in posted.at(-1)),'preset detail uses existing reason field');
f=await openProcess();change(f.elements.action,'confirm');f.requestSubmit();f.querySelector('[data-commit]').click();await wait();await wait();check(posted.at(-1).status==='confirmed'&&!('employee' in posted.at(-1))&&!('consent' in posted.at(-1)),'confirm preserves employee');
item.status='confirmed';item.statusLabel='Đã xác nhận';item.canConfirm=false;item.canComplete=true;
f=await openProcess();f.elements.action.value='complete';f.elements.action.dispatchEvent(new Event('change'));f.requestSubmit();f.querySelector('[data-commit]').click();await wait();await wait();check(posted.at(-1).status==='completed','complete contract');
item.canComplete=false;item.canNoShow=true;item.canCancel=true;
f=await openProcess();cancel(f,'no_show');check(f.elements.reason.getBoundingClientRect().height>0&&f.elements.reason.disabled,'no-show detail visible with canonical reason');check(!f.checkValidity(),'no-show verification required');f.elements.no_show_confirm.click();f.requestSubmit();f.querySelector('[data-commit]').click();await wait();await wait();check(posted.at(-1).no_show==='true'&&posted.at(-1).reason==='Khách không đến'&&posted.at(-1).status==='cancelled','no show contract');
item.status='cancelled';item.canNoShow=false;item.canCancel=false;item.cancelReason='Lý do đã lưu';item.cancelledBy='Admin thử';item.cancelledAt='2026-11-20T08:30:00+07:00';
f=await openProcess();check(!f,'cancelled readonly');check(document.querySelector('#ops-dialog').textContent.includes('Lý do đã lưu')&&document.querySelector('#ops-dialog').textContent.includes('Admin thử'),'cancellation audit');
document.querySelector('#ops-dialog').close();item.status='completed';item.statusLabel='Đã hoàn thành';item.canCancel=false;item.canReassign=false;item.invoiceId=3;item.invoiceStatus='Đã thanh toán';item.note='Ghi chú kiểm thử';
document.querySelector('[data-readonly]').click();await wait();check(!document.querySelector('#ops-dialog form'),'completed readonly');check(document.querySelector('#ops-dialog a').href.includes('HD-3'),'invoice preserved');check(document.querySelector('#ops-dialog h3').textContent==='Khách thử','customer heading');check(document.querySelector('#ops-dialog .appointment-history:not([open])'),'empty history collapsed');
check(document.querySelector('#ops-dialog').textContent.includes('Ghi chú kiểm thử'),'notes preserved in readonly view');
document.body.insertAdjacentHTML('beforeend',`<pre id="test-result">PASS ${checks}</pre>`);
}catch(e){document.body.insertAdjacentHTML('beforeend','<pre id="test-result">FAIL '+e.message+'</pre>');}})();
'''
html=html.replace('</body>','<script>'+ (ROOT/'static/js/ui.js').read_text(encoding='utf-8')+'</script><script>'+mock+'</script><script>'+ (ROOT/'static/js/admin.js').read_text(encoding='utf-8')+'</script><script>'+ (ROOT/'static/js/live-admin.js').read_text(encoding='utf-8')+'</script><script>'+tests+'</script></body>')
with tempfile.TemporaryDirectory(prefix='annhien-ui-', dir=ROOT/'staticfiles') as temp:
    fixture=Path(temp)/'admin-appointments.html';fixture.write_text(html,encoding='utf-8')
    for width in (1440,768,500):
        result=subprocess.run([r'C:\Program Files\Google\Chrome\Application\chrome.exe','--headless','--disable-gpu','--force-device-scale-factor=1','--disable-smooth-scrolling','--no-first-run','--no-default-browser-check','--allow-file-access-from-files','--user-data-dir='+str(Path(temp)/str(width)),f'--window-size={width},1000','--virtual-time-budget=3000','--screenshot='+str(ROOT/'staticfiles'/f'appointments-ui-{width}.png'),'--dump-dom',fixture.as_uri()],capture_output=True,encoding='utf-8',errors='replace',timeout=35)
        found=re.search(r'<pre id="test-result">(PASS [0-9]+|FAIL [^<]+)</pre>',re.sub(r"<script\b[^>]*>.*?</script>", "", result.stdout, flags=re.S))
        print(width,found.group(1) if found else 'NO RESULT')
        if not found: print(result.stderr[-1500:]); print(result.stdout[-700:])
        if not found or not found.group(1).startswith('PASS'):raise SystemExit(1)
