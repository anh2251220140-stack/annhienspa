"""User invoice UI checks: Django DB connections forbidden, all billing calls mocked.
Run directly; never uses the MySQL test runner, CLEAN, or the payOS gateway.
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
window.uiErrors=[];window.addEventListener('error',e=>uiErrors.push(e.message));window.addEventListener('unhandledrejection',e=>uiErrors.push(String(e.reason)));
window.spaAuth={allowed:true,isAuthenticated:()=>true,getSession:()=>({role:'User'})};
const fixtures=Array.from({length:13},(_,n)=>{const id=n+1;return {id,appointmentId:id+40,service:'Dịch vụ chăm sóc '+id,employee:'Chuyên viên thử',date:'2026-12-23',time:'08:00',appointmentStatus:'confirmed',subtotal:'390000',priceSnapshot:'390000',discount:'0',total:'390000',promotion:'',status:id===3?'paid':id===4?'cancelled':'unpaid',statusLabel:id===3?'Đã thanh toán':id===4?'Đã hủy':'Chưa thanh toán',createdAt:'2026-10-23T17:05:00Z',paymentAllowed:![3,4].includes(id),onlineEligible:![3,4,5].includes(id),promotionEditable:![3,4].includes(id),payosConfigured:true,needsReview:id===6,paymentPreference:'',payments:[],currentOnline:null,promotionUsage:null};});
Object.assign(fixtures[2],{appointmentId:4,discount:'39000',total:'351000',promotion:'HISTORY10',payments:[{status:'success',requiresReview:false,method:'online',paidAt:'2026-10-23T17:05:00Z',reference:'MOCK-ONLY'}]});
fixtures[5].paymentAllowed=false;
let failList=false,failDetail=false,failPromotion=false,failOnline=false,slowDetail=0,slowPoll=0,pollResolve=null,posts=[],unexpected=0,autoChecks=0,orderSequence=9000;
const copy=x=>JSON.parse(JSON.stringify(x)),pause=ms=>new Promise(r=>setTimeout(r,ms));
function onlineSession(id,remaining=75){const orderCode=++orderSequence;return {orderCode,amount:'351000',providerStatus:'PENDING',expiresAt:'2026-12-23T01:10:00Z',serverNow:'mock-'+orderCode,remainingSeconds:remaining,expired:false,qrImage:'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',checkoutUrl:'https://checkout.mock.invalid/'+orderCode};}
window.fetch=async(path,options={})=>{
 const respond=(body,status=200)=>({ok:status<400,status,json:async()=>copy(body)});
 if(!path.startsWith('/api/billing/')){unexpected++;throw Error('Non-mock network blocked');}
 if(path.startsWith('/api/billing/?')){
  await pause(35);if(failList){failList=false;return respond({error:'Không tải được danh sách thử nghiệm.'},503);}
  const q=new URLSearchParams(path.split('?')[1]),search=q.get('search'),status=q.get('status');
  let rows=[...fixtures].reverse().filter(i=>(!status||i.status===status)&&(!search||('HD-'+i.id).toLowerCase()===search.toLowerCase()||('LH-'+String(i.appointmentId).padStart(6,'0'))===search||i.service.toLowerCase().includes(search.toLowerCase())));
  const pages=Math.max(1,Math.ceil(rows.length/10)),page=Math.min(pages,Math.max(1,Number(q.get('page'))||1));
  return respond({items:rows.slice((page-1)*10,page*10),page,pages,total:rows.length});
 }
 const match=path.match(/^\/api\/billing\/(\d+)\/(?:([a-z-]+)\/)?$/);
 if(!match){unexpected++;throw Error('Endpoint not mocked: '+path);}
 const id=Number(match[1]),invoice=fixtures.find(i=>i.id===id),name=match[2];
 if(!invoice)return respond({error:'Không tìm thấy hóa đơn.'},404);
 if(!options.method){
  if(name==='promotions'){if(failPromotion){failPromotion=false;return respond({error:'Chưa tải được ưu đãi.'},503);}return respond({items:[{code:'TEST10',name:'Ưu đãi thử nghiệm',discount:'39000'}],unavailable:[{code:'UNSUPPORTED',reason:'Cần xác minh điều kiện.'}]});}
  if(name){unexpected++;throw Error('Unexpected GET action');}
  const saved=copy(invoice);
  if(slowPoll===id){slowPoll=0;await new Promise(r=>pollResolve=r);}
  if(slowDetail===id){slowDetail=0;await pause(280);}
  if(failDetail){failDetail=false;return respond({error:'Không tải được chi tiết thử nghiệm.'},503);}
  return respond({item:saved});
 }
 if(options.method!=='POST'||!['select-spa','promotion','remove-promotion','edit-promotion','online','refresh-online','cancel-online'].includes(name)){unexpected++;throw Error('Mutation not mocked');}
 posts.push({id,name,body:new URLSearchParams(options.body),csrf:options.headers['X-CSRFToken']});await pause(100);
 if(name==='online'&&failOnline){failOnline=false;return respond({error:'Thanh toán payOS chưa được cấu hình'},503);}
 if(name==='select-spa')invoice.paymentPreference='spa';
 if(name==='promotion'){invoice.promotion='TEST10';invoice.discount='39000';invoice.total='351000';invoice.promotionUsage={limit:1};}
 if(name==='remove-promotion'){invoice.promotion='';invoice.discount='0';invoice.total='390000';invoice.promotionUsage=null;}
 if(name==='edit-promotion')invoice.promotionEditable=true;
 if(name==='cancel-online'){invoice.currentOnline=null;invoice.paymentPreference='';return respond({item:invoice});}
 if(name==='online'){invoice.currentOnline=onlineSession(id);invoice.promotionEditable=false;invoice.paymentPreference='online';return respond({checkoutUrl:invoice.currentOnline.checkoutUrl});}
 if(name==='refresh-online'){autoChecks++;invoice.currentOnline.providerStatus='EXPIRED';invoice.currentOnline.expired=true;invoice.currentOnline.remainingSeconds=0;}
 return respond({item:invoice});
};
'''

TESTS = r'''
(async()=>{
const $=s=>document.querySelector(s),all=s=>[...document.querySelectorAll(s)];let count=0;
const check=(v,m)=>{if(!v)throw Error(m);count++;},wait=ms=>new Promise(r=>setTimeout(r,ms||100));
const ready=async()=>{for(let i=0;i<80;i++){if($('[data-invoice-list]').getAttribute('aria-busy')==='false')return;await wait(30);}throw Error('Loading did not settle');};
const selected=()=>$('[data-invoice-code]').textContent,filter=async(search='',status='')=>{$('#invoice-search').value=search;$('#invoice-status-filter').value=status;$('#invoice-filter').requestSubmit();await wait(20);await ready();};
async function choose(id){await filter('HD-'+id);check(selected()==='HD-'+id,'detail HD-'+id);check($('[data-invoice-open="'+id+'"][aria-current="true"]'),'selected card '+id);const state=fixtures.find(i=>i.id===id);check($('[data-payment-refund]').hidden===(state.status!=='paid'||state.needsReview||!!state.currentOnline),'refund guidance matches selected invoice '+id);}
const noOverflow=()=>check(document.documentElement.scrollWidth<=innerWidth,'no horizontal page overflow');
try{
await document.fonts.ready;await ready();
check(!document.querySelector('[data-invoice-select]'),'dropdown removed');
const original=new URL(location.href);const initial=Number(original.searchParams.get('id'));
if(location.hash==='#payos-return'){
 check(selected()==='HD-2'&&all('[data-invoice-row]').length===1,'payOS return selects requested invoice outside first page');
 check(fixtures[1].status==='unpaid'&&!$('[data-payment-message]').textContent.includes('Đã ghi nhận thanh toán'),'provider URL never confirms payment');
}else if(location.hash==='#initial-empty'){
 check($('[data-invoice-content]').hidden&&!$('[data-invoice-empty]').hidden,'unauthorized/missing direct ID stays empty');check(posts.length===0,'no payment on missing ID');
}else if(initial===2&&location.hash!=='#reload'){
 check(selected()==='HD-2'&&all('[data-invoice-row]').length===1,'direct ID outside first page selects correct card');
 check($('#invoice-search').value==='HD-2','direct ID is explicit searchable filter');
}else if(location.hash==='#reload'){
 check(selected()==='HD-2'&&$('#invoice-page').textContent==='2 / 2','reload URL restores page and selection');
}else{
 check(all('[data-invoice-row]').length===10&&selected()==='HD-13','server page1 exact ten');
 check($('#invoice-page').textContent==='1 / 2','server pagination');
 const ids=all('[data-invoice-row]').map(e=>e.dataset.invoiceRow);$('#invoice-next').click();await wait(20);await ready();
 check(all('[data-invoice-row]').length===3&&!all('[data-invoice-row]').some(e=>ids.includes(e.dataset.invoiceRow)),'page2 no repeat or missing IDs');
 $('[data-invoice-open="2"]').click();await wait(20);await ready();check(selected()==='HD-2','card on second page');
 check(new URL(location.href).searchParams.get('id')==='2'&&new URL(location.href).searchParams.get('page')==='2','URL stores exact page and ID');
 $('#invoice-prev').click();await wait(20);await ready();check(selected()==='HD-13','page change discards absent selection');
}
$('#invoice-reset').click();await wait(20);await ready();
check(all('[data-invoice-row]').length===10,'view all resets direct filter');
check(getComputedStyle($('.user-invoice-row')).backgroundColor==='rgb(255, 248, 241)','B2 cream cards');
const card=$('.user-invoice-row'),summary=card.querySelector('.user-invoice-summary');
check(innerWidth>600?summary.getBoundingClientRect().left>card.getBoundingClientRect().left+card.offsetWidth/2:summary.getBoundingClientRect().top>card.querySelector('h3').getBoundingClientRect().bottom,'card responsive layout');noOverflow();
await choose(3);
check($('[data-invoice-appointment]').textContent==='LH-000004 · 23/12/2026 08:00','actual appointment FK padded6');
check($('[data-invoice-issued]').textContent==='24/10/2026 00:05','issue timestamp Vietnam midnight');
check($('[data-invoice-total]').textContent==='351.000 VND'&&$('[data-invoice-price]').textContent==='390.000 VND','historical snapshot and discount');
check($('[data-invoice-row="3"]').textContent.includes('LH-000004')&&$('[data-invoice-row="3"]').textContent.includes('24/10/2026 00:05'),'card identity and timestamp');
check($('[data-payment-options]').hidden&&!$('[data-payment-receipt]').hidden,'paid no new payment, receipt retained');
check($('[data-payment-date]').textContent==='24/10/2026 00:05','receipt timestamp Vietnam');
const details=$('.invoice-card').getBoundingClientRect(),payment=$('.invoice-payment').getBoundingClientRect();
check(innerWidth>900?payment.left>details.right:payment.top>=details.bottom,'payment right desktop / below mobile');noOverflow();
await choose(4);check($('[data-payment-options]').hidden&&$('[data-payment-message]').textContent.includes('đã hủy'),'cancelled no payment');
await choose(6);check($('[data-payment-options]').hidden&&$('[data-payment-message]').textContent.includes('đối soát'),'review blocks payment');
await choose(5);check($('[data-payment-online]').hidden&&!$('[data-payment-spa]').hidden,'past appointment spa only');
check($('[data-payment-spa]').textContent.trim()==='Chọn thanh toán tại Spa','Spa button describes preference only');
const base5=copy(fixtures[4]),postCount=posts.length;
Object.assign(fixtures[4],{appointmentStatus:'completed',date:'2026-10-23',paymentPreference:'',onlineEligible:false});await choose(5);
check($('[data-payment-message]').textContent.startsWith('Chưa ghi nhận thanh toán.')&&$('[data-payment-message]').textContent.includes('Nếu bạn đã trả tiền'),'completed unpaid guides customer to contact Spa');
check(!$('[data-payment-spa]').hidden&&!$('[data-payment-spa]').disabled,'completed old appointment does not lock backend-allowed preference');
$('[data-payment-spa]').click();await wait(230);
check(fixtures[4].status==='unpaid'&&fixtures[4].payments.length===0&&posts.length===postCount+1,'completed Spa preference creates no successful payment');
check($('[data-payment-spa]').hidden&&$('[data-payment-options]').hidden&&$('[data-payment-message]').textContent.includes('lựa chọn này chưa xác nhận đã thu tiền'),'completed selected Spa hides duplicate choice, clarifies unpaid');
await choose(2);await choose(5);check($('[data-payment-spa]').hidden&&$('[data-payment-message]').textContent.startsWith('Chưa ghi nhận thanh toán.'),'server-stored preference survives reopening');
Object.assign(fixtures[4],base5,{date:'2026-10-23',appointmentStatus:'confirmed',paymentPreference:'spa'});await choose(5);
check(!$('[data-payment-message]').textContent.includes('Nếu bạn đã trả tiền')&&$('[data-payment-spa]').hidden,'past date alone is not completion; selected preference still hidden');
Object.assign(fixtures[4],base5,{paymentPreference:'spa',onlineEligible:true});await choose(5);
check($('[data-payment-spa]').hidden&&!$('[data-payment-online]').hidden&&!$('[data-payment-options]').hidden,'online remains allowed after Spa preference when API eligible');
const onlyOnline=$('[data-payment-online]').getBoundingClientRect(),optionsBox=$('[data-payment-options]').getBoundingClientRect();
check(Math.abs(onlyOnline.width-optionsBox.width)<2,'single remaining option full width');
Object.assign(fixtures[4],base5,{appointmentStatus:'completed',needsReview:true,paymentAllowed:false});await choose(5);
check($('[data-payment-message]').textContent.includes('đối soát')&&!$('[data-payment-message]').textContent.startsWith('Chưa ghi nhận'),'review warning outranks completed message');
Object.assign(fixtures[4],base5,{appointmentStatus:'completed',currentOnline:onlineSession(5),paymentPreference:'online'});fixtures[4].currentOnline.providerStatus='PROCESSING';await choose(5);
check($('[data-payment-message]').textContent.includes('đang xử lý')&&$('[data-payment-spa]').disabled,'provider processing warning and guard preserved');
Object.assign(fixtures[4],base5,{appointmentStatus:'completed',currentOnline:onlineSession(5),paymentPreference:'online'});await choose(5);
check($('[data-payment-message]').textContent.includes('chờ xác minh')&&!$('[data-payment-message]').textContent.startsWith('Chưa ghi nhận'),'unresolved payOS warning preserved');
Object.assign(fixtures[4],base5,{appointmentStatus:'completed',status:'paid',statusLabel:'Đã thanh toán',paymentAllowed:false,paymentPreference:'spa'});await choose(5);
check($('[data-payment-options]').hidden&&$('[data-payment-message]').textContent==='Đã ghi nhận thanh toán.','completed paid never offers payment again');
fixtures[4].needsReview=true;await choose(5);check($('[data-payment-refund]').hidden&&$('[data-payment-message]').textContent.includes('đối soát'),'review warning preserved even for paid record');
Object.assign(fixtures[4],base5);

await filter('khong-co');check(all('[data-invoice-row]').length===0&&$('[data-invoice-content]').hidden&&!$('[data-invoice-empty]').hidden,'empty search clears detail and payment');
check(!new URL(location.href).searchParams.has('id'),'empty removes stale URL ID');
await filter('','paid');check(all('[data-invoice-row]').length===1&&selected()==='HD-3','status filter selection');
await filter('LH-000004','unpaid');check($('[data-invoice-content]').hidden,'combined filters empty');
await choose(1);
$('[data-payment-spa]').click();$('[data-payment-spa]').click();await wait(230);
check(posts.filter(p=>p.name==='select-spa'&&p.id===1).length===1&&posts.at(-1).id===1,'single payment request belongs to selected invoice');
check($('[data-payment-spa]').hidden,'selected Spa choice not offered repeatedly');
check(fixtures[0].status==='unpaid'&&$('[data-payment-message]').textContent.includes('sau khi Spa nhận đủ tiền'),'spa choice is not cash receipt');
$('#invoice-promo-code').value='TEST10';$('[data-invoice-promo]').requestSubmit();await wait(230);
check($('[data-invoice-total]').textContent==='351.000 VND'&&$('[data-invoice-row="1"]').textContent.includes('351.000 VND'),'promotion updates detail AND card');
check($('#invoice-promo-status').textContent.includes('giữ một lượt'),'usage reservation notice retained');
$('[data-promo-remove]').click();await wait(230);check($('[data-invoice-total]').textContent==='390.000 VND','remove promotion');
$('#invoice-promo-code').value='TEST10';$('[data-invoice-promo]').requestSubmit();await wait(230);
await choose(2);await choose(1);check($('#invoice-promo-code').value==='TEST10'&&$('[data-invoice-total]').textContent==='351.000 VND','saved promotion survives re-open');
failOnline=true;$('[data-payment-online]').click();await wait(260);check($('[data-payment-message]').textContent.includes('chưa được cấu hình'),'API config error shown, not silent');
const prior=posts.length;$('[data-payment-online]').click();$('[data-payment-online]').click();await wait(260);
check(posts.length===prior+1&&posts.at(-1).id===1&&posts.at(-1).name==='online','double-click blocked, correct invoice');
check(!posts.at(-1).body.has('amount')&&posts.every(p=>p.csrf==='mock-token'),'backend amount contract, CSRF unchanged');
check(!$('[data-payment-qr-image]').hidden&&$('[data-payment-amount]').textContent==='351.000 VND'&&fixtures[0].status==='unpaid','QR uses server discounted amount, not paid');
check(/^01:1[0-5]$/.test($('[data-payment-countdown]').textContent),'server remaining time, not reset to ten minutes');
await choose(2);check($('[data-payment-qr]').hidden&&selected()==='HD-2','switch clears previous QR');
await choose(1);check(!$('[data-payment-qr]').hidden,'existing QR reused on re-open');
const before=posts.length;fixtures[0].currentOnline.remainingSeconds=0;fixtures[0].currentOnline.expired=true;await choose(1);await wait(280);
check($('[data-payment-qr-image]').hidden&&!$('[data-payment-checkout]').hasAttribute('href')&&!$('[data-payment-online]').disabled&&$('[data-payment-online]').textContent==='Làm mới mã QR','expired QR hidden, renewal offered on same invoice');
check(posts.length===before,'read/reopen never creates QR or checks provider');
const oldOrder=fixtures[0].currentOnline.orderCode;$('[data-payment-online]').click();$('[data-payment-online]').click();await wait(480);
check(posts.slice(before).map(p=>p.name).join(',')==='cancel-online,online'&&fixtures[0].currentOnline.orderCode!==oldOrder,'one click closes old QR and creates one new order on the same invoice');
check(selected()==='HD-1'&&!$('[data-payment-qr-image]').hidden&&$('[data-payment-online]').textContent==='Thanh toán online bằng payOS','new QR shown without another invoice');
$('[data-payment-refresh]').click();await wait(250);check(autoChecks===1,'only explicit click refreshes provider via mock');
failList=true;await filter('');check(!$('[data-invoice-empty]').hidden&&$('[data-invoice-content]').hidden&&!$('#invoice-retry').hidden,'list error no stale payment');
$('#invoice-retry').click();await wait(20);await ready();check(all('[data-invoice-row]').length===10,'list retry');
failDetail=true;$('[data-invoice-open="12"]').click();await wait(20);await ready();check($('[data-invoice-content]').hidden&&!$('#invoice-retry').hidden,'detail error no old payment');
$('#invoice-retry').click();await wait(20);await ready();check(selected()==='HD-12','retry exact requested invoice');
slowDetail=11;$('[data-invoice-open="11"]').click();await wait(50);
check($('[data-invoice-content]').hidden&&all('[data-invoice-open]').every(e=>e.disabled),'loading hides previous payment, locks switching');
await ready();check(selected()==='HD-11','slow detail correct');
slowPoll=11;window.dispatchEvent(new Event('focus'));await wait(20);
$('[data-invoice-open="10"]').click();await wait(20);await ready();check(selected()==='HD-10','switch while old GET in flight');
pollResolve();await wait(100);check(selected()==='HD-10','late old detail cannot overwrite new invoice');
failPromotion=true;await choose(9);check($('[data-payment-message]').textContent.includes('Chưa tải được ưu đãi'),'promotion API failure visible without wrong invoice');
await choose(8);Object.assign(fixtures[7],{status:'paid',statusLabel:'Đã thanh toán',paymentAllowed:false,payments:[{status:'success',requiresReview:false,method:'online',paidAt:'2026-11-09T08:00:00+07:00',reference:'MOCK-VERIFIED'}]});
window.dispatchEvent(new Event('focus'));await wait(150);check($('[data-payment-options]').hidden&&!$('[data-payment-receipt]').hidden&&$('[data-invoice-row="8"]').textContent.includes('Đã thanh toán'),'verified backend paid refresh updates card and receipt');
check(!$('[data-payment-refund]').hidden,'verified paid refresh shows refund guidance');
failPromotion=true;await choose(8);
check($('[data-payment-message]').textContent==='Đã ghi nhận thanh toán.','promotion request failure cannot mask confirmed paid message');
check(unexpected===0&&uiErrors.length===0,'no external/unexpected endpoint or JS error: '+uiErrors.join(','));noOverflow();
await choose(location.hash==='#spa-preview'?5:3);
if(location.hash==='#spa-preview'){Object.assign(fixtures[4],{appointmentStatus:'completed',date:'2026-10-23',onlineEligible:false});await choose(5);}
if(location.hash==='#detail-preview')$('#invoice-detail').scrollIntoView({block:'start',behavior:'instant'});
else if(location.hash!=='#spa-preview'){$('#invoice-reset').click();await wait(20);await ready();}
document.body.insertAdjacentHTML('beforeend',`<pre id="test-result">PASS ${count}</pre>`);
}catch(e){document.body.insertAdjacentHTML('beforeend','<pre id="test-result">FAIL '+e.message+'</pre>');}
})();
'''


def main():
    from tools.check_admin_promotions_ui import CHROME_CHECK
    chrome = CHROME_CHECK.replace(
        "for(let i=0;i<100&&!fs.existsSync(portFile);i++)await sleep(100);\n const [port,path]=fs.readFileSync(portFile,'utf8').trim().split(/\\r?\\n/);",
        "let portText='';for(let i=0;i<100;i++){try{portText=fs.readFileSync(portFile,'utf8').trim();if(portText.split(/\\r?\\n/).length>=2)break;}catch{}await sleep(100);}\n const [port,path]=portText.split(/\\r?\\n/);")
    chrome = chrome.replace("await call('Page.enable');", "await call('Network.enable');await call('Network.setBlockedURLs',{urls:['http://*','https://*']});await call('Page.enable');")
    if '--detail-preview' in sys.argv or '--spa-preview' in sys.argv:
        chrome = chrome.replace('window.scrollTo({top:0,behavior:"instant"})', 'document.getElementById("invoice-detail").scrollIntoView({block:"start",behavior:"instant"})')
    from django.db.backends.base.base import BaseDatabaseWrapper
    with patch.object(BaseDatabaseWrapper, 'ensure_connection', side_effect=RuntimeError('Database forbidden in User invoice UI checks')):
        import django
        django.setup()
        from django.core.management import call_command
        from django.template.loader import render_to_string
        call_command('check')
        html = render_to_string('pages/invoice.html', {'auth_ui': {}, 'live_catalog': {}, 'live_promotions': {}})
        html = re.sub(r'<script\b[^>]*>.*?</script>', '', html, flags=re.S).replace('/static/', (ROOT/'static').as_uri()+'/')
        scripts = (ROOT/'static/js/ui.js').read_text(encoding='utf-8')+'\n;'+MOCK+'\n;'
        for name in ('phase4-api.js', 'live-invoice.js'):
            scripts += (ROOT/'static/js'/name).read_text(encoding='utf-8')+'\n;'
        html = html.replace('</body>', '<input type="hidden" name="csrfmiddlewaretoken" value="mock-token"><script>'+scripts+TESTS+'</script></body>')
        with tempfile.TemporaryDirectory(prefix='user-invoice-ui-', dir=ROOT/'staticfiles') as temp:
            helper = Path(temp)/'chrome.cjs'
            helper.write_text(chrome, encoding='utf-8')
            fixture = Path(temp)/'invoice.html'
            fixture.write_text(html, encoding='utf-8')
            for width in (1440,768,500,390):
                if any(a.startswith('--width=') for a in sys.argv) and '--width='+str(width) not in sys.argv:
                    continue
                scenarios = [('list', ''), ('direct', '?id=2'), ('reload', '?page=2&id=2#reload'), ('missing', '?id=999#initial-empty'), ('payos-return', '?invoice_id=2&id=provider-link&status=PAID&orderCode=9002#payos-return'), ('payos-legacy', '?id=2&status=PAID&orderCode=9002#payos-return')] if '--all-scenarios' in sys.argv else [('detail' if '--detail-preview' in sys.argv else 'list', '#detail-preview' if '--detail-preview' in sys.argv else '')]
                if '--spa-preview' in sys.argv: scenarios=[('spa','#spa-preview')]
                for scenario, suffix in scenarios:
                    dom = ROOT/'staticfiles/user-invoice-ui-last.html'
                    config = dict(profile=str(Path(temp)/f'{width}-{scenario}'), width=width, url=fixture.as_uri()+suffix, screenshot=str(ROOT/'staticfiles'/f'user-invoice-{scenario}-{width}.png'), dom=str(dom))
                    result = subprocess.run([r'D:\node\node.exe',str(helper)], input=json.dumps(config), capture_output=True, encoding='utf-8', errors='replace', timeout=45)
                    print(width,scenario,result.stdout.strip() or 'NO RESULT',flush=True)
                    if result.returncode:
                        print(result.stderr[-1200:])
                        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
