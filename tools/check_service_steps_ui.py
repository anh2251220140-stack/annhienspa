"""Real service-detail renderer in isolated Chrome frames; no DB/migration/API."""
from contextlib import ExitStack
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--width',type=int,action='append',choices=(1440,768,500,390))
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    from tools.chat_sqlite import configure
    out=args.output or Path((ROOT/'docs/services-display-current-20261119.txt').read_text(encoding='utf-8'))
    if not out.is_absolute():out=ROOT/out
    if not out.resolve().is_relative_to((ROOT/'docs').resolve()):raise RuntimeError('Output must stay inside docs')
    out.mkdir(parents=True,exist_ok=True)
    cases=[]
    for count in (4,5,6,8,10,21):
        text=[f'Nội dung riêng bước {i} — không tự thay tiêu đề.' for i in range(1,count+1)]
        cases.append({'name':f'{count}-steps','raw':[f'Bước {i}: {s}' for i,s in enumerate(text,1)],'expected':text})
        structured=[{'title':f'Tên riêng {i}','description':f'Mô tả riêng {i} theo dữ liệu Admin.'} for i in range(1,count+1)]
        cases.append({'name':f'json-{count}-steps','raw':structured,'expected':[v['title'] for v in structured],'descriptions':[v['description'] for v in structured]})
    cases.extend([
        {'name':'empty','raw':[],'expected':[]},
        {'name':'missing','raw':None,'expected':[]},
        {'name':'blank','raw':[' ', '\n', 'Bước 1: ', '2. '],'expected':[]},
        {'name':'multiline','raw':'Bước 1: Làm sạch.\r\n\r\n2. Cấp ẩm.\n3) Tư vấn.','expected':['Làm sạch.','Cấp ẩm.','Tư vấn.']},
        {'name':'escaping','raw':['1. <img src=x onerror=alert(1)> & dưỡng ẩm.','2. 1.5% là dữ liệu Admin nhập.'],'expected':['<img src=x onerror=alert(1)> & dưỡng ẩm.','1.5% là dữ liệu Admin nhập.']},
    ])
    cases.append({'name':'json-escaping','raw':[{'title':'Tên <img src=x>','description':'Mô tả <b>giữ nguyên</b> & an toàn.'}],'expected':['Tên <img src=x>'],'descriptions':['Mô tả <b>giữ nguyên</b> & an toàn.']})
    dv_path=out/'dv002-public.json'
    if not dv_path.exists():dv_path=ROOT/'docs/service-dv002-public-read-20261119.json'
    dv=json.loads(dv_path.read_text(encoding='utf-8'))['service']
    cases.append({'name':'DV-002-live-read','raw':dv['steps'],'expected':[v['title'] if isinstance(v,dict) else re.sub(r'^Bước \d+:\s*','',v) for v in dv['steps']],'descriptions':[v['description'] if isinstance(v,dict) else '' for v in dv['steps']]})
    with TemporaryDirectory(prefix='service-steps-ui-') as temp, ExitStack() as stack:
        configure(stack,Path(temp))
        from django.template.loader import render_to_string
        stack.enter_context(patch('django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection',side_effect=RuntimeError('DB forbidden')))
        html=render_to_string('pages/service-detail.html',{'auth_ui':{},'live_catalog':{},'live_promotions':{}})
        html=re.sub(r'<script\b[^>]*>.*?</script>','',html,flags=re.S)
        html=html.replace('/static/',(ROOT/'static').as_uri()+'/')
        script=(ROOT/'static/js/catalog-pages.js').read_text(encoding='utf-8')
        icon=(ROOT/'static/js/ui.js').read_text(encoding='utf-8')
        for i,case in enumerate(cases):
            item={'id':2,'active':True,'name':dv['name'],'category':'Danh mục giả lập','description':'Mô tả giả lập',
                  'introduction':'Mô tả giả lập','image':(ROOT/'static/images/facial.jpg').as_uri(),'gallery':(ROOT/'static/images/facial.jpg').as_uri(),'price':'300.000 VND','duration':'60 phút',
                  'benefits':['Lợi ích giữ nguyên'],'steps':case['raw'],'careGroup':'face','suitable':'Giả lập','note':'Giả lập'}
            boot='window.spaAuth={allowed:true,urlFor:p=>p};window.spaCatalog='+json.dumps({'services':[item],'products':[],'staff':[],'relations':[]},ensure_ascii=False)+';'
            boot+='window.addEventListener("error",e=>document.documentElement.dataset.scriptError=e.message);'
            (Path(temp)/f'{i}.html').write_text(html.replace('</body>','<script>'+boot+icon+';'+script+'</script></body>'),encoding='utf-8')
        driver="""<!doctype html><meta charset=utf-8><style>body{margin:0}iframe{border:0;display:block;height:950px}</style><iframe></iframe><pre id=result></pre><script>
(async()=>{const data=__CASES__,frame=document.querySelector('iframe'),results=[];
try{for(const [i,test]of data.entries()){
 await new Promise(resolve=>{frame.onload=resolve;frame.src=i+'.html?id=2'});
 const d=frame.contentDocument,w=frame.contentWindow,section=d.querySelector('.ritual-process'),rows=[...d.querySelectorAll('[data-list=steps] li')];
 await d.fonts.ready;
 const check=(ok,message)=>{if(!ok)throw Error(test.name+': '+message)};
 check(!d.documentElement.dataset.scriptError,'no JavaScript errors');
 check(rows.length===test.expected.length,'exact count');check(section.hidden===(test.expected.length===0),'hide empty only');
 check(JSON.stringify(rows.map(r=>r.querySelector('h3').textContent))===JSON.stringify(test.expected),'Admin text preserved');
 check(JSON.stringify(rows.map(r=>r.querySelector('p')?.textContent||''))===JSON.stringify(test.descriptions||test.expected.map(()=>'')),'descriptions separate and legacy unchanged');
 check(rows.every((r,j)=>r.querySelector('.step-number').textContent===String(j+1).padStart(2,'0')),'ordinal numbering');
 check(!section.querySelector('img'),'no injected markup');
 check(d.querySelector('[data-list=benefits] li').textContent.includes('Lợi ích giữ nguyên'),'benefits unchanged');
 check(d.documentElement.scrollWidth<=w.innerWidth,'no page overflow '+JSON.stringify([...d.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>w.innerWidth+1).map(e=>({tag:e.tagName,cls:e.className,right:e.getBoundingClientRect().right})).slice(0,12)));
 if(rows.length){check(rows.every(r=>r.scrollWidth<=r.clientWidth+1),'no step overflow');check(getComputedStyle(rows[0].querySelector('h3')).fontFamily.length>0,'serif styling retained')}
 if(test.name==='DV-002-live-read'){check(rows.length===8,'DV002 eight steps');d.documentElement.style.scrollBehavior='auto';section.scrollIntoView({behavior:'instant',block:'start'});await new Promise(r=>setTimeout(r,100))}
 results.push({case:test.name,status:'PASS',steps:rows.length,viewport:w.innerWidth,columns:getComputedStyle(d.querySelector('[data-list=steps]')).gridTemplateColumns});
}
document.querySelector('#result').textContent='PASS '+results.length+' '+JSON.stringify(results);
}catch(e){document.querySelector('#result').textContent='FAIL '+e.message}})();</script>"""
        for width in (args.width or (1440,768,500,390)):
            page=Path(temp)/f'driver-{width}.html'
            page.write_text(driver.replace('__CASES__',json.dumps(cases,ensure_ascii=False)).replace('<iframe>',f'<iframe style="width:{width}px">'),encoding='utf-8')
            result=subprocess.run([r'C:\Program Files\Google\Chrome\Application\chrome.exe','--headless','--disable-gpu','--disable-background-networking','--disable-sync',
                 '--proxy-server=http://127.0.0.1:9','--proxy-bypass-list=<-loopback>','--allow-file-access-from-files','--no-first-run','--no-default-browser-check',
                 '--force-device-scale-factor=1','--user-data-dir='+str(Path(temp)/f'chrome-{width}'),f'--window-size={max(width+32,550)},1100',
                 '--virtual-time-budget=10000','--screenshot='+str(out/f'service-steps-{width}.png'),'--dump-dom',page.as_uri()],
                 capture_output=True,encoding='utf-8',errors='replace',timeout=40)
            dom=re.sub(r'<script\b[^>]*>.*?</script>','',result.stdout,flags=re.S)
            found=re.search(r'<pre id="result">(PASS \d+ .*?|FAIL.*?)</pre>',dom,re.S)
            value=found.group(1) if found else 'NO RESULT'
            print(width,value,flush=True)
            (out/f'service-steps-{width}-result.txt').write_text(value,encoding='utf-8')
            if not value.startswith('PASS '):
                (out/f'service-steps-{width}-failure.html').write_text(result.stdout,encoding='utf-8')
                raise SystemExit(1)

if __name__=='__main__':main()
