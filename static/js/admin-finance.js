(async () => {
  "use strict";
  const main = document.querySelector("[data-admin-finance]");
  if (!main || !window.spaAuth?.isAuthenticated()) return;
  try { if (window.spaAuth.getSession()?.role !== "Admin") return; } catch { return; }
  const module = main.dataset.adminFinance;
  const $ = (selector) => document.querySelector(selector);
  const escape = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const normalize = (value) => String(value ?? "").toLocaleLowerCase("vi").normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/g, "d").trim();
  const money = (value) => `${new Intl.NumberFormat("vi-VN").format(value)} VND`;
  const dateLabel = (value) => value.slice(0, 10).split("-").reverse().join(".");
  const timeLabel = (value) => new Date(value).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Ho_Chi_Minh" });
  const methodLabel = (method) => method === "spa" ? "Trực tiếp tại Spa" : "payOS";
  const badge = (label, style) => `<span class="admin-status-badge admin-status-${style}">${escape(label)}</span>`;
  const paymentLabels = { success: "Thành công", pending: "Đang chờ", cancelled: "Đã hủy", review: "Cần đối soát" };
  const paymentBadge = (status) => badge(paymentLabels[status], status === "success" ? "completed" : status === "pending" ? "pending" : "cancelled");
  const invoiceBadge = status => badge({paid:"Đã thanh toán",unpaid:"Chưa thanh toán",cancelled:"Đã hủy"}[status], status === "paid" ? "completed" : status === "cancelled" ? "cancelled" : "pending");

  let data;
  try { data=await window.spaLive.api('/api/billing/ledger/'); }
  catch(e) { document.querySelector('#finance-empty').hidden=false; document.querySelector('#finance-empty').textContent=e.message; return; }
  const invoices=data.invoices.map(i=>({...i,dbId:i.id,id:`HD-${i.id}`,appointmentId:`LH-${i.appointmentId}`,subtotal:Number(i.subtotal),priceSnapshot:Number(i.priceSnapshot),discount:Number(i.discount),total:Number(i.total)}));
  const payments=data.payments.map(p=>({...p,id:`GD-${p.id}`,invoiceId:`HD-${p.invoiceId}`,amount:Number(p.amount)}));
  const invoiceFor = (payment) => invoices.find((invoice) => invoice.id === payment.invoiceId);
  const paymentsFor = (invoice) => payments.filter((payment) => payment.invoiceId === invoice.id);
  const pageSize = 5;
  let page = 1, returnFocus;
  const dialog = $("#finance-dialog");
  const actionButton = (kind, id, label) => `<button class="admin-button" type="button" data-finance-view="${kind}" data-record="${escape(id)}">${window.spaIcon("eye")}${label}</button>`;
  const invoiceRow = (invoice) => `<tr>
    <td><strong class="admin-finance-code">${invoice.id}</strong><span class="admin-table-time">${invoice.appointmentId}</span></td>
    <td class="admin-finance-description"><strong>${escape(invoice.customer)}</strong><span class="admin-table-time">${escape(invoice.service)}</span></td>
    <td class="admin-finance-money">${money(invoice.subtotal)}</td>
    <td class="admin-finance-money">${money(invoice.discount)}<span class="admin-table-time">${escape(invoice.promotion || "Không áp dụng")}</span></td>
    <td class="admin-finance-money admin-finance-total">${money(invoice.total)}</td>
    <td>${dateLabel(invoice.createdAt)}<span class="admin-table-time">${timeLabel(invoice.createdAt)}</span></td>
    <td>${invoiceBadge(invoice.status)}${invoice.appointmentStatus === "cancelled" ? '<span class="admin-table-time">Lịch hẹn đã hủy</span>' : ""}</td>
    <td><div class="admin-row-actions">${actionButton("invoice", invoice.id, "Xem")}</div></td></tr>`;
  const paymentRow = (payment) => {
    const invoice = invoiceFor(payment);
    return `<tr><td><strong class="admin-finance-code">${payment.id}</strong><span class="admin-table-time">${escape(payment.reference || "Không có tham chiếu payOS")}</span></td>
      <td><strong>${invoice.id}</strong><span class="admin-table-time">${escape(invoice.customer)}</span></td>
      <td class="admin-finance-money admin-finance-total">${money(payment.amount)}</td>
      <td><span class="admin-finance-method">${window.spaIcon(payment.method === "spa" ? "note" : "calendar")}${methodLabel(payment.method)}</span></td>
      <td>${dateLabel(payment.createdAt)}<span class="admin-table-time">${timeLabel(payment.createdAt)}</span></td>
      <td>${paymentBadge(payment.status)}${payment.requiresReview ? '<span class="admin-table-time">Cần đối soát</span>' : ""}</td>
      <td><div class="admin-row-actions">${actionButton("payment", payment.id, "Xem")}</div></td></tr>`;
  };
  const renderStats = () => {
    const successful = payments.filter((p) => p.status === "success" && !p.requiresReview);
    const paid = invoices.filter((i) => i.status === "paid");
    const received = successful.reduce((sum, p) => sum + p.amount, 0);
    const stats = module === "invoices"
      ? [["Tổng đã thanh toán", money(received), `${paid.length} hóa đơn · dữ liệu mẫu`, "leaf"],
        ["Tổng hóa đơn", invoices.length, "Mỗi lịch hẹn tối đa một hóa đơn", "note"],
        ["Đã thanh toán", paid.length, "Khớp giao dịch thành công demo", "heart"],
        ["Chưa thanh toán", invoices.filter(i=>i.status==="unpaid").length, "Gồm một lịch hẹn đã hủy", "clock"]]
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
    dialog.innerHTML = `<header class="admin-service-modal-heading"><span class="admin-service-modal-icon">${window.spaIcon("note")}</span><div><span class="admin-eyebrow">AN NHIÊN SPA / TÀI CHÍNH</span><h2 id="finance-dialog-title">${escape(title)}</h2></div><button class="admin-icon-button" type="button" data-finance-close aria-label="Đóng">${window.spaIcon("close")}</button></header><div class="admin-service-modal-scroll">${body}</div><div class="admin-dialog-actions"><span class="admin-finance-readonly">${window.spaIcon("eye")}Dữ liệu được lưu tại Spa</span><button class="admin-button" type="button" data-finance-close>Đóng</button></div>`;
    if (!dialog.open) dialog.showModal();
    else dialog.querySelector("[data-finance-close]").focus();
  };
  const invoiceDetail = (invoice) => {
    const related = paymentsFor(invoice);
    const appointmentLabels = { pending: "Chờ xác nhận", confirmed: "Đã xác nhận", completed: "Đã hoàn thành", cancelled: "Đã hủy", review: "Cần đối soát" };
    open("Chi tiết hóa đơn", `<div class="admin-finance-detail-banner"><div><span class="admin-eyebrow">HÓA ĐƠN DỊCH VỤ / SNAPSHOT</span><h3>${invoice.id}</h3></div>${invoiceBadge(invoice.status)}</div>
      <section class="admin-ops-detail-section"><h4>${window.spaIcon("calendar")}Lịch hẹn liên quan</h4>${facts([["Mã lịch hẹn", invoice.appointmentId], ["Khách hàng", invoice.customer], ["Dịch vụ (snapshot)", invoice.service], ["Ngày giờ hẹn", `${dateLabel(invoice.date)} · ${invoice.time}`], ["Trạng thái lịch hẹn (snapshot)", appointmentLabels[invoice.appointmentStatus]], ["Ngày lập hóa đơn", `${dateLabel(invoice.createdAt)} · ${timeLabel(invoice.createdAt)}`]])}</section>
      <section class="admin-finance-breakdown"><h4>Chi tiết các khoản</h4><dl><div><dt>Giá dịch vụ khi lập</dt><dd>${money(invoice.priceSnapshot)}</dd></div><div><dt>Tạm tính</dt><dd>${money(invoice.subtotal)}</dd></div><div><dt>Khuyến mãi (snapshot)</dt><dd>${escape(invoice.promotion || "Không áp dụng")}</dd></div><div><dt>Giảm giá đã ghi nhận</dt><dd>− ${money(invoice.discount)}</dd></div><div class="admin-finance-grand-total"><dt>Tổng thanh toán</dt><dd>${money(invoice.total)}</dd></div></dl><p>Giá và khoản giảm là dữ liệu lịch sử, không tính lại khi catalog hoặc chương trình khuyến mãi thay đổi.</p></section>
      <section class="admin-ops-detail-section"><h4>${window.spaIcon("note")}Giao dịch của hóa đơn</h4>${related.length ? related.map((p) => `<div class="admin-finance-related"><div><strong>${p.id}</strong><span>${money(p.amount)} · ${methodLabel(p.method)}</span></div>${paymentBadge(p.status)}${actionButton("payment", p.id, "Xem giao dịch")}</div>`).join("") : '<p>Chưa có giao dịch thanh toán cho hóa đơn này.</p>'}<div class="admin-finance-modal-links"><a class="admin-button admin-finance-link" href="admin-payments.html?invoice=${encodeURIComponent(invoice.id)}"><svg class="line-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 12h16m-5-5 5 5-5 5"/></svg>Đến quản lý thanh toán</a></div></section>
      ${invoice.status === 'unpaid' && invoice.appointmentStatus !== 'cancelled' ? `<form data-cash-form="${invoice.dbId}" class="admin-toolbar"><label>Số tiền đã nhận<input name="amount" type="number" min="0" step="0.01" required value="${invoice.total}"></label><label><input type="checkbox" required> Tôi xác nhận đã nhận tiền trực tiếp</label><button class="admin-button admin-button-primary" type="submit">Ghi nhận thanh toán</button><p role="status" data-cash-status></p></form>` : ''}
      <p class="admin-data-note">Hóa đơn lưu giá tại thời điểm lập. Giao dịch online chỉ được xác nhận qua webhook hợp lệ.</p>`);
  };
  const paymentDetail = (payment) => {
    const invoice = invoiceFor(payment);
    open("Chi tiết thanh toán", `<div class="admin-finance-detail-banner"><div><span class="admin-eyebrow">GIAO DỊCH / THANH TOÁN</span><h3>${payment.id}</h3></div>${paymentBadge(payment.status)}</div>
      <div class="admin-finance-amount-panel"><span>Số tiền giao dịch</span><strong>${money(payment.amount)}</strong><small>Khớp tổng hóa đơn ${invoice.id}</small></div>
      <section class="admin-ops-detail-section"><h4>${window.spaIcon("note")}Thông tin giao dịch</h4>${facts([["Mã hóa đơn", invoice.id], ["Mã lịch hẹn", invoice.appointmentId], ["Khách hàng", invoice.customer], ["Dịch vụ (snapshot)", invoice.service], ["Phương thức", methodLabel(payment.method)], ["Thời gian (giờ Việt Nam)", `${dateLabel(payment.createdAt)} · ${timeLabel(payment.createdAt)}`], ["Tham chiếu giao dịch", payment.reference || "Không áp dụng — thanh toán tại Spa"], ["Thời điểm thanh toán", payment.paidAt ? window.spaLive.date(payment.paidAt) : "Chưa thanh toán"], ["Người ghi nhận (ID)", payment.recordedBy || "Webhook payOS"], ["Trạng thái nhà cung cấp", payment.providerStatus || "Không áp dụng"], ["Trạng thái hóa đơn", invoice.status === "paid" ? "Đã thanh toán" : "Chưa thanh toán"]])}<div class="admin-finance-modal-links">${actionButton("invoice", invoice.id, "Xem hóa đơn")}<a class="admin-button admin-finance-link" href="admin-invoices.html?invoice=${encodeURIComponent(invoice.id)}"><svg class="line-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 12h16m-5-5 5 5-5 5"/></svg>Đến quản lý hóa đơn</a></div></section>
      <p class="admin-finance-modal-note">${payment.requiresReview ? 'Cần đối soát thủ công: khoản này chưa được tính vào doanh thu.' : 'Thanh toán online được xác nhận qua webhook. Không sửa trạng thái thủ công.'}</p>`);
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
  dialog.addEventListener('submit',async e=>{
    const form=e.target.closest('[data-cash-form]'); if(!form)return;
    e.preventDefault(); const button=form.querySelector('button');button.disabled=true;
    try { await window.spaLive.api(`/api/billing/${form.dataset.cashForm}/cash/`,Object.fromEntries(new FormData(form)));location.reload(); }
    catch(error) {form.querySelector('[data-cash-status]').textContent=error.message;button.disabled=false;}
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
