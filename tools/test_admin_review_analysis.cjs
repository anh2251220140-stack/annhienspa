/* Offline DOM/event regression. No browser, server, sockets or external packages. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../static/js/live-admin-reviews.js'), 'utf8');
const review = {id: 7, rating: 5, customer: 'Fixture', service: 'Fixture', comment: 'Fixture', replies: [], createdAt: '2026-11-17T02:00:00Z'};
const saved = {reviewId: 7, mode: 'rule', sentiment: 'positive', priority: 'low', themes: ['Fixture'], summary: 'Fixture', actions: ['Fixture'], analyzedAt: '2026-11-17T03:00:00Z', stale: false};
const settle = () => new Promise(resolve => setImmediate(resolve));
async function harness({analysis = saved, rows = [review], analyses = null, deferGet = false, deferPost = false} = {}) {
  const elements = new Map(), gets = [], posts = [];
  function element(id) {
    if (!elements.has(id)) elements.set(id, {
      value: id === '#analysis-mode' ? 'aggregate' : '', hidden: false, disabled: false,
      innerHTML: '', textContent: '', listeners: {}, children: [],
      addEventListener(type, fn) { this.listeners[type] = fn; },
      setAttribute() {}, querySelector: element,
      replaceChildren(...children) { this.children = children; this.innerHTML = ''; if (id === '#analysis-review') this.value = children.length ? String(children[0].value) : ''; },
      async fire(type) { if (this.listeners[type]) await this.listeners[type]({target: this}); },
    });
    return elements.get(id);
  }
  const root = element('root');root.querySelector = element;
  let releaseGet, releasePost;
  const api = async url => {
    gets.push(url);
    if (url === '/api/reviews/') return {items: rows};
    const match = /^\/api\/ai\/reviews\/(\d+)\/analyze\/$/.exec(url);assert.ok(match);
    if (deferGet) await new Promise(resolve => {releaseGet = resolve;});
    return {analysis: analyses ? analyses.find(a=>a.reviewId===Number(match[1])) || null : analysis};
  };
  const context = {
    document: {querySelector: selector => selector === '[data-reviews-admin]' ? root : element(selector)},
    window: {spaLive: {api, escape: value => String(value ?? '').replace(/</g, '&lt;')}, spaIcon: () => ''},
    Option: function(text, value) {this.text = text;this.value = value;},
    fetch: async (url, options) => {
      assert.equal(url, '/api/ai/reviews/analyze/');assert.equal(options.method, 'POST');
      posts.push(JSON.parse(options.body));
      if (deferPost) await new Promise(resolve => {releasePost = resolve;});
      return {ok: true, json: async () => ({items: analyses || [saved]})};
    },
  };
  await vm.runInNewContext(source, context);await settle();
  return {element, gets, posts, releaseGet: () => releaseGet(), releasePost: () => releasePost()};
}
async function main() {
  let count = 0;
  async function test(name, fn) {await fn();count++;console.log('PASS', name);}
  await test('load and F5 restore with GET only', async () => {
    for (let i = 0; i < 2; i++) {
      const h = await harness();
      assert.match(h.element('#analysis-results').innerHTML, /DG-7/);
      assert.equal(h.posts.length, 0);assert.equal(h.gets.length, 2);
    }
  });
  await test('no saved result does not POST', async () => {
    const h = await harness({analysis: null});
    assert.match(h.element('#analysis-results').innerHTML, /Chưa có kết quả đã lưu/);assert.equal(h.posts.length, 0);
  });
  await test('stale is visibly marked as not current', async () => {
    const h = await harness({analysis: {...saved, stale: true}});
    assert.match(h.element('#analysis-results').innerHTML, /Đánh giá đã thay đổi kể từ lần phân tích gần nhất\. Vui lòng phân tích lại\./);
    assert.match(h.element('#analysis-results').innerHTML, /không còn hiện hành/);
  });
  await test('invalid date clears IDs, selection, results and blocks POST', async () => {
    const h = await harness();h.element('#quality-from').value = '31/02/2026';await h.element('#quality-from').fire('input');
    assert.equal(h.element('#analysis-review').value, '');assert.equal(h.element('#analysis-results').innerHTML, '');
    assert.equal(h.element('#analysis-run').disabled, true);
    await h.element('#analysis-run').fire('click');assert.equal(h.posts.length, 0);
  });
  await test('tampered individual selection cannot POST old ID', async () => {
    const h = await harness();h.element('#analysis-mode').value = 'individual';h.element('#analysis-review').value = '999';
    await h.element('#analysis-run').fire('click');assert.equal(h.posts.length, 0);
  });
  await test('explicit click alone sends matching IDs and shows result', async () => {
    const h = await harness();await h.element('#analysis-run').fire('click');
    assert.deepEqual(h.posts, [{reviewIds: [7]}]);assert.match(h.element('#analysis-results').innerHTML, /DG-7/);
  });
  await test('late GET cannot restore results after invalid filter', async () => {
    const h = await harness({deferGet: true});h.element('#quality-to').value = 'bad';await h.element('#quality-to').fire('input');
    h.releaseGet();await settle();assert.equal(h.element('#analysis-results').innerHTML, '');assert.equal(h.posts.length, 0);
  });
  await test('late POST cannot restore results after invalid filter', async () => {
    const h = await harness({deferPost: true});const pending = h.element('#analysis-run').fire('click');
    h.element('#quality-to').value = 'bad';await h.element('#quality-to').fire('input');h.releasePost();await pending;
    assert.equal(h.element('#analysis-results').innerHTML, '');assert.equal(h.element('#analysis-run').disabled, true);
  });
  const fixtures = Array.from({length:5}, (_,i)=>({...review,id:i+1,customer:'Fixture '+(i+1),comment:i===4?'':'Synthetic comment '+(i+1)}));
  const results = fixtures.map(r=>({...saved,reviewId:r.id,mode:'ai',themes:['Không gian','Không gian'],summary:'Stored summary '+r.id,actions:['Stored action '+r.id]}));
  function countAttr(html,name) {const m=new RegExp('data-fr23-'+name+'="(\\d+)"').exec(html);assert.ok(m,name);return Number(m[1]);}
  await test('one AI result has all B2 analysis sections', async()=>{
    const h=await harness({analysis:{...saved,mode:'ai'}}),html=h.element('#analysis-results').innerHTML;
    for(const label of ['Bức tranh cảm xúc','Chủ đề được nhắc đến','Điểm khách hàng hài lòng','Góp ý cần cải thiện','Lộ trình hành động đề xuất','Phân tích từng đánh giá'])assert.ok(html.includes(label));
    assert.equal(countAttr(html,'ai'),1);assert.equal(h.posts.length,0);
  });
  await test('five AI records count only reviews with text', async()=>{
    const h=await harness({rows:fixtures,analyses:results}),html=h.element('#analysis-results').innerHTML;
    assert.equal(countAttr(html,'ai'),4);assert.equal(countAttr(html,'insufficient'),1);
    assert.match(html,/Không gian · 4/);assert.equal(h.gets.length,6);assert.equal(h.posts.length,0);
  });
  await test('all five text AI records aggregate to five', async()=>{
    const h=await harness({rows:fixtures.map(r=>({...r,comment:'Synthetic text'})),analyses:results});
    assert.equal(countAttr(h.element('#analysis-results').innerHTML,'ai'),5);
  });
  await test('all rule results do not fabricate content sentiment or topics', async()=>{
    const h=await harness({rows:fixtures,analyses:results.map(a=>({...a,mode:'rule'}))}),html=h.element('#analysis-results').innerHTML;
    assert.equal(countAttr(html,'ai'),0);assert.equal(countAttr(html,'rule'),4);
    assert.ok(!html.includes('Không gian ·'));assert.match(html,/Chưa có kết quả AI hiện hành/);
  });
  await test('mixed AI and rule remain separate', async()=>{
    const h=await harness({rows:fixtures,analyses:results.map((a,i)=>({...a,mode:i<2?'ai':'rule'}))}),html=h.element('#analysis-results').innerHTML;
    assert.equal(countAttr(html,'ai'),2);assert.equal(countAttr(html,'rule'),2);assert.match(html,/Không gian · 2/);
  });
  await test('stale result excluded from counts, topics and actions', async()=>{
    const h=await harness({rows:fixtures,analyses:results.map((a,i)=>i===0?{...a,stale:true,themes:['STALE_TOPIC'],actions:['STALE_ACTION']}:a)}),html=h.element('#analysis-results').innerHTML;
    assert.equal(countAttr(html,'ai'),3);assert.equal(countAttr(html,'stale'),1);
    assert.ok(!html.includes('STALE_TOPIC'));assert.ok(!html.includes('STALE_ACTION'));
  });
  await test('no saved results shows missing results without inference', async()=>{
    const h=await harness({rows:fixtures,analyses:[]}),html=h.element('#analysis-results').innerHTML;
    assert.equal(countAttr(html,'ai'),0);assert.equal(countAttr(html,'missing'),5);assert.equal(h.posts.length,0);
  });
  await test('duplicate result IDs cannot inflate counts', async()=>{
    const h=await harness({rows:fixtures.slice(0,1),analyses:[results[0],results[0]]}),html=h.element('#analysis-results').innerHTML;
    assert.equal(countAttr(html,'ai'),1);assert.match(html,/Không gian · 1/);
  });
  await test('more than five scope is blocked for GET aggregation and POST', async()=>{
    const h=await harness({rows:[...fixtures,{...review,id:99}],analyses:results});
    assert.equal(h.element('#analysis-run').disabled,true);assert.equal(h.gets.length,1);
    await h.element('#analysis-run').fire('click');assert.equal(h.posts.length,0);
  });
  await test('actions deduplicate per mode and preserve references', async()=>{
    const h=await harness({rows:fixtures.slice(0,2),analyses:results.slice(0,2).map(a=>({...a,actions:['ONE_ACTION','ONE_ACTION']}))}),html=h.element('#analysis-results').innerHTML;
    assert.equal((html.match(/ONE_ACTION/g)||[]).length,1);assert.match(html,/Tham chiếu DG-1, DG-2/);
  });
  await test('legacy result cannot enter AI aggregate', async()=>{
    const h=await harness({analysis:{...saved,mode:'legacy'}}),html=h.element('#analysis-results').innerHTML;
    assert.equal(countAttr(html,'ai'),0);assert.equal(countAttr(html,'rule'),0);assert.match(html,/chưa xác minh/);
  });
  await test('unsafe markup from saved results is escaped', async()=>{
    const h=await harness({analysis:{...saved,mode:'ai',summary:'<script>BAD</script>',themes:['<img src=x>'],actions:['<iframe>']}}),html=h.element('#analysis-results').innerHTML;
    assert.ok(!html.includes('<script>BAD'));assert.ok(!html.includes('<img src=x>'));assert.ok(!html.includes('<iframe>'));
  });
  console.log(`${count} PASS, 0 FAIL`);
}
main().catch(error => {console.error(error);process.exitCode = 1;});
