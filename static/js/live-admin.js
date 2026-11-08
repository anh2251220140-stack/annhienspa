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
  const nouns={categories:"danh mục",services:"dịch vụ",products:"sản phẩm",employees:"nhân viên",promotions:"khuyến mãi"};
  let returnFocus;
  const notify = message => { const el = $(servicePage ? "#services-notice" : "#ops-notice"); el.textContent = message; el.hidden = false; };
  async function api(path, data) {
    const response = await fetch(path, data ? {method:"POST", body:data, headers:{"X-CSRFToken":token()}} : {});
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) { const error=Error(payload.error || Object.values(payload.errors || {}).flat().join(" ") || "Không thể thực hiện thao tác. Vui lòng tải lại và kiểm tra đăng nhập."); error.fields=payload.errors; throw error; }
    return payload;
  }
  function open(title, body) {
    if (!dialog.open) returnFocus = document.activeElement;
    dialog.dataset.opsModule = module;
    dialog.innerHTML = `<header class="admin-service-modal-heading"><span class="admin-service-modal-icon">${window.spaIcon(({services:"leaf",products:"droplet",employees:"heart",promotions:"star",appointments:"calendar"})[module]||"folder")}</span><div><span class="admin-eyebrow">AN NHIÊN SPA</span><h2 id="${servicePage ? "service" : "ops"}-dialog-title">${escape(title)}</h2></div><button class="admin-icon-button" data-close aria-label="Đóng">×</button></header>${body}`;
    dialog.querySelectorAll("[data-close]").forEach(b => b.addEventListener("click", () => dialog.close()));
    dialog.querySelectorAll("[data-live-icon]").forEach(el=>el.innerHTML=window.spaIcon(el.dataset.liveIcon));
    dialog.querySelectorAll("select[name$='_preset']").forEach(select=>{const preview=document.createElement("img");preview.className="live-image-preview";preview.alt="Ảnh minh họa đã chọn";select.after(preview);const show=()=>{preview.hidden=!select.value;if(select.value)preview.src="/static/images/"+encodeURIComponent(select.value);};select.onchange=show;show();});
    if (!dialog.open) dialog.showModal();
  }
  dialog.addEventListener("close", () => returnFocus?.isConnected && returnFocus.focus());
  function bindForm(path, after) {
    const form = dialog.querySelector("form");
    form.addEventListener("submit", async event => {
      event.preventDefault(); const submit = form.querySelector('[type="submit"]'); submit.disabled = true;
      try { await api(path, new FormData(form)); dialog.close(); await after(); notify("Đã lưu thay đổi."); }
      catch (error) { const el = form.querySelector("[data-error]"); el.textContent = error.message; el.hidden = false;
        for(const [name,messages] of Object.entries(error.fields||{})){const field=form.elements.namedItem(name);if(field?.setAttribute){field.setAttribute("aria-invalid","true");const details=field.closest("details");if(details)details.open=true;}const label=form.querySelector(`[data-field-error="${name}"]`);if(label){label.textContent=messages.join(" ");label.hidden=false;}} el.focus(); }
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
      const action = `<div class="admin-row-actions"><button class="admin-button" data-view="${r.id}" data-type="${type}">Xem</button><button class="admin-button" data-edit="${r.id}" data-type="${type}">Sửa</button><button class="admin-button" data-toggle="${r.id}" data-type="${type}">${r.active ? "Tắt" : "Bật"}</button>${type === "employees" ? `<button class="admin-button" data-schedule="${r.id}">Lịch làm việc</button>` : ""}</div>`;
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
  async function edit(type,id=0) { const data=await api(url(type,id)); open(`${id ? "Sửa" : "Thêm"} ${nouns[type]}`,data.html); bindForm(url(type,id),refresh); }
  async function schedule(employee) { await window.spaSchedule(employee,{open,api,dialog,notify}); }
  if (module === "appointments") {
    const toolbar=$(".admin-toolbar");
    const icon=name=>window.spaIcon(name);
    const nativeDate=$("#ops-date"), dateControl=document.createElement("span");
    dateControl.className="appointment-date-control";
    nativeDate.before(dateControl);dateControl.append(nativeDate);
    const dateText=document.createElement("input");dateText.type="text";dateText.placeholder="dd/mm/yyyy";dateText.inputMode="numeric";
    dateText.setAttribute("aria-label","Ngày hẹn, định dạng ngày/tháng/năm");
    const picker=document.createElement("button");picker.type="button";picker.className="admin-button";picker.innerHTML=icon("calendar");picker.setAttribute("aria-label","Mở lịch chọn ngày");
    dateControl.append(dateText,picker);nativeDate.tabIndex=-1;
    picker.onclick=()=>{try{nativeDate.showPicker();}catch(_){dateText.focus();}};
    dateText.addEventListener("input",()=>{
      const match=/^(\d{2})\/(\d{2})\/(\d{4})$/.exec(dateText.value);
      let iso="";
      if(match){const candidate=`${match[3]}-${match[2]}-${match[1]}`;const parsed=new Date(candidate+"T12:00:00Z");if(!isNaN(parsed)&&parsed.toISOString().slice(0,10)===candidate)iso=candidate;}
      nativeDate.value=iso;dateText.setCustomValidity(dateText.value&&!iso?"Nhập ngày hợp lệ theo dd/mm/yyyy.":"");
      dateText.setAttribute("aria-invalid",String(Boolean(dateText.validationMessage)));
      $("#ops-notice").textContent=dateText.validationMessage;$("#ops-notice").hidden=!dateText.validationMessage;
    });
    nativeDate.addEventListener("input",()=>{dateText.value=nativeDate.value?nativeDate.value.split("-").reverse().join("/"):"";dateText.setCustomValidity("");dateText.removeAttribute("aria-invalid");$("#ops-notice").hidden=true;});

    const code=id=>"LH-"+String(id).padStart(6,"0");
    const day=value=>/^\d{4}-\d{2}-\d{2}$/.test(value)?value.split("-").reverse().join("/"):value;
    const normalize=value=>String(value).normalize("NFD").replace(/[\u0300-\u036f]/g,"").replace(/đ/g,"d").toLocaleLowerCase("vi");
    const duration=r=>{const minutes=t=>Number(t.slice(0,2))*60+Number(t.slice(3,5));return minutes(r.end)-minutes(r.time);};
    const statusBadge=r=>`<span class="admin-status-badge admin-status-${escape(r.status)}">${escape(r.statusLabel)}</span>`;
    let items=[],page=1,loadVersion=0;
    function renderAppointments() {
      const q=normalize($("#ops-search").value.trim());
      const rows=items.filter(r=>!dateText.validationMessage&&(!$("#ops-date").value||r.date===$("#ops-date").value)&&
        (!$("#ops-status").value||r.status===$("#ops-status").value)&&
        normalize(`${code(r.id)} LH-${r.id} ${r.customer} ${r.service} ${r.employee}`).includes(q));
      const count=Math.max(1,Math.ceil(rows.length/5));page=Math.max(1,Math.min(page,count));
      const visible=rows.slice((page-1)*5,page*5);
      $("#ops-rows").innerHTML=visible.map(r=>`<tr>
        <td class="admin-appointment-code"><strong>${code(r.id)}</strong></td><td><strong>${escape(r.customer)}</strong></td>
        <td><div class="admin-ops-wrap">${escape(r.service)}</div></td>
        <td><span class="admin-ops-date">${icon("calendar")}${day(r.date)}</span><small class="admin-table-time">${escape(r.time)} · ${duration(r)} phút</small></td>
        <td><span class="admin-ops-assignee">${icon("heart")}${escape(r.employee)}</span></td><td>${statusBadge(r)}</td>
        <td><div class="admin-row-actions"><button class="admin-button" data-appointment="${r.id}" data-readonly>${icon("eye")} Xem</button>${["pending","confirmed"].includes(r.status)?`<button class="admin-button" data-appointment="${r.id}">${icon("calendar")} Xử lý</button>`:""}</div></td></tr>`).join("");
      $("#ops-empty").hidden=rows.length>0;
      $("#ops-pagination").innerHTML=`<span>${visible.length} / ${rows.length} lịch hẹn${rows.length?` · ${(page-1)*5+1}–${(page-1)*5+visible.length}`:""}</span><div><button type="button" class="admin-button" data-appointment-page="${page-1}" ${page===1?"disabled":""}>Trước</button><span>${page} / ${count}</span><button type="button" class="admin-button" data-appointment-page="${page+1}" ${page===count?"disabled":""}>Sau</button></div>`;
    }
    async function load() {
      const version=++loadVersion;
      // The existing Admin endpoint returns the complete authorized collection (no server pagination).
      const result=await api("/api/appointments/");if(version!==loadVersion)return;
      items=result.items;
      $("#ops-stats").innerHTML=[["Tổng lịch hẹn",items.length,"calendar"],["Chờ xác nhận",items.filter(x=>x.status==="pending").length,"leaf"],["Đã xác nhận",items.filter(x=>x.status==="confirmed").length,"clock"]].map(([label,n,symbol])=>`<article><div><span class="admin-ops-stat-symbol">${icon(symbol)}</span><span>${label}</span></div><strong>${n}</strong></article>`).join("");
      renderAppointments();
    }
    const dateTime=value=>value?new Date(value).toLocaleString("vi-VN",{timeZone:"Asia/Ho_Chi_Minh"}):"Chưa ghi nhận";
    async function detail(id, editable, message="") {
      const {item:r,history}=await api(`/api/appointments/${id}/admin-detail/`);
      const facts=[["Mã lịch hẹn",code(r.id),"note"],["Khách hàng",r.customer,"heart"],
        ["Dịch vụ",r.service,"note"],["Ngày / giờ",`${day(r.date)} · ${r.time}–${r.end}`,"calendar"],
        ["Thời lượng",`${duration(r)} phút`,"clock"],["Nhân viên",r.employee,"heart"],
        ["Ghi chú",r.note||"—","note"],["Hóa đơn",r.invoiceStatus||"Chưa lập hóa đơn","note"]];
      const cancellation=r.cancelReason||r.cancelledBy||r.cancelledAt;
      const actions=[["confirm","Xác nhận lịch",r.canConfirm],["complete","Xác nhận đã hoàn thành",r.canComplete],
        ["cancel","Hủy lịch",r.canCancel],["no_show","Khách không đến",r.canNoShow],["reassign","Đổi chuyên viên ngoại lệ",r.canReassign]].filter(x=>x[2]);
      open(editable?"Xử lý lịch hẹn":"Thông tin lịch hẹn",`<div class="admin-service-modal-scroll">
        <p role="status" class="appointment-feedback" ${message?"":"hidden"}>${escape(message)}</p><div class="admin-ops-detail-heading"><span class="admin-ops-detail-symbol">${icon("calendar")}</span><h3>${escape(r.customer)}</h3>${statusBadge(r)}</div>
        <dl class="admin-profile-facts admin-ops-facts">${facts.map(([k,v,symbol])=>`<div><dt>${icon(symbol)}${escape(k)}</dt><dd>${escape(v)}</dd></div>`).join("")}</dl>
        ${r.invoiceId?`<a class="admin-button" href="admin-invoices.html?invoice=HD-${r.invoiceId}">Xem hóa đơn HD-${r.invoiceId}</a>`:""}
        ${cancellation?`<section class="admin-ops-detail-section"><h4>${icon("note")}Thông tin hủy</h4><dl class="admin-profile-facts admin-ops-facts">${[["Lý do hủy",r.cancelReason||"Chưa ghi nhận"],["Người hủy",r.cancelledBy||"Chưa ghi nhận"],["Thời điểm hủy",dateTime(r.cancelledAt)]].map(([k,v])=>`<div><dt>${escape(k)}</dt><dd>${escape(v)}</dd></div>`).join("")}</dl></section>`:""}
        <details class="appointment-history" ${history.length?"open":""}><summary>Lịch sử phân công lại (${history.length})</summary>${history.length?history.map(h=>`<article class="admin-ops-form-section"><h4>${escape(h.previousEmployee)} → ${escape(h.newEmployee)}</h4><p>${escape(h.reason)}</p><p>${escape(h.changedBy)} · ${escape(dateTime(h.changedAt))}</p><p>Khách đã đồng ý · ${escape(h.consentMethod)} · ${escape(dateTime(h.consentAt))}</p><p>${escape(h.consentNote)}</p></article>`).join(""):"<p>Chưa có lịch sử phân công được ghi nhận.</p>"}</details>
        ${editable&&actions.length?`<form class="admin-service-form admin-ops-form">
          ${r.canReassign?`<fieldset class="admin-ops-reassignment"><legend>${icon("heart")}Phân công lại ngoại lệ</legend><p>Giữ nhân viên khách đã chọn khi xác nhận thông thường. Chỉ đổi trước giờ hẹn khi nhân viên không thể phục vụ và khách đã đồng ý.</p><label><input type="checkbox" data-reassign-toggle>Nhân viên hiện tại không thể phục vụ — cần phân công lại</label></fieldset>`:""}
          <label>Thao tác<select name="action" required><option value="">Chọn thao tác</option>${actions.filter(([v])=>v!=="reassign").map(([v,l])=>`<option value="${v}">${l}</option>`).join("")}</select></label>
          <fieldset class="admin-ops-form-section" data-reason hidden disabled><legend>Lý do hủy</legend><textarea name="reason" maxlength="500" required aria-label="Lý do hủy"></textarea></fieldset>
          <fieldset class="admin-ops-form-section" data-reassign-fields hidden disabled><legend>${icon("heart")}Thông tin phân công và sự đồng ý của khách</legend>
            <label>Chuyên viên thay thế<select name="employee" required><option value="">Chọn chuyên viên</option>${window.spaCatalog.staff.filter(x=>x.serviceIds.includes(r.serviceId)&&x.id!==r.employeeId).map(x=>`<option value="${x.id}">${escape(x.name)}</option>`).join("")}</select></label>
            <label>Lý do ngoại lệ<textarea name="reassign_reason" maxlength="500" required></textarea></label>
            <label><input type="checkbox" name="consent" required>Đã thông báo và được khách đồng ý</label>
            <label>Kênh xác nhận<select name="consent_method" required><option value="">Chọn kênh</option><option value="phone">Điện thoại</option><option value="in_person">Trực tiếp</option><option value="other">Kênh khác</option></select></label>
            <label>Ghi chú / bằng chứng xác nhận<textarea name="consent_note" maxlength="500" required></textarea></label>
            <label>Thời điểm khách đồng ý (giờ Việt Nam)<input type="datetime-local" name="consent_at" required></label>
          </fieldset>
          <p data-action-note role="status"></p><p data-error class="admin-service-error" tabindex="-1" role="alert" hidden></p>
          <div class="appointment-confirm" data-confirm hidden tabindex="-1"><h3>Xác nhận thao tác</h3><p data-confirm-text></p><div class="admin-dialog-actions"><button type="button" class="admin-button" data-back>Quay lại</button><button type="button" class="admin-button admin-button-primary" data-commit>Xác nhận</button></div></div>
          <button class="admin-button admin-button-primary" type="submit" disabled>Tiếp tục</button>
        </form>`:"<p>Chế độ xem thông tin. Lịch đã hoàn thành hoặc đã hủy không được chỉnh sửa. Yêu cầu hủy lịch đã thanh toán cần xử lý thủ công theo quy định.</p>"}</div><footer class="admin-dialog-actions"><button type="button" class="admin-button" data-close>Đóng</button></footer>`);
      dialog.querySelector(".admin-eyebrow").textContent="AN NHIÊN SPA / QUẢN TRỊ";
      dialog.querySelector(".admin-service-modal-heading [data-close]").innerHTML=icon("close");
      const form=dialog.querySelector("form");if(!form)return;
      const submit=form.querySelector('[type="submit"]');
      form.id="appointment-action-form";
      submit.setAttribute("form",form.id);
      const footer=dialog.querySelector(":scope > .admin-dialog-actions");
      footer.querySelector("[data-close]").textContent="Hủy";
      footer.append(submit);
      const toggle=form.querySelector("[data-reassign-toggle]");
      const selectedAction=()=>toggle?.checked?"reassign":form.elements.action.value;
      if(toggle)toggle.onchange=()=>{
        // Reassignment is a separate API operation, never an implicit side effect of confirmation.
        form.elements.action.disabled=toggle.checked;
        form.elements.action.required=!toggle.checked;
        form.elements.action.closest("label").hidden=toggle.checked;
        form.elements.action.value="";
        if(!toggle.checked){
          form.querySelectorAll("[data-reassign-fields] input,[data-reassign-fields] select,[data-reassign-fields] textarea").forEach(field=>{if(field.type==="checkbox")field.checked=false;else field.value="";});
        }
        form.elements.action.onchange();resetConfirmation();
      };
      form.elements.action.onchange=()=>{
        const action=selectedAction();
        for(const [selector,on] of [["[data-reason]",action==="cancel"],["[data-reassign-fields]",action==="reassign"]]){
          const fieldset=form.querySelector(selector);fieldset.hidden=!on;fieldset.disabled=!on;
        }
        submit.disabled=!action;
        form.querySelector("[data-action-note]").textContent=action==="no_show"?"Chỉ xác nhận sau khi đã kiểm tra khách không đến. Không tự động hủy theo thời gian.":action==="reassign"?"Backend kiểm tra lại chuyên môn, ca làm và lịch trùng. Thông tin đồng ý được lưu nội bộ.":"";
      };
      const confirmation=form.querySelector("[data-confirm]");
      const resetConfirmation=()=>{confirmation.hidden=true;submit.hidden=false;};
      form.addEventListener("input",resetConfirmation);
      form.querySelector("[data-back]").onclick=()=>{resetConfirmation();submit.focus();};
      form.onsubmit=event=>{
        event.preventDefault();if(!form.reportValidity())return;
        const action=selectedAction();
        form.querySelector("[data-confirm-text]").textContent=`${actions.find(x=>x[0]===action)[1]} — ${code(r.id)}, ${day(r.date)} ${r.time}. `+(action==="reassign"?`Chuyên viên mới: ${form.elements.employee.selectedOptions[0].textContent}. Lý do: ${form.elements.reassign_reason.value}`:action==="cancel"?`Lý do: ${form.elements.reason.value}`:"Vui lòng kiểm tra trước khi xác nhận.");
        confirmation.hidden=false;submit.hidden=true;confirmation.focus();
      };
      let saving=false;
      form.querySelector("[data-commit]").onclick=async ()=>{
        if(saving||!form.reportValidity())return;
        saving=true;submit.disabled=true;
        const snapshot=new FormData(form);snapshot.set("action",selectedAction());
        const controls=[...form.querySelectorAll("input,select,textarea,button")].filter(el=>!el.disabled);
        controls.forEach(el=>el.disabled=true);
        const errorNode=form.querySelector("[data-error]");errorNode.hidden=true;
        try {
          const latest=(await api(`/api/appointments/${id}/admin-detail/`)).item;
          if(latest.updatedAt!==r.updatedAt){await load();await detail(id,true,"Lịch đã thay đổi. Vui lòng kiểm tra dữ liệu mới và xác nhận lại.");return;}
          const data=snapshot,action=data.get("action");data.delete("action");
          data.set("status",({confirm:"confirmed",complete:"completed",cancel:"cancelled",no_show:"cancelled",reassign:r.status})[action]);
          if(action==="no_show"){data.set("no_show","true");data.set("reason","Khách không đến");}
          if(action==="reassign"){
            data.set("reason",data.get("reassign_reason"));data.delete("reassign_reason");
            data.set("expected_employee",r.employeeId);data.set("expected_updated_at",r.updatedAt);
            data.set("consent_at",data.get("consent_at")+(data.get("consent_at").length===16?":00":"")+"+07:00");
          }
          await api(`/api/appointments/${id}/status/`,data);
          await load();await detail(id,true,"Đã cập nhật lịch hẹn.");
        } catch(error) {
          try {
            const latest=(await api(`/api/appointments/${id}/admin-detail/`)).item;
            if(latest.updatedAt!==r.updatedAt){await load();await detail(id,true,"Lịch đã thay đổi. Vui lòng kiểm tra và xác nhận lại.");return;}
          } catch (_) { /* Keep original failure visible; never retry a mutation. */ }
          errorNode.textContent=error.message;errorNode.hidden=false;errorNode.focus();
        } finally {saving=false;controls.forEach(el=>el.disabled=false);form.elements.action.disabled=Boolean(toggle?.checked);submit.disabled=!selectedAction();resetConfirmation();}
      };
    }
    root.addEventListener("click",event=>{
      const pager=event.target.closest("[data-appointment-page]");
      if(pager){page=Number(pager.dataset.appointmentPage);renderAppointments();$(".admin-table-scroll").focus();return;}
      const b=event.target.closest("[data-appointment]");if(!b)return;
      detail(b.dataset.appointment,!b.hasAttribute("data-readonly")).catch(e=>notify(e.message));
    });
    toolbar.addEventListener("input",()=>{page=1;renderAppointments();});
    $("#ops-reset").onclick=()=>{toolbar.querySelectorAll("input,select").forEach(e=>e.value="");dateText.setCustomValidity("");dateText.removeAttribute("aria-invalid");$("#ops-notice").hidden=true;page=1;renderAppointments();};
    load().catch(e=>notify(e.message));
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
      if(b.dataset.view){const data=await api(url(b.dataset.type,b.dataset.view)+"?view=1");open("Thông tin "+nouns[b.dataset.type],data.html);}
      if(b.dataset.edit) await edit(b.dataset.type,Number(b.dataset.edit));
      if(b.dataset.toggle){const r=cache[b.dataset.type].find(x=>String(x.id)===b.dataset.toggle);open(`${r.active?"Tắt":"Bật"} ${nouns[b.dataset.type]}`,`<form class="admin-service-form"><div class="admin-service-modal-scroll"><p>${r.active?"Tạm ngừng":"Bật lại"} “${escape(r.name)}”?</p><p>Dữ liệu lịch sử được giữ nguyên.</p><input type="hidden" name="_toggle" value="1"><p data-error class="admin-service-error" role="alert" hidden></p></div><div class="admin-dialog-actions"><button class="admin-button" type="button" data-close>Hủy</button><button class="admin-button admin-button-primary" type="submit">Xác nhận</button></div></form>`);bindForm(url(b.dataset.type,b.dataset.toggle),refresh);}
      if(b.dataset.schedule)await schedule(b.dataset.schedule);
    }catch(error){notify(error.message);}finally{b.disabled=false;}
  });
  refresh().catch(error=>notify(error.message));
})();
