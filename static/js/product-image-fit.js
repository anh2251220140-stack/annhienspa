/* Display only. Enlarge genuinely blank image margins without cropping packaging.
   The original image URL and bytes are never changed or transmitted. */
(() => {
  "use strict";
  const grid = document.querySelector('[data-catalog-list="products"] [data-catalog-grid]');
  const detail = document.querySelector('[data-catalog-detail="product"] .detail-photo');
  const root = grid || detail;
  if (!root) return;
  const bounds = new WeakMap();
  function fit(image) {
    if (!image.complete || !image.naturalWidth || !image.parentElement) return;
    const previous = bounds.get(image);
    let box = previous?.source === image.currentSrc ? previous.box : undefined;
    if (!box) {
      try {
        const canvas = document.createElement("canvas");
        canvas.width = 160;
        canvas.height = Math.max(1, Math.round(160 * image.naturalHeight / image.naturalWidth));
        // Extremely tall images retain the conservative unzoomed presentation.
        if (canvas.height > 640) throw Error();
        const context = canvas.getContext("2d", {willReadFrequently: true});
        context.drawImage(image, 0, 0, canvas.width, canvas.height);
        const {data} = context.getImageData(0, 0, canvas.width, canvas.height);
        const corners = [0, canvas.width - 1, (canvas.height - 1) * canvas.width, canvas.height * canvas.width - 1];
        // Only near-white, uniform backgrounds can safely be treated as padding.
        const white = corners.every(p => data[p*4] > 235 && data[p*4+1] > 235 && data[p*4+2] > 235);
        if (!white) throw Error();
        let left = canvas.width, right = -1, top = canvas.height, bottom = -1;
        for (let y = 0; y < canvas.height; y++) for (let x = 0; x < canvas.width; x++) {
          const p = (y * canvas.width + x) * 4;
          if (data[p+3] > 24 && Math.min(data[p], data[p+1], data[p+2]) < 235) {
            left = Math.min(left, x); right = Math.max(right, x+1);
            top = Math.min(top, y); bottom = Math.max(bottom, y+1);
          }
        }
        if (right < 0) throw Error();
        // Keep an extra 6% of the source on every side, including faint edges.
        box = {left: Math.max(0, left/canvas.width-.06), right: Math.min(1, right/canvas.width+.06),
               top: Math.max(0, top/canvas.height-.06), bottom: Math.min(1, bottom/canvas.height+.06)};
      } catch (_) {
        // Non-white backgrounds, CORS restrictions or canvas failures: no zoom.
        box = {left:0, right:1, top:0, bottom:1};
      }
      bounds.set(image, {source: image.currentSrc, box});
    }
    const width = grid ? image.parentElement.clientWidth : image.clientWidth;
    const height = grid ? image.parentElement.clientHeight : image.clientHeight;
    if (!width || !height) return;
    const ratio = Math.min(width/image.naturalWidth, height/image.naturalHeight);
    const paintedWidth = image.naturalWidth * ratio, paintedHeight = image.naturalHeight * ratio;
    const x = Math.max(.5-box.left, box.right-.5) * paintedWidth;
    const y = Math.max(.5-box.top, box.bottom-.5) * paintedHeight;
    const scale = Math.max(1, Math.min(1.15, width/(2*x), height/(2*y)));
    image.style.setProperty("--product-image-scale", String(scale));
    image.dataset.imageFitScale = scale.toFixed(4);
    image.dataset.imageFitBounds = JSON.stringify(box);
  }
  const observed = new WeakSet();
  const resize = new ResizeObserver(entries => entries.forEach(entry => {
    const image = entry.target.querySelector("img"); if (image) fit(image);
  }));
  function scan() {
    resize.disconnect();
    root.querySelectorAll(grid ? ".product-image img" : "img[data-image]").forEach(image => {
      if (!observed.has(image)) {
        observed.add(image);
        image.addEventListener("load", () => fit(image));
      }
      resize.observe(image.parentElement);
      fit(image);
    });
  }
  new MutationObserver(scan).observe(root, {childList:true, subtree:true});
  scan();
})();
