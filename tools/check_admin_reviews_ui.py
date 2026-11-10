"""Chrome review UI regression checks. All APIs mocked; Django DB forbidden.
Session storage is used ONLY by this local test fixture to emulate server data
surviving a browser reload. No product scripts or MySQL records use this store.
"""
import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
MOCK=r'''
window.uiErrors=[];window.addEventListener('error',e=>uiErrors.push(e.message));window.addEventListener('unhandledrejection',e=>uiErrors.push(String(e.reason)));
window.spaAuth={allowed:true,isAuthenticated:()=>true,getSession:()=>({role:mode==='admin'?'Admin':'User'})};
window.spaCatalog={services:[],products:[],staff:[]};
const seed=()=>[5,4,3,2,1,5,4].map((rating,n)=>({id:n+1,appointmentId:n+101,customer:'Khách kiểm thử '+(n+1),service:n===1?'Chăm sóc da':'Massage đá nóng',serviceId:1,rating,comment:n===0?'':n===6?'<img src=x onerror="window.injected=true">':'Chia sẻ thử nghiệm '+(n+1),createdAt:n===0?'2026-11-09T17:05:00Z':'2026-11-09T01:00:00Z',replies:n===0?[{id:1,name:'spa-admin',role:'Admin',content:'Spa đã ghi nhận.',createdAt:'2026-11-09T17:10:00Z'},{id:2,name:'customer-owner',role:'User',content:'Cảm ơn Spa.',createdAt:'2026-11-09T17:15:00Z'}]:[]}));
let records=JSON.parse(sessionStorage.getItem('review-ui-store')||'null')||(mode==='user'?seed():[]),failInitial=mode==='admin'&&!sessionStorage.getItem('review-ui-stage'),failRead=false,failWrite=false,writes=0,lastPost=null,unexpected=0;
const persist=()=>sessionStorage.setItem('review-ui-store',JSON.stringify(records));
const copy=x=>JSON.parse(JSON.stringify(x)),delay=ms=>new Promise(r=>setTimeout(r,ms));
const eligible=()=>Array.from({length:mode==='service'?1:7},(_,n)=>({id:n+101,serviceId:1,service:'Massage đá nóng',date:'2026-10-23'}));
window.fetch=async(path,options={})=>{
 const response=(body,status=200)=>({ok:status<400,status,json:async()=>copy(body)});
 if(!path.startsWith('/api/reviews/')){unexpected++;throw Error('External endpoint blocked');}
 await delay(30);
 if(options.method==='POST'){
  lastPost={path,body:new URLSearchParams(options.body),csrf:options.headers['X-CSRFToken']};
  if(lastPost.csrf!=='mock-token')throw Error('Missing CSRF');
  await delay(80);if(failWrite){failWrite=false;return response({error:'Không thể gửi phản hồi thử nghiệm.'},503);}
  const save=path.match(/^\/api\/reviews\/appointments\/(\d+)\/$/),reply=path.match(/^\/api\/reviews\/(\d+)\/replies\/$/);
  if(save){
   if(mode==='admin')return response({error:'Không được phép.'},403);
   const id=Number(save[1]),rating=Number(lastPost.body.get('rating')),comment=lastPost.body.get('comment')||'';
   if(!Number.isInteger(rating)||rating<1||rating>5||comment.length>2000)return response({errors:{rating:['Điểm hoặc nhận xét không hợp lệ.']}},400);
   let r=records.find(r=>r.appointmentId===id);
   if(!r){r={id:records.length+1,appointmentId:id,customer:'Khách kiểm thử',service:'Massage đá nóng',serviceId:1,createdAt:'2026-11-10T08:00:00+07:00',replies:[]};records.push(r);}
   Object.assign(r,{rating,comment});writes++;persist();return response({item:r});
  }
  if(reply){
   const r=records.find(r=>r.id===Number(reply[1])),content=(lastPost.body.get('content')||'').trim();
   if(!r)return response({error:'Không tìm thấy đánh giá.'},404);
   if(!content||content.length>2000)return response({error:'Nội dung phải từ 1 đến 2000 ký tự.'},400);
   r.replies.push({id:100+r.replies.length,name:mode==='admin'?'spa-admin':'customer-owner',role:mode==='admin'?'Admin':'User',content,createdAt:'2026-11-10T09:15:00+07:00'});writes++;persist();return response({item:r},201);
  }
  unexpected++;throw Error('Unexpected write endpoint');
 }
 if(failRead||failInitial){failRead=false;failInitial=false;return response({error:'Không tải được đánh giá thử nghiệm.'},503);}
 if(path==='/api/reviews/')return response({items:records,eligible:mode==='admin'?[]:eligible()});
 if(path.startsWith('/api/reviews/services/1/'))return response({items:records.map(r=>({rating:r.rating,comment:r.comment,name:r.customer,createdAt:r.createdAt,replies:r.replies.map(x=>({name:x.role==='Admin'?'An Nhiên Spa':r.customer,content:x.content,createdAt:x.createdAt}))})),total:records.length,average:records.length?records.reduce((s,r)=>s+r.rating,0)/records.length:0,page:1,pages:1});
 unexpected++;throw Error('Unexpected read endpoint');
};
'''
TESTS=r'''
(async()=>{
const $=s=>document.querySelector(s),all=s=>[...document.querySelectorAll(s)];let checks=Number(sessionStorage.getItem('review-ui-checks')||0);
const check=(v,m)=>{if(!v)throw Error(m);checks++;},wait=ms=>new Promise(r=>setTimeout(r,ms||120));
const input=e=>e.dispatchEvent(new Event('input',{bubbles:true}));
const ready=async()=>{for(let n=0;n<70;n++){if(mode!=='admin'||$('#reviews-panel').getAttribute('aria-busy')==='false')return;await wait(30);}throw Error('Load timeout');};
const reset=()=>$('#quality-reset').click();
const close=()=>$('#quality-dialog [data-close-review]').click();
const open=async id=>{reset();$('#quality-search').value='DG-'+id;input($('#quality-search'));$('[data-view-review="'+id+'"]').click();await wait(180);};
const fits=()=>{const r=$('#quality-dialog').getBoundingClientRect();check(r.top>=0&&r.bottom<=innerHeight+1&&r.left>=0&&r.right<=innerWidth,'modal fits viewport');};
function finish(){check(unexpected===0&&uiErrors.length===0,'no unexpected API / JS errors '+uiErrors.join(','));check(document.documentElement.scrollWidth<=innerWidth,'no page overflow');document.body.insertAdjacentHTML('beforeend',`<pre id="test-result">PASS ${checks}</pre>`);}
try{
await document.fonts.ready;await wait(200);await ready();
if(sessionStorage.getItem('review-ui-stage')==='reload'){
 if(mode==='admin'){
  check(records.length===7,'ratings persist after F5');await open(1);fits();
  check($('#quality-dialog').textContent.includes('Phản hồi mới từ Spa <b>giữ nguyên</b>')&&all('#quality-dialog .review-reply').length===3,'new reply and history persist after F5');
  check(writes===0,'F5 never resubmits');
  if(location.hash!=='#modal-preview'){close();reset();}
  if(location.hash==='#empty-preview'){records=[];$('#quality-retry').click();await wait(180);await ready();check(!$('#quality-empty').hidden&&$('#quality-empty').textContent.includes('Chưa có đánh giá'),'empty preview honest');}
 }else if(mode==='service'){
  check($('[data-review-count]').textContent==='1 đánh giá'&&$('[data-review-average]').textContent==='3.0 / 5','public saved rating survives F5');
  $('[data-review-open]').click();check($('#review-form').elements.rating.value==='3'&&$('#review-form').elements.message.value==='','own edit prefill after reload');
  $('[data-review-cancel]').click();check(writes===0,'F5 does not create duplicate');
 }else{
  check(all('[data-review]').length===7,'User own history after F5');const form=$('[data-review="101"]');
  check(form.elements.rating.value==='3'&&form.elements.comment.value==='Đã chỉnh sửa','User edited review loaded from API');
  check(form.closest('article').textContent.includes('Phản hồi của chủ đánh giá'),'User reply persists after F5');check(writes===0,'reload no auto writes');
 }
 finish();return;
}
if(mode==='admin'){
 check(!$('#quality-api-error').hidden&&all('#quality-stats strong').every(e=>e.textContent==='—'),'initial error not fake zero KPI');
 $('#quality-retry').click();await wait(170);await ready();
 check($('#quality-empty').textContent.includes('Chưa có đánh giá')&&!$('#quality-empty').hidden,'true empty state');
 check(all('#quality-stats strong').map(e=>e.textContent).join(',')==='—,0,0,0','empty KPI honest');
 records=seed();persist();$('#quality-retry').click();await wait(180);await ready();
 check(all('#quality-stats strong').map(e=>e.textContent).join(',')==='3,4,7,4,2','filtered KPI numeric definitions');
 check(all('#quality-stats .line-icon').length===4,'four KPI icons');check($('#quality-stats').textContent.includes('theo số sao'),'not AI sentiment');
 check(all('#quality-rows tr').length===5,'five rows page1');
 check(!/Admin Core|Admin Operations|Finance & Quality|Dashboard/.test($('.admin-sidebar').textContent),'Vietnamese sidebar');
 const ids=all('#quality-rows .reviews-code').map(e=>e.textContent);$('[data-review-page="2"]').click();
 check(all('#quality-rows tr').length===2&&!all('#quality-rows .reviews-code').some(e=>ids.includes(e.textContent)),'page2 no repeats');
 check($('#quality-rows').textContent.includes('<img src=x')&&!$('#quality-rows img'),'escaped review HTML');

 $('#quality-search').value='cham soc';input($('#quality-search'));check(all('#quality-rows tr').length===1,'search unaccented resets page');
 $('#quality-stars').value='1';input($('#quality-stars'));check(!$('#quality-empty').hidden,'combined empty filter');reset();
 $('#quality-from').value='10/11/2026';input($('#quality-from'));$('#quality-to').value='10/11/2026';input($('#quality-to'));
 check(all('#quality-rows tr').length===1&&$('#quality-rows').textContent.includes('DG-1')&&$('#quality-rows').textContent.includes('10/11/2026 00:05'),'Vietnam midnight and inclusive day filter');
 check($('#quality-from-picker').value==='2026-11-10','visible date serializes ISO picker');
 $('#quality-to').value='09/11/2026';input($('#quality-to'));check(!$('#quality-filter-error').hidden&&all('#quality-rows tr').length===0,'reversed range clears stale results');
 $('#quality-from').value='31/02/2026';input($('#quality-from'));check(!$('#quality-filter-error').hidden&&!$('#quality-from-picker').value,'invalid date rejected');reset();
 $('#quality-from-picker').value='2026-11-09';$('#quality-from-picker').dispatchEvent(new Event('change'));check($('#quality-from').value==='09/11/2026','calendar has dd/mm display');reset();
 await open(1);fits();
 check($('#quality-dialog').textContent.includes('Chỉ chấm sao, không có nhận xét.')&&$('#quality-dialog').textContent.includes('LH-000101'),'rating-only detail and appointment code');
 check(all('#quality-dialog .review-reply').length===2&&all('#quality-dialog .review-reply .review-reply').length===0,'flat thread');
 check($('#quality-dialog').textContent.includes('spa-admin')&&$('#quality-dialog').textContent.includes('customer-owner')&&$('#quality-dialog').textContent.includes('10/11/2026 00:10'),'sender role and Vietnam times');
 check(!$('#quality-dialog [name="rating"]')&&!$('#quality-dialog [data-delete]'),'Admin cannot edit or delete review');
 const area=$('#review-reply-content');area.focus();check(document.activeElement===area&&area.getBoundingClientRect().width>200,'reply input visible and usable');
 area.value='Phản hồi mới từ Spa <b>giữ nguyên</b>';failWrite=true;$('#quality-dialog form').requestSubmit();await wait(210);
 check($('#review-reply-status').textContent.includes('Không thể gửi')&&$('#review-reply-content').value.includes('Phản hồi mới')&&writes===0,'reply error retains draft');
 $('#quality-dialog form').requestSubmit();$('#quality-dialog form').requestSubmit();await wait(230);
 check(writes===1&&lastPost.path==='/api/reviews/1/replies/'&&lastPost.csrf==='mock-token','reply correct endpoint, CSRF and duplicate click guard');
 check(all('#quality-dialog .review-reply').length===3&&!$('#quality-dialog .review-reply b')&&$('#review-reply-status').textContent==='Đã gửi phản hồi.','saved response escaped and shown');
 close();check(!$('#quality-dialog').open,'X closes');await open(1);check(all('#quality-dialog .review-reply').length===3,'fresh modal reload retains replies');
 $('#quality-dialog .admin-dialog-actions [data-close-review]').click();check(!$('#quality-dialog').open,'footer closes');
 await open(1);window.__requestEscape=true;for(let n=0;n<30&&$('#quality-dialog').open;n++)await wait(50);check(!$('#quality-dialog').open,'Escape closes');
 failRead=true;$('[data-view-review="1"]').click();await wait(150);check($('#quality-dialog [role=alert]')&&!$('#quality-dialog form'),'modal error no stale reply form');close();
 check($('#analysis-run').disabled&&$('#analysis-mode').disabled&&$('#analysis-results').textContent.includes('chưa được kết nối'),'FR23 honestly disabled');
 check(!document.body.innerText.includes('Bản mẫu'),'no demo banner');
 const table=$('.admin-table-scroll');table.scrollLeft=table.scrollWidth;
 const action=$('#quality-rows tr .admin-row-actions button');check(action.getBoundingClientRect().right<=table.getBoundingClientRect().right+1,'action accessible by table scroll');table.scrollLeft=0;
}else if(mode==='service'){
 check($('[data-review-count]').textContent==='0 đánh giá'&&!$('[data-review-open]').hidden,'eligible completed appointment permits review');
 $('[data-review-open]').click();const form=$('#review-form');check(!form.hidden&&form.elements.appointment.value==='101','actual service form opens own appointment');
 form.requestSubmit();await wait(100);check(writes===0,'rating required before POST');
 form.elements.rating.value='5';form.elements.message.value='';form.requestSubmit();await wait(250);
 check(writes===1&&records.length===1&&records[0].comment===''&&$('[data-review-count]').textContent==='1 đánh giá','rating-only create and public reload');
 $('[data-review-open]').click();check(form.elements.rating.value==='5','edit preselected from own API');form.elements.rating.value='3';form.elements.message.value='';form.requestSubmit();await wait(240);
 check(writes===2&&records.length===1&&records[0].rating===3,'edit upsert never duplicates appointment');
 $('[data-review-open]').click();form.elements.message.value='Bản nháp không lưu';$('[data-review-cancel]').click();check(writes===2&&records[0].comment==='','cancel no write');
 check(lastPost.path==='/api/reviews/appointments/101/'&&lastPost.csrf==='mock-token','User review actual endpoint and CSRF');
}else{
 check(all('[data-review]').length===7,'User reviews render eligible own appointments');const form=$('[data-review="101"]');
 check(form.elements.rating.value==='5','User edit rating prefilled');form.elements.rating.value='3';form.elements.comment.value='Đã chỉnh sửa';form.requestSubmit();await wait(230);
 check(records.length===7&&records[0].rating===3,'User edit updates existing review');
 const reply=$('[data-reply="1"]');reply.elements.content.value='Phản hồi của chủ đánh giá';reply.requestSubmit();await wait(230);
 check(records[0].replies.length===3&&records[0].replies.at(-1).role==='User','owner reply through existing UI');
 check($('[data-reply="1"]').closest('article').textContent.includes('Phản hồi của chủ đánh giá'),'User reply rendered after API reload');
}
check(unexpected===0&&uiErrors.length===0,'no JS errors or real endpoints');persist();sessionStorage.setItem('review-ui-checks',checks);sessionStorage.setItem('review-ui-stage','reload');location.reload();
}catch(error){document.body.insertAdjacentHTML('beforeend','<pre id="test-result">FAIL '+error.message+'</pre>');}
})();
'''

