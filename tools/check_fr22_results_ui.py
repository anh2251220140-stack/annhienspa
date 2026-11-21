"""FR-22 presentation in real isolated Chrome; synthetic responses, no DB/API."""
from contextlib import ExitStack
from html import unescape
import json
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BOOT = r'''
window.errors=[];addEventListener('error',e=>errors.push(e.message));addEventListener('unhandledrejection',e=>errors.push(String(e.reason)));
const bottle='data:image/svg+xml,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="300" height="440"><rect width="300" height="440" fill="#faf9f6"/><rect x="115" y="35" width="70" height="55" rx="8" fill="#b89a82"/><rect x="85" y="82" width="130" height="300" rx="30" fill="#e5d7c8"/><rect x="88" y="170" width="124" height="120" fill="#fff8f1"/><text x="150" y="208" text-anchor="middle" font-size="16" fill="#795439">AN NHIÊN</text><text x="150" y="240" text-anchor="middle" font-size="12" fill="#795439">CHĂM SÓC DA</text></svg>');
const services=Array.from({length:8},(_,i)=>({id:i+1,active:true,name:'Chăm sóc da mặt dịu nhẹ '+(i+1),category:'Chăm sóc da mặt',description:'Liệu trình làm sạch và chăm sóc dịu nhẹ từ danh mục giả lập.',priceValue:350000,price:'350.000 VND',minutes:60,duration:'60 phút',careGroup:'face'}));
const products=Array.from({length:7},(_,i)=>({id:i+1,active:true,name:i?'Sản phẩm chăm sóc dịu nhẹ '+(i+1):'Bioderma Sensibio H2O – tên dài dùng kiểm tra bố cục sản phẩm',category:'Nước tẩy trang',description:'Giới thiệu sản phẩm giả lập. '.repeat(35),benefits:'Hỗ trợ làm sạch dịu nhẹ. '.repeat(12),ingredients:'Thông tin thành phần giả lập được giữ đầy đủ.',note:'Trao đổi với chuyên viên trước khi sử dụng.',image:bottle,skins:['Da dầu'],audiences:['Da dầu'],price:i===1?'120000':null,brand:i===1?'Thương hiệu giả lập':undefined}));
window.spaCatalog={services,products,relations:services.flatMap(s=>products.map(p=>({serviceId:s.id,productId:p.id})))};
window.spaAuth={isAuthenticated:()=>true,getProfile:()=>({skin_type:'Da dầu',care_needs:['Kiểm soát dầu, chăm sóc da mụn'],budget:null,preferences:'Dịu nhẹ'})};
const read=()=>({role:'User'});window.responseFixture={mode:'ai',items:[],alternatives:[]};window.requests=[];
window.fetch=async(url,options)=>{if(url!='/api/ai/recommendations/')throw Error('Unexpected API');requests.push({url,options});return {ok:true,json:async()=>responseFixture};};
'''

