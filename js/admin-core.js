(() => {
  "use strict";
  if (!window.spaAuth?.isAuthenticated()) return;
  try { if (JSON.parse(sessionStorage.getItem("spa-auth"))?.role !== "Admin") return; } catch { return; }
  const $ = (selector) => document.querySelector(selector);
  const escape = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const money = (value) => `${new Intl.NumberFormat("vi-VN").format(value)} VND`;
  const normalize = (value) => String(value ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/g, "d").toLowerCase();
  const initials = (name) => String(name).trim().split(/\s+/).slice(-2).map((part) => part[0]).join("").toUpperCase();
  const avatar = (person) => `<span class="admin-customer-initials" aria-hidden="true">${/^data:image\/(?:png|jpeg|webp);base64,/.test(person.avatar || "") ? `<img src="${escape(person.avatar)}" alt="">` : escape(initials(person.name))}</span>`;
  const tier = (value) => `<span class="admin-tier" data-tier="${escape(value)}">${escape(value)}</span>`;
  const pageSize = 5;
  const paginate = (id, page, total, noun, change) => {
    const pages = Math.max(1, Math.ceil(total / pageSize));
    const shown = Math.min(pageSize, Math.max(0, total - (page - 1) * pageSize));
    $(id).innerHTML = `<span>${shown} / ${total} ${noun}${total ? ` · ${(page - 1) * pageSize + 1}–${(page - 1) * pageSize + shown}` : ""}</span><div><button class="admin-button" type="button" data-page="${page - 1}" ${page === 1 ? "disabled" : ""} aria-label="Trang trước">Trước</button><span> ${page} / ${pages} </span><button class="admin-button" type="button" data-page="${page + 1}" ${page >= pages ? "disabled" : ""} aria-label="Trang sau">Sau</button></div>`;
    $(id).querySelectorAll("[data-page]").forEach((button) => button.addEventListener("click", () => change(Number(button.dataset.page))));
  };
  const dialog = document.createElement("dialog");
  dialog.className = "admin-dialog";
  dialog.setAttribute("aria-labelledby", "admin-dialog-title");
  document.body.append(dialog);
  let returnFocus;
  dialog.addEventListener("close", () => { if (returnFocus?.isConnected) returnFocus.focus(); });
  const openDialog = (title, body, confirm) => {
    returnFocus = document.activeElement;
    dialog.innerHTML = `<button class="admin-dialog-close admin-icon-button" type="button" aria-label="Đóng">${window.spaIcon("close")}</button><span class="admin-eyebrow">AN NHIÊN SPA / TÀI KHOẢN</span><h2 id="admin-dialog-title">${escape(title)}</h2><div class="admin-dialog-body">${body}</div><div class="admin-dialog-actions"><button class="admin-button" data-cancel type="button" autofocus>${confirm ? "Hủy" : "Đóng"}</button>${confirm ? '<button class="admin-button admin-button-primary" data-confirm type="button">Xác nhận</button>' : ""}</div>`;
    dialog.querySelector(".admin-dialog-close").onclick = () => dialog.close();
    dialog.querySelector("[data-cancel]").onclick = () => dialog.close();
    if (confirm) dialog.querySelector("[data-confirm]").onclick = () => { dialog.close(); confirm(); };
    dialog.showModal();
  };

  if ($("[data-admin-accounts]")) {
    const accounts = [
      { id: "TK-001", username: "admin", email: "admin@annhienspa.vn", role: "Admin", joined: "01/01/2026" },
      { id: "TK-002", username: "user", email: "user@annhienspa.vn", role: "User", joined: "15/02/2026" },
      ...["thanhtruc_demo", "hoangnam_demo", "hamy_demo", "minhthu_demo", "quoclong_demo", "bichngoc_demo"].map((username, index) => ({
        id: `TK-00${index + 3}`, username, email: `${username}@example.com`, role: "User", joined: `${10 + index}/03/2026`,
      })),
    ];
    const storageKey = "spa-admin-account-status";
    let saved = {};
    try { saved = JSON.parse(sessionStorage.getItem(storageKey)) || {}; } catch { /* In-memory fallback. */ }
    accounts.forEach((a) => { a.status = a.role === "Admin" ? "active" : ["active", "locked"].includes(saved[a.id]) ? saved[a.id] : ["TK-005", "TK-007"].includes(a.id) ? "locked" : "active"; });
    let page = 1;
    const render = () => {
      const active = accounts.filter((a) => a.status === "active").length;
      $("#accounts-stats").innerHTML = [["Tổng tài khoản", accounts.length], ["Đang hoạt động", active], ["Đã khóa", accounts.length - active]].map(([label, value]) => `<article><span>${label}</span><strong>${value}</strong></article>`).join("");
      const query = normalize($("#accounts-search").value.trim());
      const rows = accounts.filter((a) => normalize(`${a.username} ${a.email}`).includes(query) && (!$("#accounts-role").value || a.role === $("#accounts-role").value) && (!$("#accounts-status").value || a.status === $("#accounts-status").value));
      page = Math.min(page, Math.max(1, Math.ceil(rows.length / pageSize)));
      $("#accounts-rows").innerHTML = rows.slice((page - 1) * pageSize, page * pageSize).map((a) => `<tr><td>${a.id}</td><td><strong>${escape(a.username)}</strong>${a.role === "Admin" ? '<span class="admin-table-time">Đang quản trị</span>' : ""}</td><td>${escape(a.email)}</td><td><span class="admin-tier">${a.role}</span></td><td><span class="admin-status-badge ${a.status === "active" ? "admin-status-completed" : "admin-status-cancelled"}">${a.status === "active" ? "Hoạt động" : "Đã khóa"}</span></td><td>${a.joined}</td><td><div class="admin-row-actions"><button class="admin-button" data-view="${a.id}" type="button" aria-label="Xem ${escape(a.username)}">Xem</button>${a.role === "User" ? `<button class="admin-button" data-toggle="${a.id}" type="button">${a.status === "active" ? "Khóa" : "Mở khóa"}</button>` : '<span class="admin-table-time">Không thể tự khóa</span>'}</div></td></tr>`).join("");
      $("#accounts-empty").hidden = Boolean(rows.length);
      paginate("#accounts-pagination", page, rows.length, "tài khoản", (next) => { page = next; render(); });
    };
    ["#accounts-search", "#accounts-role", "#accounts-status"].forEach((id) => $(id).addEventListener(id.includes("search") ? "input" : "change", () => { page = 1; render(); }));
    $("#accounts-rows").addEventListener("click", (event) => {
      const button = event.target.closest("[data-view], [data-toggle]");
      if (!button) return;
      const a = accounts.find((entry) => entry.id === (button.dataset.view || button.dataset.toggle));
      if (!a) return;
      if (button.dataset.view) {
        openDialog("Thông tin tài khoản", `<dl class="admin-profile-facts">${[["Mã tài khoản", a.id], ["Username", a.username], ["Email", a.email], ["Vai trò", a.role], ["Trạng thái", a.status === "active" ? "Hoạt động" : "Đã khóa"], ["Ngày tham gia", a.joined]].map(([key, value]) => `<div><dt>${key}</dt><dd>${escape(value)}</dd></div>`).join("")}</dl>`);
        return;
      }
      if (a.role !== "User") return;
      const locking = a.status === "active";
      openDialog(locking ? "Khóa tài khoản" : "Mở khóa tài khoản", `<p>${locking ? "Tài khoản sẽ bị hạn chế truy cập; hồ sơ, lịch hẹn và hóa đơn cũ không bị xóa." : "Tài khoản sẽ trở lại trạng thái Hoạt động."}</p><p><strong>${escape(a.username)}</strong> · ${escape(a.email)}</p><p>Đây là thao tác demo, chỉ áp dụng cho dataset Admin trong phiên.</p>`, () => {
        a.status = locking ? "locked" : "active";
        try { sessionStorage.setItem(storageKey, JSON.stringify(Object.fromEntries(accounts.filter((item) => item.role === "User").map((item) => [item.id, item.status])))); } catch { /* State remains usable until navigation. */ }
        render();
        $("#accounts-rows").querySelector(`[data-toggle="${a.id}"]`)?.focus();
      });
    });
    render();
  }

  if ($("[data-admin-customers]")) {
    const customers = [
      { ...window.spaAuth.getProfile(), id: "KH-001", joined: "", tier: "Bạc" },
      ...[
        ["Trần Thanh Trúc", "thanhtruc_demo", "Da hỗn hợp", "Kim cương", ["Kiểm soát dầu, chăm sóc da mụn.", "Làm sáng da, cải thiện da xỉn màu."], ["Ưu tiên nguyên liệu thiên nhiên.", "Thích liệu trình chăm sóc chuyên sâu."], 1500000],
        ["Lê Hoàng Nam", "hoangnam_demo", "Da dầu", "Vàng", ["Thư giãn, giảm căng thẳng."], ["Thích massage và chăm sóc cơ thể."], 800000],
        ["Lê Hà My", "hamy_demo", "Da nhạy cảm", "Bạc", ["Dưỡng ẩm, cải thiện da khô."], ["Liệu trình nhẹ nhàng, thư giãn."], 600000],
        ["Phạm Minh Thư", "minhthu_demo", "Da khô", "Vàng", ["Chăm sóc tóc và da đầu."], ["Ưu tiên liệu trình ngắn, tiết kiệm thời gian."], 900000],
        ["Trần Quốc Long", "quoclong_demo", "Da thường", "Bạc", ["Chăm sóc cơ thể, giảm mệt mỏi."], ["Không có sở thích đặc biệt."], null],
        ["Trần Bích Ngọc", "bichngoc_demo", "Chưa xác định", "Kim cương", [], [], null],
      ].map(([name, username, skin, rank, needs, interests, budget], index) => ({ id: `KH-00${index + 2}`, name, username, skin, tier: rank, needs, interests, budget, email: `${username}@example.com`, phone: "", joined: `${10 + index}/03/2026` })),
    ];
    let page = 1, selected = customers[0].id;
    const display = (value) => Array.isArray(value) ? value.join(" ") || "Chưa cập nhật" : value || "Chưa cập nhật";
    const renderProfile = (person) => {
      if (!person) { $("#customer-profile").innerHTML = '<div class="admin-empty-state"><h3>Chưa chọn khách hàng</h3><p>Không có hồ sơ khớp với bộ lọc.</p></div>'; return; }
      const fields = [["Username", person.username], ["Email", person.email], ["Số điện thoại", person.phone], ["Ngày tham gia", person.joined]];
      const care = [["Loại da", person.skin], ["Nhu cầu chăm sóc", person.needs], ["Sở thích", person.interests], ["Ngân sách dự kiến", person.budget !== null && person.budget !== "" && Number.isFinite(Number(person.budget)) ? money(Number(person.budget)) : ""]];
      $("#customer-profile").innerHTML = `<div class="admin-profile-heading"><span class="admin-eyebrow">HỒ SƠ KHÁCH HÀNG</span>${tier(person.tier)}</div><div class="admin-profile-identity">${avatar(person)}<h2>${escape(person.name)}</h2></div><h3>Thông tin cơ bản</h3><dl class="admin-profile-facts">${fields.map(([label, value]) => `<div><dt>${label}</dt><dd class="${display(value) === "Chưa cập nhật" ? "is-unset" : ""}">${escape(display(value))}</dd></div>`).join("")}</dl><h3>Thông tin chăm sóc</h3><dl class="admin-care-facts">${care.map(([label, value]) => `<div><dt>${label}</dt><dd class="${display(value) === "Chưa cập nhật" ? "is-unset" : ""}">${escape(display(value))}</dd></div>`).join("")}</dl><p class="admin-data-note">Chỉ xem · Thông tin do khách hàng chia sẻ. Hạng thành viên minh họa.</p>`;
    };
    const render = () => {
      const query = normalize($("#customers-search").value.trim());
      const rows = customers.filter((c) => normalize(`${c.name} ${c.email} ${c.phone}`).includes(query) && (!$("#customers-tier").value || c.tier === $("#customers-tier").value));
      page = Math.min(page, Math.max(1, Math.ceil(rows.length / pageSize)));
      const visible = rows.slice((page - 1) * pageSize, page * pageSize);
      if (!visible.some((c) => c.id === selected)) selected = visible[0]?.id;
      $("#customers-rows").innerHTML = visible.map((c) => `<tr class="${selected === c.id ? "is-selected" : ""}"><td><button class="admin-customer-select" data-customer="${c.id}" type="button" aria-pressed="${selected === c.id}">${avatar(c)}<span><strong>${escape(c.name)}</strong><small>${escape(c.username ? `@${c.username}` : c.email)}</small></span></button></td><td><span>${escape(c.phone || "Chưa cập nhật")}</span><span class="admin-table-time">${escape(c.email)}</span></td><td>${tier(c.tier)}${c.skin ? `<span class="admin-customer-skin">${escape(c.skin)}</span>` : ""}</td></tr>`).join("");
      $("#customers-empty").hidden = Boolean(rows.length);
      paginate("#customers-pagination", page, rows.length, "khách hàng", (next) => { page = next; render(); });
      renderProfile(customers.find((c) => c.id === selected));
    };
    $("#customers-rows").addEventListener("click", (event) => {
      const button = event.target.closest("[data-customer]");
      if (!button) return;
      selected = button.dataset.customer;
      render();
      $("#customers-rows").querySelector(`[data-customer="${selected}"]`)?.focus();
    });
    ["#customers-search", "#customers-tier"].forEach((id) => $(id).addEventListener(id.includes("search") ? "input" : "change", () => { page = 1; render(); }));
    render();
  }
})();
