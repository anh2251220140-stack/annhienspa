// Actual invoice script with an in-memory DOM/API; no browser/network/database.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync('static/js/live-invoice.js', 'utf8');
async function fixture(search = '') {
  const nodes = new Map();
  const node = key => {
    if (!nodes.has(key)) nodes.set(key, {
      hidden: false, textContent: '', value: '', attrs: {},
      setAttribute(k,v) { this.attrs[k] = v; }, getAttribute(k) { return this.attrs[k]; },
      removeAttribute(k) { delete this.attrs[k]; }, querySelectorAll() { return []; },
      addEventListener() {}, replaceChildren() {}, add() {}, focus() {}, scrollIntoView() {},
    });
    return nodes.get(key);
  };
  const requests = [], timers = new Map(); let sequence = 0;
  const context = {
    URL, URLSearchParams, Intl, Date, performance: {now:()=>0},
    location: {search, href:'https://offline.invalid/invoice.html'+search},
    history: {replaceState(_state,_title,url) { context.lastUrl=String(url); }},
    document: {hidden:false, querySelector:node, addEventListener() {}},
    Option: function(text,value) { this.text=text; this.value=value; },
    setTimeout(fn) { const id=++sequence; timers.set(id,fn); return id; },
    clearTimeout(id) { timers.delete(id); }, setInterval() {}, clearInterval() {},
    window: {addEventListener() {}, spaLive: {
      api: async (path,data) => { requests.push({path,data}); return context.response(path,data); },
      escape:String, money:String,
    }},
  };
  vm.createContext(context);
  await vm.runInContext(source.replace('await load(initialId);', `window.test={
    initialId, appliedSearch, appliedStatus, page, paint, poll, open, schedule, updateUrl,
    setNotice(value){notice=value;}, getInvoice(){return invoice;}
  };`), context);
  return {context, api:context.window.test, node, requests, timers};
}
function invoice(status='unpaid') {
  return {id:6,appointmentId:7,service:'Synthetic service',employee:'Synthetic',
    date:'2026-12-23',time:'10:00',status,statusLabel:status==='paid'?'Đã thanh toán':'Chưa thanh toán',
    payments:[],paymentPreference:'online',paymentAllowed:status==='unpaid',
    promotionEditable:false,onlineEligible:status==='unpaid',needsReview:false,currentOnline:null};
}
(async()=>{
  const tests=[
    ['dedicated invoice ID survives provider ID and status',async()=>{
      const {api}=await fixture('?invoice_id=6&id=provider-link&status=PAID&orderCode=123');
      assert.equal(api.initialId,6); assert.equal(api.appliedSearch,'HD-6'); assert.equal(api.appliedStatus,'');
    }],
    ['legacy payment return selects invoice outside first page',async()=>{
      const {api}=await fixture('?id=6&status=PAID&orderCode=123');
      assert.equal(api.appliedSearch,'HD-6'); assert.equal(api.page,1);
    }],
    ['ordinary list filters and pagination are preserved',async()=>{
      const {api}=await fixture('?id=6&search=massage&status=unpaid&page=2');
      assert.equal(api.appliedSearch,'massage'); assert.equal(api.appliedStatus,'unpaid'); assert.equal(api.page,2);
    }],
    ['invalid and unsafe invoice IDs are rejected',async()=>{
      for(const value of ['0','-6','bad','9007199254740993']){
        const {api}=await fixture('?invoice_id='+value+'&status=PAID'); assert.equal(api.initialId,null);
      }
    }],
    ['return marker is removed before selecting another invoice',async()=>{
      const {api,context}=await fixture('?invoice_id=6&id=provider&status=PAID&orderCode=123');
      api.paint({...invoice(),id:7}); api.updateUrl();
      const params=new URL(context.lastUrl).searchParams;
      assert.equal(params.get('id'),'7'); assert.equal(params.has('invoice_id'),false);
      assert.equal(params.has('orderCode'),false); assert.equal(params.has('status'),false);
    }],
    ['old error does not hide confirmed paid message',async()=>{
      const {api,node}=await fixture(); api.setNotice('Old network failure'); api.paint(invoice('paid'));
      assert.equal(node('[data-payment-message]').textContent,'Đã ghi nhận thanh toán.');
    }],
    ['promotion load failure cannot mask confirmed payment on reopen',async()=>{
      const {api,context,node}=await fixture(); context.response=async path=>{
        if(path.endsWith('/promotions/'))throw Error('Promotion unavailable'); return {item:invoice('paid')};
      };
      await api.open(6); assert.equal(node('[data-payment-message]').textContent,'Đã ghi nhận thanh toán.');
    }],
    ['poll updates server-confirmed payment and stops timer',async()=>{
      const {api,context,node,requests,timers}=await fixture(); api.paint(invoice()); api.schedule();
      assert.equal(timers.size,1); context.response=async()=>({item:invoice('paid')});
      await api.poll(); assert.equal(node('[data-payment-message]').textContent,'Đã ghi nhận thanh toán.');
      assert.equal(timers.size,0); assert.equal(requests.length,1); assert.equal(requests[0].data,undefined);
    }],
    ['return status alone never confirms payment',async()=>{
      const {api,node}=await fixture('?invoice_id=6&status=PAID&orderCode=123'); api.paint(invoice());
      assert.notEqual(node('[data-payment-message]').textContent,'Đã ghi nhận thanh toán.');
      assert.equal(api.getInvoice().status,'unpaid');
    }],
    ['expired QR cannot overwrite confirmed payment',async()=>{
      const {api,node}=await fixture(); api.paint({...invoice('paid'),currentOnline:{expired:true,remainingSeconds:0}});
      assert.equal(node('[data-payment-message]').textContent,'Đã ghi nhận thanh toán.');
      assert.equal(node('[data-payment-qr]').hidden,true);
    }],
    ['hidden browser tab does not query the provider',async()=>{
      const {api,context,requests,timers}=await fixture(); api.paint(invoice()); context.document.hidden=true;
      await api.poll(); assert.equal(requests.length,0); assert.equal(timers.size,1);
    }],
    ['pending status remains pending and polling continues',async()=>{
      const {api,context,requests,timers}=await fixture(); api.paint(invoice());
      context.response=async()=>({item:invoice()}); await api.poll();
      assert.equal(api.getInvoice().status,'unpaid'); assert.equal(timers.size,1);
      assert.ok(requests.every(r=>r.data===undefined));
    }],
    ['review warning is retained',async()=>{
      const {api,node}=await fixture(); api.paint({...invoice('paid'),needsReview:true});
      assert.match(node('[data-payment-message]').textContent,/đối soát/);
    }],
  ];
  let failed=0;
  for(const [name,test] of tests){try{await test();console.log('PASS '+name);}catch(e){failed++;console.log('FAIL '+name+': '+e.message);}}
  console.log(`${tests.length-failed} PASS, ${failed} FAIL`); process.exitCode=failed?1:0;
})();
