(() => {
  "use strict";
  const main = document.querySelector("[data-admin-finance]");
  if (!main || !window.spaAuth?.isAuthenticated()) return;
  try { if (JSON.parse(sessionStorage.getItem("spa-auth"))?.role !== "Admin") return; } catch { return; }
  const module = main.dataset.adminFinance;
  const $ = (selector) => document.querySelector(selector);
  const escape = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const normalize = (value) => String(value ?? "").toLocaleLowerCase("vi").normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/g, "d").trim();
  const money = (value) => `${new Intl.NumberFormat("vi-VN").format(value)} VND`;
  const dateLabel = (value) => value.slice(0, 10).split("-").reverse().join(".");
  const timeLabel = (value) => new Date(value).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Ho_Chi_Minh" });
  const methodLabel = (method) => method === "spa" ? "Trực tiếp tại Spa" : "payOS · minh họa";
  const badge = (label, style) => `<span class="admin-status-badge admin-status-${style}">${escape(label)}</span>`;
  const paymentLabels = { success: "Thành công", pending: "Đang chờ", cancelled: "Đã hủy" };
  const paymentBadge = (status) => badge(paymentLabels[status], status === "success" ? "completed" : status === "pending" ? "pending" : "cancelled");
  const invoiceBadge = (status) => badge(status === "paid" ? "Đã thanh toán" : "Chưa thanh toán", status === "paid" ? "completed" : "pending");

  // Historical Finance-only fixtures. Literal prices/discounts are snapshots, never
  // looked up from a mutable catalog or copied from the User's appointment storage.
  // LH-FIN codes deliberately distinguish these from Operations' LH-001 fixtures.
  const invoiceSnapshots = [
    ["Lan Anh", "Massage đá nóng", 590000, 0, 590000, "", "2026-10-14", "09:00", "pending", "unpaid", "2026-10-11T09:00:00+07:00"],
    ["Minh Thư", "Chăm sóc da chuyên sâu", 450000, 67500, 382500, "FACIAL15", "2026-10-14", "10:00", "confirmed", "unpaid", "2026-10-11T10:00:00+07:00"],
    ["Hà My", "Ủ chăm sóc tóc và da đầu", 390000, 39000, 351000, "HAIR10", "2026-10-13", "11:00", "completed", "paid", "2026-10-12T10:00:00+07:00"],
    ["Hoàng Nam", "Dưỡng thể thư giãn", 420000, 0, 420000, "", "2026-10-14", "14:00", "confirmed", "paid", "2026-10-12T14:00:00+07:00"],
    ["Thanh Trúc", "Ủ dưỡng tóc phục hồi", 320000, 0, 320000, "", "2026-10-14", "16:00", "cancelled", "unpaid", "2026-10-12T15:00:00+07:00"],
    ["Quốc Long", "Tẩy tế bào chết body", 350000, 50000, 300000, "RELAX50", "2026-10-13", "09:00", "completed", "paid", "2026-10-12T16:00:00+07:00"],
    ["Bích Ngọc", "Massage da đầu thư giãn", 290000, 0, 290000, "", "2026-10-15", "11:00", "confirmed", "unpaid", "2026-10-13T09:00:00+07:00"],
    ["Lan Anh", "Chăm sóc da chuyên sâu", 450000, 0, 450000, "", "2026-10-16", "10:00", "confirmed", "paid", "2026-10-13T10:00:00+07:00"],
  ];
  const invoices = invoiceSnapshots.map(([customer, service, priceSnapshot, discount, total, promotion, date, time, appointmentStatus, status, createdAt], index) => Object.freeze({
    id: `HD-DEMO-${String(index + 1).padStart(3, "0")}`,
    appointmentId: `LH-FIN-${String(index + 1).padStart(3, "0")}`,
    customer, service, priceSnapshot, subtotal: priceSnapshot, discount, total,
    promotion, date, time, appointmentStatus, status, createdAt,
  }));
  // Existing method semantics: "spa" or "online". These are sample ledger entries,
  // not requests, webhook responses or an Admin-controlled payment simulator.
  const paymentSnapshots = [
    [1, "online", "pending", "2026-10-11T10:10:00+07:00"],
    [2, "spa", "success", "2026-10-13T12:20:00+07:00"],
    [3, "online", "success", "2026-10-12T14:20:00+07:00"],
    [4, "online", "cancelled", "2026-10-12T15:10:00+07:00"],
    [5, "spa", "success", "2026-10-13T10:00:00+07:00"],
    [6, "online", "pending", "2026-10-13T09:10:00+07:00"],
    [7, "online", "success", "2026-10-13T10:15:00+07:00"],
  ];
  const payments = paymentSnapshots.map(([invoiceIndex, method, status, createdAt], index) => Object.freeze({
    id: `GD-DEMO-${String(index + 1).padStart(3, "0")}`,
    invoiceId: invoices[invoiceIndex].id, amount: invoices[invoiceIndex].total,
    method, status, createdAt,
    reference: method === "online" ? `DEMO-PAYOS-${String(index + 1).padStart(3, "0")}` : "",
  }));
  const invoiceFor = (payment) => invoices.find((invoice) => invoice.id === payment.invoiceId);
  const paymentsFor = (invoice) => payments.filter((payment) => payment.invoiceId === invoice.id);
  // Guard fixture integrity before rendering totals or relations.
  const consistent = new Set(invoices.map((i) => i.appointmentId)).size === invoices.length &&
    new Set(invoices.map((i) => i.id)).size === invoices.length &&
    invoices.every((i) => i.total === i.subtotal - i.discount && i.discount >= 0 && i.total >= 0 &&
      ((i.status === "paid") === paymentsFor(i).some((p) => p.status === "success"))) &&
    payments.every((p) => invoiceFor(p)?.total === p.amount);
  if (!consistent) {
    $("#finance-data-note").textContent = "Dữ liệu demo chưa nhất quán. Chưa thể hiển thị sổ tài chính.";
    return;
  }
  const pageSize = 5;
  let page = 1, returnFocus;
  const dialog = $("#finance-dialog");
  const actionButton = (kind, id, label) => `<button class="admin-button" type="button" data-finance-view="${kind}" data-record="${escape(id)}">${window.spaIcon("eye")}${label}</button>`;
  const invoiceRow = (invoice) => `<tr>
    <td><strong class="admin-finance-code">${invoice.id}</strong><span class="admin-table-time">${invoice.appointmentId}</span></td>
    <td class="admin-finance-description"><strong>${escape(invoice.customer)}</strong><span class="admin-table-time">${escape(invoice.service)}</span></td>
    <td class="admin-finance-money">${money(invoice.subtotal)}</td>
    <td class="admin-finance-money">${money(invoice.discount)}<span class="admin-table-time">${invoice.promotion || "Không áp dụng"}</span></td>
    <td class="admin-finance-money admin-finance-total">${money(invoice.total)}</td>
    <td>${dateLabel(invoice.createdAt)}<span class="admin-table-time">${timeLabel(invoice.createdAt)}</span></td>
    <td>${invoiceBadge(invoice.status)}${invoice.appointmentStatus === "cancelled" ? '<span class="admin-table-time">Lịch hẹn đã hủy</span>' : ""}</td>
    <td><div class="admin-row-actions">${actionButton("invoice", invoice.id, "Xem")}</div></td></tr>`;
  const paymentRow = (payment) => {
    const invoice = invoiceFor(payment);
    return `<tr><td><strong class="admin-finance-code">${payment.id}</strong><span class="admin-table-time">${payment.reference || "Không có tham chiếu payOS"}</span></td>
      <td><strong>${invoice.id}</strong><span class="admin-table-time">${escape(invoice.customer)}</span></td>
      <td class="admin-finance-money admin-finance-total">${money(payment.amount)}</td>
      <td><span class="admin-finance-method">${window.spaIcon(payment.method === "spa" ? "note" : "calendar")}${methodLabel(payment.method)}</span></td>
      <td>${dateLabel(payment.createdAt)}<span class="admin-table-time">${timeLabel(payment.createdAt)}</span></td>
      <td>${paymentBadge(payment.status)}</td>
      <td><div class="admin-row-actions">${actionButton("payment", payment.id, "Xem")}</div></td></tr>`;
  };
  const renderStats = () => {
    const successful = payments.filter((p) => p.status === "success");
    const paid = invoices.filter((i) => i.status === "paid");
    const received = successful.reduce((sum, p) => sum + p.amount, 0);
    const stats = module === "invoices"
      ? [["Tổng đã thanh toán", money(received), `${paid.length} hóa đơn · dữ liệu mẫu`, "leaf"],
        ["Tổng hóa đơn", invoices.length, "Mỗi lịch hẹn tối đa một hóa đơn", "note"],
        ["Đã thanh toán", paid.length, "Khớp giao dịch thành công demo", "heart"],
        ["Chưa thanh toán", invoices.length - paid.length, "Gồm một lịch hẹn đã hủy", "clock"]]
      : [["Thanh toán thành công", money(received), `${successful.length} giao dịch · không có tiền thật`, "leaf"],
        ["Tổng giao dịch", payments.length, "Tham chiếu hóa đơn dịch vụ", "note"],
        ["Đang chờ", payments.filter((p) => p.status === "pending").length, "Chưa ghi nhận thanh toán", "clock"],
        ["Đã hủy", payments.filter((p) => p.status === "cancelled").length, "Yêu cầu gắn với lịch hẹn đã hủy", "calendar"]];
    $("#finance-stats").innerHTML = stats.map(([label, value, , icon], index) => `<article class="admin-finance-stat${index === 0 ? " is-featured" : ""}"><div class="admin-finance-stat-heading"><span>${label}</span>${window.spaIcon(icon)}</div><strong>${value}</strong></article>`).join("");
  };
  const render = () => {
    const query = normalize($("#finance-search").value);
    const date = $("#finance-date").value, status = $("#finance-status").value;
    const source = module === "invoices" ? invoices : payments;
    const rows = source.filter((record) => {
      const invoice = module === "invoices" ? record : invoiceFor(record);
      return (!status || record.status === status) && (!date || record.createdAt.slice(0, 10) === date) &&
        normalize(`${record.id} ${invoice.id} ${invoice.appointmentId} ${invoice.customer} ${invoice.service} ${record.reference || ""}`).includes(query);
    });
    page = Math.min(page, Math.max(1, Math.ceil(rows.length / pageSize)));
    const visible = rows.slice((page - 1) * pageSize, page * pageSize);
    $("#finance-rows").innerHTML = visible.map(module === "invoices" ? invoiceRow : paymentRow).join("");
    $("#finance-empty").hidden = Boolean(rows.length);
    const pages = Math.max(1, Math.ceil(rows.length / pageSize));
    const noun = module === "invoices" ? "hóa đơn" : "giao dịch";
    $("#finance-pagination").innerHTML = `<span>${visible.length} / ${rows.length} ${noun}${rows.length ? ` · ${(page - 1) * pageSize + 1}–${(page - 1) * pageSize + visible.length}` : ""}</span><div><button class="admin-button" type="button" data-finance-page="${page - 1}" ${page === 1 ? "disabled" : ""} aria-label="Trang trước">Trước</button><span>${page} / ${pages}</span><button class="admin-button" type="button" data-finance-page="${page + 1}" ${page >= pages ? "disabled" : ""} aria-label="Trang sau">Sau</button></div>`;
  };
  const facts = (entries) => `<dl class="admin-profile-facts admin-ops-facts">${entries.map(([label, value]) => `<div><dt>${escape(label)}</dt><dd>${escape(value)}</dd></div>`).join("")}</dl>`;
  const open = (title, body) => {
    if (!dialog.open) returnFocus = document.activeElement;
    dialog.innerHTML = `<header class="admin-service-modal-heading"><span class="admin-service-modal-icon">${window.spaIcon("note")}</span><div><span class="admin-eyebrow">AN NHIÊN SPA / FINANCE DEMO</span><h2 id="finance-dialog-title">${escape(title)}</h2></div><button class="admin-icon-button" type="button" data-finance-close aria-label="Đóng">${window.spaIcon("close")}</button></header><div class="admin-service-modal-scroll">${body}</div><div class="admin-dialog-actions"><span class="admin-finance-readonly">${window.spaIcon("eye")}Chỉ xem · Demo frontend</span><button class="admin-button" type="button" data-finance-close>Đóng</button></div>`;
    if (!dialog.open) dialog.showModal();
    else dialog.querySelector("[data-finance-close]").focus();
  };
  const invoiceDetail = (invoice) => {
    const related = paymentsFor(invoice);
    const appointmentLabels = { pending: "Chờ xác nhận", confirmed: "Đã xác nhận", completed: "Đã hoàn thành", cancelled: "Đã hủy" };
    open("Chi tiết hóa đơn", `<div class="admin-finance-detail-banner"><div><span class="admin-eyebrow">HÓA ĐƠN DỊCH VỤ / SNAPSHOT</span><h3>${invoice.id}</h3></div>${invoiceBadge(invoice.status)}</div>
      <section class="admin-ops-detail-section"><h4>${window.spaIcon("calendar")}Lịch hẹn liên quan</h4>${facts([["Mã lịch hẹn minh họa", invoice.appointmentId], ["Khách hàng", invoice.customer], ["Dịch vụ (snapshot)", invoice.service], ["Ngày giờ hẹn", `${dateLabel(invoice.date)} · ${invoice.time}`], ["Trạng thái lịch hẹn (snapshot)", appointmentLabels[invoice.appointmentStatus]], ["Ngày lập hóa đơn", `${dateLabel(invoice.createdAt)} · ${timeLabel(invoice.createdAt)}`]])}</section>
      <section class="admin-finance-breakdown"><h4>Chi tiết các khoản</h4><dl><div><dt>Giá dịch vụ khi lập</dt><dd>${money(invoice.priceSnapshot)}</dd></div><div><dt>Tạm tính</dt><dd>${money(invoice.subtotal)}</dd></div><div><dt>Khuyến mãi (snapshot)</dt><dd>${invoice.promotion || "Không áp dụng"}</dd></div><div><dt>Giảm giá đã ghi nhận</dt><dd>− ${money(invoice.discount)}</dd></div><div class="admin-finance-grand-total"><dt>Tổng thanh toán</dt><dd>${money(invoice.total)}</dd></div></dl><p>Giá và khoản giảm là dữ liệu lịch sử minh họa, không tính lại khi catalog hoặc chương trình khuyến mãi thay đổi.</p></section>
      <section class="admin-ops-detail-section"><h4>${window.spaIcon("note")}Giao dịch của hóa đơn</h4>${related.length ? related.map((p) => `<div class="admin-finance-related"><div><strong>${p.id}</strong><span>${money(p.amount)} · ${methodLabel(p.method)}</span></div>${paymentBadge(p.status)}${actionButton("payment", p.id, "Xem giao dịch")}</div>`).join("") : '<p>Chưa có giao dịch thanh toán cho hóa đơn này.</p>'}<div class="admin-finance-modal-links"><a class="admin-button admin-finance-link" href="admin-payments.html?invoice=${encodeURIComponent(invoice.id)}"><svg class="line-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 12h16m-5-5 5 5-5 5"/></svg>Đến quản lý thanh toán</a></div></section>
      <p class="admin-data-note">${invoice.appointmentStatus === "cancelled" ? "Lịch hẹn đã hủy: không còn yêu cầu thu trong demo; hóa đơn và tham chiếu cũ được giữ để tra cứu. Không xử lý hoàn tiền." : "Chỉ xem sổ demo; không sửa tiền, tạo hóa đơn hay xác nhận thanh toán thật."}</p>`);
  };
  const paymentDetail = (payment) => {
    const invoice = invoiceFor(payment);
    open("Chi tiết thanh toán", `<div class="admin-finance-detail-banner"><div><span class="admin-eyebrow">GIAO DỊCH / DỮ LIỆU MẪU</span><h3>${payment.id}</h3></div>${paymentBadge(payment.status)}</div>
      <div class="admin-finance-amount-panel"><span>Số tiền giao dịch demo</span><strong>${money(payment.amount)}</strong><small>Khớp tổng hóa đơn ${invoice.id}</small></div>
      <section class="admin-ops-detail-section"><h4>${window.spaIcon("note")}Thông tin giao dịch</h4>${facts([["Mã hóa đơn", invoice.id], ["Mã lịch hẹn", invoice.appointmentId], ["Khách hàng", invoice.customer], ["Dịch vụ (snapshot)", invoice.service], ["Phương thức", methodLabel(payment.method)], ["Thời gian (giờ Việt Nam)", `${dateLabel(payment.createdAt)} · ${timeLabel(payment.createdAt)}`], ["Tham chiếu payOS minh họa", payment.reference || "Không áp dụng — thanh toán tại Spa"], ["Trạng thái hóa đơn", invoice.status === "paid" ? "Đã thanh toán" : "Chưa thanh toán"]])}<div class="admin-finance-modal-links">${actionButton("invoice", invoice.id, "Xem hóa đơn")}<a class="admin-button admin-finance-link" href="admin-invoices.html?invoice=${encodeURIComponent(invoice.id)}"><svg class="line-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 12h16m-5-5 5 5-5 5"/></svg>Đến quản lý hóa đơn</a></div></section>
      <p class="admin-finance-modal-note">${payment.status === "success" ? "“Thành công” là trạng thái mẫu có sẵn, không phải xác nhận ngân hàng hoặc webhook. Không có chuyển tiền thật." : payment.status === "pending" ? "Giao dịch đang chờ trong dataset mẫu. Admin không có nút đổi trạng thái payOS sang thành công." : "Yêu cầu thanh toán mẫu gắn với lịch hẹn đã hủy. Không ghi nhận doanh thu từ giao dịch này và không xử lý hoàn tiền."}</p>`);
  };
  const view = (kind, id) => {
    const record = (kind === "invoice" ? invoices : payments).find((item) => item.id === id);
    if (record) (kind === "invoice" ? invoiceDetail : paymentDetail)(record);
  };
  dialog.addEventListener("click", (event) => {
    if (event.target.closest("[data-finance-close]")) dialog.close();
    const button = event.target.closest("[data-finance-view]");
    if (button) view(button.dataset.financeView, button.dataset.record);
  });
  dialog.addEventListener("close", () => {
    if (returnFocus?.isConnected) returnFocus.focus({ preventScroll: true });
    else $("#finance-search").focus({ preventScroll: true });
  });
  $("#finance-rows").addEventListener("click", (event) => {
    const button = event.target.closest("[data-finance-view]");
    if (button) view(button.dataset.financeView, button.dataset.record);
  });
  $("#finance-pagination").addEventListener("click", (event) => {
    const button = event.target.closest("[data-finance-page]");
    if (button && !button.disabled) { page = Number(button.dataset.financePage); render(); }
  });
  ["#finance-search", "#finance-date", "#finance-status"].forEach((selector) => $(selector).addEventListener(selector === "#finance-search" ? "input" : "change", () => { page = 1; render(); }));
  $("#finance-reset").addEventListener("click", () => {
    ["#finance-search", "#finance-date", "#finance-status"].forEach((selector) => { $(selector).value = ""; });
    page = 1; render(); $("#finance-search").focus();
  });
  const invoiceQuery = new URLSearchParams(location.search).get("invoice");
  if (invoiceQuery) $("#finance-search").value = invoiceQuery;
  renderStats(); render();
})();
