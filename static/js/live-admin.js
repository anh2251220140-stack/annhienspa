(() => {
  "use strict";
  const root = document.querySelector("[data-admin-services], [data-admin-operations]");
  if (!root) return;
  const servicePage = root.hasAttribute("data-admin-services");
  const module = servicePage ? "services" : root.dataset.adminOperations;
  const $ = (s) => document.querySelector(s);
  const escape = (s) => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const token = () => document.querySelector('[name="csrfmiddlewaretoken"]').value;
  const money = v => Number(v).toLocaleString("vi-VN") + " VND";
  const url = (m, id) => `/api/admin/${m}/${id === undefined ? "" : id + "/"}`;
  const dialog = $(servicePage ? "#service-dialog" : "#ops-dialog");
  let returnFocus;
  const notify = message => { const el = $(servicePage ? "#services-notice" : "#ops-notice"); el.textContent = message; el.hidden = false; };
  async function api(path, data) {
    const response = await fetch(path, data ? {method:"POST", body:data, headers:{"X-CSRFToken":token()}} : {});
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw Error(payload.error || Object.values(payload.errors || {}).flat().join(" ") || "Không thể thực hiện thao tác. Vui lòng tải lại và kiểm tra đăng nhập.");
    return payload;
  }
  function open(title, body) {
    if (!dialog.open) returnFocus = document.activeElement;
    dialog.innerHTML = `<header class="admin-service-modal-heading"><div><span class="admin-eyebrow">AN NHIÊN SPA</span><h2 id="${servicePage ? "service" : "ops"}-dialog-title">${escape(title)}</h2></div><button class="admin-icon-button" data-close aria-label="Đóng">×</button></header>${body}`;
    dialog.querySelectorAll("[data-close]").forEach(b => b.addEventListener("click", () => dialog.close()));
    if (!dialog.open) dialog.showModal();
  }
  dialog.addEventListener("close", () => returnFocus?.isConnected && returnFocus.focus());
  function bindForm(path, after) {
    const form = dialog.querySelector("form");
    form.addEventListener("submit", async event => {
      event.preventDefault(); const submit = form.querySelector('[type="submit"]'); submit.disabled = true;
      try { await api(path, new FormData(form)); dialog.close(); await after(); notify("Đã lưu thay đổi."); }
      catch (error) { const el = form.querySelector("[data-error]"); el.textContent = error.message; el.hidden = false; }
      finally { submit.disabled = false; }
    });
  }
  let cache = {}, pages = {};
  const badge = active => `<span class="admin-status-badge admin-status-${active ? "completed" : "cancelled"}">${active ? "Hoạt động" : "Tạm ngừng"}</span>`;
  const promoStatus = r => {
    const today = window.spaPromotions.referenceDate;
    if (!r.active) return "inactive";
    if (r.start_date > today) return "future";
    if (r.end_date < today) return "expired";
    return (Date.parse(r.end_date)-Date.parse(today))/86400000 <= 7 ? "ending" : "active";
  };
  function render(type) {
    const prefix = servicePage ? type : "ops";
    const query = $(`#${prefix}-search`)?.value.toLocaleLowerCase("vi") || "";
    const status = $(`#${prefix}-status`)?.value || "";
    const category = $(servicePage ? "#services-category" : "#ops-category")?.value || "";
    const items = (cache[type] || []).filter(r => `${r.name} ${r.id} ${r.code || ""}`.toLocaleLowerCase("vi").includes(query) &&
      (!status || (type === "promotions" ? promoStatus(r) === status : r.active === (status === "active"))) &&
      (type !== "services" && type !== "products" || !category || String(type === "services" ? r.category_id : r.product_type) === category));
    pages[type] = Math.max(1, Math.min(pages[type] || 1, Math.ceil(items.length/8)));
    $(`#${prefix}-rows`).innerHTML = items.slice((pages[type]-1)*8,pages[type]*8).map(r => {
      const action = `<div class="admin-row-actions"><button class="admin-button" data-edit="${r.id}" data-type="${type}">Sửa</button><button class="admin-button" data-toggle="${r.id}" data-type="${type}">${r.active ? "Tắt" : "Bật"}</button>${type === "employees" ? `<button class="admin-button" data-schedule="${r.id}">Lịch làm việc</button>` : ""}</div>`;
      let cells = [r.id, r.name];
      if (type === "categories") cells.push(r.description);
      if (type === "services") cells.push(r.category, money(r.price), `${r.duration_minutes} phút`);
      if (type === "products") cells.push(r.product_type);
      if (type === "employees") cells.push(r.phone || "—", r.specialty);
      if (type === "promotions") { cells = [r.code, r.name]; cells.push(r.discount_type === "percent" ? `${r.discount_value}%` : money(r.discount_value), `${r.start_date} — ${r.end_date}`); }
      return `<tr>${cells.map(c => `<td>${escape(c)}</td>`).join("")}<td>${type === "promotions" ? escape(({active:"Đang hiệu lực", ending:"Sắp hết hạn", future:"Chưa bắt đầu", expired:"Hết hạn", inactive:"Tạm ngưng"})[promoStatus(r)]) : badge(r.active)}</td><td>${action}</td></tr>`;
    }).join("");
    $(`#${prefix}-empty`).hidden = items.length > 0;
    const pager = $(`#${prefix}-pagination`);
    pager.innerHTML = `<button class="admin-button" data-page="-1" ${pages[type]===1 ? "disabled" : ""}>Trước</button><span>Trang ${pages[type]} · ${items.length} bản ghi</span><button class="admin-button" data-page="1" ${pages[type]*8 >= items.length ? "disabled" : ""}>Sau</button>`;
    pager.querySelectorAll("[data-page]").forEach(b => b.onclick=()=>{pages[type]+=Number(b.dataset.page);render(type);});
  }
  async function refresh() {
    const types = servicePage ? ["categories","services"] : [module];
    for (const type of types) cache[type] = (await api(url(type))).items;
    const select = $(servicePage ? "#services-category" : "#ops-category");
    if (select) { const value=select.value; const options=servicePage ? cache.categories.map(c=>[c.id,c.name]) : [...new Set(cache[module].map(r=>r.product_type))].map(v=>[v,v]); select.replaceChildren(new Option("Tất cả danh mục",""), ...options.map(([v,l])=>new Option(l,v))); select.value=value; }
    types.forEach(render);
    const all=types.flatMap(t=>cache[t]);
    $(servicePage ? "#services-stats" : "#ops-stats").innerHTML = [["Tổng bản ghi",all.length],["Hoạt động",all.filter(x=>x.active).length],["Tạm ngừng",all.filter(x=>!x.active).length]].map(([label,n])=>`<article><span>${label}</span><strong>${n}</strong></article>`).join("");
  }
  async function edit(type,id=0) { const data=await api(url(type,id)); open(id ? "Cập nhật thông tin" : "Thêm mới",data.html); bindForm(url(type,id),refresh); }
  async function schedule(employee) {
    const path=`/api/admin/employees/${employee}/schedules/`;
    const data=await api(path);
    open("Lịch làm việc",`<div class="admin-service-modal-scroll"><button class="admin-button admin-button-primary" data-new-shift>Thêm ca làm / ca nghỉ</button><div class="admin-table-scroll"><table class="admin-data-table"><thead><tr><th>Ngày</th><th>Giờ</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody>${data.items.map(s=>`<tr><td>${escape(s.date)}</td><td>${escape(s.start)}–${escape(s.end)}</td><td>${escape(s.status)}</td><td><button class="admin-button" data-shift="${s.id}">Sửa</button></td></tr>`).join("")}</tbody></table></div></div>`);
    const editShift=async id=>{const form=await api(path+id+"/");open("Ca làm việc",form.html);bindForm(path+id+"/",()=>schedule(employee));};
    dialog.querySelector("[data-new-shift]").onclick=()=>editShift(0).catch(e=>notify(e.message));
    dialog.querySelectorAll("[data-shift]").forEach(b=>b.onclick=()=>editShift(b.dataset.shift).catch(e=>notify(e.message)));
  }
  if (module === "appointments") {
    const toolbar=$(".admin-toolbar"); const label=document.createElement("label");label.textContent="Nhân viên";
    const employees=document.createElement("select");employees.id="ops-employee";label.append(employees);toolbar.append(label);
    let items=[];
    async function load() {
      const params=new URLSearchParams({date:$("#ops-date").value,status:$("#ops-status").value,employee:employees.value});
      items=(await api("/api/appointments/?"+params)).items;
      const q=$("#ops-search").value.toLocaleLowerCase("vi");
      const rows=items.filter(r=>`${r.id} ${r.customer} ${r.service}`.toLocaleLowerCase("vi").includes(q));
      $("#ops-rows").innerHTML=rows.map(r=>`<tr>${["LH-"+r.id,r.customer,r.service,`${r.date} ${r.time}–${r.end}`,r.employee,r.statusLabel].map(x=>`<td>${escape(x)}</td>`).join("")}<td><button class="admin-button" data-appointment="${r.id}">Xem chi tiết</button></td></tr>`).join("");
      $("#ops-empty").hidden=rows.length>0;$("#ops-pagination").textContent=`${rows.length} lịch hẹn`;
      $("#ops-stats").innerHTML=[["Tổng lịch hẹn",items.length],["Chờ xác nhận",items.filter(x=>x.status==="pending").length],["Đã xác nhận",items.filter(x=>x.status==="confirmed").length]].map(([l,n])=>`<article><span>${l}</span><strong>${n}</strong></article>`).join("");
    }
    root.addEventListener("click",event=>{
      const b=event.target.closest("[data-appointment]");if(!b)return;
      const r=items.find(x=>String(x.id)===b.dataset.appointment);
      const editable=["pending","confirmed"].includes(r.status);
      const statuses=r.status==="pending"?[["confirmed","Xác nhận"],["cancelled","Hủy lịch"]]:[["completed","Xác nhận đã hoàn thành"],["cancelled","Hủy lịch"]];
      open("Lịch hẹn LH-"+r.id,`<div class="admin-service-modal-scroll"><dl class="journey-facts">${[["Khách hàng",r.customer],["Dịch vụ",r.service],["Chuyên viên",r.employee],["Thời gian",`${r.date} ${r.time}–${r.end}`],["Trạng thái",r.statusLabel],["Ghi chú / Thông báo",r.note || "—"]].map(([k,v])=>`<div><dt>${k}</dt><dd>${escape(v)}</dd></div>`).join("")}</dl>${editable?`<form class="admin-service-form admin-ops-form"><div class="admin-service-form-grid"><label>Cập nhật trạng thái<select name="status">${statuses.map(([v,l])=>`<option value="${v}">${l}</option>`).join("")}<option value="${r.status}">Giữ trạng thái (chỉ khi đổi chuyên viên)</option></select></label><label><input type="checkbox" data-reassign>Đổi chuyên viên trong trường hợp ngoại lệ</label><label>Chuyên viên thay thế<select name="employee" disabled><option value="">Chọn chuyên viên</option>${window.spaCatalog.staff.filter(x=>x.serviceIds.includes(r.serviceId)&&x.id!==r.employeeId).map(x=>`<option value="${x.id}">${escape(x.name)}</option>`).join("")}</select></label><label><input type="checkbox" name="consent">Đã được khách đồng ý và thông báo việc đổi chuyên viên</label><label>Lý do / thông báo hiển thị cho khách<textarea name="reason" maxlength="500"></textarea></label></div><p class="admin-service-error" data-error hidden></p><div class="admin-dialog-actions"><button class="admin-button admin-button-primary" type="submit">Xác nhận cập nhật</button></div></form>`:"<p>Lịch đã kết thúc, chỉ xem thông tin.</p>"}</div>`);
      if(editable){const form=dialog.querySelector("form");form.querySelector("[data-reassign]").onchange=e=>{form.elements.employee.disabled=!e.target.checked;form.elements.employee.required=e.target.checked;};bindForm(`/api/appointments/${r.id}/status/`,load);}
    });
    toolbar.addEventListener("input",()=>load().catch(e=>notify(e.message)));
    $("#ops-reset").onclick=()=>{toolbar.querySelectorAll("input,select").forEach(e=>e.value="");load().catch(e=>notify(e.message));};
    api(url("employees")).then(data=>{employees.replaceChildren(new Option("Tất cả nhân viên",""),...data.items.map(e=>new Option(e.name,e.id)));return load();}).catch(e=>notify(e.message));
    return;
  }
  if(servicePage){
    root.querySelectorAll("[data-service-tab]").forEach(button=>button.onclick=()=>{root.querySelectorAll("[data-service-tab]").forEach(b=>{const selected=b===button;b.setAttribute("aria-selected",selected);b.tabIndex=selected?0:-1;$(`#panel-${b.dataset.serviceTab}`).hidden=!selected;});});
    root.querySelectorAll("[data-service-icon]").forEach(el=>el.innerHTML=window.spaIcon(el.dataset.serviceIcon));
  }
  root.querySelectorAll(".admin-toolbar").forEach(bar=>bar.addEventListener("input",()=>{(servicePage?["categories","services"]:[module]).forEach(type=>{pages[type]=1;render(type);});}));
  $("#ops-reset")?.addEventListener("click",()=>{root.querySelectorAll(".admin-toolbar input,.admin-toolbar select").forEach(el=>el.value="");render(module);});
  root.addEventListener("click",async event=>{
    const b=event.target.closest("button");if(!b)return;
    try {
      if(b.hasAttribute("data-service-add") || b.id==="ops-add") await edit(b.dataset.serviceAdd || module);
      if(b.dataset.edit) await edit(b.dataset.type,Number(b.dataset.edit));
      if(b.dataset.toggle){b.disabled=true;const data=new FormData();data.set("_toggle","1");await api(url(b.dataset.type,b.dataset.toggle),data);await refresh();}
      if(b.dataset.schedule)await schedule(b.dataset.schedule);
    }catch(error){notify(error.message);}finally{b.disabled=false;}
  });
  refresh().catch(error=>notify(error.message));
})();
