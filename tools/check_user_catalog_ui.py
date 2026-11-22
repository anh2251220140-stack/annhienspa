"""User catalog UI regression with synthetic data; no DB, migration or API."""
from contextlib import ExitStack
import json
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.chat_sqlite import configure


def main():
    out = Path((ROOT/'docs/user-three-polish-current.txt').read_text(encoding='utf-8').strip())
    selected = sys.argv[1:] or ['services','products','promotions','index','home','product-detail']
    with TemporaryDirectory(prefix='user-ui-five-') as temp, ExitStack() as stack:
        folder = Path(temp)
        configure(stack, folder)
        stack.enter_context(patch('django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection', side_effect=RuntimeError('DB forbidden')))
        from django.template.loader import render_to_string
        services = [{'id':i, 'active':True, 'name':f'Dịch vụ giả lập {i}', 'category':'Da mặt' if i%2 else 'Massage',
                     'price':'300.000 VND', 'priceValue':100000+i*1000, 'minutes':30+i, 'duration':f'{30+i} phút',
                     'image':(ROOT/'static/images/facial.jpg').as_uri(), 'description':'Nội dung kiểm thử riêng, giữ đầy đủ đường dẫn và các chức năng hiện có.'} for i in range(13,0,-1)]
        products = [{'id':i, 'active':True, 'name':f'Sản phẩm giả lập {i}', 'category':'Dưỡng da' if i%2 else 'Tinh dầu',
                     'description':'Sản phẩm giả lập với nội dung đủ dài để kiểm tra căn lề và nút xem chi tiết.',
                     'image':(ROOT/'static/images/facial.jpg').as_uri(), 'skins':['Da khô'], 'audiences':['Người trưởng thành'],
                     'benefits':['Công dụng một','Công dụng hai'], 'ingredients':'Thành phần một\nThành phần hai',
                     'usage':'Lấy lượng phù hợp, thoa nhẹ nhàng rồi làm sạch.', 'note':'Lưu ý giữ nguyên, không dùng dữ liệu thật.'} for i in range(13,0,-1)]
        catalog = {'services':services, 'products':products, 'staff':[], 'relations':[{'serviceId':1,'productId':1}]}
        promos = {'referenceDate':'2026-11-20','expiringWithinDays':7,'items':[
            {'code':f'TEST{i}', 'aliases':[], 'active':True, 'name':f'Ưu đãi giả lập {i}', 'badge':'Kiểm thử', 'accent':'warm',
             'discount':'10%', 'description':'Nội dung ưu đãi giả lập', 'startDate':'2026-11-01',
             'endDate':'2026-11-22' if i==2 else '2026-12-20'} for i in range(1,14)]}
        # Ensure inactive/expired records cannot leak into visible pages.
        catalog['services'].append(dict(services[0],id=99,active=False))
        catalog['products'].append(dict(products[0],id=99,active=False))
        promos['items'].append(dict(promos['items'][0],code='EXPIRED',endDate='2026-11-01'))
        public = json.loads((out/'public-catalog-readonly.json').read_text(encoding='utf-8'))
        for product in products:
            product['image'] = (ROOT / public['products'][(product['id']-1)%len(public['products'])]['image'].lstrip('/')).as_uri()
        for group in ('services','products'):
            for item in public[group]:
                for key in ('image','gallery'):
                    if item.get(key):item[key]=(ROOT/item[key].lstrip('/')).as_uri()
        from PIL import Image,ImageDraw
        ratio_images=[]
        for label,size in [('portrait',(240,400)),('landscape',(400,240))]:
            im=Image.new('RGB',size,'white');d=ImageDraw.Draw(im);d.rounded_rectangle((size[0]*.3,size[1]*.1,size[0]*.7,size[1]*.9),radius=10,fill='#568452');im.save(folder/(label+'.png'));ratio_images.append((folder/(label+'.png')).as_uri())
        context = {'auth_ui':{}, 'live_catalog':catalog, 'live_promotions':promos}
        scripts = '\n;'.join((ROOT/'static/js'/name).read_text(encoding='utf-8') for name in ('ui.js','card-pagination.js'))
        cases = selected
        results = []
        for name in cases:
            page_catalog=public if name in ('index','home','product-detail') else catalog
            page_context=dict(context,live_catalog=page_catalog)
            html = render_to_string(f'pages/{name}.html', page_context)
            html = re.sub(r'<script\b[^>]*>.*?</script>', '', html, flags=re.S)
            html = html.replace('"/static/', '"'+(ROOT/'static').as_uri()+'/')
            boot = 'window.spaAuth={allowed:true,urlFor:p=>p,getSession:()=>({role:"User"})};window.spaCatalog='+json.dumps(page_catalog,ensure_ascii=False)+';window.spaPromotions='+json.dumps(promos,ensure_ascii=False)+';'
            if name in ('services','products','product-detail'):
                page_script = (ROOT/'static/js/catalog-pages.js').read_text(encoding='utf-8')
            elif name=='promotions':
                page_script = (ROOT/'static/js/promotions.js').read_text(encoding='utf-8')
            else:
                page_script = ''
            tests = r'''
(async()=>{let count=0;const check=(ok,msg)=>{if(!ok)throw Error(msg);count++;};try{
[...document.images].forEach(img=>img.loading='eager');
if(document.readyState!=='complete')await new Promise(resolve=>window.addEventListener('load',resolve,{once:true}));
await document.fonts.ready;
const $=s=>document.querySelector(s), all=s=>[...document.querySelectorAll(s)];
check(!document.documentElement.dataset.jsError,'no script errors');
check($('.user-opening-hours').textContent.includes('08:00–17:00'),'shared header hours');
check(!document.body.innerText.includes('09:00 — 21:00'),'old displayed hours removed');
if(['services','products','promotions'].includes('__PAGE__')){
 const grid=$('[data-catalog-grid], [data-promotion-grid]'),nav=$('.catalog-pagination');
 check(grid.children.length===6,'first page exactly six');check(nav.textContent.includes('13'),'filtered total');
 nav.querySelector('[data-next]').click();check(grid.children.length===6,'second page six');
 nav.querySelector('[data-next]').click();check(grid.children.length===1,'last page one');check(nav.querySelector('[data-next]').disabled,'last disabled');
 nav.querySelector('[data-previous]').click();check(grid.children.length===6,'previous works');
 const search=$('input[name=search]');search.value='không có kết quả';search.dispatchEvent(new Event('input',{bubbles:true}));
 check(grid.children.length===0,'empty search');check(nav.hidden,'empty pager hidden');
 $('[data-reset],[data-reset-promotions]').click();check(grid.children.length===6,'reset restores six');check(nav.querySelector('[data-previous]').disabled,'reset page one');
 if('__PAGE__'==='services'){
  check(all('[data-card-id]').map(e=>e.dataset.cardId).join(',')==='1,2,3,4,5,6','global default order');
  const sort=$('select[name=sort]');sort.value='price-desc';sort.dispatchEvent(new Event('change',{bubbles:true}));
  check(all('[data-card-id]').map(e=>e.dataset.cardId).join(',')==='13,12,11,10,9,8','global price before pagination');
  nav.querySelector('[data-next]').click();const category=$('select[name=category]');category.value='Da mặt';category.dispatchEvent(new Event('change',{bubbles:true}));
  check(nav.querySelector('[data-previous]').disabled,'filter resets current page');check(grid.children.length===6,'filtered first six');
  check(all('[data-card-id]').every(n=>Number(n.dataset.cardId)%2===1),'category retained');
 }else if('__PAGE__'==='products'){
  const suitable=$('select[name=suitable]');suitable.value='Da khô';suitable.dispatchEvent(new Event('change',{bubbles:true}));check(grid.children.length===6,'product suitability filter');
 }else{
  const status=$('select[name=status]');status.value='ending';status.dispatchEvent(new Event('change',{bubbles:true}));check(grid.children.length===1,'promotion status filter');
  check(grid.textContent.includes('TEST2'),'eligible promotion preserved');
 }
 $('[data-reset],[data-reset-promotions]').click();
}
if(['index','home','services','products'].includes('__PAGE__')){
 const cards=all('.home-page .card-grid > .service-card, .home-page .card-grid > .product-card, [data-catalog-grid] > article');
 check(cards.length>0,'cards rendered');
 if(['index','home'].includes('__PAGE__')){
  const summaries=all('.product-info > p:not(.product-suitable)'),links=all('.product-info .text-link');
  check(summaries.length===4,'Home product preview count unchanged');
  const heights=summaries.map(n=>n.getBoundingClientRect().height);
  check(Math.max(...heights)-Math.min(...heights)<1,'Home summary heights equal');
  check(summaries.every(n=>getComputedStyle(n).webkitLineClamp==='3'),'Home three-line ellipsis');
  const columns=getComputedStyle($('.home-page #san-pham .card-grid')).gridTemplateColumns.split(' ').length;
  for(let i=0;i<links.length;i+=columns){const row=links.slice(i,i+columns).map(n=>n.getBoundingClientRect().top);check(Math.max(...row)-Math.min(...row)<1,'Home detail links aligned');}
 }

 const collection=$('.home-page .card-grid, [data-catalog-grid]');
 const home=['index','home'].includes('__PAGE__');
 check(getComputedStyle(collection).gridTemplateColumns.split(' ').length===(home?(innerWidth>900?4:2):(innerWidth>900?3:innerWidth>600?2:1)),'B2 family responsive columns');
 for(const card of cards){
  const image=card.querySelector('.product-image, :scope > img'), title=card.querySelector('h3');
  const service=card.classList.contains('service-card');
  if(service){
   check(getComputedStyle(image).objectFit==='cover','service background covers');
   check(getComputedStyle(card.querySelector('.card-shade')).display!=='none','service gradient visible');
   check(getComputedStyle(title).color==='rgb(255, 248, 241)','service light text restored');
   check(['absolute','relative'].includes(getComputedStyle(card.querySelector('.service-info')).position),'service text overlays image');
   check(!card.querySelector('.service-info').getBoundingClientRect().height||card.querySelector('.service-info').getBoundingClientRect().top>=card.getBoundingClientRect().top-1,'service text stays in card');
  }else{
   check(Math.abs(image.getBoundingClientRect().height-(home?(innerWidth>900?225:innerWidth>600?280:185):innerWidth>600?255:280))<1,'B2 product image frame');
   check(getComputedStyle(card.querySelector('img')).objectFit==='contain','product image ratio preserved');
  }
  check(card.querySelector('a[href*="detail"]'),'detail URL preserved');
  check(card.querySelector('img').naturalWidth>0,'card image loads');
  check(card.scrollWidth<=card.clientWidth+1,'card content fits '+card.className+' '+card.scrollWidth+'/'+card.clientWidth);
 }
 if('__PAGE__'==='products'){
  const audit=[];
  for(let page=1;page<=3;page++){
   [...document.images].forEach(img=>img.loading='eager');
   await Promise.all(all('[data-catalog-grid] img').map(img=>img.complete?Promise.resolve():new Promise(resolve=>{img.addEventListener('load',resolve,{once:true});img.addEventListener('error',resolve,{once:true});})));
   await new Promise(resolve=>setTimeout(resolve,0));
   for(const img of all('[data-catalog-grid] img')){
    const scale=Number(img.dataset.imageFitScale),box=JSON.parse(img.dataset.imageFitBounds),frame=img.parentElement;
    check(scale>=1&&scale<=1.1501,'controlled enlargement never shrinks');
    const ratio=Math.min(frame.clientWidth/img.naturalWidth,frame.clientHeight/img.naturalHeight);
    check(Math.max(.5-box.left,box.right-.5)*img.naturalWidth*ratio*scale<=frame.clientWidth/2+1,'horizontal packaging bounds protected');
    check(Math.max(.5-box.top,box.bottom-.5)*img.naturalHeight*ratio*scale<=frame.clientHeight/2+1,'vertical packaging bounds protected');
    check(getComputedStyle(img).padding==='0px','no extra white padding');
    audit.push({src:img.getAttribute('src').split('/').pop(),scale});
   }
   const next=$('.catalog-pagination [data-next]');if(next.disabled)break;next.click();
  }
  check(new Set(audit.map(x=>x.src)).size===12,'all twelve actual product images checked');
  window.imageFitAudit=audit;
  $('[data-reset]').click();await new Promise(resolve=>setTimeout(resolve,0));
 }
}
if('__PAGE__'==='product-detail'){
 check(getComputedStyle($('[data-image]')).objectFit==='contain','detail image contain');
 const original=window.spaCatalog.products.find(p=>p.id===2);check($('[data-ingredients]').children.length===original.ingredients.split(/\r?\n/).filter(Boolean).length,'ingredient content preserved');
 check($('[data-usage]').children.length>0,'usage content preserved');
 check($('[data-field=note]').textContent===original.note,'note preserved');
 const facts=all('.care-facts dd'),labels=all('.care-facts dt');
 const typography=n=>{const c=getComputedStyle(n);return [c.fontFamily,c.fontSize,c.fontWeight,c.lineHeight,c.marginTop,c.marginBottom].join('|');};
 check(new Set(facts.map(typography)).size===1,'four contents identical typography');
 check(new Set(labels.map(typography)).size===1,'four labels identical typography');
 check(getComputedStyle($('.care-facts')).gridTemplateColumns.split(' ').length===2,'facts remain two by two');
 const detailAudit=[],image=$('[data-image]'),saved=image.src;
 for(const src of __DETAIL_IMAGES__){
  if(image.src!==src){await new Promise((resolve,reject)=>{image.onload=resolve;image.onerror=()=>reject(Error('image load failed'));image.src=src;});}
  await new Promise(resolve=>setTimeout(resolve,0));
  const frame=image.parentElement,box=JSON.parse(image.dataset.imageFitBounds),scale=Number(image.dataset.imageFitScale),ratio=Math.min(image.clientWidth/image.naturalWidth,image.clientHeight/image.naturalHeight);
  check(scale>=1&&scale<=1.1501,'detail zoom controlled');
  check(Math.max(.5-box.left,box.right-.5)*image.naturalWidth*ratio*scale<=image.clientWidth/2+1,'detail horizontal subject protected');
  check(Math.max(.5-box.top,box.bottom-.5)*image.naturalHeight*ratio*scale<=image.clientHeight/2+1,'detail vertical subject protected');
  const pad=innerWidth>650?64:48,oldHeight=innerWidth>650?480:340,previousRatio=Math.min((frame.clientWidth-pad)/image.naturalWidth,(oldHeight-pad)/image.naturalHeight);
  check(ratio*scale>previousRatio*1.08,'actual subject enlarged beyond old padding');
  detailAudit.push({src:src.split('/').pop(),scale,paintGain:ratio*scale/previousRatio});
 }
 image.src=saved;await new Promise(resolve=>{if(image.complete)resolve();else image.onload=resolve;});await new Promise(resolve=>setTimeout(resolve,0));
 window.detailImageAudit=detailAudit;

 const panels=all('.product-ritual > section');
 if(innerWidth>650){check(Math.abs(panels[0].getBoundingClientRect().width-panels[1].getBoundingClientRect().width)<1,'even information columns');check(Math.abs(panels[0].getBoundingClientRect().top-panels[1].getBoundingClientRect().top)<1,'aligned panels');}
}
check(document.documentElement.scrollWidth<=innerWidth+1,'no page horizontal overflow');
const focus=$('[data-catalog-grid], [data-promotion-grid], .home-page #san-pham .card-grid, [data-catalog-detail="product"] .catalog-detail-hero');if(focus)focus.scrollIntoView({block:'start',behavior:'instant'});
parent.postMessage({status:'PASS',checks:count,page:'__PAGE__',width:innerWidth,imageAudit:window.imageFitAudit,detailImageAudit:window.detailImageAudit},'*');
}catch(e){parent.postMessage({status:'FAIL',page:'__PAGE__',message:e.message,width:innerWidth},'*');}})();
'''.replace('__PAGE__',name).replace('__DETAIL_IMAGES__',json.dumps([p['image'] for p in public['products']]+ratio_images))
            onerror='window.addEventListener("error",e=>document.documentElement.dataset.jsError=e.message);window.fetch=()=>{throw Error("Network forbidden in UI fixture")};'
            fixture = folder/f'{name}.html'
            fixture.write_text(html.replace('</body>','<script>'+onerror+boot+scripts+';'+page_script+';'+((ROOT/'static/js/product-image-fit.js').read_text(encoding='utf-8') if name in ('products','product-detail') else '')+';'+tests+'</script></body>'),encoding='utf-8')
            for width in (1440,768,500,390):
                driver=folder/f'driver-{name}-{width}.html'
                driver.write_text('<!doctype html><meta charset="utf-8"><style>html,body{margin:0;background:#3a2419}iframe{display:block;border:0}pre{display:none}</style><script>addEventListener("message",e=>{const p=document.createElement("pre");p.id="result";p.textContent=JSON.stringify(e.data);document.body.append(p)});</script>'+f'<iframe width="{width}" height="950" src="{fixture.as_uri()}?id=2"></iframe>',encoding='utf-8')
                result=subprocess.run([r'C:\Program Files\Google\Chrome\Application\chrome.exe','--headless','--disable-gpu','--disable-background-networking','--disable-sync','--proxy-server=http://127.0.0.1:9','--proxy-bypass-list=<-loopback>','--allow-file-access-from-files','--no-first-run','--no-default-browser-check','--force-device-scale-factor=1','--user-data-dir='+str(folder/f'chrome-{name}-{width}'),f'--window-size={max(width+32,550)},1050','--virtual-time-budget=3500','--screenshot='+str(out/f'{name}-{width}.png'),'--dump-dom',driver.as_uri()],capture_output=True,encoding='utf-8',errors='replace',timeout=35)
                match=re.search(r'<pre id="result">(.*?)</pre>',result.stdout,re.S)
                if not match:
                    (out/f'failure-{name}-{width}.html').write_text(result.stdout,encoding='utf-8')
                    raise RuntimeError(f'No Chrome result: {name} {width}')
                from html import unescape
                record=json.loads(unescape(match[1]));results.append(record)
                (out/'chrome-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
                print(json.dumps(record,ensure_ascii=True),flush=True)
                if record['status']!='PASS':raise SystemExit(1)


if __name__=='__main__':
    main()
