/* Presentation-only pagination shared by the three User catalog lists. */
(() => {
  "use strict";
  window.spaCardPager = (grid, label, render) => {
    let page = 1;
    const nav = document.createElement("nav");
    nav.className = "catalog-pagination";
    nav.setAttribute("aria-label", `Phân trang ${label}`);
    grid.after(nav);
    return {
      reset() { page = 1; },
      slice(items) {
        const pages = Math.max(1, Math.ceil(items.length / 6));
        page = Math.min(page, pages);
        nav.hidden = items.length === 0;
        const button = (text, target, disabled) => {
          const node = document.createElement("button");
          node.type = "button";
          node.className = "button small";
          node.textContent = text;
          node.disabled = disabled;
          node.onclick = () => {
            page = target;
            render();
            nav.querySelector(target === pages ? "[data-previous]" : "[data-next]")?.focus();
          };
          return node;
        };
        const previous = button("Trước", page - 1, page === 1);
        previous.dataset.previous = "";
        const next = button("Sau", page + 1, page === pages);
        next.dataset.next = "";
        const status = document.createElement("span");
        status.setAttribute("role", "status");
        status.textContent = `Trang ${page} / ${pages} · ${items.length} ${label}`;
        nav.replaceChildren(previous, status, next);
        return items.slice((page - 1) * 6, page * 6);
      },
    };
  };
})();