def main():
    from tools.check_admin_promotions_ui import CHROME_CHECK
    chrome=CHROME_CHECK.replace("for(let i=0;i<100&&!fs.existsSync(portFile);i++)await sleep(100);\n const [port,path]=fs.readFileSync(portFile,'utf8').trim().split(/\\r?\\n/);", "let portText='';for(let i=0;i<100;i++){try{portText=fs.readFileSync(portFile,'utf8').trim();if(portText.split(/\\r?\\n/).length>=2)break;}catch{}await sleep(100);}\n const [port,path]=portText.split(/\\r?\\n/);")
    chrome=chrome.replace("await call('Page.enable');", "await call('Network.enable');await call('Network.setBlockedURLs',{urls:['http://*','https://*']});await call('Page.enable');")
    chrome=chrome.replace('i<160','i<300')
    if '--modal-preview' in sys.argv:chrome=chrome.replace('window.scrollTo({top:0,behavior:"instant"})','document.getElementById("quality-dialog").scrollIntoView()')
    from django.db.backends.base.base import BaseDatabaseWrapper
    with patch.object(BaseDatabaseWrapper,'ensure_connection',side_effect=RuntimeError('DB forbidden in review UI checks')):
        import django
        django.setup()
        from django.template.loader import render_to_string
        from django.core.management import call_command
        call_command('check')
        with tempfile.TemporaryDirectory(prefix='reviews-ui-',dir=ROOT/'staticfiles') as temp:
            helper=Path(temp)/'chrome.cjs';helper.write_text(chrome,encoding='utf-8')
            for mode,template,scripts in [('admin','admin-reviews',('admin.js','live-admin-reviews.js')),('service','service-detail',('live-service-reviews.js',)),('user','reviews',('live-reviews.js',))]:
                if any(a.startswith('--mode=') for a in sys.argv) and '--mode='+mode not in sys.argv:continue
                html=render_to_string('pages/'+template+'.html',{'auth_ui':{},'live_catalog':{},'live_promotions':{},'csrf_token':'mock-token'})
                html=re.sub(r'<script\b[^>]*>.*?</script>','',html,flags=re.S).replace('/static/',(ROOT/'static').as_uri()+'/')
                js='const mode='+json.dumps(mode)+';'+MOCK+'\n;'+(ROOT/'static/js/ui.js').read_text(encoding='utf-8')+'\n;'+(ROOT/'static/js/phase4-api.js').read_text(encoding='utf-8')+'\n;'
                for name in scripts:js+=(ROOT/'static/js'/name).read_text(encoding='utf-8-sig')+'\n;'
                html=html.replace('</body>','<script>'+js+TESTS+'</script></body>')
                fixture=Path(temp)/(template+'.html');fixture.write_text(html,encoding='utf-8')
                for width in (1440,768,500,390):
                    if any(a.startswith('--width=') for a in sys.argv) and '--width='+str(width) not in sys.argv:continue
                    config=dict(profile=str(Path(temp)/f'{mode}-{width}'),width=width,url=fixture.as_uri()+('?id=1' if mode=='service' else '')+('#modal-preview' if '--modal-preview' in sys.argv else '#empty-preview' if '--empty-preview' in sys.argv else ''),screenshot=str(ROOT/'staticfiles'/f'reviews-{mode}-{width}.png'),dom=str(ROOT/'staticfiles/reviews-ui-last.html'))
                    result=subprocess.run([r'D:\node\node.exe',str(helper)],input=json.dumps(config),capture_output=True,encoding='utf-8',errors='replace',timeout=60)
                    print(mode,width,result.stdout.strip() or 'NO RESULT',flush=True)
                    if result.returncode:print(result.stderr[-1000:]);return 1
    return 0
if __name__=='__main__':raise SystemExit(main())