CHECK = r'''
(async()=>{const checks=[],rowChecks=[];const check=(ok,name)=>{if(!ok)throw Error(name);checks.push(name);};
const $=s=>document.querySelector(s),all=s=>[...document.querySelectorAll(s)];
try{
const form=$('[data-recommendation-form]'),out=$('[data-recommendation-results]');
const protectedParts=()=>['header','footer','[data-recommendation-form]','.catalog-toolbar','[data-catalog-grid]'].map(s=>$(s)?.outerHTML).join('');
const protectedBefore=protectedParts();check(!out.children.length,'initial empty result');
for(const count of [0,1,2,3,4,7]){
 const reason='Lý do do AI trả về: ưu tiên làm sạch dịu nhẹ, đối chiếu nhu cầu và dữ liệu dịch vụ. '.repeat(count===3?8:1);
 responseFixture={mode:count===0?'rule':'ai',items:services.slice(0,count).map((s,i)=>({id:s.id,name:s.name,price:'350000',minutes:60,reason:i===0?reason+' Nội dung dài cần được giữ đầy đủ.'.repeat(12):reason,caution:'Lưu ý giả lập.',products:products.slice(0,count)})),alternatives:[{id:8,name:'Phương án khác',price:'400000',minutes:60}]};
 const original=JSON.stringify(responseFixture);form.requestSubmit();await new Promise(r=>setTimeout(r,30));
 check(JSON.stringify(responseFixture)===original,`response unchanged ${count}`);
 check(all('[data-recommended-service]').length===count,`service count ${count}`);
 check(all('[data-recommended-product]').length===count,`product count ${count}`);
 check(protectedParts()===protectedBefore,`form/header/footer/catalog unchanged ${count}`);
 check(document.documentElement.scrollWidth<=innerWidth+1,`no horizontal overflow ${count}`);
 for(const card of all('[data-recommended-service],[data-recommended-product]')){
  const rect=card.getBoundingClientRect();check(rect.left>=-1&&rect.right<=innerWidth+1,`card fits ${count}`);
  check(card.scrollWidth<=card.clientWidth+1,`card content fits ${count}`);
  for(const a of card.querySelectorAll('a')){
   const id=card.dataset.recommendedService||card.dataset.recommendedProduct;
   check(a.getAttribute('href')===(a.textContent==='Đặt lịch'?`booking.html?service=${id}`:`${card.hasAttribute('data-recommended-service')?'service':'product'}-detail.html?id=${id}`),'original navigation');
   const box=a.getBoundingClientRect();check(box.width>0&&box.height>=43&&box.right<=innerWidth+1,'action visible');
  }
 }
 for(const el of all('.recommendation-reasons li'))check(el.textContent===responseFixture.items.find(r=>r.id===Number(el.closest('[data-recommended-service]').dataset.recommendedService)).reason,'AI reason preserved');
 const serviceCards=all('[data-recommended-service]');
 const rows=new Map();for(const card of serviceCards){const top=Math.round(card.getBoundingClientRect().top);rows.set(top,[...(rows.get(top)||[]),card]);}
 for(const row of rows.values()){
  if(row.length<2)continue;
  const heights=row.map(c=>c.getBoundingClientRect().height),buttons=row.map(c=>c.querySelector('.review-actions').getBoundingClientRect().bottom);
  const heightDifference=Math.max(...heights)-Math.min(...heights),buttonDifference=Math.max(...buttons)-Math.min(...buttons);
  check(heightDifference<1,'equal service height in row');check(buttonDifference<1,'service actions aligned at bottom');
  rowChecks.push({count,cards:row.length,heightDifference,buttonDifference});
 }
 if(innerWidth<=500&&count>=2)check(serviceCards[0].getBoundingClientRect().height>serviceCards[1].getBoundingClientRect().height+20,'mobile natural height');
 for(const image of all('.recommendation-product-image'))check(getComputedStyle(image).objectFit==='contain','image contains packaging');
 for(const details of all('.fr22-product-details')){details.open=true;check(details.textContent.includes(products[0].ingredients),'full detail accessible');details.open=false;}
 if(count>0){
  for(const grid of all('.fr22-grid')){
   const cards=[...grid.children],last=cards.at(-1).getBoundingClientRect(),peers=cards.filter(c=>Math.abs(c.getBoundingClientRect().top-last.top)<2);
   if(peers.length===1){const box=grid.getBoundingClientRect();check(Math.abs((last.left+last.right)/2-(box.left+box.right)/2)<2,`last card centered ${count}`);}
   if(innerWidth<=500)check(new Set(cards.map(c=>Math.round(c.getBoundingClientRect().left))).size===1,'mobile one column');
  }
  check(!out.textContent.includes('undefined'),'no undefined labels');
  check(!all('[data-recommended-product="1"] .recommendation-meta').length,'no invented product price');
  if(count>=2)check($('[data-recommended-product="2"] .recommendation-meta').textContent.includes('120.000'),'real fixture price');
 }
}
// Capture the key one-service/one-product layout after all count scenarios.
responseFixture={mode:'ai',items:services.slice(0,location.search.includes('capture=equal')?2:1).map((s,i)=>({id:s.id,name:s.name,price:'350000',minutes:60,reason:i===0?'Ưu tiên làm sạch dịu nhẹ theo nhu cầu đã cung cấp. '.repeat(5):'Ưu tiên làm sạch dịu nhẹ.',products:[products[0]]})),alternatives:[]};
form.requestSubmit();await new Promise(r=>setTimeout(r,30));
check(!errors.length,'no JavaScript errors');
if(location.search.includes('capture=products'))$('.fr22-products').scrollIntoView({block:'start',behavior:'instant'});
else out.scrollIntoView({block:'start',behavior:'instant'});
parent.postMessage({status:'PASS',width:innerWidth,checks:checks.length,scenarios:[0,1,2,3,4,7],rowChecks,errors},'*');
}catch(e){parent.postMessage({status:'FAIL',width:innerWidth,message:e.message,checks:checks.length,errors},'*');}})();
'''


