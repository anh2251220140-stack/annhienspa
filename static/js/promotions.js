(() => {
  "use strict";
  const main = document.querySelector("[data-promotions-page]");
  const data = window.spaPromotions;
  if (!main || !data) return;
  const escape = (value) => String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);
  const normalize = (value) => value.toLocaleLowerCase("vi")
    .normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/g, "d").trim();
  const day = (value) => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return NaN;
    const date = new Date(`${value}T00:00:00Z`);
    return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value
      ? date.getTime() / 86400000 : NaN;
  };
  const dateLabel = (value) => value.split("-").reverse().join(".");
  const statusFor = (item) => {
    const today = day(data.referenceDate), start = day(item.startDate), end = day(item.endDate);
    if (item.active !== true || ![today, start, end].every(Number.isFinite) || start > end) return "inactive";
    if (today < start) return "future";
    if (today > end) return "expired";
    return end - today <= data.expiringWithinDays ? "ending" : "active";
  };
  const labels = { active: "Đang hiệu lực", ending: "Sắp hết hạn", expired: "Hết hạn", future: "Chưa bắt đầu" };
  const eligible = (item) => ["active", "ending"].includes(statusFor(item));
  const findPromotion = (code) => data.items.find((item) =>
    [item.code, ...item.aliases].some((value) => value.toUpperCase() === code.toUpperCase()));
  const detailUrl = (item) => `promotion-detail.html?code=${encodeURIComponent(item.code)}`;
  const statusBadge = (item) => `<span class="promotion-status ${statusFor(item) === "ending" ? "ending" : ""}">${labels[statusFor(item)] || "Chưa khả dụng"}</span>`;
  const statusLine = (item) => `<span class="promotion-status-line ${statusFor(item) === "ending" ? "ending" : ""}">${labels[statusFor(item)] || "Chưa khả dụng"}</span>`;
  const card = (item) => `<article class="offer-card promo-${item.accent}" id="${escape(item.code)}">
    <div class="offer-topline"><span class="eyebrow">${escape(item.code)}</span><span class="offer-badge">${escape(item.badge)}</span></div>
    <div class="offer-ornament">${window.spaIcon("leaf")}</div>
    <h2>${escape(item.name)}</h2><div class="discount">${escape(item.discount)}</div>
    <p class="promotion-description">${escape(item.description)}</p>
    <div class="offer-bottom"><div class="promotion-validity"><span>${dateLabel(item.startDate)} — ${dateLabel(item.endDate)}</span>${statusLine(item)}</div>
    <a class="button small" href="${detailUrl(item)}">Xem chi tiết</a></div></article>`;

  if (main.dataset.promotionsPage === "list") {
    // Keep existing Home card URLs working without changing their markup/content.
    const legacyCode = location.hash.slice(1);
    const legacy = findPromotion(legacyCode);
    if (legacy?.active === true) {
      location.replace(detailUrl(legacy));
      return;
    }
    const form = main.querySelector("[data-promotion-filters]");
    const grid = main.querySelector("[data-promotion-grid]");
    const render = () => {
      const query = normalize(form.elements.search.value);
      const status = form.elements.status.value;
      const items = data.items.filter((item) => eligible(item) &&
        (!query || normalize([item.name, item.code, ...item.aliases].join(" ")).includes(query)) &&
        (status === "all" || statusFor(item) === status));
      grid.innerHTML = items.map(card).join("");
      main.querySelector("[data-promotion-count]").textContent = `${items.length} ưu đãi đang hiệu lực`;
      main.querySelector("[data-empty]").hidden = items.length > 0;
    };
    form.addEventListener("submit", (event) => event.preventDefault());
    form.addEventListener("input", render);
    form.addEventListener("change", render);
    main.querySelectorAll("[data-reset-promotions]").forEach((button) => {
      button.addEventListener("click", () => { form.reset(); render(); form.elements.search.focus(); });
    });
    render();
    return;
  }

  // Presentation only: keep numeric catalog prices and promotion fixtures untouched.
  const numberFormatter = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 });
  const formatCurrency = (value) => `${numberFormatter.format(value)} VND`;
  const formatMoneyInText = (text) => String(text).replace(
    /(\d+(?:[.,]\d{3})*)\s*(?:VNĐ|VND|₫|đ)(?![\p{L}\p{N}])/giu,
    (_, amount) => formatCurrency(Number(amount.replace(/[.,]/g, ""))),
  );
  const code = new URLSearchParams(location.search).get("code") ?? "WELCOME10";
  const item = findPromotion(code);
  if (!item || statusFor(item) === "inactive") {
    document.title = "Khuyến mãi chưa khả dụng | An Nhiên Spa";
    main.innerHTML = `<section class="container catalog-empty"><span class="eyebrow">AN NHIÊN SPA</span><h1>Chương trình chưa khả dụng</h1>
      <p>Khuyến mãi không tồn tại hoặc đang tạm ngưng.</p><a class="button" href="promotions.html">Xem các ưu đãi khác</a></section>`;
    return;
  }
  document.title = `${item.name} | An Nhiên Spa`;
  main.querySelectorAll("[data-promotion-name]").forEach((node) => { node.textContent = formatMoneyInText(item.name); });
  main.querySelector("[data-promotion-code]").textContent = item.code;
  const discount = main.querySelector("[data-promotion-discount]");
  discount.textContent = formatMoneyInText(item.discount);
  discount.classList.toggle("is-amount", discount.textContent.includes(" VND"));
  main.querySelector("[data-promotion-description]").textContent = formatMoneyInText(item.description);
  main.querySelector("[data-promotion-detail]").textContent = formatMoneyInText(item.detail);
  main.querySelector("[data-promotion-period]").textContent = `${dateLabel(item.startDate)} — ${dateLabel(item.endDate)}`;
  main.querySelector("[data-promotion-status]").innerHTML = statusBadge(item);
  main.querySelector("[data-promotion-conditions]").replaceChildren(...item.conditions.map((text, index) => {
    const li = document.createElement("li");
    li.className = "condition-item";
    li.innerHTML = `<span class="condition-number" aria-hidden="true">${String(index + 1).padStart(2, "0")}</span><p>${escape(formatMoneyInText(text))}</p>`;
    return li;
  }));
  main.querySelector("[data-promotion-note]").textContent =
    formatMoneyInText(item.note);
  main.querySelector("[data-promotion-aliases]").textContent = item.aliases.length ? "Mã thay thế: " + item.aliases.join(" · ") : "";
  main.querySelector("[data-promotion-badge]").textContent = item.badge;
  const services = window.spaCatalog.services.filter((service) =>
    service.active === true && item.serviceIds.includes(service.id));
  const book = main.querySelector("[data-promotion-book]");
  book.href = window.spaAuth.urlFor("booking.html");
  const canBook = eligible(item) && services.length > 0;
  book.hidden = !canBook;
  const finalCta = main.querySelector("[data-final-promotion-cta]");
  finalCta.hidden = !canBook;
  main.querySelector("[data-final-promotion-book]").href = window.spaAuth.urlFor("booking.html");
  const stateNotice = main.querySelector("[data-state-notice]");
  stateNotice.hidden = eligible(item);
  stateNotice.textContent = statusFor(item) === "expired"
    ? "Chương trình đã hết hạn. Vui lòng xem các ưu đãi đang hiệu lực."
    : "Chương trình chưa bắt đầu. Bạn có thể tham khảo các ưu đãi đang hiệu lực.";
  main.querySelector("[data-discount-panel]").classList.add(`promo-${item.accent}`);
  main.querySelector("[data-applicable-services]").innerHTML = services.map((service) => `
    <article class="service-card catalog-service" data-service-id="${service.id}">
      <img src="${escape(service.image)}" alt="${escape(service.name)}" loading="lazy" width="700" height="900">
      <div class="card-shade"></div><div class="service-info"><span class="eyebrow">${escape(service.category)}</span>
      <h3>${escape(formatMoneyInText(service.name))}</h3>
      <div class="promotion-service-meta"><p><span>Giá gốc</span><strong>${formatCurrency(service.priceValue)}</strong></p><p>${window.spaIcon("clock")}<span>${escape(service.duration)}</span></p></div>
      <p class="card-description">Giảm theo điều kiện chương trình</p>
      <div class="catalog-card-actions"><a class="button small" href="service-detail.html?id=${service.id}">Xem chi tiết</a>
      ${canBook ? `<a class="button small filled" href="${window.spaAuth.urlFor(`booking.html?service=${service.id}`)}">${window.spaIcon("calendar")}Đặt lịch</a>` : ""}</div></div></article>`).join("");
  const scope = main.querySelector("[data-service-scope]");
  scope.textContent = (item.scopeNote ? item.scopeNote + " " : "") + (services.length
    ? "Giá hiển thị là giá gốc. Spa sẽ kiểm tra điều kiện chương trình trước khi xác nhận mức giảm."
    : "Hiện chưa có dịch vụ phù hợp với điều kiện của chương trình.");
})();
