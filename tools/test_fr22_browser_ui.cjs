/* Execute the existing services recommendation UI block, no DOM framework/network. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../static/js/app.js'),'utf8');
const block=source.slice(source.indexOf('  const recommendation ='),source.indexOf('  const chatPages ='));
assert.ok(block.includes('/api/ai/recommendations/'));
const services=Array.from({length:7},(_,i)=>({id:i+1,active:true,name:'Dịch vụ giả '+(i+1),category:'Giả lập',description:'Dịu nhẹ, cấp ẩm',priceValue:200000+i*30000,price:'200.000 VND',minutes:60,duration:'60 phút',careGroup:i<3?'face':'relax'}));
const products=Array.from({length:3},(_,i)=>({id:i+1,active:true,name:'Sản phẩm giả '+(i+1),category:'Giả lập',description:'Dưỡng ẩm',skins:['Da khô'],audiences:['Da khô'],benefits:['Chăm sóc giả lập']}));
function harness({mode='ai',items=null,error=null,alternatives=[],defer=false,networkError=false}={}){
  let calls=0,submit,release,reject;
  const status={textContent:''},results={innerHTML:'',replaceChildren(){this.innerHTML='';}},button={disabled:false};
  const elements={skin:{value:'',options:[{value:''},{value:'Da khô'}]},needs:{value:''},budget:{value:'',get valueAsNumber(){return Number(this.value)}},interests:{value:''},duration:{value:''}};
  const form={elements,reportValidity:()=>true,querySelector:s=>s==='[type="submit"]'?button:null,addEventListener:(type,fn)=>{if(type==='submit')submit=fn;}};
  const root={hidden:true,setAttribute(){},querySelector:s=>s==='form'?form:s==='[data-recommendation-status]'?status:s==='[data-recommendation-results]'?results:null};
  const fetch=async(url,options)=>{
    calls++;if(defer)await new Promise((resolve,fail)=>{release=resolve;reject=fail});if(networkError)throw Error('Network unavailable');assert.equal(url,'/api/ai/recommendations/');assert.equal(options.method,'POST');assert.equal(options.headers['X-CSRFToken'],'fake-csrf');
    const body=JSON.parse(options.body);assert.equal(body.needs,'face');assert.equal(body.skin,'Da khô');
    return {ok:!error,json:async()=>error?{error}:{mode,label:mode==='ai'?'Gợi ý AI':'Gợi ý theo quy tắc',alternatives,items:items||[{id:1,name:services[0].name,price:'200000',minutes:60,reason:'Lý do giả lập đã kiểm tra',products:[{id:1,serviceId:1,name:'Sản phẩm giả 1',description:'Giá minh họa: 120.000 VND',ingredients:'Công thức giả lập',benefits:'Chăm sóc',image:'images/care-5.jpg'}]}]}};
  };
  vm.runInNewContext(block,{
    window:{spaAuth:{isAuthenticated:()=>true,getProfile:()=>({skin_type:'Da khô',budget:600000,preferences:'Dịu nhẹ',care_needs:['Dưỡng ẩm, cải thiện da khô']})},spaCatalog:{services,products,relations:[{serviceId:1,productId:1}]}},
    document:{querySelector:s=>s==='[data-recommendation]'?root:{value:'fake-csrf'}},read:()=>({role:'User'}),fetch,
  });
  return {root,status,results,button,get calls(){return calls},release:()=>release(),reject:()=>reject(Error("Network unavailable")),submit:()=>submit({preventDefault(){}})};
}
async function main(){
  let count=0;async function test(name,fn){await fn();count++;console.log('PASS',name)}
  await test('page load and fresh reload do not POST',()=>{for(let i=0;i<2;i++){const h=harness();assert.equal(h.calls,0);assert.equal(h.root.hidden,false)}});
  await test('AI mode uses actual UI renderer and product links',async()=>{const h=harness();await h.submit();assert.match(h.status.textContent,/Đề xuất bởi AI/);assert.match(h.results.innerHTML,/Lý do giả lập đã kiểm tra/);assert.match(h.results.innerHTML,/data-recommended-product="1"/);assert.equal(h.calls,1)});
  await test('fallback label stays rule, not AI',async()=>{const h=harness({mode:'rule'});await h.submit();assert.match(h.status.textContent,/Đề xuất theo quy tắc/);assert.ok(!h.status.textContent.includes('Đề xuất bởi AI'))});
  await test('cooldown API error is shown without fabricated results',async()=>{const h=harness({error:'Vui lòng chờ 5 giây'});await h.submit();assert.equal(h.status.textContent,'Vui lòng chờ 5 giây');assert.equal(h.results.innerHTML,'');assert.equal(h.button.disabled,false)});
  await test('empty eligible list is displayed without service or product fabrication',async()=>{const h=harness({mode:'rule',items:[]});await h.submit();assert.match(h.status.textContent,/0 liệu trình/);assert.ok(!h.results.innerHTML.includes('data-recommended-product="'))});
  await test('provider reason markup is escaped',async()=>{const h=harness({items:[{id:1,name:'Fixture',price:'200000',minutes:60,reason:'<script>untrusted</script>'}]});await h.submit();assert.ok(!h.results.innerHTML.includes('<script>untrusted'));assert.match(h.results.innerHTML,/&lt;script&gt;/)});
  await test('alternatives exclude all main suggestions and duplicate alternatives',async()=>{
    const h=harness({items:[{id:1,name:'Main 1',price:'200000',minutes:60,reason:'Fixture'},{id:2,name:'Main 2',price:'230000',minutes:60,reason:'Fixture'}],alternatives:[{id:1,name:'DUP_MAIN',price:'200000',minutes:60},{id:2,name:'DUP_MAIN_2',price:'230000',minutes:60},{id:3,name:'OTHER_OPTION',price:'260000',minutes:60},{id:3,name:'DUP_OTHER',price:'260000',minutes:60}]});
    await h.submit();assert.ok(!h.results.innerHTML.includes('DUP_MAIN'));assert.ok(!h.results.innerHTML.includes('DUP_OTHER'));assert.equal((h.results.innerHTML.match(/OTHER_OPTION/g)||[]).length,1);
  });
  await test('unrelated catalog product is not displayed without backend approval',async()=>{const h=harness({items:[{id:1,name:'Main',price:'200000',minutes:60,reason:'Fixture',products:[]}]});await h.submit();assert.ok(!h.results.innerHTML.includes('data-recommended-product="'))});
  await test('product constituents and images are taken from approved catalog data',async()=>{const h=harness();await h.submit();assert.match(h.results.innerHTML,/Công thức giả lập/);assert.match(h.results.innerHTML,/120.000 VND/);assert.match(h.results.innerHTML,/recommendation-product-image/)});
  await test('loading exists only while pending, locks duplicate submit and disappears after real response',async()=>{
    const h=harness({defer:true});const task=h.submit();assert.equal(h.button.disabled,true);assert.match(h.results.innerHTML,/recommendation-spinner/);assert.match(h.results.innerHTML,/Đang phân tích\.\.\./);assert.ok(!h.results.innerHTML.includes('data-recommended-service'));await h.submit();assert.equal(h.calls,1);h.release();await task;assert.equal(h.button.disabled,false);assert.ok(!h.results.innerHTML.includes('recommendation-spinner'));assert.match(h.results.innerHTML,/data-recommended-service/);
  });
  await test('transport failure removes spinner and leaves no fabricated result',async()=>{
    const h=harness({defer:true});const task=h.submit();h.reject();await task;assert.equal(h.button.disabled,false);assert.equal(h.results.innerHTML,'');assert.equal(h.status.textContent,'Network unavailable');
  });
  console.log(`${count} PASS, 0 FAIL`);
}
main().catch(error=>{console.error(error);process.exitCode=1});
