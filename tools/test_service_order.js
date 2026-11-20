// Offline execution of the real list renderer. No network, database or AI.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source = fs.readFileSync('static/js/catalog-pages.js', 'utf8');
const ids = [2, 6, 1, 3, 5, 4];
const services = ids.map(id => ({id, active: true, name: `Dịch vụ ${id}`, category: id % 2 ? 'Massage' : 'Da mặt', priceValue: 1000 - id * 10, minutes: 90 - id, price: 'Giá thử', duration: 'Thời lượng thử', image: 'test.jpg', description: 'Giả lập'}));
const initial = JSON.stringify(services);
const handlers = {};
const elements = {search: {value: ''}, category: {value: '', replaceChildren() {}}, sort: {value: 'default'}};
let nav;
const createElement = () => ({dataset:{},setAttribute(){},focus(){},replaceChildren(...children){this.children=children;},querySelector(selector){return this.children.find(n=> selector==='[data-next]' ? 'next' in n.dataset : 'previous' in n.dataset);}});
const grid = {innerHTML: '', after(node){nav=node;}}, empty = {}, count = {}, reset = {};
const form = {elements, addEventListener(name, fn) {handlers[name] = fn;}, reset() {for (const key of ['search', 'category']) elements[key].value = ''; elements.sort.value = 'default';}};
const main = {dataset: {catalogList: 'services'}, querySelector(selector) {return ({'.catalog-toolbar': form, '[data-catalog-grid]': grid, '[data-empty]': empty, '[data-result-count]': count})[selector];}, querySelectorAll() {return [reset];}};
reset.addEventListener = (_, fn) => reset.click = fn;
elements.search.focus = () => {};
const catalog = {services, products: []};
const context=vm.createContext({window: {spaCatalog: catalog}, document: {querySelector: () => main,createElement}, location: {search: ''}, URLSearchParams, Option: function(label, value) {this.value = value;}});
vm.runInContext(fs.readFileSync('static/js/card-pagination.js','utf8'),context);
vm.runInContext(source,context);
const visible = () => [...grid.innerHTML.matchAll(/data-card-id="(\d+)"/g)].map(m => Number(m[1]));
const allVisible = () => {while(!nav.children[0].disabled)nav.children[0].onclick(); const result=[...visible()];while(!nav.children[2].disabled){nav.children[2].onclick();result.push(...visible());}return result;};
let passed = 0;
function test(name, run) {run(); passed++; console.log('PASS', name);}
test('unordered source becomes DV-001 through DV-006', () => assert.deepEqual(visible(), [1,2,3,4,5,6]));
test('source order is not mutated for AI consumers', () => assert.equal(JSON.stringify(services), initial));
test('future DV-007 and DV-008 sort globally', () => {services.unshift({...services[0], id: 8, name: 'Dịch vụ 8'}, {...services[0], id: 7, name: 'Dịch vụ 7'}); handlers.input(); assert.deepEqual(allVisible(), [1,2,3,4,5,6,7,8]);});
test('numeric codes handle DV-010 and DV-021', () => {services.unshift({...services[0], id: 21, name: 'Dịch vụ 21'}, {...services[0], id: 10, name: 'Dịch vụ 10'}); handlers.input(); assert.deepEqual(allVisible(), [1,2,3,4,5,6,7,8,10,21]);});
test('search retains ascending code order', () => {elements.search.value = 'Dịch vụ 2'; handlers.input(); assert.deepEqual(visible(), [2,21]);});
test('category filter retains ascending code order', () => {elements.search.value=''; elements.category.value='Massage'; handlers.change(); assert.deepEqual(visible(), [1,3,5]);});
test('price ascending remains independent', () => {elements.category.value=''; elements.sort.value='price-asc'; handlers.change(); const prices=allVisible().map(id=>services.find(s=>s.id===id).priceValue); assert.deepEqual(prices,[...prices].sort((a,b)=>a-b));});
test('price descending remains independent', () => {elements.sort.value='price-desc'; handlers.change(); const prices=allVisible().map(id=>services.find(s=>s.id===id).priceValue); assert.deepEqual(prices,[...prices].sort((a,b)=>b-a));});
test('duration ordering remains independent', () => {elements.sort.value='duration'; handlers.change(); const minutes=allVisible().map(id=>services.find(s=>s.id===id).minutes); assert.deepEqual(minutes,[...minutes].sort((a,b)=>a-b));});
test('hidden service omitted without renumbering codes', () => {elements.sort.value='default'; services.find(s=>s.id===3).active=false; handlers.input(); assert(!visible().includes(3)); assert.deepEqual(allVisible(), [1,2,4,5,6,7,8,10,21]);});
test('empty search and reset', () => {elements.search.value='Không tồn tại'; handlers.input(); assert.deepEqual(visible(), []); assert.equal(empty.hidden,false); reset.click(); assert.deepEqual(allVisible(), [1,2,4,5,6,7,8,10,21]);});


test('six cards maximum on each page',()=>{handlers.input();assert.equal(visible().length,6);nav.children[2].onclick();assert.equal(visible().length,3);});
test('filter resets page',()=>{elements.search.value='Dịch vụ 2';handlers.input();assert(nav.children[0].disabled);assert.deepEqual(visible(),[2,21]);});

console.log(`${passed} PASS, 0 FAIL`);