def main():
    output = ROOT / ('docs/fr22-equal-cards-20261122' if '--equal' in sys.argv else 'docs/fr22-results-ui-20261122')
    output.mkdir(exist_ok=True)
    source = (ROOT/'static/js/app.js').read_text(encoding='utf-8')
    block = source[source.index('  const recommendation ='):source.index('  const chatPages =')]
    from tools.chat_sqlite import configure
    with TemporaryDirectory(prefix='fr22-results-ui-') as temp, ExitStack() as stack:
        folder = Path(temp)
        configure(stack, folder)
        from unittest.mock import patch
        stack.enter_context(patch('django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection',side_effect=AssertionError('DB forbidden')))
        from django.template.loader import render_to_string
        html = render_to_string('pages/services.html', {'live_catalog':{},'live_promotions':[],'auth_ui':{}})
        html = re.sub(r'<script\b[^>]*>.*?</script>', '', html, flags=re.S)
        html = html.replace('"/static/', '"'+(ROOT/'static').as_uri()+'/')
        csp="<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; style-src 'unsafe-inline' file:; script-src 'unsafe-inline'; img-src file: data:; font-src file:; connect-src 'none'; form-action 'none'\">"
        html = html.replace('<head>','<head>'+csp)
        html = html.replace('</body>','<script>'+BOOT+'\n'+block+'\n'+CHECK+'</script></body>')
        fixture = folder/'services.html'
        fixture.write_text(html,encoding='utf-8')
        results=[]
        capture = 'equal' if '--equal' in sys.argv else 'products' if '--products' in sys.argv else 'one-card'
        for width in (1920,1440,768,500,390):
            driver=folder/f'driver-{width}.html'
            driver.write_text('<!doctype html><meta charset="utf-8"><style>html,body{margin:0}iframe{display:block;border:0}pre{display:none}</style><script>addEventListener("message",e=>{let p=document.createElement("pre");p.id="result";p.textContent=JSON.stringify(e.data);document.body.append(p)});</script>'+f'<iframe width="{width}" height="1400" src="{fixture.as_uri()}?capture={capture}"></iframe>',encoding='utf-8')
            run=subprocess.run([r'C:\Program Files\Google\Chrome\Application\chrome.exe','--headless','--disable-gpu','--disable-background-networking','--no-first-run','--allow-file-access-from-files',f'--user-data-dir={folder / ("chrome-"+str(width))}',f'--window-size={max(550,width+32)},1500','--force-device-scale-factor=1','--virtual-time-budget=6000','--screenshot='+str(output/f'{capture}-{width}.png'),'--dump-dom',driver.as_uri()],capture_output=True,encoding='utf-8',errors='replace',timeout=60)
            match=re.search(r'<pre id="result">(.*?)</pre>',run.stdout,re.S)
            if not match:
                (output/f'failure-{width}.html').write_text(run.stdout,encoding='utf-8')
                print(run.stderr[-1400:],flush=True)
            record=json.loads(unescape(match[1])) if match else {'status':'FAIL','width':width,'message':'Chrome produced no result'}
            results.append(record)
            (output/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps(record,ensure_ascii=True),flush=True)
            if record['status']!='PASS':return 1
    return 0


if __name__=='__main__':
    raise SystemExit(main())
