(() => {
  "use strict";
  if (!document.querySelector("[data-admin-services]") || !window.spaAuth?.isAuthenticated()) return;
  try { if (window.spaAuth.getSession()?.role !== "Admin") return; } catch { return; }

  const $ = (selector) => document.querySelector(selector);
  const escape = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const normalize = (value) => String(value).normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/gi, "d").toLocaleLowerCase("vi").trim().replace(/\s+/g, " ");
  const money = (value) => `${new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 }).format(value)} VND`;
  const key = "spa-admin-services";
  const catalog = window.spaCatalog.services;
  const names = [...new Set(catalog.map((item) => item.category))];
  let data = {
    categories: names.map((name, index) => ({ id: index + 1, name, description: "", active: true })),
    // Preserve all catalog fields; these independent records never mutate the User catalog.
    services: catalog.map((service) => ({ ...JSON.parse(JSON.stringify(service)), categoryId: names.indexOf(service.category) + 1 })),
  };
  try {
    const saved = JSON.parse(sessionStorage.getItem(key));
    if (saved && Array.isArray(saved.categories) && Array.isArray(saved.services) &&
      saved.categories.every((c) => Number.isInteger(c.id) && typeof c.name === "string" && typeof c.active === "boolean") &&
      saved.services.every((s) => Number.isInteger(s.id) && typeof s.name === "string" && typeof s.active === "boolean" && Number.isFinite(s.priceValue) && s.priceValue >= 0 && Number.isFinite(s.minutes) && s.minutes > 0 && saved.categories.some((c) => c.id === s.categoryId))) data = saved;
  } catch { /* Start from the catalog if the session is unavailable or invalid. */ }
  const pageSize = 5;
  const state = { categories: { page: 1 }, services: { page: 1 } };
  let tab = "categories", returnFocus;
  const dialog = $("#service-dialog");
  // Presentation only: reuse the shared line-art icon language.
  const icon = (name) => {
    const paths = {
      folder: '<path d="M3 7V5h7l2 2h9v13H3V7Z"/>',
      search: '<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/>',
      plus: '<path d="M12 5v14M5 12h14"/>',
      edit: '<path d="m15 4 5 5M4 20l5-1L21 7l-5-5L4 14v6Z"/>',
      power: '<path d="M12 3v9M7 5a9 9 0 1 0 10 0"/>',
      check: '<path d="m5 12 4 4L19 6"/>',
    };
    return paths[name] ? `<svg class="line-icon" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.35" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name]}</svg>` : window.spaIcon(name);
  };
  document.querySelectorAll("[data-service-icon]").forEach((node) => { node.innerHTML = icon(node.dataset.serviceIcon); });
  const badge = (active) => `<span class="admin-status-badge admin-status-${active ? "completed" : "cancelled"}">${active ? "Hoạt động" : "Ngừng hoạt động"}</span>`;
  const code = (type, id) => `${type === "categories" ? "DM" : "DV"}-${String(type === "services" ? id + 1 : id).padStart(3, "0")}`;
  const notice = (text) => { $("#services-notice").textContent = text; $("#services-notice").hidden = false; };
  const commit = (next) => {
    try { sessionStorage.setItem(key, JSON.stringify(next)); data = next; return true; }
    catch {
      const error = dialog.querySelector("[data-form-error]");
      const message = "Không thể lưu phiên demo. Vui lòng kiểm tra quyền lưu trữ hoặc dung lượng trình duyệt rồi thử lại.";
      if (error) { error.textContent = message; error.hidden = false; error.focus(); }
      else notice(message);
      return false;
    }
  };
  const categoryOptions = (selected = "") => data.categories.map((c) => `<option value="${c.id}" ${String(c.id) === String(selected) ? "selected" : ""}>${escape(c.name)}${c.active ? "" : " (Ngừng hoạt động)"}</option>`).join("");
  const updateCategoryFilter = () => {
    const select = $("#services-category"), selected = select.value;
    select.innerHTML = '<option value="">Tất cả danh mục</option>' + categoryOptions(selected);
  };
  const renderStats = () => {
    $("#services-stats").innerHTML = [["Danh mục dịch vụ", data.categories.length, "folder"], ["Dịch vụ hoạt động", data.services.filter((s) => s.active).length, "leaf"], ["Dịch vụ tạm ngừng", data.services.filter((s) => !s.active).length, "power"]].map(([label, value, symbol]) => `<article><span class="admin-service-stat-icon">${icon(symbol)}</span><span>${label}</span><strong>${value}</strong></article>`).join("");
  };
  const render = (type) => {
    const query = normalize($(`#${type}-search`).value);
    const status = $(`#${type}-status`).value;
    const category = $("#services-category").value;
    const rows = data[type].filter((item) => normalize(item.name).includes(query) &&
      (!status || item.active === (status === "active")) &&
      (type !== "services" || !category || String(item.categoryId) === category));
    state[type].page = Math.min(state[type].page, Math.max(1, Math.ceil(rows.length / pageSize)));
    const page = state[type].page;
    const visible = rows.slice((page - 1) * pageSize, page * pageSize);
    $(`#${type}-rows`).innerHTML = visible.map((item) => {
      const actions = `<div class="admin-row-actions"><button class="admin-button" type="button" data-edit="${item.id}" aria-label="Sửa ${escape(item.name)}">${icon("edit")}Sửa</button><button class="admin-button" type="button" data-toggle="${item.id}" aria-label="${item.active ? "Tắt" : "Bật"} ${escape(item.name)}">${icon("power")}${item.active ? "Tắt" : "Bật"}</button></div>`;
      if (type === "categories") return `<tr><td class="admin-appointment-code">${code(type, item.id)}</td><td><strong>${escape(item.name)}</strong></td><td class="admin-service-description">${escape(item.description || "Chưa cập nhật")}</td><td>${badge(item.active)}</td><td>${actions}</td></tr>`;
      const category = data.categories.find((c) => c.id === item.categoryId);
      const image = imagePaths.includes(item.image) ? `<img src="${escape(item.image)}" alt="" width="48" height="56">` : '<span class="admin-service-image-placeholder" aria-hidden="true">AN</span>';
      return `<tr><td class="admin-appointment-code">${code(type, item.id)}</td><td><div class="admin-service-name">${image}<strong>${escape(item.name)}</strong></div></td><td><span class="admin-service-category-chip">${escape(category?.name || "Chưa cập nhật")}</span></td><td class="admin-service-price">${money(item.priceValue)}</td><td><span class="admin-service-duration">${icon("clock")}${item.minutes} phút</span></td><td>${badge(item.active)}</td><td>${actions}</td></tr>`;
    }).join("");
    $(`#${type}-empty`).hidden = Boolean(rows.length);
    const pages = Math.max(1, Math.ceil(rows.length / pageSize));
    $(`#${type}-pagination`).innerHTML = `<span>${visible.length} / ${rows.length} ${type === "categories" ? "danh mục" : "dịch vụ"}${rows.length ? ` · ${(page - 1) * pageSize + 1}–${(page - 1) * pageSize + visible.length}` : ""}</span><div><button class="admin-button" type="button" data-page="${page - 1}" ${page === 1 ? "disabled" : ""}>Trước</button><span>${page} / ${pages}</span><button class="admin-button" type="button" data-page="${page + 1}" ${page >= pages ? "disabled" : ""}>Sau</button></div>`;
  };
  const imagePaths = [...new Set(catalog.flatMap((s) => [s.image, s.gallery]).filter(Boolean))];
  const refresh = () => { updateCategoryFilter(); renderStats(); render("categories"); render("services"); };
  const open = (title, content) => {
    returnFocus = document.activeElement;
    dialog.innerHTML = `<header class="admin-service-modal-heading"><span class="admin-service-modal-icon">${icon("leaf")}</span><div><span class="admin-eyebrow">AN NHIÊN SPA / DỮ LIỆU DEMO</span><h2 id="service-dialog-title">${escape(title)}</h2></div><button class="admin-icon-button" type="button" data-close aria-label="Đóng">${window.spaIcon("close")}</button></header>${content}`;
    dialog.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", () => dialog.close()));
    dialog.showModal();
  };
  dialog.addEventListener("close", () => {
    if (returnFocus?.isConnected) returnFocus.focus({ preventScroll: true });
    else $(`#${tab}-search`).focus({ preventScroll: true });
  });
  const field = (label, name, value = "", attrs = "") => `<label>${label}<input name="${name}" value="${escape(value)}" ${attrs}></label>`;
  const textArea = (label, name, value = "") => `<label class="admin-service-content-field" data-content-field="${name}"><span class="admin-service-field-title">${icon(({ benefits: "star", steps: "note", suitable: "heart", note: "note", introduction: "leaf" })[name] || "note")}<span>${label}</span></span><textarea name="${name}" rows="3">${escape(value)}</textarea></label>`;
  const imageSelect = (label, name, value) => `<label>${label}<select name="${name}"><option value="">Chưa có ảnh</option>${imagePaths.map((path) => `<option value="${escape(path)}" ${value === path ? "selected" : ""}>${escape(path.replace("images/", ""))}</option>`).join("")}</select></label>`;

  const edit = (type, id) => {
    const existing = id === undefined ? null : data[type].find((item) => item.id === id);
    const item = existing || { name: "", description: "", active: true };
    const isService = type === "services";
    const noun = isService ? "dịch vụ" : "danh mục";
    let fields = field(`Tên ${noun} *`, "name", item.name, 'required maxlength="120" autofocus');
    if (isService) fields += `<label>Danh mục *<select name="categoryId" required><option value="">Chọn danh mục</option>${categoryOptions(item.categoryId)}</select></label>` +
      field("Giá (VND) *", "priceValue", item.priceValue ?? "", 'type="number" min="0" step="1" required') +
      field("Thời lượng (phút) *", "minutes", item.minutes ?? "", 'type="number" min="1" step="1" required');
    fields += textArea("Mô tả", "description", item.description);
    if (isService) fields += imageSelect("Hình minh họa", "image", item.image);
    const additional = isService ? `<details class="admin-service-extra"><summary><span>${icon("note")}Nội dung chi tiết liệu trình</span></summary><div class="admin-service-form-grid">${textArea("Giới thiệu", "introduction", item.introduction)}${textArea("Lợi ích — mỗi dòng một ý", "benefits", (item.benefits || []).join("\n"))}${textArea("Các bước — mỗi dòng một bước", "steps", (item.steps || []).join("\n"))}${textArea("Đối tượng phù hợp", "suitable", item.suitable)}${textArea("Lưu ý", "note", item.note)}${imageSelect("Ảnh chi tiết", "gallery", item.gallery)}<label>Nhóm chăm sóc (catalog)<select name="careGroup"><option value="">Chưa xác định</option>${[["relax", "Thư giãn"], ["face", "Da mặt"], ["body", "Cơ thể"], ["hair", "Tóc / da đầu"]].map(([value, label]) => `<option value="${value}" ${item.careGroup === value ? "selected" : ""}>${label}</option>`).join("")}</select></label></div></details>` : "";
    open(`${existing ? "Sửa" : "Thêm"} ${noun}`, `<form class="admin-service-form" novalidate><div class="admin-service-modal-scroll"><fieldset class="admin-service-basic"><legend>${icon(isService ? "leaf" : "folder")}Thông tin ${noun}</legend><div class="admin-service-form-grid">${fields}</div></fieldset>${additional}<p class="admin-data-note">Các trường * là bắt buộc. Trạng thái được quản lý bằng nút Bật/Tắt trong danh sách. Chỉ lưu bản demo trong phiên Admin.</p><p class="admin-service-error" data-form-error role="alert" tabindex="-1" hidden></p></div><div class="admin-dialog-actions"><button class="admin-button" type="button" data-close>Hủy</button><button class="admin-button admin-button-primary" type="submit">${icon("check")}Lưu demo</button></div></form>`);
    const form = dialog.querySelector("form");
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const values = Object.fromEntries(new FormData(form));
      const name = values.name.trim();
      const invalid = (message, fieldName) => {
        const error = form.querySelector("[data-form-error]");
        error.hidden = false; error.textContent = message;
        form.elements[fieldName].setAttribute("aria-invalid", "true");
        form.elements[fieldName].focus();
      };
      form.querySelectorAll("[aria-invalid]").forEach((node) => node.removeAttribute("aria-invalid"));
      if (!name) return invalid(`Vui lòng nhập tên ${noun}, không chỉ khoảng trắng.`, "name");
      if (name.length > 120) return invalid("Tên không được dài quá 120 ký tự.", "name");
      if (data[type].some((entry) => entry.id !== existing?.id && normalize(entry.name) === normalize(name))) return invalid(`Tên ${noun} đã tồn tại trong dữ liệu demo.`, "name");
      const categoryId = Number(values.categoryId), priceValue = Number(values.priceValue), minutes = Number(values.minutes);
      if (isService) {
        if (!data.categories.some((c) => c.id === categoryId)) return invalid("Vui lòng chọn danh mục hợp lệ.", "categoryId");
        if (!values.priceValue.trim() || !Number.isSafeInteger(priceValue) || priceValue < 0) return invalid("Giá phải là số nguyên VND không âm.", "priceValue");
        if (!values.minutes.trim() || !Number.isSafeInteger(minutes) || minutes <= 0) return invalid("Thời lượng phải là số phút nguyên lớn hơn 0.", "minutes");
      }
      const next = JSON.parse(JSON.stringify(data));
      const record = { ...item, id: existing?.id ?? Math.max(type === "services" ? -1 : 0, ...data[type].map((entry) => entry.id)) + 1, name, description: values.description.trim() };
      if (isService) Object.assign(record, {
        categoryId, category: data.categories.find((c) => c.id === categoryId).name,
        priceValue, price: money(priceValue), minutes, duration: `${minutes} phút`, image: values.image,
        introduction: values.introduction.trim(), benefits: values.benefits.split("\n").map((s) => s.trim()).filter(Boolean),
        steps: values.steps.split("\n").map((s) => s.trim()).filter(Boolean), suitable: values.suitable.trim(),
        note: values.note.trim(), gallery: values.gallery, careGroup: values.careGroup,
      });
      if (existing) next[type][next[type].findIndex((entry) => entry.id === id)] = record;
      else next[type].push(record);
      if (!isService) next.services.forEach((s) => { if (s.categoryId === record.id) s.category = name; });
      if (!commit(next)) return;
      refresh(); dialog.close(); notice(`Đã ${existing ? "cập nhật" : "thêm"} ${noun} “${name}” trong phiên demo.`);
    });
  };
  const toggle = (type, id) => {
    const item = data[type].find((entry) => entry.id === id), action = item.active ? "Tắt" : "Bật";
    open(`${action} ${type === "categories" ? "danh mục" : "dịch vụ"}`, `<div class="admin-dialog-body"><p>Bạn muốn ${action.toLowerCase()} “${escape(item.name)}” trong dữ liệu demo?</p><p>Dữ liệu cũ không bị xóa. ${type === "categories" ? "Trạng thái các dịch vụ liên kết không tự thay đổi." : "Không thay đổi các lịch hẹn và hóa đơn hiện có."}</p></div><p data-form-error class="admin-service-error" role="alert" tabindex="-1" hidden></p><div class="admin-dialog-actions"><button class="admin-button" data-close type="button" autofocus>Hủy</button><button class="admin-button admin-button-primary" data-confirm type="button">Xác nhận</button></div>`);
    dialog.querySelector("[data-confirm]").addEventListener("click", () => {
      const next = JSON.parse(JSON.stringify(data));
      next[type].find((entry) => entry.id === id).active = !item.active;
      if (!commit(next)) return;
      refresh(); dialog.close(); notice(`Đã ${action.toLowerCase()} “${item.name}” trong phiên demo.`);
    });
  };
  const tabs = [...document.querySelectorAll("[data-service-tab]")];
  const activate = (button) => {
    tab = button.dataset.serviceTab;
    tabs.forEach((node) => {
      const selected = node === button;
      node.setAttribute("aria-selected", String(selected)); node.tabIndex = selected ? 0 : -1;
      $(`#panel-${node.dataset.serviceTab}`).hidden = !selected;
    });
  };
  tabs.forEach((button, index) => {
    button.addEventListener("click", () => activate(button));
    button.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      event.preventDefault();
      const next = tabs[event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length];
      activate(next); next.focus();
    });
  });
  ["categories", "services"].forEach((type) => {
    [`#${type}-search`, `#${type}-status`, ...(type === "services" ? ["#services-category"] : [])].forEach((id) => $(id).addEventListener(id.endsWith("search") ? "input" : "change", () => { state[type].page = 1; render(type); }));
    $(`[data-service-add="${type}"]`).addEventListener("click", () => edit(type));
    $(`#panel-${type}`).addEventListener("click", (event) => {
      const target = event.target.closest("[data-edit], [data-toggle], [data-page]");
      if (!target) return;
      if (target.hasAttribute("data-page")) { state[type].page = Number(target.dataset.page); render(type); }
      else if (target.hasAttribute("data-edit")) edit(type, Number(target.dataset.edit));
      else toggle(type, Number(target.dataset.toggle));
    });
  });
  refresh();
})();
