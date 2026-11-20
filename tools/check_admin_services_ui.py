"""Core UI checks with synthetic API responses; no database connections."""
import os,sys,re,tempfile,subprocess,argparse
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from contextlib import ExitStack
import atexit
from tools.chat_sqlite import configure
isolation=ExitStack();atexit.register(isolation.close)
folder=isolation.enter_context(tempfile.TemporaryDirectory(prefix='admin-services-ui-'))
configure(isolation,Path(folder))  # No dotenv, MySQL, external network or PayOS.
isolation.enter_context(patch('django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection',side_effect=RuntimeError('DB forbidden')))
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path)
parser.add_argument('--accounts-modal',action='store_true')
args=parser.parse_args()
OUT=args.output or Path((ROOT/'docs/services-display-current-20261119.txt').read_text(encoding='utf-8'))
if not OUT.is_absolute():OUT=ROOT/OUT
if not OUT.resolve().is_relative_to((ROOT/'docs').resolve()):raise RuntimeError('Output must stay inside project docs')
OUT.mkdir(parents=True,exist_ok=True)

from django.template.loader import render_to_string
mock=r'''

window.spaAuth={allowed:true,isAuthenticated:()=>true,getSession:()=>({role:'Admin'})};
const cats=[{id:1,name:'Thư giãn cơ thể và phục hồi năng lượng',description:'Danh mục',active:true},{id:2,name:'Chăm sóc da mặt cơ bản và chuyên sâu',description:'',active:false}];
const services=Array.from({length:7},(_,i)=>({id:i+1,name:'Dịch vụ '+(i+1),category_id:i%2+1,category:cats[i%2].name,price:390000,duration_minutes:60,active:i!==6,image_url:''}));
let writes=0, savedSteps=null;
window.fetch=async(path,options)=>{const type=path.includes('/categories/')?'categories':'services',rows=type==='categories'?cats:services;let data;
if(options?.method==='POST'){writes++;if(options.body.has('steps')){savedSteps=JSON.parse(options.body.get('steps'));data={};}else{const id=Number(path.split('/')[4]);rows.find(r=>r.id===id).active=!rows.find(r=>r.id===id).active;data={};}}
else if(/\/\d+\//.test(path)){data={html:type==='services'?serviceDetails[Number(path.split('/')[4])]:categoryDetail};}
else data={items:rows};if(/\/\d+\//.test(path)&&!path.includes('?view=1')&&!options?.method)data={html:type==='services'?(path.includes('/0/')?serviceForm.replace(/(<textarea[^>]*name="steps"[^>]*>)[\s\S]*?(<\/textarea>)/,'$1$2'):serviceForm):categoryForm};return {ok:true,json:async()=>data};};

'''
tests=r'''

(async()=>{let count=0;const wait=()=>new Promise(r=>setTimeout(r,80)),check=(ok,msg)=>{if(!ok)throw Error(msg);count++;},$=s=>document.querySelector(s);try{await wait();await wait();
check($('#services-stats').textContent.includes('Danh mục dịch vụ'),'KPI labels');check([...document.querySelectorAll('#services-stats strong')].map(e=>e.textContent).join(',')==='2,6,1','KPI sources');
for(const tab of ['categories','services']){
$('#tab-'+tab).click();const buttons=[...document.querySelectorAll('#'+tab+'-rows tr:first-child .admin-row-actions button')];check(buttons.length===3,'three actions '+tab);const rects=buttons.map(b=>b.getBoundingClientRect());check(rects.every(r=>Math.abs(r.top-rects[0].top)<1),'same action row '+tab);check(document.documentElement.scrollWidth<=innerWidth,'no page overflow '+tab);
}
for(const tab of ['categories','services']){
 $('#tab-'+tab).click();const panel=$('#panel-'+tab),scroll=panel.querySelector('.admin-table-scroll'),cells=[...panel.querySelectorAll('tbody tr:first-child td')];
 const budgets=tab==='services'?[110,250,180,140,130,130,300]:[110,230,230,130,300];
 budgets.forEach((minimum,i)=>check(cells[i].getBoundingClientRect().width>=minimum-.5,'column '+tab+' '+i));
 check(getComputedStyle(cells[tab==='services'?2:1]).overflowWrap==='break-word','word wrapping '+tab);check(getComputedStyle(cells[tab==='services'?2:1]).wordBreak==='normal','word break '+tab);
 check(scroll.getBoundingClientRect().right<=document.documentElement.clientWidth+1,'scroll confined '+tab);
 if(innerWidth<1300){check(scroll.scrollWidth>scroll.clientWidth,'horizontal overflow local '+tab);scroll.scrollLeft=scroll.scrollWidth;check(scroll.scrollLeft>0,'scroll operable '+tab);scroll.scrollLeft=0;}
}
$('#tab-services').click();check(!$('#panel-services').hidden&&$('#panel-categories').hidden,'tabs');check($('#services-rows').children.length===5,'five rows');check($('#services-rows').textContent.includes('DV-001'),'display code');check($('#services-rows .service-image-fallback'),'no demo image');
$('#services-pagination [data-page="1"]').click();check($('#services-rows').children.length===2,'page two');
$('#services-search').value='DV-001';$('#services-search').dispatchEvent(new Event('input',{bubbles:true}));check($('#services-rows').children.length===1,'code search resets page');
$('#services-search').value='missing';$('#services-search').dispatchEvent(new Event('input',{bubbles:true}));check(!$('#services-empty').hidden&&$('#services-rows').children.length===0,'empty');check([...document.querySelectorAll('#services-pagination button')].every(b=>b.disabled),'empty pagination');
$('#services-search').value='';$('#services-search').dispatchEvent(new Event('input',{bubbles:true}));$('#services-category').value='2';$('#services-category').dispatchEvent(new Event('input',{bubbles:true}));check($('#services-rows').children.length===3,'category filter');check($('#services-stats strong').textContent==='2','KPI independent');
$('#services-rows [data-view]').click();await wait();check($('#service-dialog').open&&!$('#service-dialog input'),'readonly view');check($('#service-dialog-title').textContent.includes('DV-002'),'view code from filtered ID');check(document.querySelectorAll('[data-service-procedure] h5').length===8,'View has 8 titles');check(document.querySelectorAll('[data-service-procedure] p').length===8,'View has 8 descriptions');check(!document.querySelector('[data-service-procedure]').textContent.includes('description'),'no raw JSON in View');let rect=$('#service-dialog').getBoundingClientRect();check(rect.top>=0&&rect.bottom<=innerHeight,'modal fits');$('#service-dialog [data-close]').click();
$('#services-rows [data-toggle]').click();await wait();check(writes===0&&$('#service-dialog').open,'confirmation before write');check($('#service-dialog-title').textContent.includes('DV-002'),'toggle code');check($('#service-dialog .admin-dialog-actions').getBoundingClientRect().bottom<=innerHeight,'footer visible');$('#service-dialog form').requestSubmit();await wait();await wait();check(writes===1,'mock toggle');check([...document.querySelectorAll('#services-stats strong')].map(e=>e.textContent).join(',')==='2,5,2','KPI refreshed '+[...document.querySelectorAll('#services-stats strong')].map(e=>e.textContent).join(','));
$('#tab-services').dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowLeft',bubbles:true}));check($('#tab-categories').getAttribute('aria-selected')==='true','keyboard tab');
for(const type of ['categories','services']){
$('#tab-'+type).click();$('#'+type+'-rows [data-edit]').click();await wait();check($('#service-dialog').open&&$('#service-dialog input[name="name"]'),'edit form '+type);check(writes===1,'edit open has no write '+type);$('#service-dialog [data-close]').click();$('[data-service-add="'+type+'"]').click();await wait();
check($('#service-dialog form')&&$('#service-dialog input[name="name"]'),'Django form '+type);
if(type==='services'){check($('#service-dialog input[name="image"]')&&$('#service-dialog input[name="gallery"]'),'upload fields retained');check($('#service-dialog select[name="category"]')&&$('#service-dialog select[name="care_group"]'),'separate category and care group');$('#service-dialog details').open=true;}
check($('#service-dialog .admin-dialog-actions').getBoundingClientRect().bottom<=innerHeight,'form footer visible '+type);$('#service-dialog [data-close]').click();}

check(writes===1,'form cancel has no write');
$('#tab-services').click();$('[data-service-add="services"]').click();await wait();$('#service-dialog details').open=true;
const add=$('[data-step-add]'),rows=$('[data-step-rows]');
for(let i=1;i<=21;i++){add.click();rows.lastElementChild.querySelector('input').value='Tên '+i;rows.lastElementChild.querySelector('textarea').value='Mô tả '+i;}
check(rows.children.length===21,'21 editable steps');
rows.lastElementChild.querySelector('[data-step-up]').click();check(rows.children[19].querySelector('input').value==='Tên 21','move up');
rows.children[19].querySelector('[data-step-down]').click();check(rows.lastElementChild.querySelector('input').value==='Tên 21','move down');
rows.lastElementChild.querySelector('[data-step-delete]').click();check(rows.children.length===20,'delete step');
add.click();$('#service-dialog form').requestSubmit();await wait();check(writes===1&&$('#service-dialog').open,'incomplete step blocks POST');
rows.lastElementChild.querySelector('input').value='Tên 21';rows.lastElementChild.querySelector('textarea').value='Mô tả 21';
check(rows.lastElementChild.querySelector('legend').textContent==='Bước 21','numbering');
check(rows.getBoundingClientRect().right<=$('#service-dialog').getBoundingClientRect().right+1,'editor no horizontal overflow');
$('#service-dialog form').requestSubmit();await wait();await wait();check(writes===2&&savedSteps.length===21,'create serializes JSON');check(savedSteps[20].title==='Tên 21'&&savedSteps[20].description==='Mô tả 21','separate title description');
$('#services-rows [data-edit]').click();await wait();$('#service-dialog details').open=true;
check($('[data-step-rows]').children.length===2,'edit loads structured steps');
check($('[data-step-rows] input').value==='Bước đã lưu','edit title restored');
$('#service-dialog form').requestSubmit();await wait();await wait();check(writes===3&&savedSteps.length===2,'edit JSON roundtrip');

check(document.documentElement.scrollWidth<=innerWidth,'no page overflow');check(!document.body.innerText.includes('Bản mẫu'),'no demo banner');$('#services-category').value='';$('#services-category').dispatchEvent(new Event('input',{bubbles:true}));for(const [id,n] of [[1,4],[2,8],[3,5],[4,0]]){$('#services-search').value='DV-'+String(id).padStart(3,'0');$('#services-search').dispatchEvent(new Event('input',{bubbles:true}));$('#services-rows [data-view]').click();await wait();check(document.querySelectorAll('[data-service-procedure] h5').length===n,'View case '+id);if(!n)check(document.querySelector('[data-service-procedure]').textContent.includes('Chưa có thông tin'),'View empty message');$('#service-dialog [data-close]').click();}$('#services-search').value='DV-002';$('#services-search').dispatchEvent(new Event('input',{bubbles:true}));$('#services-rows [data-view]').click();await wait();$('[data-service-procedure]').scrollIntoView({block:'center'});check($('[data-service-procedure]').getBoundingClientRect().right<=$('#service-dialog').getBoundingClientRect().right+1,'View procedure fits');document.body.insertAdjacentHTML('beforeend',`<pre id="test-result">PASS ${count}</pre>`);
}catch(e){document.body.insertAdjacentHTML('beforeend','<pre id="test-result">FAIL '+e.message+'</pre>');}})();

'''
with tempfile.TemporaryDirectory(prefix='core-ui-',dir=ROOT/'staticfiles') as temp:
 for kind in ('services',):
  with patch('django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection',side_effect=RuntimeError('DB forbidden')):
   html=render_to_string('pages/admin-'+kind+'.html',{'auth_ui':{},'live_catalog':{},'live_promotions':{}})
  html=re.sub(r'<script\b[^>]*>.*?</script>','',html,flags=re.S).replace('/static/',(ROOT/'static').as_uri()+'/').replace('<body class=',f'<body data-fixture="{kind}" class=')
  import json
  from core.business_forms import ServiceForm,CategoryForm
  from core.business_layout import groups_for
  with patch('django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection',side_effect=RuntimeError('DB forbidden')):
   from services.models import Service
   form=ServiceForm(instance=Service(steps=json.dumps([{'title':'Bước đã lưu','description':'Mô tả đã lưu'},{'title':'Kết thúc','description':'Nội dung cuối'}],ensure_ascii=False)));form.fields['category'].choices=[(1,'Danh mục thử')]
   forms={name:render_to_string('partials/business_form.html',{'form':f,'module':module,'groups':groups_for(f,module)}) for name,f,module in [('serviceForm',form,'services'),('categoryForm',CategoryForm(),'categories')]}
  with patch('django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection',side_effect=RuntimeError('DB forbidden')):
   details={}
   for service_id,count in ((1,4),(2,8),(3,5),(4,0),(5,10),(6,21),(7,6)):
    raw=json.dumps([{'title':f'Tên bước {i}','description':f'Mô tả riêng {i}'} for i in range(1,count+1)],ensure_ascii=False)
    if service_id==3:raw='\n'.join(f'Bước {i}: Nội dung cũ {i}' for i in range(1,count+1))
    detail_form=ServiceForm(instance=Service(steps=raw));detail_form.fields['category'].choices=[(1,'Danh mục thử')]
    details[service_id]=render_to_string('partials/business_detail.html',{'module':'services','groups':groups_for(detail_form,'services')})
   forms['serviceDetails']=details
   forms['categoryDetail']=render_to_string('partials/business_detail.html',{'module':'categories','groups':groups_for(CategoryForm(),'categories')})
  form_script=''.join('const '+name+'='+json.dumps(value)+';' for name,value in forms.items())
  scripts=(ROOT/'static/js/ui.js').read_text(encoding='utf-8')+'\n;'+form_script+mock+'\n;'+(ROOT/'static/js/admin.js').read_text(encoding='utf-8')+'\n;'
  scripts+=(ROOT/'static/js/live-admin.js').read_text(encoding='utf-8')+'\n;'
  active_tests=tests.replace("check(document.documentElement.scrollWidth<=innerWidth", "$('#services-rows [data-view]').click();await wait();check(document.documentElement.scrollWidth<=innerWidth") if '--accounts-modal' in sys.argv else tests
  html=html.replace('</body>','<input type="hidden" name="csrfmiddlewaretoken" value="mock-token"><script>'+scripts+active_tests+";if(parent!==window){const observer=new MutationObserver(()=>{const result=document.querySelector('#test-result');if(result){parent.postMessage(result.textContent,'*');observer.disconnect();}});observer.observe(document.body,{childList:true});}"+'</script></body>')
  fixture=Path(temp)/('admin-'+kind+'.html');fixture.write_text(html,encoding='utf-8')
  for width,height in ((1920,1080),(1440,1000),(1050,950),(768,950),(500,950),(390,950),(1440,560)):
   target=fixture
   if width < 500:
    target=Path(temp)/('frame-'+str(width)+'.html')
    relay="<script>addEventListener('message',e=>{if(typeof e.data==='string'&&/^(PASS|FAIL) /.test(e.data)){const p=document.createElement('pre');p.id='test-result';p.textContent=e.data;document.body.append(p);}});</script>"
    target.write_text('<!doctype html><meta charset="utf-8"><style>html,body{margin:0}iframe{border:0;display:block}</style>'+relay+f'<iframe src="{fixture.as_uri()}" width="{width}" height="{height-100}"></iframe>',encoding='utf-8')
   r=subprocess.run([r'C:\Program Files\Google\Chrome\Application\chrome.exe','--headless','--disable-gpu','--disable-background-networking','--disable-sync','--proxy-server=http://127.0.0.1:9','--proxy-bypass-list=<-loopback>','--force-device-scale-factor=1','--disable-smooth-scrolling','--no-first-run','--no-default-browser-check','--allow-file-access-from-files','--user-data-dir='+str(Path(temp)/(kind+str(width))),f'--window-size={width},{height}','--virtual-time-budget=3000','--screenshot='+str(OUT/f'admin-{kind}-{width}x{height}.png'),'--dump-dom',target.as_uri()],capture_output=True,encoding='utf-8',errors='replace',timeout=35)
   dom=re.sub(r'<script\b[^>]*>.*?</script>','',r.stdout,flags=re.S);found=re.search(r'<pre id="test-result">(PASS \d+|FAIL [^<]+)</pre>',dom)
   print(kind,str(width)+'x'+str(height),found.group(1) if found else 'NO RESULT',flush=True)
   if not found:
    print('Chrome exit:',r.returncode,'output length:',len(r.stdout));print(r.stderr[-1800:]);(OUT/f'admin-failed-{width}x{height}.html').write_text(r.stdout,encoding='utf-8')
   if not found or not found.group(1).startswith('PASS'):raise SystemExit(1)
