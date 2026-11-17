/* Actual chatbot widget block, minimal DOM, deferred mock fetch; no network. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),crypto=require('node:crypto');
const source=fs.readFileSync('static/js/app.js','utf8');
const block=source.slice(source.indexOf('  const chatPages ='),source.lastIndexOf('})()'));
class Element {
  constructor(){this.children=[];this.handlers={};this.textContent='';this.hidden=false;this.disabled=false;this.style={setProperty(){}};this.classList={add:v=>{this.className+=' '+v}};this.scrollHeight=100;}
  append(...children){for(const child of children){this.children.push(child);if(typeof child==='object')child.parent=this}}
  replaceChildren(...children){this.children=[];this.textContent='';this.append(...children)}
  setAttribute(key,value){this[key]=value}
  addEventListener(name,handler){this.handlers[name]=handler}
  remove(){if(this.parent)this.parent.children=this.parent.children.filter(c=>c!==this)}
  matches(){return false}
  focus(){}
}
function harness(store={items:[],posts:0}){
  const nodes=Object.fromEntries(['.concierge-bubble','.concierge-panel','.concierge-messages','form','.concierge-status','[data-chat-provider]','[data-chat-limit]','[data-chat-close]'].map(k=>[k,new Element()]));
  const input=new Element();input.value='';nodes.form.elements={message:input};nodes['.concierge-panel'].hidden=true;
  let root,resolve,reject;
  const document={currentScript:{src:'http://fixture/static/js/app.js'},head:new Element(),body:new Element(),hidden:false,
    createElement(tag){const e=new Element();if(tag==='aside'){root=e;e.querySelector=s=>nodes[s];e.querySelectorAll=()=>[];e.contains=()=>true;}return e},
    querySelector:s=>s==='footer'?null:s.includes('csrf')?{value:'synthetic-csrf'}:null,addEventListener(){}};
  const fetch=async(url,options)=>{
    if(options.method==='POST'){
      store.posts++;await new Promise((yes,no)=>{resolve=yes;reject=no});
      store.items=[{id:1,role:'user',status:'success',content:'Dịch vụ',createdAt:'2026-11-18T01:00:00Z'},
        {id:2,role:'assistant',status:'success',content:'Phản hồi giả lập đã lưu',createdAt:'2026-11-18T01:00:01Z'}];
      return {ok:true,json:async()=>({session:{id:'fixture'},answer:{status:'success'}})};
    }
    if(url.includes('resume=1'))return {ok:true,json:async()=>({session:store.items.length?{id:'fixture'}:null,dailyLimit:30,cooldown:5,providerMode:'mock'})};
    return {ok:true,json:async()=>({session:{id:'fixture',status:'open'},items:store.items,page:1,pages:1})};
  };
  vm.runInNewContext(block,{document,window:{spaAuth:{getSession:()=>({id:1,role:'User',chatEnabled:true})},spaIcon:()=>'',addEventListener(){},visualViewport:null},
    location:{pathname:'/services.html'},URL,Intl,Date,Set,crypto,innerHeight:900,fetch,setTimeout});
  return {nodes,store,input,open:()=>nodes['.concierge-bubble'].handlers.click(),close:()=>nodes['[data-chat-close]'].handlers.click(),
    submit:()=>nodes.form.handlers.submit({preventDefault(){}}),resolve:()=>resolve(),reject:()=>reject(Error('Offline timeout'))};
}
const tick=()=>new Promise(r=>setImmediate(r));
(async()=>{
 let n=0;async function test(name,fn){await fn();console.log('PASS',name);n++}
 await test('loading is an assistant bubble in the thread; no large processing alert',async()=>{
  const h=harness();await h.open();h.input.value='Dịch vụ';h.submit();await tick();
  const log=h.nodes['.concierge-messages'];assert.equal(log.children.length,1);const pending=log.children[0];
  assert.match(pending.className,/is-pending/);assert.equal(pending.children[0].textContent,'Trợ lý An Nhiên');
  assert.equal(pending.children[1].textContent,'Đang trả lời...');assert.equal(pending.children[2].textContent,'- Đang xử lý');
  assert.equal(h.nodes['.concierge-status'].textContent,'');assert.equal(h.store.posts,1);
  h.resolve();await tick();await tick();assert.equal(log.children.length,2);assert.ok(log.children.every(e=>!e.className.includes('is-pending')));
  assert.equal(log.children[1].children[1].textContent,'Phản hồi giả lập đã lưu');
 });
 await test('failed request removes pending bubble and retains error display',async()=>{
  const h=harness();await h.open();h.input.value='Dịch vụ';h.submit();await tick();h.reject();await tick();await tick();
  assert.equal(h.nodes['.concierge-messages'].children.length,0);assert.equal(h.nodes['.concierge-status'].textContent,'Offline timeout');
 });
 await test('close/open and fresh page restore saved messages with no extra POST or duplicate',async()=>{
  const h=harness();await h.open();h.input.value='Dịch vụ';h.submit();await tick();h.resolve();await tick();await tick();
  await h.close();await h.open();assert.equal(h.store.posts,1);assert.equal(h.nodes['.concierge-messages'].children.length,2);
  const reload=harness(h.store);await reload.open();assert.equal(reload.store.posts,1);assert.equal(reload.nodes['.concierge-messages'].children.length,2);
 });
 await test('limits retain server supplied 30/day and five-second caption',async()=>{
  const h=harness();await h.open();assert.match(h.nodes['[data-chat-limit]'].textContent,/30 lượt\/ngày/);assert.match(h.nodes['[data-chat-limit]'].textContent,/5 giây/);
 });
 console.log(`${n} PASS, 0 FAIL`);
})().catch(error=>{console.error(error);process.exitCode=1});
