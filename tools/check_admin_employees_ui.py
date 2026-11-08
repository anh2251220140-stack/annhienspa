"""Core UI checks with synthetic API responses; no database connections."""
import os,sys,re,tempfile,subprocess
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from django.template.loader import render_to_string
mock=r'''

window.spaPromotions={referenceDate:'2026-11-08'};window.spaAuth={allowed:true,isAuthenticated:()=>true,getSession:()=>({role:'Admin'})};
const employees=Array.from({length:7},(_,i)=>({id:i+1,name:'Nhân viên '+(i+1),description:'Mô tả thử cô lập',specialty:'Chăm sóc da',email:'staff@example.invalid',phone:'0900000000',active:i!==6,image_url:'',serviceIds:[1]}));
let writes=0,failWrite=false,lastBody,lastPath,shiftCount=8;
window.fetch=async(path,options)=>{let data;
if(options?.method==='POST'){lastPath=path;lastBody=options.body;if(failWrite){failWrite=false;return {ok:false,json:async()=>({errors:{name:['Lỗi kiểm thử tên']}})};}writes++;const id=Number(path.split('/')[4]);const row=employees.find(p=>p.id===id);if(options.body.get('_toggle'))row.active=!row.active;else if(row)row.name=options.body.get('full_name');data={};}
else if(path.includes('/schedules/'))data={items:Array.from({length:shiftCount},(_,i)=>({date:'2026-11-09',start:'08:00',end:'09:00',status:i%2?'Nghỉ':'Làm việc',note:'Ghi chú ca '+i}))};else if(path.startsWith('/api/appointments/'))data={items:[{id:6,customer:'Khách thử',date:'2026-11-09',time:'08:00',end:'09:00',status:'confirmed',statusLabel:'Đã xác nhận'}]};else if(/\/\d+\//.test(path))data={html:path.includes('?view=1')?detailHTML:(path.includes("/0/")?addFormHTML:formHTML)};else data={items:employees};return {ok:true,json:async()=>data};};

'''
tests=r'''

(async()=>{let count=0;const wait=()=>new Promise(r=>setTimeout(r,70)),check=(ok,msg)=>{if(!ok)throw Error(msg);count++;},$=s=>document.querySelector(s),input=e=>e.dispatchEvent(new Event('input',{bubbles:true}));try{await wait();await wait();
check([...document.querySelectorAll('#ops-stats strong')].map(e=>e.textContent).join(',')==='7,6,1','KPI');check($('#ops-rows').children.length===5,'page size');check($('#ops-rows').textContent.includes('NV-001'),'code');check($('#ops-rows .employee-placeholder'),'fallback');
const button=$('[data-employee-view]'),svg=button.querySelector('svg');check(getComputedStyle(svg).color==='rgb(185, 144, 87)','champagne icon');const buttons=[...document.querySelectorAll('#ops-rows tr:first-child .admin-row-actions button')];check(buttons.every(b=>Math.abs(b.getBoundingClientRect().top-buttons[0].getBoundingClientRect().top)<1),'three actions same row');check(svg.getBoundingClientRect().width===18,'icon size');
check($('#ops-rows tr').children.length===6,'six table cells');
check(!/Admin Core|Admin Operations|Finance & Quality/i.test($('.admin-nav').textContent),'Vietnamese sidebar');
$('[data-employee-page="1"]').click();check($('#ops-rows').children.length===2,'page 2');$('#ops-search').value='NV-002';input($('#ops-search'));check($('#ops-rows').children.length===1,'search reset');$('#ops-status').value='inactive';input($('#ops-status'));check(!$('#ops-empty').hidden,'combined filter');$('#ops-reset').click();check($('#ops-rows').children.length===5,'reset');check($('#ops-stats strong').textContent==='7','KPI independent');
$('[data-employee-view="1"]').click();await wait();check($('#ops-dialog').textContent.includes('NV-001'),'detail code');check(getComputedStyle($('#ops-dialog .employee-summary .employee-placeholder')).borderRadius==='50%','round avatar');check(![...document.querySelectorAll('#ops-dialog dt')].some(e=>['Tải ảnh đại diện','Hình minh họa','Họ và tên'].includes(e.textContent.trim())),'no repeated avatar or technical fields');check(!$('#ops-dialog input'),'readonly');check($('#ops-dialog').getBoundingClientRect().bottom<=innerHeight,'view fits');$('#ops-dialog [data-close]').click();
$('[data-employee-edit="1"]').click();await wait();check($('#ops-dialog [name="avatar"]')&&$('#ops-dialog [name="specialty"]'),'fields retained');check($('#ops-dialog [data-link-summary]').textContent.includes('Đã chọn 1'),'selected count');
const search=$('[data-link-search]');search.scrollIntoView({block:'center'});await wait();
const searchRect=search.getBoundingClientRect();check(searchRect.width>200&&searchRect.height>=40,'search full-size');search.focus();check(document.activeElement===search,'search focusable');check(document.elementFromPoint(searchRect.left+searchRect.width/2,searchRect.top+searchRect.height/2)===search,'search not covered');
check(search.placeholder==='Nhập tên hoặc mã dịch vụ...','search placeholder');
check($('#ops-dialog .employee-file-picker').textContent.includes('Thay ảnh đại diện'),'Vietnamese file picker');check(getComputedStyle($('#ops-dialog [name="avatar"]')).opacity==='0','native file UI concealed');
check($('#ops-dialog [name="avatar-clear"]')&&!$('#ops-dialog [name="avatar-clear"]').checked,'clear initially unchecked');check($('#ops-dialog .has-current'),'edit image board');
search.value='cham soc';input(search);check([...document.querySelectorAll('#ops-dialog [name="services"]')].filter(c=>!c.closest('label').hidden).length===1,'unaccented service search');
search.value='DV-001';input(search);check(!$('#ops-dialog [name="services"][value="1"]').closest('label').hidden,'service code search');
search.value='';input(search);const second=$('#ops-dialog [name="services"][value="2"]');second.checked=true;second.dispatchEvent(new Event('change'));check($('[data-link-summary]').textContent.includes('Đã chọn 2'),'multi selection');
check($('#ops-dialog [type="submit"]').textContent.trim()==='Lưu','save label');check($('#ops-dialog .admin-dialog-actions').getBoundingClientRect().bottom<=innerHeight,'form footer');
failWrite=true;$('#ops-dialog form').requestSubmit();await wait();check(!$('#ops-dialog [data-error]').hidden&&writes===0,'validation no write');$('#ops-dialog form').requestSubmit();await wait();await wait();check(writes===1&&lastBody.getAll('services').join(',')==='1,2','exact service IDs');check(lastPath==='/api/admin/employees/1/','real API ID');
$('#ops-add').click();await wait();check(!$('#ops-dialog .employee-upload-board')&&!$('#ops-dialog [name="avatar-clear"]'),'add has no upload board');const nativeFile=$('#ops-dialog input[type="file"]');check(nativeFile.classList.contains('employee-file-simple')&&getComputedStyle(nativeFile).opacity!=='0'&&nativeFile.getBoundingClientRect().width>200,'native add file chooser visible');const addSearch=$('[data-link-search]');addSearch.scrollIntoView({block:'center'});await wait();check(addSearch.getBoundingClientRect().width>200&&addSearch.getBoundingClientRect().height>=40,'add search visible');addSearch.focus();addSearch.value='massage';input(addSearch);check(document.activeElement===addSearch,'add search receives input');$('#ops-dialog [data-close]').click();check(writes===1,'cancel no write');
$('[data-employee-schedule="1"]').click();await wait();
check($('#ops-dialog').textContent.includes('Ca đang áp dụng'),'schedule read');check($('.employee-schedule-identity').textContent.includes('NV-001')&&$('.employee-schedule-identity').textContent.includes('Nhân viên 1'),'schedule identity');check($('.employee-shift-table').textContent.includes('09/11/2026'),'shift date');check($('.employee-booked-table').textContent.includes('LH-000006'),'appointment code');
const scroller=$('.employee-shift-scroll'),head=scroller.querySelector('th');check(scroller.scrollHeight>scroller.clientHeight,'eight shifts scroll');const firstFive=[...scroller.querySelectorAll('tbody tr')].slice(0,5).reduce((n,r)=>n+r.getBoundingClientRect().height,0);check(Math.abs(scroller.clientHeight-(head.getBoundingClientRect().height+firstFive))<6,'exact five shift viewport');scroller.scrollTop=120;check(Math.abs(head.getBoundingClientRect().top-scroller.getBoundingClientRect().top)<3,'sticky header');
for(const mode of ['day','leave','weekly']){
 for(const control of ['x','cancel','escape']){
 $('[data-plan="'+mode+'"]').click();check($('#ops-dialog [data-date-display="start_date"]').placeholder==='dd/mm/yyyy','date format '+mode);if(control==='escape')$('#ops-dialog').dispatchEvent(new Event('cancel',{cancelable:true}));else if(control==='x')$('#ops-dialog header [data-close]').click();else $('#ops-dialog .admin-dialog-actions [data-close]').click();
 check($('#ops-dialog').open&&$('.employee-shift-scroll'),'child returns parent '+mode+' '+control);
 }
}
$('[data-plan="day"]').click();const day=$('[data-date-display="start_date"]');day.scrollIntoView({block:'center'});await wait();check(day.getBoundingClientRect().width>180&&day.getBoundingClientRect().height>=40,'date input visible');day.focus();check(document.activeElement===day,'date input receives focus');day.value='09/11/2026';input(day);check($('#ops-dialog [name="start_date"]').value==='2026-11-09','ISO payload date');day.value='31/02/2026';input(day);check(!day.checkValidity()&&!$('#ops-dialog [name="start_date"]').value,'invalid date rejected');day.value='09/11/2026';input(day);$('#ops-dialog [data-start]').value='08:00';$('#ops-dialog [data-end]').value='09:00';failWrite=true;$('#ops-dialog form').requestSubmit();await wait();check(JSON.parse(lastBody.get('plan')).start_date==='2026-11-09'&&JSON.parse(lastBody.get('plan')).end_date==='2026-11-09','day plan ISO serialized');check(writes===1&&!$('#ops-dialog [data-error]').hidden,'failed mock plan safe');$('#ops-dialog .admin-dialog-actions [data-close]').click();$('#ops-dialog header [data-close]').click();
for(const n of [0,1,5,6]){shiftCount=n;$('[data-employee-schedule="1"]').click();await wait();const region=$('.employee-shift-scroll');check(region.querySelectorAll('tbody tr').length===n,'all real fixture rows '+n);check((region.scrollHeight>region.clientHeight)===(n>5),'scroll threshold '+n);$('#ops-dialog header [data-close]').click();}
check(writes===1,'schedule cancel no write');
$('[data-employee-toggle="1"]').click();await wait();check(writes===1&&$('#ops-dialog').open,'toggle confirmation');$('#ops-dialog form').requestSubmit();await wait();await wait();check(writes===2&&!employees[0].active,'mock toggle');check([...document.querySelectorAll('#ops-stats strong')].map(e=>e.textContent).join(',')==='7,5,2','KPI updated');
$('#ops-search').value='missing';input($('#ops-search'));check(!$('#ops-empty').hidden&&[...document.querySelectorAll('#ops-pagination button')].every(b=>b.disabled),'empty pager');
check(document.documentElement.scrollWidth<=innerWidth,'no page overflow');check(!document.body.innerText.includes('Bản mẫu'),'no demo');if(location.hash==='#day-preview'){$('#ops-reset').click();$('[data-employee-schedule="1"]').click();await wait();$('[data-plan="day"]').click();await wait();}if(location.hash==='#schedule-preview'){$('#ops-reset').click();shiftCount=8;$('[data-employee-schedule="1"]').click();await wait();}if(location.hash==='#upload-preview'||location.hash==='#edit-upload-preview'){$('#ops-reset').click();$(location.hash==='#upload-preview'?'#ops-add':'[data-employee-edit="1"]').click();await wait();$('.employee-upload').scrollIntoView({block:'center'});await wait();}if(location.hash==='#links-preview'){$('#ops-reset').click();$('#ops-add').click();await wait();$('[data-link-search]').scrollIntoView({block:'center'});await wait();}document.body.insertAdjacentHTML('beforeend',`<pre id="test-result">PASS ${count}</pre>`);
}catch(e){document.body.insertAdjacentHTML('beforeend','<pre id="test-result">FAIL '+e.message+'</pre>');}})();

'''
with tempfile.TemporaryDirectory(prefix='employees-ui-',dir=ROOT/'staticfiles') as temp:
 for kind in ('employees',):
  with patch('django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection',side_effect=RuntimeError('DB forbidden')):
   html=render_to_string('pages/admin-'+kind+'.html',{'auth_ui':{},'live_catalog':{},'live_promotions':{}})
  html=re.sub(r'<script\b[^>]*>.*?</script>','',html,flags=re.S).replace('/static/',(ROOT/'static').as_uri()+'/').replace('<body class=',f'<body data-fixture="{kind}" class=')
  import json
  from core.business_forms import EmployeeForm
  from core.business_layout import groups_for
  with patch('django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection',side_effect=RuntimeError('DB forbidden')):
   from employees.models import Employee
   form=EmployeeForm(instance=Employee(full_name='Nhân viên 1',avatar='employees/current.jpg'));form.fields['services'].choices=[(1,'Massage đá nóng'),(2,'Chăm sóc da')];form.initial['services']=[1]
   form_html=render_to_string('partials/business_form.html',{'form':form,'module':'employees','groups':groups_for(form,'employees')})
   add=EmployeeForm();add.fields['services'].choices=[(1,'Massage đá nóng'),(2,'Chăm sóc da')]
   add_html=render_to_string('partials/business_form.html',{'form':add,'module':'employees','groups':groups_for(add,'employees')})
  if (ROOT/'media/employees/nv1_hltcskY.jpg').exists():form_html=form_html.replace('/media/employees/current.jpg',(ROOT/'media/employees/nv1_hltcskY.jpg').as_uri())
  detail_html=render_to_string('partials/employee_detail.html',{'form':form,'module':'employees','groups':groups_for(form,'employees')})
  form_script='const addFormHTML='+json.dumps(add_html)+';const formHTML='+json.dumps(form_html)+';const detailHTML='+json.dumps(detail_html)+';'
  scripts=(ROOT/'static/js/ui.js').read_text(encoding='utf-8')+'\n;'+form_script+mock+'\n;'+(ROOT/'static/js/admin.js').read_text(encoding='utf-8')+'\n;'+(ROOT/'static/js/live-schedules.js').read_text(encoding='utf-8')+'\n;'+(ROOT/'static/js/live-employees.js').read_text(encoding='utf-8')+'\n;'
  active_tests=tests.replace("check(document.documentElement.scrollWidth<=innerWidth", "$('#services-rows [data-view]').click();await wait();check(document.documentElement.scrollWidth<=innerWidth") if '--accounts-modal' in sys.argv else tests
  html=html.replace('</body>','<input type="hidden" name="csrfmiddlewaretoken" value="mock-token"><script>'+scripts+active_tests+'</script></body>')
  fixture=Path(temp)/('admin-'+kind+'.html');fixture.write_text(html,encoding='utf-8')
  for width in (1440,768,500):
   r=subprocess.run([r'C:\Program Files\Google\Chrome\Application\chrome.exe','--headless','--disable-gpu','--force-device-scale-factor=1','--disable-smooth-scrolling','--no-first-run','--no-default-browser-check','--allow-file-access-from-files','--user-data-dir='+str(Path(temp)/(kind+str(width))),f'--window-size={width},1000','--virtual-time-budget=3000','--screenshot='+str(ROOT/'staticfiles'/f'employees-{kind}-{width}.png'),'--dump-dom',fixture.as_uri()+('#day-preview' if '--day-preview' in sys.argv else '#schedule-preview' if '--schedule-preview' in sys.argv else '#upload-preview' if '--upload-preview' in sys.argv else '#edit-upload-preview' if '--edit-upload-preview' in sys.argv else '#links-preview' if '--links-preview' in sys.argv else '')],capture_output=True,encoding='utf-8',errors='replace',timeout=35)
   dom=re.sub(r'<script\b[^>]*>.*?</script>','',r.stdout,flags=re.S);found=re.search(r'<pre id="test-result">(PASS \d+|FAIL [^<]+)</pre>',dom)
   print(kind,width,found.group(1) if found else 'NO RESULT',flush=True)
   if not found:
    print('Chrome exit:',r.returncode,'output length:',len(r.stdout));print(r.stderr[-1800:]);Path(ROOT/'staticfiles/services-check-dom.html').write_text(r.stdout,encoding='utf-8')
   if not found or not found.group(1).startswith('PASS'):raise SystemExit(1)
