"""Core UI checks with synthetic API responses; no database connections."""
import os,sys,re,tempfile,subprocess
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from django.template.loader import render_to_string
mock=r'''

window.spaAuth={allowed:true,isAuthenticated:()=>true,getSession:()=>({role:'Admin'})};
const cats=[{id:1,name:'Thư giãn',description:'Danh mục',active:true},{id:2,name:'Chăm sóc',description:'',active:false}];
const services=Array.from({length:7},(_,i)=>({id:i+1,name:'Dịch vụ '+(i+1),category_id:i%2+1,category:cats[i%2].name,price:390000,duration_minutes:60,active:i!==6,image_url:''}));
let writes=0;
window.fetch=async(path,options)=>{const type=path.includes('/categories/')?'categories':'services',rows=type==='categories'?cats:services;let data;
if(options?.method==='POST'){writes++;const id=Number(path.split('/')[4]);rows.find(r=>r.id===id).active=!rows.find(r=>r.id===id).active;data={};}
else if(/\/\d+\//.test(path)){data={html:'<div class="admin-service-modal-scroll"><p>Thông tin chỉ đọc</p></div><div class="admin-dialog-actions"><button type="button" class="admin-button" data-close>Đóng</button></div>'};}
else data={items:rows};if(/\/\d+\//.test(path)&&!path.includes('?view=1')&&!options?.method)data={html:type==='services'?serviceForm:categoryForm};return {ok:true,json:async()=>data};};

'''
tests=r'''

(async()=>{let count=0;const wait=()=>new Promise(r=>setTimeout(r,80)),check=(ok,msg)=>{if(!ok)throw Error(msg);count++;},$=s=>document.querySelector(s);try{await wait();await wait();
check($('#services-stats').textContent.includes('Danh mục dịch vụ'),'KPI labels');check([...document.querySelectorAll('#services-stats strong')].map(e=>e.textContent).join(',')==='2,6,1','KPI sources');
for(const tab of ['categories','services']){
$('#tab-'+tab).click();const buttons=[...document.querySelectorAll('#'+tab+'-rows tr:first-child .admin-row-actions button')];check(buttons.length===3,'three actions '+tab);const rects=buttons.map(b=>b.getBoundingClientRect());check(rects.every(r=>Math.abs(r.top-rects[0].top)<1),'same action row '+tab);check(document.documentElement.scrollWidth<=innerWidth,'no page overflow '+tab);
}
$('#tab-services').click();check(!$('#panel-services').hidden&&$('#panel-categories').hidden,'tabs');check($('#services-rows').children.length===5,'five rows');check($('#services-rows').textContent.includes('DV-001'),'display code');check($('#services-rows .service-image-fallback'),'no demo image');
$('#services-pagination [data-page="1"]').click();check($('#services-rows').children.length===2,'page two');
$('#services-search').value='DV-001';$('#services-search').dispatchEvent(new Event('input',{bubbles:true}));check($('#services-rows').children.length===1,'code search resets page');
$('#services-search').value='missing';$('#services-search').dispatchEvent(new Event('input',{bubbles:true}));check(!$('#services-empty').hidden&&$('#services-rows').children.length===0,'empty');check([...document.querySelectorAll('#services-pagination button')].every(b=>b.disabled),'empty pagination');
$('#services-search').value='';$('#services-search').dispatchEvent(new Event('input',{bubbles:true}));$('#services-category').value='2';$('#services-category').dispatchEvent(new Event('input',{bubbles:true}));check($('#services-rows').children.length===3,'category filter');check($('#services-stats strong').textContent==='2','KPI independent');
$('#services-rows [data-view]').click();await wait();check($('#service-dialog').open&&!$('#service-dialog input'),'readonly view');check($('#service-dialog-title').textContent.includes('DV-002'),'view code from filtered ID');let rect=$('#service-dialog').getBoundingClientRect();check(rect.top>=0&&rect.bottom<=innerHeight,'modal fits');$('#service-dialog [data-close]').click();
$('#services-rows [data-toggle]').click();await wait();check(writes===0&&$('#service-dialog').open,'confirmation before write');check($('#service-dialog-title').textContent.includes('DV-002'),'toggle code');check($('#service-dialog .admin-dialog-actions').getBoundingClientRect().bottom<=innerHeight,'footer visible');$('#service-dialog form').requestSubmit();await wait();await wait();check(writes===1,'mock toggle');check([...document.querySelectorAll('#services-stats strong')].map(e=>e.textContent).join(',')==='2,5,2','KPI refreshed '+[...document.querySelectorAll('#services-stats strong')].map(e=>e.textContent).join(','));
$('#tab-services').dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowLeft',bubbles:true}));check($('#tab-categories').getAttribute('aria-selected')==='true','keyboard tab');
for(const type of ['categories','services']){
$('#tab-'+type).click();$('[data-service-add="'+type+'"]').click();await wait();
check($('#service-dialog form')&&$('#service-dialog input[name="name"]'),'Django form '+type);
if(type==='services'){check($('#service-dialog input[name="image"]')&&$('#service-dialog input[name="gallery"]'),'upload fields retained');check($('#service-dialog select[name="category"]')&&$('#service-dialog select[name="care_group"]'),'separate category and care group');$('#service-dialog details').open=true;}
check($('#service-dialog .admin-dialog-actions').getBoundingClientRect().bottom<=innerHeight,'form footer visible '+type);$('#service-dialog [data-close]').click();}
check(writes===1,'form cancel has no write');
check(document.documentElement.scrollWidth<=innerWidth,'no page overflow');check(!document.body.innerText.includes('Bản mẫu'),'no demo banner');document.body.insertAdjacentHTML('beforeend',`<pre id="test-result">PASS ${count}</pre>`);
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
   form=ServiceForm();form.fields['category'].choices=[(1,'Danh mục thử')]
   forms={name:render_to_string('partials/business_form.html',{'form':f,'module':module,'groups':groups_for(f,module)}) for name,f,module in [('serviceForm',form,'services'),('categoryForm',CategoryForm(),'categories')]}
  form_script=''.join('const '+name+'='+json.dumps(value)+';' for name,value in forms.items())
  scripts=(ROOT/'static/js/ui.js').read_text(encoding='utf-8')+'\n;'+form_script+mock+'\n;'+(ROOT/'static/js/admin.js').read_text(encoding='utf-8')+'\n;'
  scripts+=(ROOT/'static/js/live-admin.js').read_text(encoding='utf-8')+'\n;'
  active_tests=tests.replace("check(document.documentElement.scrollWidth<=innerWidth", "$('#services-rows [data-view]').click();await wait();check(document.documentElement.scrollWidth<=innerWidth") if '--accounts-modal' in sys.argv else tests
  html=html.replace('</body>','<input type="hidden" name="csrfmiddlewaretoken" value="mock-token"><script>'+scripts+active_tests+'</script></body>')
  fixture=Path(temp)/('admin-'+kind+'.html');fixture.write_text(html,encoding='utf-8')
  for width in (1440,768,500):
   r=subprocess.run([r'C:\Program Files\Google\Chrome\Application\chrome.exe','--headless','--disable-gpu','--force-device-scale-factor=1','--disable-smooth-scrolling','--no-first-run','--no-default-browser-check','--allow-file-access-from-files','--user-data-dir='+str(Path(temp)/(kind+str(width))),f'--window-size={width},1000','--virtual-time-budget=3000','--screenshot='+str(ROOT/'staticfiles'/f'core-{kind}-{width}.png'),'--dump-dom',fixture.as_uri()],capture_output=True,encoding='utf-8',errors='replace',timeout=35)
   dom=re.sub(r'<script\b[^>]*>.*?</script>','',r.stdout,flags=re.S);found=re.search(r'<pre id="test-result">(PASS \d+|FAIL [^<]+)</pre>',dom)
   print(kind,width,found.group(1) if found else 'NO RESULT',flush=True)
   if not found:
    print('Chrome exit:',r.returncode,'output length:',len(r.stdout));print(r.stderr[-1800:]);Path(ROOT/'staticfiles/services-check-dom.html').write_text(r.stdout,encoding='utf-8')
   if not found or not found.group(1).startswith('PASS'):raise SystemExit(1)
