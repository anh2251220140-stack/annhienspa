// Execute the real image fitter offline; no browser server, network or database.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source = fs.readFileSync('static/js/product-image-fit.js', 'utf8');
let passed = 0, failed = 0;
function fixture(detail) {
  const images = [];
  let mutation, resize, reads = 0;
  const root = {querySelectorAll: () => images};
  function add() {
    const listeners = [];
    const parent = {clientWidth: 200, clientHeight: 200};
    const image = {complete: true, naturalWidth: 200, naturalHeight: 200,
      currentSrc: 'offline-square', clientWidth: 200, clientHeight: 200,
      parentElement: parent, dataset: {}, writes: 0, listeners,
      style: {setProperty() { image.writes++; }},
      addEventListener(event, fn) { assert.equal(event, 'load'); listeners.push(fn); }};
    parent.querySelector = () => image;
    images.push(image);
    return image;
  }
  const first = add();
  vm.runInNewContext(source, {
    document: {
      querySelector: selector => selector.includes('data-catalog-list') ? (detail ? null : root) : (detail ? root : null),
      createElement: () => {
        const canvas = {width: 0, height: 0};
        canvas.getContext = () => ({drawImage() {}, getImageData() {
          reads++;
          const data = new Uint8ClampedArray(canvas.width * canvas.height * 4).fill(255);
          for (let y = canvas.height * .3 | 0; y < canvas.height * .7; y++) {
            for (let x = canvas.width * .3 | 0; x < canvas.width * .7; x++) {
              const p = (y * canvas.width + x) * 4;
              data[p] = data[p + 1] = data[p + 2] = 30;
            }
          }
          return {data};
        }});
        return canvas;
      }
    },
    ResizeObserver: class {
      constructor(callback) { resize = this; this.callback = callback; this.targets = new Set(); }
      observe(target) { this.targets.add(target); }
      disconnect() { this.targets.clear(); }
      fire() { this.callback([...this.targets].map(target => ({target}))); }
    },
    MutationObserver: class {
      constructor(callback) { mutation = callback; }
      observe() {}
    }
  });
  return {images, first, add, scan: () => mutation(), resize, reads: () => reads};
}
function test(name, run) {
  try { run(); passed++; console.log('PASS', name); }
  catch (error) { failed++; console.log('FAIL', name, error.message); }
}
for (const detail of [false, true]) {
  const label = detail ? 'detail' : 'listing';
  test(`${label}: new image is observed and fitted`, () => {
    const f = fixture(detail), image = f.add(); f.scan();
    assert(f.resize.targets.has(image.parentElement));
    assert.equal(image.listeners.length, 1); assert(image.writes > 0);
  });
  test(`${label}: existing images remain observed after DOM mutation`, () => {
    const f = fixture(detail); f.scan();
    assert(f.resize.targets.has(f.first.parentElement));
  });
  test(`${label}: repeated scans observe every image without duplicate load handlers`, () => {
    const f = fixture(detail); f.add();
    for (let i = 0; i < 10; i++) f.scan();
    assert.equal(f.resize.targets.size, 2);
    for (const image of f.images) assert.equal(image.listeners.length, 1);
  });
  test(`${label}: resize recalculates fit after repeated scans`, () => {
    const f = fixture(detail); f.scan(); f.scan();
    const before = f.first.writes;
    f.first.parentElement.clientWidth = f.first.clientWidth = 80;
    f.resize.fire();
    assert.equal(f.first.writes, before + 1);
    assert.equal(Number(f.first.dataset.imageFitScale), 1.15);
  });
  test(`${label}: reload reuses bounds and source change recalculates them`, () => {
    const f = fixture(detail); f.scan(); const reads = f.reads();
    f.first.listeners[0](); assert.equal(f.reads(), reads);
    f.first.currentSrc = 'offline-portrait'; f.first.naturalHeight = 300;
    f.first.listeners[0](); assert.equal(f.reads(), reads + 1);
    assert.equal(f.first.listeners.length, 1);
  });
  test(`${label}: pending image fits on load exactly once`, () => {
    const f = fixture(detail), image = f.add(); image.complete = false;
    f.scan(); f.scan(); assert.equal(image.writes, 0);
    image.complete = true; image.listeners.forEach(fn => fn());
    assert.equal(image.writes, 1);
  });
  test(`${label}: all remaining images fit and detached images are not observed`, () => {
    const f = fixture(detail), second = f.add(); f.scan();
    f.images.shift(); f.scan();
    assert(!f.resize.targets.has(f.first.parentElement));
    assert(f.resize.targets.has(second.parentElement));
    const before = second.writes; f.resize.fire();
    assert.equal(second.writes, before + 1);
    assert.equal(Number(second.dataset.imageFitScale), 1.15);
  });
}
console.log(`${passed} PASS, ${failed} FAIL`);
process.exitCode = failed ? 1 : 0;
