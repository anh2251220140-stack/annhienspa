(() => {
  "use strict";
  if (window.spaAuth?.allowed === false) return;
  const catalog = window.spaCatalog;
  const main = document.querySelector(".catalog-view");
  if (!main || !catalog) return;

  const escape = (value) => String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);
  const normalize = (value) => value.toLocaleLowerCase("vi")
    .normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/g, "d").trim();
  const active = (items) => items.filter((item) => item.active === true);
  const params = new URLSearchParams(location.search);
  const memberUrl = (path) => window.spaAuth?.urlFor(path) || path;

  function serviceCard(item) {
    return `<article class="service-card catalog-service" data-card-id="${item.id}">
      <img src="${escape(item.image)}" alt="${escape(item.name)}" loading="lazy" width="700" height="900">
      <div class="card-shade"></div><span class="card-number">${String(item.id).padStart(2, "0")}</span>
      <div class="service-info"><span class="eyebrow">${escape(item.category)}</span><h3>${escape(item.name)}</h3>
      <p class="card-description">${escape(item.description)}</p>
      <p class="service-meta">${escape(item.price)} <span class="dot">·</span> ${escape(item.duration)}</p>
      <div class="catalog-card-actions"><a class="button small" href="service-detail.html?id=${item.id}">Xem chi tiết</a>
      <a class="button small filled" href="${memberUrl(`booking.html?service=${item.id}`)}">Đặt lịch</a></div></div></article>`;
  }
  function productCard(item) {
    const suitable = item.skins.includes("Không áp dụng") ? item.audiences : item.skins;
    return `<article class="product-card catalog-product" data-card-id="${item.id}">
      <div class="product-image"><img src="${escape(item.image)}" alt="${escape(item.name)}" loading="lazy" width="700" height="700"></div>
      <div class="product-info"><span class="eyebrow">${escape(item.category)}</span><h3>${escape(item.name)}</h3>
      <p>${escape(item.description)}</p><p class="product-suitable">${escape(suitable.join(" · "))}</p>
      <a class="text-link" href="${memberUrl(`product-detail.html?id=${item.id}`)}">Xem chi tiết</a></div></article>`;
  }
  const listType = main.dataset.catalogList;
  if (listType) {
    const form = main.querySelector(".catalog-toolbar");
    const grid = main.querySelector("[data-catalog-grid]");
    const empty = main.querySelector("[data-empty]");
    const isService = listType === "services";
    if (isService) {
      form.elements.category.replaceChildren(new Option("Tất cả danh mục", ""), ...[...new Set(catalog.services.map(x => x.category))].map(name => new Option(name,name)));
    }
    if (!isService) {
      const products = active(catalog.products);
      const setOptions = (select, label, values) => {
        select.replaceChildren(new Option(label, ""), ...[...new Set(values)]
          .map((value) => new Option(value, value)));
      };
      setOptions(form.elements.category, "Tất cả loại sản phẩm", products.map((item) => item.category));
      setOptions(form.elements.suitable, "Tất cả đối tượng", products
        .flatMap((item) => [...item.skins, ...item.audiences])
        .filter((value) => value !== "Không áp dụng"));
    }
    const render = () => {
      const query = normalize(form.elements.search.value);
      const category = form.elements.category.value;
      const suitable = form.elements.suitable?.value || "";
      let items = active(catalog[listType]).filter((item) =>
        normalize(item.name).includes(query) &&
        (!category || item.category === category) &&
        (!suitable || [...item.skins, ...item.audiences].includes(suitable)));
      if (isService) {
        const sort = form.elements.sort.value;
        if (sort === "price-asc") items.sort((a, b) => a.priceValue - b.priceValue);
        if (sort === "price-desc") items.sort((a, b) => b.priceValue - a.priceValue);
        if (sort === "duration") items.sort((a, b) => a.minutes - b.minutes);
      }
      grid.innerHTML = items.map(isService ? serviceCard : productCard).join("");
      empty.hidden = items.length > 0;
      main.querySelector("[data-result-count]").textContent =
        `${items.length} ${isService ? "liệu trình" : "gợi ý chăm sóc"} dành cho bạn`;
    };
    form.addEventListener("submit", (event) => event.preventDefault());
    form.addEventListener("input", render);
    form.addEventListener("change", render);
    main.querySelectorAll("[data-reset]").forEach((button) => {
      button.addEventListener("click", () => {
        form.reset();
        render();
        form.elements.search.focus();
      });
    });
    render();
  }

  const kind = main.dataset.catalogDetail;
  if (!kind) return;
  const isService = kind === "service";
  const rawId = params.get("id") ?? "0";
  const id = /^\d+$/.test(rawId) ? Number(rawId) : NaN;
  const item = active(isService ? catalog.services : catalog.products)
    .find((entry) => entry.id === id);
  if (!item) {
    const ownReview = isService && params.has("appointment") && window.spaAuth?.getSession()?.role === "User"
      ? main.querySelector("[data-service-reviews]") : null;
    document.title = "Không tìm thấy nội dung | An Nhiên Spa";
    main.innerHTML = `<section class="container catalog-empty"><span class="eyebrow">AN NHIÊN SPA</span>
      <h1>Nội dung chưa khả dụng</h1><p>${isService ? "Liệu trình" : "Sản phẩm"} này không tồn tại hoặc hiện không hoạt động.</p>
      <a class="button" href="${isService ? "services" : "products"}.html">Trở về danh sách</a></section>`;
    if (ownReview) {
      ownReview.hidden = true;
      ownReview.dataset.serviceUnavailable = "";
      ownReview.classList.add("container");
      main.append(ownReview);
    }
    return;
  }
  document.title = `${item.name} | An Nhiên Spa`;
  main.querySelectorAll("[data-name]").forEach((node) => { node.textContent = item.name; });
  main.querySelector("[data-category]").textContent = item.category;
  main.querySelector("[data-description]").textContent = item.description;
  const image = main.querySelector("[data-image]");
  image.src = item.image;
  image.alt = item.name;
  main.querySelectorAll("[data-field]").forEach((node) => {
    const value = item[node.dataset.field];
    node.textContent = Array.isArray(value) ? value.join(" · ") : value;
  });
  if (isService) {
    main.querySelector("[data-price]").textContent = item.price;
    main.querySelector("[data-duration]").textContent = item.duration;
    main.querySelector("[data-book]").href = memberUrl(`booking.html?service=${item.id}`);
    main.querySelector("[data-gallery]").src = item.gallery;
    const startsWithDescription = item.introduction.startsWith(item.description);
    main.querySelector("[data-intro-lead]").textContent = startsWithDescription ? item.description : item.introduction;
    const introRest = main.querySelector("[data-intro-rest]");
    introRest.textContent = startsWithDescription ? item.introduction.slice(item.description.length).trim() : "";
    introRest.hidden = !introRest.textContent;
    const benefitTitles = item.careGroup === "hair"
      ? ["Mềm mại mái tóc", "Chăm sóc da đầu", "Thư giãn nhẹ nhàng"]
      : item.careGroup === "face"
        ? ["Làm sạch & cấp ẩm", "Nâng niu làn da", "Một khoảng nghỉ"]
        : ["Thư giãn cơ thể", "Nuôi dưỡng làn da", "Cân bằng cảm xúc"];
    const stepTitles = item.careGroup === "hair"
      ? ["Lắng nghe nhu cầu", "Làm sạch tóc", "Ủ dưỡng & thư giãn", "Hoàn thiện"]
      : ["Lắng nghe nhu cầu", "Chuẩn bị", "Thực hiện liệu trình", "Hoàn thiện"];
    main.querySelectorAll("[data-list]").forEach((node) => {
      node.replaceChildren(...item[node.dataset.list].map((text, index) => {
        const li = document.createElement("li");
        li.innerHTML = node.dataset.list === "benefits"
          ? `${window.spaIcon(["leaf", "droplet", "heart"][index % 3])}<div><h3>${escape(benefitTitles[index] || "Chăm sóc tận tâm")}</h3><p>${escape(text)}</p></div>`
          : `<span class="step-number">${String(index + 1).padStart(2, "0")}</span><div><h3>${escape(stepTitles[index] || "Chăm sóc")}</h3><p>${escape(text)}</p></div>`;
        return li;
      }));
    });
    const specialists = active(catalog.staff).filter((person) => person.serviceIds.includes(item.id));
    main.querySelector("[data-staff]").innerHTML = specialists.length
      ? specialists.map((person) => `<article class="specialist-card">
          <img src="${escape(person.image)}" alt="Ảnh minh họa chuyên viên ${escape(person.name)}" width="96" height="96" loading="lazy">
          <div><span class="specialist-badge">Đồng hành liệu trình</span><h3>${escape(person.name)}</h3><p>${escape(person.specialty)}</p></div></article>`).join("")
      : "<p>Chuyên viên cho liệu trình đang được cập nhật.</p>";
  } else {
    main.querySelector("[data-product-benefits]").innerHTML = item.benefits.map(text =>
      `<li>${window.spaIcon("leaf")}<div><p>${escape(text)}</p></div></li>`).join("");
    const ingredients = item.ingredients.split(/\r?\n/).filter(Boolean);
    main.querySelector("[data-ingredients]").innerHTML = ingredients.map(name =>
      `<article class="ingredient-card"><h3>${escape(name)}</h3></article>`).join("");
    // Split the existing directions rather than inventing a universal skin routine.
    // This keeps diffusion-only essential oils distinct from topical products.
    const clauses = item.usage.replace(/\.$/, "").split(/,\s*|\s+rồi\s+/).filter(Boolean);
    const usageTitle = (clause) => {
      const text = normalize(clause);
      if (/khong gian/.test(text)) return "Không gian thư thái";
      if (/^(sau|lam uot)|sau buoc/.test(text)) return "Chuẩn bị";
      if (/^(lay|them|lam am)/.test(text)) return "Lượng dùng phù hợp";
      if (/^(xa|rua)/.test(text)) return "Làm sạch & hoàn thiện";
      if (/^(giu|u )/.test(text)) return "Dành thời gian chăm sóc";
      if (/^(tiep tuc|ket hop)/.test(text)) return "Hoàn thiện chu trình";
      if (/^(thoa|massage|vo|tao bot)/.test(text)) return "Chăm sóc nhẹ nhàng";
      return "Lưu ý khi thực hiện";
    };
    main.querySelector("[data-usage]").innerHTML = clauses.map((text, index) =>
      `<li><span class="step-number">${String(index + 1).padStart(2, "0")}</span><div><h3>${escape(usageTitle(text))}</h3><p>${escape(text)}</p></div></li>`).join("");
  }
  // One shared relation list drives both directions; the user cannot edit it.
  const relatedIds = catalog.relations.filter((relation) =>
    isService ? relation.serviceId === item.id : relation.productId === item.id)
    .map((relation) => isService ? relation.productId : relation.serviceId);
  const related = active(isService ? catalog.products : catalog.services)
    .filter((entry) => relatedIds.includes(entry.id));
  main.querySelector("[data-related]").innerHTML = related.length
    ? related.map(isService ? productCard : serviceCard).join("")
    : "<p>Các gợi ý liên quan đang được cập nhật.</p>";
})();
