"""Render the two Admin finance templates against mock APIs, with DB forbidden.
No tests here write MySQL or contact payOS. The 205-test runner is unchanged.
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

MOCK=r"""
window.spaAuth={allowed:true,isAuthenticated:()=>true,getSession:()=>({role:'Admin'})};
window.spaCatalog={services:[],products:[],staff:[]};
window.spaPromotions={items:[],referenceDate:'2026-11-09'};
const fixtures=[1,2,3,4,5,6,10].map((id,index)=>({id,appointmentId:[2,3,4,6,7,8,12][index],customer:'Khách '+id,service:'Dịch vụ chăm sóc '+id,employee:'Chuyên viên thử',date:'2026-10-23',time:'14:30',appointmentStatus:id===5?'cancelled':id===6?'pending':'completed',subtotal:'390000',priceSnapshot:'390000',discount:id===3?'39000':'0',total:id===3?'351000':'390000',promotion:id===3?'TEST10':'',status:id===3?'paid':id===5?'cancelled':'unpaid',statusLabel:id===3?'Đã thanh toán':id===5?'Đã hủy':'Chưa thanh toán',createdAt:'2026-10-23T15:00:00Z',paymentAllowed:![3,4,5,6].includes(id),needsReview:id===4,paymentPreference:'',currentOnline:id===10?{providerStatus:'PAID'}:id===2?{providerStatus:'PENDING'}:null,payments:[]}));
function addPayment(id,invoiceId,status,extras={}){const p={id,invoiceId,amount:invoiceId===3?'351000':'390000',method:'online',status,statusLabel:status,createdAt:'2026-10-23T15:00:00Z',paidAt:null,reference:'TEST-REF-'+id,providerStatus:status==='success'?'PAID':'PENDING',requiresReview:false,recordedBy:null,...extras};fixtures.find(i=>i.id===invoiceId).payments.push(p);return p;}
addPayment(21,2,'pending');addPayment(31,3,'cancelled');addPayment(32,3,'cancelled');addPayment(33,3,'success',{paidAt:'2026-10-23T17:05:00Z'});addPayment(41,4,'review',{requiresReview:true,paidAt:'2026-10-24T01:00:00+07:00'});addPayment(51,5,'cancelled');addPayment(101,10,'pending',{providerStatus:'PAID'});
let initialFailure=true,failGet=false,failCash=false,ambiguousCash=false,emptyLedger=false,posts=0,successes=0,lastPost,lastHeader,unexpected=0;
const copy=x=>JSON.parse(JSON.stringify(x));
window.fetch=async(path,options={})=>{
 const respond=(body,ok=true,status=ok?200:400)=>({ok,status,json:async()=>copy(body)});
 if(path==='/api/billing/ledger/'&&!options.method){if(initialFailure){initialFailure=false;return respond({error:'Không thể tải sổ thanh toán.'},false,503);}return respond({invoices:emptyLedger?[]:[...fixtures].sort((a,b)=>b.id-a.id),payments:emptyLedger?[]:fixtures.flatMap(i=>i.payments).sort((a,b)=>b.id-a.id)});}
 const match=path.match(/^\/api\/billing\/(\d+)\/(cash\/)?$/);
 if(!match){unexpected++;throw Error('Unexpected endpoint: '+path);}
 const invoice=fixtures.find(i=>i.id===Number(match[1]));
 if(!invoice)return respond({error:'Không tìm thấy hóa đơn.'},false,404);
 if(!options.method){if(failGet){failGet=false;return respond({error:'Không thể tải chi tiết.'},false,503);}return respond({item:invoice});}
 if(options.method!=='POST'||!match[2]){unexpected++;throw Error('Unexpected mutation');}
 posts++;lastPost={path,body:new URLSearchParams(options.body)};lastHeader=options.headers['X-CSRFToken'];
 await new Promise(r=>setTimeout(r,100));
 if(Number(lastPost.body.get('amount'))!==Number(invoice.total))return respond({error:'Số tiền phải khớp tổng hóa đơn.'},false);
 if(failCash){failCash=false;return respond({error:'Chưa xác minh được phiên payOS đã đóng.'},false);}
 invoice.status='paid';invoice.statusLabel='Đã thanh toán';invoice.paymentAllowed=false;invoice.paymentPreference='spa';successes++;
 addPayment(200+invoice.id,invoice.id,'success',{method:'spa',paidAt:'2026-11-09T09:00:00+07:00',reference:'TEST-SPA-'+invoice.id,recordedBy:1,providerStatus:''});
 if(ambiguousCash){ambiguousCash=false;return respond({error:'Yêu cầu chưa rõ kết quả. Hãy kiểm tra lại hóa đơn.'},false,503);}
 return respond({item:invoice});
};
"""
TESTS=r"""
(async()=>{
const $=s=>document.querySelector(s),all=s=>[...document.querySelectorAll(s)],wait=()=>new Promise(r=>setTimeout(r,100));let count=0;
const check=(value,message)=>{if(!value)throw Error(message);count++;},input=e=>e.dispatchEvent(new Event('input',{bubbles:true})),change=e=>e.dispatchEvent(new Event('change',{bubbles:true}));
const module=document.querySelector('[data-admin-finance]').dataset.adminFinance;
const reset=()=>$('#finance-reset').click();
const search=value=>{$('#finance-search').value=value;input($('#finance-search'));};
const close=()=>$('#finance-dialog [data-finance-close]')?.click();
const fits=()=>{const r=$('#finance-dialog').getBoundingClientRect();check(r.top>=0&&r.bottom<=innerHeight&&r.right<=innerWidth&&r.left>=0,'modal fits');};
async function openInvoice(id){const code='HD-'+String(id).padStart(6,'0');reset();search('HD-'+id);if(module==='invoices')$(`[data-finance-view="invoice"][data-record="${code}"]`).click();else{const b=$('#finance-rows [data-finance-view="payment"]');check(!!b,'payment for invoice exists');b.click();await wait();$(`#finance-dialog [data-finance-view="invoice"][data-record="${code}"]`).click();}await wait();await wait();}
try{
await document.fonts.ready;await wait();await wait();
check(!$('#finance-error').hidden&&$('#finance-stats').children.length===0,'initial API error, no fake KPI');$('#finance-retry').click();await wait();await wait();
check($('#finance-error').hidden&&all('#finance-stats article').length===4,'retry and 4 KPIs');
const expected=module==='invoices'?['351.000 VND','7','1','5']:['351.000 VND','7','2','3'];
check(JSON.stringify(all('#finance-stats strong').map(e=>e.textContent))===JSON.stringify(expected),'unchanged global KPI formula');
check($('.finance-kpi-scope').textContent.includes('Toàn bộ dữ liệu'),'KPI scope');check(all('#finance-rows tr').length===5,'page size 5');
check(all('#finance-stats .finance-stat-symbol svg').length===4,'KPI icons');check(getComputedStyle($('#finance-rows .admin-row-actions svg')).color==='rgb(185, 144, 87)','action champagne icon');
check(!/Admin Core|Admin Operations|Finance & Quality/.test($('.admin-nav').textContent),'Vietnamese sidebar');
check(/LH-\d{6}/.test($('#finance-rows').textContent)&&!/LH-\d{1,5}(?!\d)/.test($('#finance-rows').textContent),'six digit appointment codes');
check(/HD-\d{6}/.test($('#finance-rows').textContent)&&!/HD-\d{1,5}(?!\d)/.test($('#finance-rows').textContent),'six digit invoice codes');
check($('#finance-rows').textContent.includes('23/10/2026'),'Vietnam date display');
const scroll=$('.admin-table-scroll');scroll.scrollLeft=scroll.scrollWidth;const last=$('#finance-rows tr:first-child .admin-row-actions button');check(last.getBoundingClientRect().right<=scroll.getBoundingClientRect().right+1,'last column accessible');scroll.scrollLeft=0;
$('[data-finance-page="2"]').click();check(all('#finance-rows tr').length===2,'page2');search('LH-000003');check(all('#finance-rows tr').length===1,'search true FK resets page');
$('#finance-status').value=module==='invoices'?'paid':'success';change($('#finance-status'));check(!$('#finance-empty').hidden,'combined filter empty');
check(JSON.stringify(all('#finance-stats strong').map(e=>e.textContent))===JSON.stringify(expected),'filters do not change KPI');reset();
if(module==='payments'){
$('#finance-date-basis').value='paidAt';change($('#finance-date-basis'));$('#finance-date-display').value='24/10/2026';input($('#finance-date-display'));
check(all('#finance-rows tr').length===2&&$('#finance-rows').textContent.includes('GD-33'),'paid date uses Vietnam midnight');
$('#finance-status').value='success';change($('#finance-status'));check(all('#finance-rows tr').length===1,'date and status combine');
$('#finance-date-basis').value='createdAt';change($('#finance-date-basis'));check(!$('#finance-empty').hidden,'creation versus payment date');reset();
$('#finance-status').value='review';change($('#finance-status'));check(all('#finance-rows tr').length===1&&$('#finance-rows').textContent.includes('Cần đối soát'),'review filter kept');reset();
}
$('#finance-date-display').value='31/02/2026';input($('#finance-date-display'));check(!$('#finance-date-error').hidden&&!$('#finance-date').value,'invalid date feedback');reset();
check(!$('#finance-date-display').value&&$('#finance-date-error').hidden,'date reset');
for(const code of ['HD-1','HD-000001']){
  const scoped=new URL(location.href);scoped.searchParams.set('invoice',code);history.replaceState(null,'',scoped);search('HD-000001');
  check(all('#finance-rows tr').length===(module==='invoices'?1:0),'exact invoice cross-link '+code);reset();
}
await openInvoice(3);fits();check($('#finance-dialog').textContent.includes('LH-000004')&&$('#finance-dialog').textContent.includes('351.000 VND'),'invoice identity and historical money');
check(!$('#finance-dialog [data-cash-form]'),'paid has no cash action');check(all('#finance-dialog .admin-finance-related').length===3,'multiple historical attempts');
check(!/snapshot|catalog|Bản mẫu|Không thu tiền thật/i.test($('#finance-dialog').textContent),'no technical demo copy');
check($('#finance-dialog a[href="admin-payments.html?invoice=HD-000003"]'),'invoice to payment link');
const body=$('#finance-dialog .admin-service-modal-scroll');body.scrollTop=body.scrollHeight;
check(body.scrollHeight>body.clientHeight&&$('#finance-dialog .admin-dialog-actions').getBoundingClientRect().bottom<=innerHeight,'body scroll, footer visible');
$('#finance-dialog [data-finance-view="payment"][data-record="GD-33"]').click();await wait();fits();
check($('#finance-dialog').textContent.includes('24/10/2026 · 00:05'),'payment detail local timestamp');check($('#finance-dialog a[href="admin-invoices.html?invoice=HD-000003"]'),'payment to invoice link');
$('#finance-dialog .admin-dialog-actions [data-finance-close]').click();check(!$('#finance-dialog').open,'footer close');
await openInvoice(4);check(!$('#finance-dialog [data-cash-form]')&&$('#finance-dialog').textContent.includes('đối soát'),'review invoice blocked with reason');close();
await openInvoice(5);check(!$('#finance-dialog [data-cash-form]')&&$('#finance-dialog').textContent.includes('đã hủy'),'cancelled blocked');close();
await openInvoice(10);check(!$('#finance-dialog [data-cash-form]')&&$('#finance-dialog').textContent.includes('đang xử lý'),'provider processing blocked');close();
await openInvoice(2);check($('#finance-dialog [data-cash-form]')&&$('#finance-dialog').textContent.includes('xác minh và đóng phiên cũ'),'pending online warns before allowed backend verification');close();
if(module==='invoices'){
await openInvoice(6);check(!$('#finance-dialog [data-cash-form]')&&$('#finance-dialog').textContent.includes('chưa được xác nhận'),'pending appointment no cash');close();
await openInvoice(1);fits();check($('#finance-dialog').textContent.includes('LH-000002'),'HD-1 actual FK not invoice ID');
const timingFixture=fixtures.find(i=>i.id===1);
timingFixture.cashTimingIssue='Chưa đến giờ hẹn. Chỉ được ghi nhận thanh toán tại Spa từ 09:00 ngày 16/11/2026 (giờ Việt Nam).';
close();await openInvoice(1);
check(!$('#finance-dialog [data-cash-form]')&&$('#finance-dialog').textContent.includes(timingFixture.cashTimingIssue)&&posts===0,'server cutoff hides cash form and explains timing');
timingFixture.cashTimingIssue='';close();await openInvoice(1);
const form=$('[data-cash-form]');form.scrollIntoView({block:'center'});await wait();const amount=form.querySelector('[name="amount"]');amount.focus();
check(amount.getBoundingClientRect().width>200&&document.activeElement===amount,'cash amount usable');
check(form.querySelector('button').textContent.includes('Xác nhận đã thu tiền tại Spa'),'cash CTA');
check(!$('[data-cash-consent]').checked&&getComputedStyle($('[data-cash-consent]')).colorScheme==='light','checkbox clear and unchecked');
form.requestSubmit();await wait();check(posts===0,'checkbox required');$('[data-cash-consent]').checked=true;
amount.value='1';form.requestSubmit();await wait();await wait();check(posts===1&&successes===0&&!$('[data-cash-status]').hidden,'backend amount error, no receipt');
amount.value='390000';failCash=true;form.requestSubmit();await wait();await wait();check(posts===2&&successes===0&&$('[data-cash-status]').textContent.includes('Chưa xác minh'),'provider error displayed');
form.requestSubmit();form.requestSubmit();check(form.querySelector('button').disabled,'busy state');await wait();await wait();
check(posts===3&&successes===1,'repeat click one receipt');check(lastPost.path==='/api/billing/1/cash/'&&lastPost.body.get('amount')==='390000'&&lastHeader==='mock-token','API amount, ID, CSRF unchanged');
check(!$('#finance-dialog [data-cash-form]')&&$('#finance-dialog').textContent.includes('Đã ghi nhận thanh toán tại Spa.'),'paid receipt replaces action');
check($('#finance-stats strong').textContent==='741.000 VND','KPI refreshed once after receipt');close();
// Ambiguous API outcome: client must read local state, not automatically POST again.
const target=fixtures.find(i=>i.id===6);target.appointmentStatus='confirmed';target.paymentAllowed=true;
await openInvoice(6);$('[data-cash-consent]').checked=true;ambiguousCash=true;const before=posts;$('[data-cash-form]').requestSubmit();await wait();await wait();
check(posts===before+1&&!$('#finance-dialog [data-cash-form]')&&$('#finance-dialog').textContent.includes('chưa rõ kết quả'),'ambiguous result re-read, no automatic retry');close();
}
reset();failGet=true;const b=$('#finance-rows [data-finance-view]');b.click();await wait();check(!$('#finance-error').hidden&&$('#finance-data-note').textContent==='Không thể tải chi tiết.','detail GET error');$('#finance-retry').click();await wait();
await openInvoice(3);window.__requestEscape=true;for(let n=0;n<20&&$('#finance-dialog').open;n++)await wait();check(!$('#finance-dialog').open,'native Escape');
reset();search('no such record');check(!$('#finance-empty').hidden&&all('#finance-pagination button').every(b=>b.disabled),'empty state and pager');reset();
emptyLedger=true;$('#finance-retry').click();await wait();check(!$('#finance-empty').hidden&&all('#finance-stats strong').map(e=>e.textContent).join(',')==='0 VND,0,0,0','empty ledger has accurate zero KPIs');emptyLedger=false;$('#finance-retry').click();await wait();
check(document.documentElement.scrollWidth<=innerWidth,'no page overflow');check(unexpected===0,'no payment-provider endpoints');
if(location.hash==='#invoice-preview')await openInvoice(3);
if(location.hash==='#cash-preview'){await openInvoice(2);$('[data-cash-form]').scrollIntoView({block:'center'});await wait();}
if(location.hash==='#payment-preview'){await openInvoice(3);$('#finance-dialog [data-finance-view="payment"][data-record="GD-33"]').click();await wait();}
window.scrollTo({top:0,behavior:'instant'});document.body.insertAdjacentHTML('beforeend',`<pre id="test-result">PASS ${count}</pre>`);
}catch(e){document.body.insertAdjacentHTML('beforeend','<pre id="test-result">FAIL '+e.message+'</pre>');}
})();
"""

def main():
    from tools.check_admin_promotions_ui import CHROME_CHECK
    # Retry the temporary Chrome port file until it is fully written/unlocked.
    chrome=CHROME_CHECK.replace("for(let i=0;i<100&&!fs.existsSync(portFile);i++)await sleep(100);\n const [port,path]=fs.readFileSync(portFile,'utf8').trim().split(/\\r?\\n/);", "let portText='';for(let i=0;i<100;i++){try{portText=fs.readFileSync(portFile,'utf8').trim();if(portText.split(/\\r?\\n/).length>=2)break;}catch{}await sleep(100);}\n const [port,path]=portText.split(/\\r?\\n/);")
    from django.db.backends.base.base import BaseDatabaseWrapper
    with patch.object(BaseDatabaseWrapper,'ensure_connection',side_effect=RuntimeError('Database forbidden in finance UI checks')):
        import django
        django.setup()
        from django.template.loader import render_to_string
        with tempfile.TemporaryDirectory(prefix='finance-ui-',dir=ROOT/'staticfiles') as temp:
            helper=Path(temp)/'chrome.cjs';helper.write_text(chrome,encoding='utf-8')
            for module in ('invoices','payments'):
                if any(arg.startswith('--only=') for arg in sys.argv) and '--only='+module not in sys.argv:continue
                html=render_to_string('pages/admin-'+module+'.html',{'auth_ui':{},'live_catalog':{},'live_promotions':{}})
                html=re.sub(r'<script\b[^>]*>.*?</script>','',html,flags=re.S).replace('/static/',(ROOT/'static').as_uri()+'/')
                scripts=(ROOT/'static/js/ui.js').read_text(encoding='utf-8')+'\n;'+MOCK+'\n;'
                for script in ('admin.js','phase4-api.js','admin-finance.js'):scripts+=(ROOT/'static/js'/script).read_text(encoding='utf-8')+'\n;'
                html=html.replace('</body>','<input type="hidden" name="csrfmiddlewaretoken" value="mock-token"><script>'+scripts+TESTS+'</script></body>')
                fixture=Path(temp)/('admin-'+module+'.html');fixture.write_text(html,encoding='utf-8')
                for width in (1440,768,500,390):
                    if any(arg.startswith('--width=') for arg in sys.argv) and '--width='+str(width) not in sys.argv:continue
                    mode=next((m for m in ('invoice','payment','cash') if '--'+m+'-preview' in sys.argv),'')
                    dom=Path(temp)/f'{module}-{width}.html'
                    config=dict(profile=str(Path(temp)/f'{module}-{width}'),width=width,url=fixture.as_uri()+('#'+mode+'-preview' if mode else ''),screenshot=str(ROOT/'staticfiles'/f'finance-{module}-{mode or "list"}-{width}.png'),dom=str(dom))
                    result=subprocess.run([r'D:\node\node.exe',str(helper)],input=json.dumps(config),capture_output=True,encoding='utf-8',errors='replace',timeout=45)
                    print(module,width,result.stdout.strip() or 'NO RESULT',flush=True)
                    if result.returncode:
                        if dom.exists():(ROOT/'staticfiles/finance-ui-failure.html').write_bytes(dom.read_bytes())
                        print(result.stderr[-1200:]);return 1
    return 0

if __name__=='__main__':
    raise SystemExit(main())
