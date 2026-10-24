(async () => {
  "use strict";
  if (window.spaAuth?.allowed !== true || !document.body.classList.contains("admin-page")) return;
  // Reuse auth validation without changing the User page guard.
  if (!window.spaAuth.isAuthenticated()) { location.replace("login.html"); return; }
  if (window.spaAuth.getSession()?.role !== "Admin") { location.replace("home.html"); return; }
  const currentPage = location.pathname.split("/").pop();
  const coreLinks = {
    "Tài khoản": "admin-accounts.html", "Khách hàng": "admin-customers.html", "Dịch vụ": "admin-services.html",
    "Sản phẩm": "admin-products.html", "Nhân viên": "admin-employees.html",
    "Lịch hẹn": "admin-appointments.html", "Khuyến mãi": "admin-promotions.html",
    "Hóa đơn": "admin-invoices.html", "Thanh toán": "admin-payments.html",
    "Đánh giá": "admin-reviews.html", "Báo cáo": "admin-reports.html",
  };
  document.querySelectorAll("[data-admin-pending]").forEach((node) => {
    const href = coreLinks[node.dataset.adminPending];
    if (!href) return;
    const link = document.createElement("a");
    link.className = node.className;
    link.href = href;
    link.title = node.dataset.adminPending;
    link.innerHTML = node.innerHTML;
    node.replaceWith(link);
  });
  document.querySelectorAll(".admin-nav a").forEach((link) => {
    const active = link.getAttribute("href") === currentPage;
    link.classList.toggle("is-active", active);
    if (active) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });

  // Admin-only UI fixtures. Nothing is written to User records or sent to a server.
  const catalog = window.spaCatalog;
  const escape = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);
  const numbers = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 });
  const currency = (value) => `${numbers.format(value)} VND`;
  const paths = {
    grid: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    account: '<rect x="3" y="4" width="18" height="16" rx="3"/><circle cx="9" cy="10" r="2"/><path d="M6 16c0-3 6-3 6 0m3-7h3m-3 4h3"/>',
    users: '<circle cx="9" cy="8" r="3"/><path d="M3 21v-2a6 6 0 0 1 12 0v2m1-16a3 3 0 0 1 0 6m2 4a5 5 0 0 1 3 4v2"/>',
    product: '<path d="M8 3h8v4H8zM7 7h10a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2Z"/><path d="M9 12h6m-6 4h4"/>',
    staff: '<circle cx="10" cy="7" r="3"/><path d="M3 21v-2a7 7 0 0 1 11-5"/><rect x="15" y="13" width="6" height="8" rx="1.5"/><path d="M18 15v4m-2-2h4"/>',
    tag: '<path d="m3 4 9-1 9 9-9 9-9-9V4Z"/><circle cx="7.5" cy="7.5" r="1"/><path d="m11 9 5 5m0-5-5 5"/>',
    wallet: '<path d="M20 8V5a2 2 0 0 0-2-2H6a3 3 0 0 0 0 6h14v12H5a2 2 0 0 1-2-2V6"/><path d="M20 12h-5v5h5m-2-2.5h.01"/>',
    bars: '<path d="M4 3v18h17M8 17v-5m5 5V8m5 9V4"/>',
    panel: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16m7-11-3 3 3 3"/>',
    menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
    chevron: '<path d="m7 10 5 5 5-5"/>',
    logout: '<path d="M9 4H4v16h5M9 12h12m-4-4 4 4-4 4"/>',
    arrow: '<path d="M4 12h16m-5-5 5 5-5 5"/>',
  };
  const icon = (name) => paths[name]
    ? `<svg class="admin-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${paths[name]}</svg>`
    : window.spaIcon(name).replace('class="line-icon"', 'class="admin-icon"');
  document.querySelectorAll("[data-admin-icon]").forEach((node) => { node.innerHTML = icon(node.dataset.adminIcon); });

  const sidebar = document.querySelector(".admin-sidebar");
  const workspace = document.querySelector(".admin-workspace");
  const backdrop = document.querySelector(".admin-backdrop");
  const mobile = matchMedia("(max-width: 900px)");
  let collapsed = false, drawerOpen = false, drawerTrigger;
  const updateSidebar = () => {
    document.body.classList.toggle("admin-collapsed", collapsed && !mobile.matches);
    document.body.classList.toggle("admin-drawer-open", drawerOpen && mobile.matches);
    backdrop.hidden = !drawerOpen || !mobile.matches;
    sidebar.inert = mobile.matches && !drawerOpen;
    workspace.inert = mobile.matches && drawerOpen;
    if (mobile.matches) sidebar.setAttribute("aria-hidden", String(!drawerOpen));
    else sidebar.removeAttribute("aria-hidden");
    document.querySelectorAll("[data-sidebar-toggle]").forEach((button) => {
      button.setAttribute("aria-expanded", String(mobile.matches ? drawerOpen : !collapsed));
      button.setAttribute("aria-label", mobile.matches ? "Mở menu quản trị" : collapsed ? "Mở rộng thanh bên" : "Thu gọn thanh bên");
    });
  };
  const closeDrawer = () => {
    drawerOpen = false;
    updateSidebar();
    if (mobile.matches && drawerTrigger?.isConnected) drawerTrigger.focus({ preventScroll: true });
  };
  document.querySelectorAll("[data-sidebar-toggle]").forEach((button) => button.addEventListener("click", () => {
    if (mobile.matches) {
      drawerTrigger = button;
      drawerOpen = !drawerOpen;
    } else collapsed = !collapsed;
    updateSidebar();
    if (mobile.matches && drawerOpen) sidebar.querySelector(".admin-drawer-close").focus();
  }));
  document.querySelectorAll("[data-sidebar-close]").forEach((button) => button.addEventListener("click", closeDrawer));
  mobile.addEventListener("change", () => { drawerOpen = false; updateSidebar(); });
  sidebar.addEventListener("keydown", (event) => {
    if (!mobile.matches || !drawerOpen || event.key !== "Tab") return;
    const nodes = [...sidebar.querySelectorAll("a, button")].filter((node) => node.getClientRects().length);
    const first = nodes[0], last = nodes.at(-1);
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });
  updateSidebar();

  const account = document.querySelector(".admin-account");
  const accountTrigger = account.querySelector("button");
  const accountMenu = document.querySelector("#admin-account-menu");
  const closeAccount = () => { accountMenu.hidden = true; accountTrigger.setAttribute("aria-expanded", "false"); };
  accountTrigger.addEventListener("click", () => {
    accountMenu.hidden = !accountMenu.hidden;
    accountTrigger.setAttribute("aria-expanded", String(!accountMenu.hidden));
  });
  document.addEventListener("click", (event) => { if (!account.contains(event.target)) closeAccount(); });
  account.addEventListener("focusout", (event) => { if (!account.contains(event.relatedTarget)) closeAccount(); });
  document.querySelector("[data-admin-logout]").addEventListener("click", () => {
    closeAccount();
    accountTrigger.focus();
    window.spaAuth.logout();
  });
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".logout-dialog [data-logout-confirm]")) return;
    try {
      sessionStorage.removeItem("spa-admin-account-status");
      sessionStorage.removeItem("spa-admin-services");
      sessionStorage.removeItem("spa-admin-operations");
    } catch { /* Existing logout handles unavailable storage. */ }
  }, true);
  let toastTimer;
  const toast = document.querySelector(".toast");
  document.querySelectorAll("[data-admin-pending]").forEach((button) => button.addEventListener("click", () => {
    toast.textContent = `${button.dataset.adminPending}: Chưa triển khai trong phiên bản demo này.`;
    toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toast.hidden = true; }, 4500);
  }));
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    if (!accountMenu.hidden) { closeAccount(); accountTrigger.focus(); }
    if (drawerOpen) closeDrawer();
  });
  // The layout above can be reused without initializing Dashboard-only data widgets.
  if (!document.querySelector("[data-admin-dashboard]")) return;

  let dashboard;
  const currentYear=Number(new Date().toLocaleDateString('sv-SE',{timeZone:'Asia/Ho_Chi_Minh'}).slice(0,4));
  const yearSelect=document.querySelector('#admin-revenue-year');
  yearSelect.innerHTML=Array.from({length:6},(_,i)=>`<option value="${currentYear-i}">${currentYear-i}</option>`).join('');
  try {dashboard=await window.spaLive.api(`/api/dashboard/?start=${currentYear}-01-01&end=${currentYear}-12-31`);}
  catch(error){document.querySelector('[data-recent-caption]').textContent=error.message;return;}
  const statuses=Object.entries({pending:'Chờ xác nhận',confirmed:'Đã xác nhận',completed:'Đã hoàn thành',cancelled:'Đã hủy'}).map(([key,label])=>({key,label,count:dashboard.statuses.find(s=>s.status===key)?.count||0}));
  let invoices=dashboard.monthly.map(x=>({year:Number(x.month.slice(0,4)),month:Number(x.month.slice(5,7)),total:Number(x.total),status:'paid'}));
  document.querySelector('[data-stat-customers]').textContent=numbers.format(dashboard.customers);
  document.querySelector('[data-stat-today]').textContent=numbers.format(dashboard.todayCount);
  document.querySelector('[data-stat-revenue]').textContent=currency(dashboard.monthly.filter(x=>x.month===dashboard.today.slice(0,7)).reduce((sum,x)=>sum+Number(x.total),0));
  document.querySelector('[data-stat-services]').textContent=numbers.format(dashboard.activeServices);
  const renderRevenue = async () => {
    const year = Number(document.querySelector("#admin-revenue-year").value);
    try { const d=await window.spaLive.api(`/api/dashboard/?start=${year}-01-01&end=${year}-12-31`);invoices=d.monthly.map(x=>({year,month:Number(x.month.slice(5,7)),total:Number(x.total),status:'paid'})); }
    catch(error){document.querySelector('[data-revenue-caption]').textContent=error.message;return;}
    const values = Array.from({ length: 12 }, (_, month) =>
      invoices.filter((item) => item.year === year && item.month === month + 1 && item.status === "paid").reduce((sum, item) => sum + item.total, 0));
    const rawMaximum=Math.max(1,...values);
    const unit=10 ** Math.floor(Math.log10(rawMaximum));
    const step=Math.max(1,Math.ceil(rawMaximum/4/unit)*unit);
    const maximum=step*4;
    const left = 91, top = 21, width = 310, height = 188;
    const x = (index) => left + index * width / 11;
    const y = (value) => top + height - value / maximum * height;
    const points = values.map((value, index) => value === null ? null : { x: x(index), y: y(value), value, month: index + 1 }).filter(Boolean);
    const path = points.map((point, index) => `${index ? "L" : "M"}${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" ");
    const ticks = Array.from({ length: 5 }, (_, index) => index * step);
    document.querySelector("#admin-revenue-chart").innerHTML = `<svg viewBox="0 0 420 246" role="img" aria-label="Doanh thu các tháng năm ${year}, chỉ tính hóa đơn đã thanh toán">
      ${ticks.map((value) => `<line class="admin-chart-grid-line" x1="${left}" x2="${left + width}" y1="${y(value)}" y2="${y(value)}"/><text class="admin-chart-axis" x="${left - 10}" y="${y(value) + 3}" text-anchor="end">${currency(value)}</text>`).join("")}
      ${points.length ? `<path class="admin-chart-area" d="${path} L${points.at(-1).x},${top + height} L${points[0].x},${top + height} Z"/><path class="admin-chart-line" d="${path}"/>` : ""}
      ${points.map((point) => `<circle class="admin-chart-point" cx="${point.x}" cy="${point.y}" r="3.8"/><circle class="admin-chart-hit" cx="${point.x}" cy="${point.y}" r="10" tabindex="0" role="img" aria-label="Tháng ${point.month}: ${currency(point.value)}" data-chart-tip="Tháng ${point.month}/${year}&#10;${currency(point.value)}"/>`).join("")}
      ${values.map((_, index) => `<text class="admin-chart-axis" x="${x(index)}" y="${top + height + 25}" text-anchor="middle">T${index + 1}</text>`).join("")}</svg>`;
    document.querySelector("[data-revenue-caption]").textContent = `Hóa đơn đã thanh toán · năm ${year}`;
    document.querySelector("[data-revenue-period]").textContent = `Cả năm ${year}`;
  };
  document.querySelector("#admin-revenue-year").addEventListener("change", renderRevenue);
  renderRevenue();

  const totalAppointments = statuses.reduce((sum, item) => sum + item.count, 0);
  const circumference = 2 * Math.PI * 64;
  let offset = 0;
  document.querySelector("#admin-status-chart").innerHTML = `<svg viewBox="0 0 180 180" role="img" aria-label="${totalAppointments} lịch hẹn trong năm đã chọn theo bốn trạng thái">
    <circle cx="90" cy="90" r="64" fill="none" stroke="#c6a07e15" stroke-width="17"/>
    ${statuses.map((item) => {
      const segment = item.count / (totalAppointments || 1) * circumference;
      const circle = `<circle class="admin-status-${item.key}" cx="90" cy="90" r="64" fill="none" stroke="var(--status-color)" stroke-width="17" stroke-dasharray="${Math.max(0,segment - 3)} ${circumference - segment + 3}" stroke-dashoffset="${-offset}" transform="rotate(-90 90 90)"/>`;
      offset += segment;
      return circle;
    }).join("")}<text class="admin-donut-total" x="90" y="88" text-anchor="middle">${totalAppointments}</text><text class="admin-donut-label" x="90" y="107" text-anchor="middle">lịch hẹn</text></svg>`;
  document.querySelector("#admin-status-legend").innerHTML = statuses.map((item) => {
    const percent = (item.count / (totalAppointments || 1) * 100).toLocaleString("vi-VN", { maximumFractionDigits: 1 });
    return `<li class="admin-status-${item.key}" tabindex="0" data-chart-tip="${item.label}&#10;${item.count} lịch hẹn · ${percent}%"><span class="admin-legend-dot"></span><span>${item.label}</span><strong>${item.count}</strong><small>${percent}%</small></li>`;
  }).join("");
  const topServices=dashboard.popular.slice(0,5).map(x=>({service:{name:x.service__name},count:x.count}));
  document.querySelector("#admin-services-chart").innerHTML = topServices.map(({ service, count }) =>
    `<li tabindex="0" data-chart-tip="${escape(service.name)}&#10;${count} lượt đặt"><div class="admin-bar-label"><span>${escape(service.name)}</span><strong>${count}</strong></div><div class="admin-bar-track"><span class="admin-bar-fill" data-bar-count="${count}"></span></div></li>`).join("");
  document.querySelectorAll("[data-bar-count]").forEach((node) => { node.style.width = `${Number(node.dataset.barCount) / Math.max(1,...topServices.map(x=>x.count)) * 100}%`; });

  const recent=dashboard.recent;
  const code = (id) => /^demo-review-completed-\d+$/.test(id) ? `LH-DEMO${id.split("-").at(-1)}` : `LH-${String(id).replace(/[^a-z0-9]/gi, "").slice(0, 8).toUpperCase()}`;
  document.querySelector("#admin-recent-appointments").innerHTML = recent.map((item) => {
    const customer = item.customer || item.customerName || (item.owner === "user" ? "Lan Anh" : "Khách phiên mẫu");
    const initials = String(customer).trim().split(/\s+/).slice(-2).map((part) => part[0]).join("").toUpperCase();
    const status = statuses.find((entry) => entry.key === (item.status || "pending"));
    const service = item.service || catalog.services.find((entry) => entry.id === item.serviceId)?.name || "Dịch vụ chưa cập nhật";
    const employee = item.employee || catalog.staff.find((entry) => entry.id === item.employeeId)?.name || "Chờ phân công";
    return `<tr><td><span class="admin-appointment-code" title="${escape(item.id)}">${escape(code(item.id))}</span></td>
      <td><span class="admin-customer"><span class="admin-customer-initials" aria-hidden="true">${escape(initials)}</span>${escape(customer)}</span></td>
      <td>${escape(service)}</td><td>${escape(employee)}</td><td>${escape(item.time || "Chưa có giờ")}<span class="admin-table-time">${escape(String(item.date || "").split("-").reverse().join("."))}</span></td>
      <td><span class="admin-status-badge admin-status-${status?.key || "pending"}">${escape(status?.label || "Chờ kiểm tra")}</span></td></tr>`;
  }).join("");
  document.querySelector(".admin-table-scroll").hidden = !recent.length;
  document.querySelector("#admin-appointments-empty").hidden = Boolean(recent.length);
  document.querySelector("[data-recent-caption]").textContent = `${recent.length} lịch hẹn gần nhất trong năm ${currentYear}`;

  const tooltip = document.querySelector("#admin-chart-tooltip");
  let tooltipTarget;
  const hideTooltip = () => {
    tooltip.hidden = true;
    tooltipTarget?.removeAttribute("aria-describedby");
    tooltipTarget = null;
  };
  const showTooltip = (target, event) => {
    tooltipTarget?.removeAttribute("aria-describedby");
    tooltipTarget = target;
    tooltip.textContent = target.dataset.chartTip;
    tooltip.hidden = false;
    target.setAttribute("aria-describedby", tooltip.id);
    const rect = target.getBoundingClientRect(), tip = tooltip.getBoundingClientRect();
    const x = Number.isFinite(event.clientX) ? event.clientX : rect.left + rect.width / 2;
    const y = Number.isFinite(event.clientY) ? event.clientY : rect.top;
    tooltip.style.left = `${Math.max(8, Math.min(innerWidth - tip.width - 8, x - tip.width / 2))}px`;
    const top = y - tip.height - 12 >= 8 ? y - tip.height - 12 : y + 16;
    tooltip.style.top = `${Math.max(8, Math.min(innerHeight - tip.height - 8, top))}px`;
  };
  document.querySelectorAll(".admin-chart-card").forEach((card) => {
    card.addEventListener("pointermove", (event) => {
      const target = event.target.closest("[data-chart-tip]");
      if (target) showTooltip(target, event);
      else hideTooltip();
    });
    card.addEventListener("pointerleave", hideTooltip);
    card.addEventListener("focus", (event) => { if (event.target.matches("[data-chart-tip]")) showTooltip(event.target, event); }, true);
    card.addEventListener("blur", hideTooltip, true);
  });
  document.querySelector("#admin-revenue-year").addEventListener("change", hideTooltip);
  window.addEventListener("scroll", hideTooltip, { passive: true });
  window.addEventListener("resize", hideTooltip);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") hideTooltip();
  });
})();
