"""Browser-only Promotions checks with rendered Django forms and mock API data.

No database connection or real HTTP API request is allowed. This is separate
from the protected MySQL regression runner and does not change its test count.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

MOCK = r'''
window.spaAuth={allowed:true,isAuthenticated:()=>true,getSession:()=>({role:'Admin'})};
window.spaCatalog={services:[],products:[],staff:[]};
window.spaPromotions={referenceDate:'2026-11-09',items:[]};
const records=[
 {id:4,code:'EXACT10',name:'Ưu đãi trải nghiệm',description:'Chăm sóc tinh tế',active:true,discount_type:'percent',discount_value:'10.00',start_date:'2026-10-20',end_date:'2026-11-30'},
 {id:7,code:'FRACTION',name:'Ưu đãi thập phân',description:'Không làm tròn',active:true,discount_type:'percent',discount_value:'10.25',start_date:'2026-11-09',end_date:'2026-11-09'},
 {id:9,code:'MONEY',name:'Quà tặng thư giãn',description:'Giảm số tiền',active:true,discount_type:'amount',discount_value:'50000.00',start_date:'2026-10-20',end_date:'2026-11-30'},
 {id:12,code:'FUTURE',name:'Chương trình tương lai',description:'Chưa hiệu lực',active:true,discount_type:'percent',discount_value:'10.00',start_date:'2026-11-10',end_date:'2026-11-30'},
 {id:19,code:'EXPIRED',name:'Chương trình hết hạn',description:'Đã kết thúc',active:true,discount_type:'percent',discount_value:'10.00',start_date:'2026-10-01',end_date:'2026-11-08'},
 {id:21,code:'DISABLED',name:'Chương trình tạm ngừng',description:'Không hiệu lực',active:false,discount_type:'percent',discount_value:'10.00',start_date:'2026-10-01',end_date:'2026-11-30'},
 {id:31,code:'EXTRA',name:'Chương trình bổ sung',description:'Phân trang',active:true,discount_type:'percent',discount_value:'20.00',start_date:'2026-10-01',end_date:'2026-11-30'}];
let writes=0,lastBody,lastPath,failWrite=false,emptyAPI=false,readError=false;
window.fetch=async(path,options)=>{
 if(!path.startsWith('/api/admin/promotions/'))throw Error('External HTTP forbidden');
 if(options?.method==='POST'){
  lastBody=options.body;lastPath=path;
  if(options.headers['X-CSRFToken']!=='mock-token')throw Error('CSRF missing');
  if(failWrite){failWrite=false;return {ok:false,json:async()=>({errors:{name:['Tên chương trình không hợp lệ.']}})};}
  writes++;const id=Number(path.split('/')[4]),row=records.find(r=>r.id===id);
  if(lastBody.get('_toggle'))row.active=!row.active;
  return {ok:true,json:async()=>({})};
 }
 if(readError)return {ok:false,json:async()=>({error:'Không thể tải biểu mẫu.'})};
 if(/\/\d+\//.test(path))return {ok:true,json:async()=>({html:path.includes('?view=1')?detailHTML:path.includes('/0/')?addHTML:editHTML})};
 return {ok:true,json:async()=>({items:emptyAPI?[]:records})};
};
'''

# Use the installed Node runtime only for Chrome's DevTools protocol. Its native
# WebSocket sets an exact CSS viewport; Chrome's CLI window-size has a minimum
# window width and can otherwise produce misleading mobile screenshots.
CHROME_CHECK = r'''
const fs=require('node:fs'),{spawn}=require('node:child_process');
const config=JSON.parse(fs.readFileSync(0,'utf8'));
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const chrome=spawn('C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',[
 '--headless','--disable-gpu','--no-first-run','--no-default-browser-check',
 '--allow-file-access-from-files','--disable-smooth-scrolling','--remote-debugging-port=0',
 '--user-data-dir='+config.profile,'about:blank'],{windowsHide:true,stdio:'ignore'});
let socket;
(async()=>{try{
 const portFile=config.profile+'/DevToolsActivePort';
 for(let i=0;i<100&&!fs.existsSync(portFile);i++)await sleep(100);
 const [port,path]=fs.readFileSync(portFile,'utf8').trim().split(/\r?\n/);
 socket=new WebSocket('ws://127.0.0.1:'+port+path);
 await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
 let counter=0;const pending=new Map();
 socket.onmessage=event=>{const msg=JSON.parse(event.data);if(pending.has(msg.id)){const [resolve,reject]=pending.get(msg.id);pending.delete(msg.id);msg.error?reject(Error(msg.error.message)):resolve(msg.result);}};
 const send=(method,params={},sessionId)=>new Promise((resolve,reject)=>{const id=++counter;pending.set(id,[resolve,reject]);socket.send(JSON.stringify({id,method,params,sessionId}));});
 const {targetId}=await send('Target.createTarget',{url:'about:blank'});
 const {sessionId}=await send('Target.attachToTarget',{targetId,flatten:true});
 const call=(method,params={})=>send(method,params,sessionId);
 await call('Emulation.setDeviceMetricsOverride',{width:config.width,height:1000,deviceScaleFactor:1,mobile:false});
 await call('Page.enable');await call('Page.navigate',{url:config.url});
 let state;
 for(let i=0;i<160;i++){
  await sleep(100);
  state=(await call('Runtime.evaluate',{expression:'JSON.stringify({result:document.getElementById("test-result")?.textContent,width:innerWidth,height:innerHeight,escape:window.__requestEscape})',returnByValue:true})).result.value;
  if(state&&JSON.parse(state).escape){
   await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
   await call('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
   await call('Runtime.evaluate',{expression:'window.__requestEscape=false'});
  }
  if(state&&JSON.parse(state).result)break;
 }
 const parsed=JSON.parse(state||'{}');
 await call('Runtime.evaluate',{expression:'window.scrollTo({top:0,behavior:"instant"})'});await sleep(100);
 const {data}=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
 fs.writeFileSync(config.screenshot,Buffer.from(data,'base64'));
 const dom=(await call('Runtime.evaluate',{expression:'document.documentElement.outerHTML',returnByValue:true})).result.value;
 fs.writeFileSync(config.dom,dom);
 console.log(JSON.stringify(parsed));
 if(parsed.width!==config.width||!parsed.result?.startsWith('PASS'))process.exitCode=1;
}catch(error){console.error(error.message);process.exitCode=1;}finally{socket?.close();chrome.kill();}})();
'''

TESTS = r'''
(async()=>{
 const $=s=>document.querySelector(s),all=s=>[...document.querySelectorAll(s)],wait=()=>new Promise(r=>setTimeout(r,60));
 let count=0;const check=(ok,msg)=>{if(!ok)throw Error(msg);count++;},input=e=>e.dispatchEvent(new Event('input',{bubbles:true}));
 const fits=()=>check($('#ops-dialog').getBoundingClientRect().bottom<=innerHeight&&$('#ops-dialog').getBoundingClientRect().top>=0,'modal fits viewport');
 try{
 await document.fonts.ready;await wait();await wait();
 check(all('#ops-stats strong').map(e=>e.textContent).join(',')==='7,4,1','calendar KPI includes boundary/ending, excludes inactive/expired/future');
 check(all('#ops-stats svg').length===3,'KPI icons');check(all('#ops-rows tr').length===5,'5 per page');
 check($('#ops-rows').textContent.includes('10%')&&!$('#ops-rows').textContent.includes('10.00%'),'trim percentage');
 check($('#ops-rows').textContent.includes('10.25%'),'fraction retained');check($('#ops-rows').textContent.includes('50.000 VND'),'money');
 check($('#ops-rows').textContent.includes('20/10/2026')&&!$('#ops-rows').textContent.includes('2026-10-20'),'table dates');
 check(!/Admin Core|Admin Operations|Finance & Quality/i.test($('.admin-nav').textContent),'Vietnamese navigation');
 const actions=all('#ops-rows tr:first-child .admin-row-actions button');
 check(actions.length===3&&actions.every(e=>Math.abs(e.getBoundingClientRect().top-actions[0].getBoundingClientRect().top)<1),'actions same row');
 check(getComputedStyle(actions[0].querySelector('svg')).color==='rgb(185, 144, 87)','champagne icons');
 const scroll=$('.admin-table-scroll');scroll.scrollLeft=scroll.scrollWidth;
 check(actions[2].getBoundingClientRect().right<=scroll.getBoundingClientRect().right+1,'last action reachable');scroll.scrollLeft=0;
 $('[data-promotion-page="1"]').click();check(all('#ops-rows tr').length===2&&$('#ops-rows').textContent.includes('EXTRA'),'page2');
 $('#ops-search').value='thu gian';input($('#ops-search'));check(all('#ops-rows tr').length===1,'unaccented search resets page');
 $('#ops-status').value='expired';input($('#ops-status'));check(!$('#ops-empty').hidden,'combined filters empty');
 check(all('#ops-stats strong').map(e=>e.textContent).join(',')==='7,4,1','KPI not filtered');
 $('#ops-reset').click();$('#ops-status').value='ending';input($('#ops-status'));check(all('#ops-rows tr').length===1&&$('#ops-rows').textContent.includes('FRACTION'),'ending inclusive today');
 $('#ops-reset').click();
 if(location.hash==='#list-preview'){window.scrollTo({top:0,behavior:'instant'});document.body.insertAdjacentHTML('beforeend',`<pre id="test-result">PASS ${count}</pre>`);return;}
 const trigger=$('[data-promotion-view="4"]');trigger.focus();trigger.click();await wait();
 check($('#ops-dialog .promotion-summary h3').textContent==='Ưu đãi trải nghiệm','summary name');
 check($('#ops-dialog .promotion-summary .admin-status-badge').textContent==='Đang hiệu lực','summary status');
 check($('#ops-dialog').textContent.includes('Giảm 10%')&&$('#ops-dialog').textContent.includes('20/10/2026'),'detail formatting');
 check($('#ops-dialog').textContent.includes('200.000 VND')&&$('#ops-dialog').textContent.includes('50.000 VND'),'detail min/max');
 check($('#ops-dialog').textContent.includes('Điều kiện chưa hiểu vẫn cần xác minh'),'business conditions preserved');
 check(!$('#ops-dialog input')&&all('#ops-dialog dt svg').length>10,'read only with label icons');fits();
 if(location.hash==='#view-preview'){window.scrollTo({top:0,behavior:'instant'});await wait();fits();document.body.insertAdjacentHTML('beforeend',`<pre id="test-result">PASS ${count}</pre>`);return;}
 const body=$('#ops-dialog .admin-service-modal-scroll');body.scrollTop=body.scrollHeight;
 check(body.scrollHeight>body.clientHeight&&$('#ops-dialog .admin-dialog-actions').getBoundingClientRect().bottom<=innerHeight,'body scroll and fixed footer');
 $('#ops-dialog [data-close]').click();await wait();check(!$('#ops-dialog').open&&document.activeElement===trigger,'close and focus restored');
 trigger.click();await wait();$('#ops-dialog .admin-dialog-actions [data-close]').click();check(!$('#ops-dialog').open,'footer close');
 trigger.click();await wait();window.__requestEscape=true;
 for(let i=0;i<20&&$('#ops-dialog').open;i++)await wait();
 check(!$('#ops-dialog').open&&document.activeElement===trigger,'native Escape and focus restored');
 $('[data-promotion-edit="4"]').click();await wait();fits();
 check($('#ops-dialog [type="submit"]').textContent.trim()==='Lưu thay đổi','edit label');
 check($('#ops-dialog [name="start_date"]').type==='date'&&$('#ops-dialog [name="start_date"]').value==='2026-10-20','API ISO date unchanged');
 const dateText=$('#ops-dialog [data-date-display="start_date"]');check(dateText.value==='20/10/2026'&&dateText.placeholder==='dd/mm/yyyy','localized date entry');
 dateText.value='31/02/2026';input(dateText);check(!$('#ops-dialog [name="start_date"]').value&&!dateText.validity.valid,'invalid calendar date');
 dateText.value='20/10/2026';input(dateText);check($('#ops-dialog [name="start_date"]').value==='2026-10-20','date converts to ISO');
 check($('#ops-dialog [name="per_customer_limit"]')&&$('#ops-dialog [name="max_discount"]')&&$('#ops-dialog [name="aliases"]'),'all backend fields retained');
 check(all('#ops-dialog [name="services"]:checked').map(e=>e.value).join(',')==='1,2','edit preselected multiple');
 if(location.hash==='#edit-preview'){document.body.insertAdjacentHTML('beforeend',`<pre id="test-result">PASS ${count}</pre>`);return;}
 const search=$('#promotion-service-search');search.scrollIntoView({block:'center'});await wait();
 const rect=search.getBoundingClientRect();check(rect.width>200&&rect.height>=40,'service search usable size');
 search.focus();check(document.activeElement===search&&document.elementFromPoint(rect.left+rect.width/2,rect.top+rect.height/2)===search,'service search focus and hit test');
 search.value='cham soc';input(search);check(all('#ops-dialog [name="services"]').filter(c=>!c.closest('label').hidden).length===1,'service search unaccented');
 search.value='DV-003';input(search);check(!$('#ops-dialog [name="services"][value="3"]').closest('label').hidden,'service search ID');
 search.value='';input(search);
 $('#ops-dialog [name="services"][value="1"]').checked=false;
 $('#ops-dialog [name="services"][value="3"]').checked=true;
 $('#ops-dialog [name="services"][value="3"]').dispatchEvent(new Event('change'));
 check($('[data-service-summary]').textContent.includes('Đã chọn 2')&&$('[data-service-summary]').textContent.includes('Tạm ngừng'),'selection count and inactive label');
 $('#ops-dialog [data-close]').click();check(writes===0,'cancel never posts');
 $('[data-promotion-edit="4"]').click();await wait();
 failWrite=true;$('#ops-dialog form').requestSubmit();await wait();
 check(!$('#ops-dialog [data-error]').hidden&&$('#ops-dialog [name="name"]').getAttribute('aria-invalid')==='true'&&writes===0,'backend validation displayed, stays open');
 all('#ops-dialog [name="services"]').forEach(c=>c.checked=['2','3'].includes(c.value));
 $('#ops-dialog form').requestSubmit();$('#ops-dialog form').requestSubmit();await wait();await wait();
 check(writes===1&&lastBody.getAll('services').join(',')==='2,3','multiple exact IDs, repeat submit blocked');
 check(lastPath==='/api/admin/promotions/4/'&&lastBody.get('start_date')==='2026-10-20'&&lastBody.get('csrfmiddlewaretoken'),'unchanged API and CSRF');
 $('#ops-add').click();await wait();fits();check($('#ops-dialog [type="submit"]').textContent.trim()==='Lưu','add label');
 check(all('#ops-dialog [name="services"]:checked').length===0,'add not preselected');
 $('#ops-dialog form').requestSubmit();await wait();await wait();check(writes===2&&lastBody.getAll('services').length===0&&lastPath==='/api/admin/promotions/0/','empty selection and real create endpoint');
 $('[data-promotion-toggle="4"]').click();await wait();check(writes===2&&$('#ops-dialog').open,'toggle confirmation');
 $('#ops-dialog [data-close]').click();check(writes===2,'cancel toggle');
 $('[data-promotion-toggle="4"]').click();await wait();$('#ops-dialog form').requestSubmit();await wait();await wait();
 check(writes===3&&lastBody.get('_toggle')==='1','toggle exact existing contract');
 check(all('#ops-stats strong').map(e=>e.textContent).join(',')==='7,3,2','calendar KPI refreshed after toggle');
 readError=true;$('[data-promotion-view="4"]').click();await wait();check($('#ops-notice').textContent==='Không thể tải biểu mẫu.','GET error visible');readError=false;
 $('#ops-search').value='no-results';input($('#ops-search'));check(!$('#ops-empty').hidden&&all('#ops-pagination button').every(b=>b.disabled),'empty search pagination');
 emptyAPI=true;$('#ops-reset').click();$('[data-promotion-toggle="4"]').click();await wait();$('#ops-dialog form').requestSubmit();await wait();await wait();
 check(all('#ops-stats strong').map(e=>e.textContent).join(',')==='0,0,0'&&!$('#ops-empty').hidden,'empty API state');
 check(document.documentElement.scrollWidth<=innerWidth,'no page overflow');check(!document.body.innerText.includes('Bản mẫu'),'no demo banner');
 // Leave a populated view/form for screenshot review after all assertions.
 emptyAPI=false;if(location.hash==='#add-preview'){$('#ops-add').click();await wait();}
 document.body.insertAdjacentHTML('beforeend',`<pre id="test-result">PASS ${count}</pre>`);
 }catch(error){document.body.insertAdjacentHTML('beforeend','<pre id="test-result">FAIL '+error.message+'</pre>');}
})();
'''


def main():
    from django.db.backends.base.base import BaseDatabaseWrapper
    with patch.object(BaseDatabaseWrapper, 'ensure_connection', side_effect=RuntimeError('Database forbidden for UI checks')):
        import django
        django.setup()
        from django.template.loader import render_to_string
        from core.business_forms import PromotionForm
        from core.business_layout import groups_for
        from promotions.models import Promotion
        from datetime import date
        from decimal import Decimal

        html = render_to_string('pages/admin-promotions.html', {'auth_ui': {}, 'live_catalog': {}, 'live_promotions': {}})
        choices = [(1, 'Massage đá nóng'), (2, 'Chăm sóc da'), (3, 'Dịch vụ tạm ngừng (Tạm ngừng)')]
        form = PromotionForm(instance=Promotion(name='Ưu đãi trải nghiệm', code='EXACT10', discount_type='percent', discount_value=Decimal('10.00'), start_date=date(2026,10,20), end_date=date(2026,11,30), min_amount=Decimal('200000'), max_discount=Decimal('50000'), per_customer_limit=1, conditions='Điều kiện chưa hiểu vẫn cần xác minh', detail='Chi tiết chương trình', note='Lưu ý nghiệp vụ'))
        form.fields['services'].choices = choices
        form.initial['services'] = [1, 2]
        groups = groups_for(form, 'promotions')
        for group in groups:
            for field in group['fields']:
                if field['name'] == 'services':
                    field['value'] = 'Massage đá nóng, Chăm sóc da'
        edit = render_to_string('partials/business_form.html', {'form':form, 'module':'promotions', 'groups':groups, 'csrf_token':'mock-token'})
        detail = render_to_string('partials/business_detail.html', {'form':form, 'module':'promotions', 'groups':groups})
        add = PromotionForm()
        add.fields['services'].choices = choices
        add_html = render_to_string('partials/business_form.html', {'form':add, 'module':'promotions', 'groups':groups_for(add,'promotions'), 'csrf_token':'mock-token'})

        html = re.sub(r'<script\b[^>]*>.*?</script>', '', html, flags=re.S).replace('/static/', (ROOT/'static').as_uri()+'/')
        scripts = (ROOT/'static/js/ui.js').read_text(encoding='utf-8') + '\n;'
        scripts += 'const addHTML='+json.dumps(add_html)+';const editHTML='+json.dumps(edit)+';const detailHTML='+json.dumps(detail)+';'
        scripts += MOCK + '\n;' + (ROOT/'static/js/admin.js').read_text(encoding='utf-8') + '\n;' + (ROOT/'static/js/live-promotions.js').read_text(encoding='utf-8') + '\n;' + TESTS
        html = html.replace('</body>', '<input type="hidden" name="csrfmiddlewaretoken" value="mock-token"><script>'+scripts+'</script></body>')
        with tempfile.TemporaryDirectory(prefix='promotions-ui-', dir=ROOT/'staticfiles') as temp:
            fixture = Path(temp)/'admin-promotions.html'
            fixture.write_text(html, encoding='utf-8')
            browser_check = Path(temp)/'chrome-check.cjs'
            browser_check.write_text(CHROME_CHECK, encoding='utf-8')
            for width in (1440,768,500,390):
                mode = next((value for value in ('add','view','edit','list') if '--'+value+'-preview' in sys.argv), '')
                dom_file = ROOT/'staticfiles/promotions-ui-last-dom.html'
                result = subprocess.run([r'D:\node\node.exe',str(browser_check)], input=json.dumps({'profile':str(Path(temp)/str(width)), 'width':width, 'url':fixture.as_uri()+('#'+mode+'-preview' if mode else ''), 'screenshot':str(ROOT/'staticfiles'/f'promotions-{mode or "checks"}-{width}.png'), 'dom':str(dom_file)}), capture_output=True, encoding='utf-8', errors='replace', timeout=40)
                dom = re.sub(r'<script\b[^>]*>.*?</script>', '', dom_file.read_text(encoding='utf-8') if dom_file.exists() else '', flags=re.S)
                found = re.search(r'<pre id="test-result">(PASS \d+|FAIL [^<]+)</pre>', dom)
                print(width, result.stdout.strip() or 'NO RESULT', flush=True)
                if result.returncode or not found or not found.group(1).startswith('PASS'):
                    print('Chrome exit:', result.returncode, result.stderr[-1000:])
                    return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
