(() => {
  "use strict";
  const main = document.querySelector("[data-admin-operations]");
  if (!main || !window.spaAuth?.isAuthenticated()) return;
  try { if (JSON.parse(sessionStorage.getItem("spa-auth"))?.role !== "Admin") return; } catch { return; }
  const module = main.dataset.adminOperations;
  const $ = (selector) => document.querySelector(selector);
  const escape = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const clone = (value) => JSON.parse(JSON.stringify(value));
  const normalize = (value) => String(value ?? "").toLocaleLowerCase("vi").normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/g, "d").trim().replace(/\s+/g, " ");
  const lines = (value) => String(value || "").split("\n").map((v) => v.trim()).filter(Boolean);
  const money = (value) => `${new Intl.NumberFormat("vi-VN").format(value)} VND`;
  const dateLabel = (value) => String(value || "").split("-").reverse().join(".");
  const day = (value) => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value || "")) return NaN;
    const date = new Date(`${value}T00:00:00Z`);
    return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value ? date.getTime() / 86400000 : NaN;
  };
  const catalog = window.spaCatalog, promotions = window.spaPromotions;
  const key = "spa-admin-operations";
  let services = clone(catalog.services);
  try {
    const saved = JSON.parse(sessionStorage.getItem("spa-admin-services"));
    if (Array.isArray(saved?.services) && saved.services.every((s) => Number.isInteger(s.id) && typeof s.name === "string" && Number.isFinite(s.minutes))) services = saved.services;
  } catch { /* Use the public seed catalog without modifying it. */ }
  const statuses = { pending: "Chờ xác nhận", confirmed: "Đã xác nhận", completed: "Đã hoàn thành", cancelled: "Đã hủy" };
  const names = { products: "sản phẩm", employees: "nhân viên", appointments: "lịch hẹn", promotions: "khuyến mãi" };
  const moduleIcons = { products: "droplet", employees: "heart", appointments: "calendar", promotions: "star" };
  const moduleIcon = () => window.spaIcon(moduleIcons[module]);
  const prefixes = { products: "SP", employees: "NV", appointments: "LH", promotions: "KM" };
  const code = (item, type = module) => `${prefixes[type]}-${String(item.id + 1).padStart(3, "0")}`;
  const seedAppointments = [
    ["Lan Anh", 0, null, "2026-10-14", "09:00", "pending"],
    ["Minh Thư", 1, 1, "2026-10-14", "10:00", "confirmed"],
    ["Hà My", 5, 2, "2026-10-13", "11:00", "completed"],
    ["Hoàng Nam", 2, 0, "2026-10-14", "14:00", "confirmed"],
    ["Thanh Trúc", 4, 2, "2026-10-14", "16:00", "cancelled"],
    ["Quốc Long", 3, null, "2026-10-15", "09:00", "pending"],
    ["Bích Ngọc", 6, 2, "2026-10-15", "11:00", "confirmed"],
    ["Lan Anh", 1, 1, "2026-10-16", "10:00", "pending"],
  ].map(([customer, serviceId, employeeId, date, time, status], id) => ({
    id, customer, serviceId, employeeId, date, time, status,
    service: catalog.services.find((s) => s.id === serviceId).name,
    minutes: catalog.services.find((s) => s.id === serviceId).minutes,
    note: "Lịch hẹn minh họa riêng của Admin.", invoice: { status: "unpaid", method: "spa" },
  }));
  let data = {
    products: clone(catalog.products),
    employees: clone(catalog.staff).map((e) => ({ ...e, email: "", phone: "" })),
    appointments: seedAppointments,
    promotions: clone(promotions.items).map((p, id) => ({ ...p, id })),
  };
  try {
    const saved = JSON.parse(sessionStorage.getItem(key));
    if (saved && Object.keys(data).every((type) => Array.isArray(saved[type]) &&
      saved[type].every((x) => x && Number.isInteger(x.id) && (type === "appointments" ? statuses[x.status] && typeof x.customer === "string" : typeof x.name === "string" && typeof x.active === "boolean")))) data = saved;
  } catch { /* Invalid/unavailable storage falls back to local fixtures. */ }
  const dialog = $("#ops-dialog");
  let returnFocus, page = 1;
  const pageSize = 5;
  const notice = (text) => { $("#ops-notice").textContent = text; $("#ops-notice").hidden = false; };
  const error = (message, name) => {
    const node = dialog.querySelector("[data-error]");
    if (!node) { notice(message); return; }
    node.textContent = message; node.hidden = false;
    const field = name && dialog.querySelector(`[name="${name}"]`);
    if (field) { field.setAttribute("aria-invalid", "true"); field.focus(); }
    else node.focus();
  };
  const commit = (next) => {
    try { sessionStorage.setItem(key, JSON.stringify(next)); data = next; return true; }
    catch { error("Không thể lưu phiên demo. Vui lòng kiểm tra quyền lưu trữ hoặc dung lượng trình duyệt."); return false; }
  };
  const badge = (label, style) => `<span class="admin-status-badge admin-status-${style}">${escape(label)}</span>`;
  const promotionStatus = (p) => {
    const today = day(promotions.referenceDate), start = day(p.startDate), end = day(p.endDate);
    if (!p.active || ![today, start, end].every(Number.isFinite) || start > end) return "inactive";
    if (today < start) return "future";
    if (today > end) return "expired";
    return end - today <= promotions.expiringWithinDays ? "ending" : "active";
  };
  const promoLabels = { inactive: "Tạm ngưng", future: "Chưa bắt đầu", expired: "Hết hạn", ending: "Sắp hết hạn", active: "Đang hiệu lực" };
  const activeLabel = (active) => module === "employees" ? (active ? "Đang làm việc" : "Ngừng làm việc") : (active ? "Hoạt động" : "Ngừng hiển thị");
  const statusBadge = (item) => {
    if (module === "appointments") return badge(statuses[item.status], item.status);
    if (module === "promotions") {
      const state = promotionStatus(item);
      return badge(promoLabels[state], state === "active" ? "completed" : ["future", "ending"].includes(state) ? "pending" : "cancelled");
    }
    return badge(activeLabel(item.active), item.active ? "completed" : "cancelled");
  };
  const images = [...new Set([...catalog.products, ...catalog.staff].map((s) => s.image).filter(Boolean))];
  const portrait = (item) => images.includes(item.image)
    ? `<img class="admin-ops-image" src="${escape(item.image)}" alt="" width="54" height="62">`
    : `<span class="admin-customer-initials admin-ops-initials" aria-hidden="true">${escape(item.name.split(/\s+/).slice(-2).map((s) => s[0]).join(""))}</span>`;
  const button = (action, id, label, iconName = "note") => `<button class="admin-button" type="button" data-action="${action}" data-id="${id}">${window.spaIcon(iconName)}${label}</button>`;
  const actions = (item) => {
    let result = button("view", item.id, "Xem", "eye");
    if (module === "appointments") {
      if (["pending", "confirmed"].includes(item.status)) result += button("process", item.id, "Xử lý", "calendar");
    } else result += button("edit", item.id, "Sửa") + button("toggle", item.id, item.active ? "Tắt" : "Bật", "leaf");
    return `<div class="admin-row-actions">${result}</div>`;
  };
  const employeeName = (id) => data.employees.find((e) => e.id === id)?.name || "Chưa phân công";
  const renderRow = (item) => {
    const name = ["products", "employees"].includes(module) ? `<div class="admin-service-name">${portrait(item)}<div><strong>${escape(item.name)}</strong>${module === "products" ? `<p class="admin-ops-excerpt">${escape(item.description)}</p>` : ""}</div></div>` : "";
    const first = `<td class="admin-appointment-code">${escape(module === "promotions" ? item.code : code(item))}</td>`;
    if (module === "products") return `<tr>${first}<td>${name}</td><td><span class="admin-service-category-chip">${escape(item.category)}</span></td><td>${statusBadge(item)}</td><td>${actions(item)}</td></tr>`;
    if (module === "employees") return `<tr>${first}<td>${name}</td><td>${escape(item.email || "Chưa cập nhật")}<span class="admin-table-time">${escape(item.phone || "Chưa cập nhật")}</span></td><td class="admin-ops-wrap"><span class="admin-ops-specialty">${escape(item.specialty || "Chưa cập nhật")}</span></td><td>${statusBadge(item)}</td><td>${actions(item)}</td></tr>`;
    if (module === "appointments") return `<tr>${first}<td><strong>${escape(item.customer)}</strong></td><td class="admin-ops-wrap">${escape(item.service)}</td><td><span class="admin-ops-date">${window.spaIcon("calendar")}${dateLabel(item.date)}</span><span class="admin-table-time">${escape(item.time)} · ${item.minutes} phút</span></td><td><span class="admin-ops-assignee">${window.spaIcon("heart")}${escape(employeeName(item.employeeId))}</span></td><td>${statusBadge(item)}</td><td>${actions(item)}</td></tr>`;
    return `<tr>${first}<td class="admin-ops-wrap"><strong>${escape(item.name)}</strong><p class="admin-ops-excerpt">${escape(item.description)}</p></td><td><strong class="admin-ops-discount">${escape(item.discount)}</strong></td><td>${dateLabel(item.startDate)}<span class="admin-table-time">đến ${dateLabel(item.endDate)}</span></td><td>${statusBadge(item)}</td><td>${actions(item)}</td></tr>`;
  };
  const render = () => {
    const all = data[module], query = normalize($("#ops-search").value), status = $("#ops-status").value;
    const rows = all.filter((item) => {
      const search = module === "appointments" ? `${code(item)} ${item.customer} ${item.service} ${employeeName(item.employeeId)}` : `${item.name} ${item.code || code(item)} ${item.email || ""} ${item.phone || ""}`;
      const matches = !status || (module === "appointments" ? item.status === status : module === "promotions" ? promotionStatus(item) === status : item.active === (status === "active"));
      return normalize(search).includes(query) && matches &&
        (!$("#ops-date")?.value || item.date === $("#ops-date").value) &&
        (!$("#ops-category")?.value || item.category === $("#ops-category").value);
    });
    page = Math.min(page, Math.max(1, Math.ceil(rows.length / pageSize)));
    const visible = rows.slice((page - 1) * pageSize, page * pageSize);
    $("#ops-rows").innerHTML = visible.map(renderRow).join("");
    $("#ops-empty").hidden = Boolean(rows.length);
    const pages = Math.max(1, Math.ceil(rows.length / pageSize));
    $("#ops-pagination").innerHTML = `<span>${visible.length} / ${rows.length} ${names[module]}${rows.length ? ` · ${(page - 1) * pageSize + 1}–${(page - 1) * pageSize + visible.length}` : ""}</span><div><button class="admin-button" type="button" data-page="${page - 1}" ${page === 1 ? "disabled" : ""}>Trước</button><span>${page} / ${pages}</span><button class="admin-button" type="button" data-page="${page + 1}" ${page >= pages ? "disabled" : ""}>Sau</button></div>`;
    let stats;
    if (module === "appointments") stats = [["Tổng lịch hẹn", all.length], ["Chờ xác nhận", all.filter((a) => a.status === "pending").length], ["Đã xác nhận", all.filter((a) => a.status === "confirmed").length]];
    else if (module === "promotions") stats = [["Tổng chương trình", all.length], ["Đang hiệu lực", all.filter((p) => ["active", "ending"].includes(promotionStatus(p))).length], ["Tạm ngưng", all.filter((p) => !p.active).length]];
    else stats = [[`Tổng ${names[module]}`, all.length], [module === "employees" ? "Đang làm việc" : "Đang hiển thị", all.filter((i) => i.active).length], ["Tạm ngừng", all.filter((i) => !i.active).length]];
    $("#ops-stats").innerHTML = stats.map(([label, value], index) => `<article><div><span class="admin-ops-stat-symbol">${index === 0 ? moduleIcon() : window.spaIcon(["note", "leaf", "clock"][index])}</span><span>${escape(label)}</span></div><strong>${value}</strong></article>`).join("");
    if ($("#ops-category")) {
      const value = $("#ops-category").value;
      $("#ops-category").replaceChildren(new Option("Tất cả danh mục", ""), ...[...new Set(all.map((p) => p.category))].map((c) => new Option(c, c)));
      $("#ops-category").value = value;
    }
  };
  const closeButtons = () => dialog.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", () => dialog.close()));
  const open = (title, body) => {
    returnFocus = document.activeElement;
    dialog.dataset.opsModule = module;
    dialog.innerHTML = `<header class="admin-service-modal-heading"><span class="admin-service-modal-icon">${moduleIcon()}</span><div><span class="admin-eyebrow">AN NHIÊN SPA / ADMIN DEMO</span><h2 id="ops-dialog-title">${escape(title)}</h2></div><button class="admin-icon-button" type="button" data-close aria-label="Đóng">${window.spaIcon("close")}</button></header>${body}`;
    closeButtons();
    if (!dialog.open) dialog.showModal();
    else dialog.querySelector("[autofocus], button, input, select")?.focus();
  };
  dialog.addEventListener("close", () => {
    if (returnFocus?.isConnected) returnFocus.focus({ preventScroll: true });
    else $("#ops-search").focus({ preventScroll: true });
  });
  const errorBox = '<p class="admin-service-error" data-error role="alert" tabindex="-1" hidden></p>';
  const footer = (primary = "") => `<div class="admin-dialog-actions"><button class="admin-button" type="button" data-close>${primary ? "Hủy" : "Đóng"}</button>${primary ? `<button class="admin-button admin-button-primary" type="submit">${primary}</button>` : ""}</div>`;
  const input = (label, name, value = "", attrs = "") => `<label>${label}<input name="${name}" value="${escape(value)}" ${attrs}></label>`;
  const textarea = (label, name, value = "") => `<label class="admin-ops-full" data-ops-field="${name}"><span class="admin-ops-field-label">${window.spaIcon(({ ingredients: "droplet", usage: "note", note: "note", skins: "leaf", audiences: "heart", conditions: "note", detail: "leaf", aliases: "star" })[name] || "note")}<span>${label}</span></span><textarea name="${name}" rows="3">${escape(value)}</textarea></label>`;
  const select = (label, name, options, value = "") => `<label>${label}<select name="${name}">${options.map(([v, l]) => `<option value="${escape(v)}" ${String(v) === String(value) ? "selected" : ""}>${escape(l)}</option>`).join("")}</select></label>`;
  const imageField = (item, type) => select("Hình minh họa", "image", [["", "Chữ viết tắt / Chưa có ảnh"], ...[...new Set(catalog[type === "products" ? "products" : "staff"].map((p) => p.image))].map((path) => [path, path.replace("images/", "")])], item.image);
  const serviceChoices = (ids = []) => `<fieldset class="admin-ops-checks admin-ops-full"><legend>${window.spaIcon("leaf")}Dịch vụ ${module === "employees" ? "có thể phụ trách" : "áp dụng"}</legend><p class="admin-data-note">${module === "promotions" ? "Có thể để trống nếu phạm vi đang được cập nhật. Không tự tính giá sau giảm." : "Chọn theo chuyên môn; không tạo lịch làm việc hoặc phân quyền."}</p><div class="admin-ops-choice-grid">${services.map((s) => `<label><input type="checkbox" name="serviceIds" value="${s.id}" ${ids.includes(s.id) ? "checked" : ""}>${escape(s.name)}${s.active ? "" : " (Tạm ngừng)"}</label>`).join("")}</div></fieldset>`;
  const formGroup = (title, icon, fields) => `<fieldset class="admin-ops-form-section"><legend>${window.spaIcon(icon)}${title}</legend><div class="admin-service-form-grid">${fields}</div></fieldset>`;
  const groups = [["relax", "Thư giãn"], ["face", "Da mặt"], ["body", "Cơ thể"], ["hair", "Tóc / da đầu"]];
  const productFields = (p) => formGroup("Thông tin sản phẩm", "droplet", input("Tên sản phẩm *", "name", p.name, 'required maxlength="120" autofocus') +
    input("Danh mục *", "category", p.category, 'required maxlength="120"') + imageField(p, "products") +
    select("Nhóm chăm sóc", "careGroup", [["", "Chưa xác định"], ...groups], p.careGroup) +
    textarea("Mô tả ngắn *", "description", p.description)) + formGroup("Thông tin chăm sóc", "leaf", textarea("Thành phần", "ingredients", p.ingredients) +
    textarea("Cách sử dụng", "usage", p.usage) + textarea("Lưu ý", "note", p.note) +
    textarea("Loại da phù hợp — mỗi dòng một giá trị", "skins", (p.skins || []).join("\n")) +
    textarea("Đối tượng sử dụng — mỗi dòng một giá trị", "audiences", (p.audiences || []).join("\n")));
  const employeeFields = (p) => formGroup("Hồ sơ & liên hệ", "heart", input("Họ và tên *", "name", p.name, 'required maxlength="120" autofocus') +
    imageField(p, "employees") + input("Email", "email", p.email, 'type="email" maxlength="160"') +
    input("Số điện thoại", "phone", p.phone, 'type="tel" maxlength="20"')) +
    formGroup("Chuyên môn & dịch vụ", "leaf", textarea("Chuyên môn *", "specialty", p.specialty) + serviceChoices(p.serviceIds || []));
  const discountParts = (p) => p.discount?.includes("%") ? ["percent", Number(p.discount.match(/\d+/)?.[0]) || ""] : ["amount", Number((p.discount || "").replace(/\D/g, "")) || ""];
  const promotionFields = (p) => {
    const [type, value] = discountParts(p);
    return formGroup("Thông tin chương trình", "star", input("Tên chương trình *", "name", p.name, 'required maxlength="120" autofocus') +
      input("Mã khuyến mãi *", "code", p.code, 'required maxlength="40"') +
      select("Hình thức ưu đãi", "discountType", [["percent", "Giảm theo phần trăm"], ["amount", "Giảm số tiền VND"]], type) +
      input("Giá trị ưu đãi *", "discountValue", value, 'type="number" min="1" step="1" required') +
      input("Ngày bắt đầu *", "startDate", p.startDate, 'type="date" required') +
      input("Ngày kết thúc *", "endDate", p.endDate, 'type="date" required')) +
      formGroup("Nội dung & điều kiện", "note",
      textarea("Mô tả ngắn", "description", p.description) + textarea("Nội dung chi tiết", "detail", p.detail) +
      textarea("Điều kiện áp dụng — mỗi dòng một điều kiện", "conditions", (p.conditions || []).join("\n")) +
      textarea("Lưu ý", "note", p.note) + input("Nhãn chương trình", "badge", p.badge, 'maxlength="80"') +
      select("Màu nhấn theo catalog", "accent", [["champagne", "Champagne"], ["terracotta", "Terracotta"], ["caramel", "Caramel"]], p.accent || "champagne") +
      textarea("Mã thay thế — mỗi dòng một mã", "aliases", (p.aliases || []).join("\n"))) +
      formGroup("Phạm vi dịch vụ áp dụng", "leaf", textarea("Ghi chú phạm vi áp dụng", "scopeNote", p.scopeNote) + serviceChoices(p.serviceIds || []));
  };
  const edit = (id) => {
    const existing = id === undefined ? null : data[module].find((i) => i.id === id);
    const item = existing || { name: "", active: true };
    const fields = module === "products" ? productFields(item) : module === "employees" ? employeeFields(item) : promotionFields(item);
    open(`${existing ? "Sửa" : "Thêm"} ${names[module]}`, `<form class="admin-service-form admin-ops-form" novalidate><div class="admin-service-modal-scroll">${fields}<p class="admin-data-note">Các trường * là bắt buộc. Dữ liệu minh họa chỉ lưu trong phiên Admin.</p>${errorBox}</div>${footer("Lưu demo")}</form>`);
    dialog.querySelector("form").addEventListener("submit", (event) => {
      event.preventDefault();
      dialog.querySelectorAll("[aria-invalid]").forEach((node) => node.removeAttribute("aria-invalid"));
      const form = event.currentTarget, raw = new FormData(form);
      const v = Object.fromEntries([...raw.entries()].map(([k, val]) => [k, String(val).trim()]));
      if (!v.name || v.name.length > 120) return error("Vui lòng nhập tên từ 1 đến 120 ký tự, không chỉ khoảng trắng.", "name");
      const record = { ...item, id: existing?.id ?? Math.max(-1, ...data[module].map((p) => p.id)) + 1, name: v.name };
      if (module === "products") {
        if (!v.category) return error("Vui lòng nhập danh mục sản phẩm.", "category");
        if (!v.description) return error("Vui lòng nhập mô tả sản phẩm.", "description");
        Object.assign(record, { category: v.category, description: v.description, image: v.image, careGroup: v.careGroup, ingredients: v.ingredients, usage: v.usage, note: v.note, skins: lines(v.skins), audiences: lines(v.audiences) });
      } else if (module === "employees") {
        if (v.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.email)) return error("Email không hợp lệ.", "email");
        if (v.phone && !/^\+?[\d ()-]{8,20}$/.test(v.phone)) return error("Số điện thoại không hợp lệ.", "phone");
        if (!v.specialty) return error("Vui lòng nhập chuyên môn.", "specialty");
        Object.assign(record, { email: v.email, phone: v.phone, specialty: v.specialty, image: v.image, serviceIds: raw.getAll("serviceIds").map(Number) });
      } else {
        const amount = Number(v.discountValue);
        if (!/^[A-Z0-9_-]{2,40}$/i.test(v.code)) return error("Mã gồm 2–40 ký tự chữ, số, gạch ngang hoặc gạch dưới.", "code");
        const aliases = lines(v.aliases).map((a) => a.toUpperCase());
        const codes = [v.code.toUpperCase(), ...aliases];
        if (new Set(codes).size !== codes.length || aliases.some((a) => !/^[A-Z0-9_-]{2,40}$/.test(a)) ||
          data.promotions.some((p) => p.id !== existing?.id && [p.code, ...(p.aliases || [])].some((c) => codes.includes(c.toUpperCase())))) return error("Mã khuyến mãi hoặc mã thay thế bị trùng / không hợp lệ.", "code");
        if (!["percent", "amount"].includes(v.discountType) || !Number.isSafeInteger(amount) || amount <= 0 || (v.discountType === "percent" && amount > 100)) return error("Ưu đãi phải lớn hơn 0; phần trăm không vượt quá 100.", "discountValue");
        if (!Number.isFinite(day(v.startDate))) return error("Vui lòng nhập ngày bắt đầu hợp lệ.", "startDate");
        if (!Number.isFinite(day(v.endDate)) || day(v.endDate) < day(v.startDate)) return error("Ngày kết thúc phải từ ngày bắt đầu trở đi.", "endDate");
        Object.assign(record, {
          code: v.code.toUpperCase(), aliases, discount: v.discountType === "percent" ? `Giảm ${amount}%` : `Giảm ${money(amount)}`,
          startDate: v.startDate, endDate: v.endDate, description: v.description, detail: v.detail,
          conditions: lines(v.conditions), scopeNote: v.scopeNote, note: v.note, badge: v.badge,
          accent: v.accent, serviceIds: raw.getAll("serviceIds").map(Number),
        });
      }
      if (record.serviceIds?.some((id) => !services.some((s) => s.id === id))) return error("Danh sách dịch vụ không hợp lệ.");
      const next = clone(data);
      if (existing) next[module][next[module].findIndex((i) => i.id === id)] = record;
      else next[module].push(record);
      if (!commit(next)) return;
      render(); dialog.close(); notice(`Đã ${existing ? "cập nhật" : "thêm"} ${names[module]} “${record.name}” trong phiên demo.`);
    });
  };
  const facts = (entries) => `<dl class="admin-profile-facts admin-ops-facts">${entries.map(([label, value]) => `<div><dt>${window.spaIcon(/Ngày|Thời gian|Thời lượng/.test(label) ? "calendar" : /Nhân viên|Khách hàng/.test(label) ? "heart" : "note")}${escape(label)}</dt><dd>${escape(Array.isArray(value) ? value.join("\n") || "Chưa cập nhật" : value || "Chưa cập nhật")}</dd></div>`).join("")}</dl>`;
  const detailGroup = (title, icon, entries) => `<section class="admin-ops-detail-section"><h4>${window.spaIcon(icon)}${title}</h4>${facts(entries)}</section>`;
  const serviceNames = (ids = []) => ids.map((id) => services.find((s) => s.id === id)?.name || `DV-${id + 1}`);
  const view = (item) => {
    let entries;
    if (module === "products") entries = [["Mã sản phẩm", code(item)], ["Danh mục", item.category], ["Mô tả", item.description], ["Nhóm chăm sóc", groups.find(([k]) => k === item.careGroup)?.[1]], ["Thành phần", item.ingredients], ["Cách sử dụng", item.usage], ["Lưu ý", item.note], ["Loại da", item.skins], ["Đối tượng sử dụng", item.audiences], ["Dịch vụ liên quan (catalog)", serviceNames(catalog.relations.filter((r) => r.productId === item.id).map((r) => r.serviceId))]];
    else if (module === "employees") entries = [["Mã nhân viên", code(item)], ["Email", item.email], ["Số điện thoại", item.phone], ["Chuyên môn", item.specialty], ["Dịch vụ phụ trách", serviceNames(item.serviceIds)]];
    else if (module === "appointments") entries = [["Mã lịch hẹn", code(item)], ["Khách hàng minh họa", item.customer], ["Dịch vụ", item.service], ["Ngày / giờ", `${dateLabel(item.date)} · ${item.time}`], ["Thời lượng", `${item.minutes} phút`], ["Nhân viên", employeeName(item.employeeId)], ["Ghi chú", item.note], ["Trạng thái", statuses[item.status]]];
    else entries = [["Mã", item.code], ["Mã thay thế", item.aliases], ["Ưu đãi", item.discount], ["Thời gian", `${dateLabel(item.startDate)} — ${dateLabel(item.endDate)}`], ["Mô tả", item.description], ["Nội dung chi tiết", item.detail], ["Điều kiện", item.conditions], ["Dịch vụ áp dụng", serviceNames(item.serviceIds)], ["Phạm vi", item.scopeNote], ["Lưu ý", item.note], ["Nhãn chương trình", item.badge]];
    const content = module === "products" ? detailGroup("Thông tin sản phẩm", "droplet", entries.slice(0, 4)) + detailGroup("Thông tin chăm sóc", "leaf", entries.slice(4)) :
      module === "employees" ? detailGroup("Hồ sơ & liên hệ", "heart", entries.slice(0, 3)) + detailGroup("Chuyên môn & dịch vụ", "leaf", entries.slice(3)) :
        module === "promotions" ? detailGroup("Thông tin chương trình", "star", [...entries.slice(0, 4), entries[10]]) + detailGroup("Nội dung & điều kiện", "note", [...entries.slice(4, 7), entries[9]]) + detailGroup("Phạm vi dịch vụ áp dụng", "leaf", entries.slice(7, 9)) : facts(entries);
    open(`Thông tin ${names[module]}`, `<div class="admin-service-modal-scroll"><div class="admin-ops-detail-heading">${["products", "employees"].includes(module) ? portrait(item) : `<span class="admin-ops-detail-symbol">${moduleIcon()}</span>`}<h3>${escape(item.name || item.customer)}</h3>${statusBadge(item)}</div>${content}</div>${footer()}`);
  };
  const confirm = (title, description, perform) => {
    open(title, `<div class="admin-service-modal-scroll"><p>${escape(description)}</p><p class="admin-data-note">Chỉ cập nhật phiên demo Admin; dữ liệu cũ không bị xóa. Không xử lý thanh toán hoặc hoàn tiền.</p>${errorBox}</div><div class="admin-dialog-actions"><button class="admin-button" data-close type="button" autofocus>Hủy</button><button class="admin-button admin-button-primary" data-confirm type="button">Xác nhận</button></div>`);
    dialog.querySelector("[data-confirm]").addEventListener("click", perform);
  };
  const toggle = (item) => {
    confirm(`${item.active ? "Tắt" : "Bật"} ${names[module]}`, `${item.active ? "Tạm ngừng" : "Bật lại"} “${item.name}”?${module === "promotions" ? " Hiệu lực vẫn phụ thuộc ngày áp dụng và điều kiện chương trình." : ""}`, () => {
      const next = clone(data);
      next[module].find((i) => i.id === item.id).active = !item.active;
      if (!commit(next)) return;
      render(); dialog.close(); notice(`Đã ${item.active ? "tắt" : "bật"} “${item.name}” trong phiên demo.`);
    });
  };
  // Keep the four source statuses; terminal states cannot be reopened.
  const transitions = { pending: ["pending", "confirmed", "cancelled"], confirmed: ["confirmed", "completed", "cancelled"], completed: [], cancelled: [] };
  const validateAppointment = (item, status, employeeId, reassignment = {}) => {
    if (!transitions[item.status]?.includes(status)) return "Chuyển trạng thái không hợp lệ.";
    if (status === "cancelled" && item.invoice?.status === "paid" && item.invoice.method !== "spa") return "Lịch đã thanh toán online cần xử lý hỗ trợ riêng; demo không thực hiện hoàn tiền.";
    const hasEmployee = item.employeeId !== null && item.employeeId !== undefined;
    if (hasEmployee && employeeId !== item.employeeId) {
      if (status === "cancelled") return "Hủy lịch phải giữ nguyên nhân viên đã chọn.";
      if (employeeId === null) return "Không được bỏ nhân viên đã chọn. Vui lòng chọn người thay thế phù hợp.";
      if (!reassignment.requested || !reassignment.agreed) return "Chỉ phân công lại khi nhân viên không thể phục vụ và đã thống nhất với khách.";
    }
    if (status === "cancelled") return "";
    if (employeeId === null) return status === "confirmed" || status === "completed" ? "Vui lòng phân công nhân viên trước khi xác nhận/hoàn thành." : "";
    const employee = data.employees.find((e) => e.id === employeeId);
    if (!employee?.active || !employee.serviceIds.includes(item.serviceId)) return "Nhân viên không hoạt động hoặc không phù hợp với dịch vụ.";
    const start = new Date(`${item.date}T${item.time}:00`).getTime(), end = start + item.minutes * 60000;
    const collision = data.appointments.some((other) => {
      if (other.id === item.id || other.status === "cancelled" || other.employeeId !== employeeId) return false;
      const otherStart = new Date(`${other.date}T${other.time}:00`).getTime();
      return start < otherStart + other.minutes * 60000 && end > otherStart;
    });
    return collision ? "Nhân viên đã có lịch trùng thời gian trong phiên Admin." : "";
  };
  const process = (item) => {
    if (!transitions[item.status]?.length) return;
    const employees = data.employees.filter((e) => e.active && e.serviceIds.includes(item.serviceId));
    const hasEmployee = item.employeeId !== null && item.employeeId !== undefined;
    const options = [["", "Chưa phân công"], ...employees.map((e) => [e.id, e.name])];
    if (hasEmployee && !employees.some((e) => e.id === item.employeeId)) options.push([item.employeeId, `${employeeName(item.employeeId)} (nhân viên đã chọn, hiện không khả dụng)`]);
    const exceptionPanel = hasEmployee ? `<fieldset class="admin-ops-reassignment"><legend>${window.spaIcon("heart")}Phân công lại ngoại lệ</legend><p>Giữ nhân viên khách đã chọn khi xác nhận thông thường. Chỉ thay đổi nếu nhân viên không thể phục vụ và đã thống nhất với khách.</p><label><input type="checkbox" name="reassign">Nhân viên hiện tại không thể phục vụ — cần phân công lại</label><div data-reassignment-consent hidden><label><input type="checkbox" name="customerAgreed">Đã thống nhất với khách</label><p class="admin-data-note">Admin xác nhận thủ công trong demo. Không gửi thông báo và không tự coi khách đã đồng ý.</p></div></fieldset>` : `<p class="admin-ops-assignment-note">${window.spaIcon("calendar")}Lịch demo cũ chưa có nhân viên: được phép phân công bổ sung.</p>`;
    open("Xử lý lịch hẹn", `<form class="admin-service-form admin-ops-form" novalidate><div class="admin-service-modal-scroll"><div class="admin-ops-process-heading">${statusBadge(item)}<span>${window.spaIcon("heart")}${escape(employeeName(item.employeeId))}</span></div>${facts([["Lịch hẹn", code(item)], ["Khách hàng", item.customer], ["Dịch vụ", item.service], ["Ngày / giờ", `${dateLabel(item.date)} · ${item.time}`]])}${exceptionPanel}${formGroup("Phân công & trạng thái", "calendar", select("Nhân viên phụ trách", "employeeId", options, item.employeeId ?? "") + select("Trạng thái", "status", transitions[item.status].map((s) => [s, statuses[s]]), item.status))}<p class="admin-data-note">Chờ xác nhận → Đã xác nhận → Đã hoàn thành. Chỉ lịch chờ/đã xác nhận được hủy. Nhân viên phải phù hợp chuyên môn và không trùng lịch. Lịch hoàn thành/đã hủy chỉ được xem.</p>${errorBox}</div>${footer("Tiếp tục")}</form>`);
    const form = dialog.querySelector("form");
    const syncAssignment = () => {
      const cancelled = form.elements.status.value === "cancelled";
      const enabled = !cancelled && (!hasEmployee || form.elements.reassign.checked);
      form.elements.employeeId.disabled = !enabled;
      if (!enabled) form.elements.employeeId.value = item.employeeId ?? "";
      if (hasEmployee) {
        form.elements.reassign.disabled = cancelled;
        if (cancelled) form.elements.reassign.checked = false;
        const consent = dialog.querySelector("[data-reassignment-consent]");
        consent.hidden = !enabled;
        if (!enabled) form.elements.customerAgreed.checked = false;
      }
    };
    form.elements.reassign?.addEventListener("change", syncAssignment);
    form.elements.status.addEventListener("change", syncAssignment);
    syncAssignment();
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const v = Object.fromEntries(new FormData(event.currentTarget));
      const employeeId = v.status === "cancelled" || form.elements.employeeId.disabled ? item.employeeId ?? null : v.employeeId === "" ? null : Number(v.employeeId);
      const reassignment = { requested: form.elements.reassign?.checked === true, agreed: form.elements.customerAgreed?.checked === true };
      const message = validateAppointment(item, v.status, employeeId, reassignment);
      if (message) return error(message, "employeeId");
      if (item.status === v.status && item.employeeId === employeeId) { dialog.close(); notice("Không có thay đổi lịch hẹn."); return; }
      const changingEmployee = hasEmployee && employeeId !== item.employeeId;
      confirm(changingEmployee ? "Xác nhận phân công lại ngoại lệ" : "Xác nhận cập nhật lịch hẹn", `${code(item)} · ${item.customer}: ${statuses[item.status]} → ${statuses[v.status]}; nhân viên: ${changingEmployee ? `${employeeName(item.employeeId)} → ` : ""}${employeeName(employeeId)}.${changingEmployee ? " Admin xác nhận nhân viên cũ không thể phục vụ và đã thống nhất với khách. Không gửi thông báo thật." : ""}`, () => {
        const current = data.appointments.find((a) => a.id === item.id);
        const message = validateAppointment(current, v.status, employeeId, reassignment);
        if (message) return error(message);
        const next = clone(data), record = next.appointments.find((a) => a.id === item.id);
        record.status = v.status; record.employeeId = employeeId;
        if (!commit(next)) return;
        render(); dialog.close(); notice(`Đã cập nhật ${code(item)} trong phiên Admin.`);
      });
    });
  };
  $("#ops-context").textContent = module === "promotions"
    ? `Hiệu lực tính theo ngày demo ${dateLabel(promotions.referenceDate)} như catalog User; không tính giá dịch vụ sau giảm.`
    : module === "appointments" ? "Lịch hẹn minh họa riêng của Admin, không sao chép hoặc sửa lịch hẹn User. Chỉ dùng bốn trạng thái hiện có."
      : module === "products" ? "Sản phẩm chỉ để giới thiệu và chăm sóc tại nhà. Không bán hàng, không quản lý tồn kho."
        : "Hồ sơ nhân viên minh họa; thông tin liên hệ chưa có được hiển thị “Chưa cập nhật”. Không chấm công, tính lương hoặc phân quyền.";
  $("#ops-add")?.addEventListener("click", () => edit());
  ["#ops-search", "#ops-status", "#ops-date", "#ops-category"].forEach((selector) => $(selector)?.addEventListener(selector === "#ops-search" ? "input" : "change", () => { page = 1; render(); }));
  $("#ops-reset").addEventListener("click", () => {
    ["#ops-search", "#ops-status", "#ops-date", "#ops-category"].forEach((selector) => { if ($(selector)) $(selector).value = ""; });
    page = 1; render(); $("#ops-search").focus();
  });
  $("#ops-pagination").addEventListener("click", (event) => {
    const button = event.target.closest("[data-page]");
    if (button && !button.disabled) { page = Number(button.dataset.page); render(); }
  });
  $("#ops-rows").addEventListener("click", (event) => {
    const button = event.target.closest("[data-action]");
    if (!button) return;
    const item = data[module].find((i) => i.id === Number(button.dataset.id));
    if (!item) return;
    ({ view, edit: () => edit(item.id), toggle, process })[button.dataset.action]?.(item);
  });
  render();
})();
