(() => {
  "use strict";
  const escape=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  async function api(url,data){
    const response=await fetch(url,data?{method:"POST",body:data,headers:{"X-CSRFToken":document.querySelector('[name="csrfmiddlewaretoken"]').value}}:{});
    const result=await response.json().catch(()=>({}));
    if(!response.ok)throw Error(result.error||Object.values(result.errors||{}).flat().join(" ")||"Không thể thực hiện thao tác. Vui lòng đăng nhập lại.");return result;
  }
  const form=document.querySelector("#booking-form");
  if(form){
    const catalog = window.spaCatalog;
    const status = form.querySelector("[data-slot-status]");
    const submit = form.querySelector('[type="submit"]');
    const {service, employee, date, time, note} = form.elements;
    const displayDate = form.querySelector("#booking-date-display");
    const picker = form.querySelector(".booking-day-picker");
    const formatDate = iso => iso.split("-").reverse().join("/");
    const slotPrompt = "Chọn dịch vụ, chuyên viên và ngày để xem khung giờ phù hợp.";
    const profile = window.spaAuth.getSession();
    form.elements.name.value = profile?.name || "";
    form.elements.phone.value = profile?.phone || "";
    service.append(...catalog.services.map(item => new Option(`${item.name} · ${item.duration}`, item.id)));
    date.min = window.spaPromotions.referenceDate;
    let generation = 0;
    let submitting = false;

    function dateError() {
      if (date.validity.rangeUnderflow) return `Chọn ngày từ ${formatDate(date.min)} trở đi.`;
      if (date.validity.rangeOverflow) return `Chọn ngày không muộn hơn ${formatDate(date.max)}.`;
      if (!displayDate.hidden && displayDate.value.trim() && !date.value) return "Nhập ngày hợp lệ theo dd/mm/yyyy.";
      return "";
    }

    function syncSubmit() {
      submit.disabled = submitting || time.disabled || !time.value || !service.value || !employee.value || !date.value || !date.validity.valid;
    }

    async function slots(bookingError = "") {
      const version = ++generation;
      time.disabled = true;
      time.replaceChildren(new Option("Chọn chuyên viên và ngày hẹn", ""));
      syncSubmit();
      const invalidDate = dateError();
      displayDate.setCustomValidity(invalidDate);
      displayDate.setAttribute("aria-invalid", String(Boolean(invalidDate)));
      if (!service.value || !employee.value || !date.value || !date.validity.valid) {
        status.textContent = invalidDate || bookingError || slotPrompt;
        return;
      }
      status.textContent = bookingError || "Đang kiểm tra khung giờ…";
      try {
        const params = new URLSearchParams({service: service.value, employee: employee.value, date: date.value});
        const data = await api("/api/appointments/available-slots/?" + params);
        if (version !== generation) return;
        const hasSlots = data.slots.length > 0;
        time.replaceChildren(new Option(hasSlots ? "Chọn giờ hẹn" : "Không có khung giờ phù hợp", ""),
          ...data.slots.map(slot => new Option(slot, slot)));
        time.disabled = !hasSlots;
        const guidance = hasSlots
          ? (bookingError ? "Vui lòng chọn lại khung giờ." : "Chọn khung giờ phù hợp. Lịch sẽ được kiểm tra lại khi xác nhận.")
          : "Không có khung giờ phù hợp trong ngày này.";
        status.textContent = [bookingError, guidance].filter(Boolean).join(" ");
      } catch (error) {
        if (version === generation) status.textContent = [bookingError, error.message].filter(Boolean).join(" ");
      }
    }

    function updateEmployees() {
      const people = catalog.staff.filter(person => person.serviceIds.includes(Number(service.value)));
      const prompt = !service.value ? "Chọn dịch vụ trước" : people.length ? "Chọn chuyên viên" : "Chưa có chuyên viên phù hợp";
      employee.replaceChildren(new Option(prompt, ""), ...people.map(person => new Option(person.name, person.id)));
      employee.disabled = people.length === 0;
      slots();
    }

    if (typeof date.showPicker === "function") {
      date.parentElement.classList.add("is-localized");
      date.labels[0].htmlFor = displayDate.id;
      date.tabIndex = -1;
      date.setAttribute("aria-hidden", "true");
      displayDate.value = formatDate(date.value);
      displayDate.hidden = false;
      displayDate.required = true;
      picker.hidden = false;
      picker.addEventListener("click", () => {
        try { date.showPicker(); }
        catch {
          status.textContent = "Không mở được lịch. Vui lòng nhập ngày theo dd/mm/yyyy.";
          displayDate.focus();
        }
      });
      displayDate.addEventListener("input", () => {
        const parts = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(displayDate.value.trim());
        // The native control rejects impossible dates without converting timezones.
        date.value = parts ? `${parts[3]}-${parts[2]}-${parts[1]}` : "";
        slots();
      });
      date.addEventListener("invalid", event => {
        event.preventDefault();
        displayDate.focus();
      });
    }

    function updateDate() {
      if (!displayDate.hidden) displayDate.value = formatDate(date.value);
      slots();
    }
    service.addEventListener("change", updateEmployees);
    employee.addEventListener("change", () => slots());
    date.addEventListener("change", updateDate);
    time.addEventListener("change", syncSubmit);
    const selected = new URLSearchParams(location.search).get("service");
    if ([...service.options].some(option => option.value === selected)) service.value = selected;
    updateEmployees();

    form.addEventListener("submit", async event => {
      event.preventDefault();
      if (submit.disabled || submitting || !form.reportValidity()) return;
      submitting = true;
      syncSubmit();
      const fields = new FormData();
      for (const input of [service, employee, date, time, note]) fields.set(input.name, input.value);
      try {
        const {item} = await api("/api/appointments/book/", fields);
        form.hidden = true;
        const result = document.querySelector("#booking-result");
        const details = {service: item.service, employee: item.employee, date: formatDate(item.date), time: `${item.time}–${item.end}`};
        for (const [key, value] of Object.entries(details)) result.querySelector(`[data-booking-${key}]`).textContent = value;
        result.hidden = false;
        result.tabIndex = -1;
        result.focus();
      } catch (error) {
        await slots(error.message);
      } finally {
        submitting = false;
        syncSubmit();
      }
    });
  }
  const list=document.querySelector("#appointment-list");
  if(list){
    const filter=document.querySelector("[data-appointment-filter]");
    let version=0, reviewed=null, reviewRequest;
    const reviewLabel=id=>reviewed?.has(id)?"Chỉnh sửa đánh giá":reviewed?"Viết đánh giá":"Đánh giá dịch vụ";
    function refreshReviewLabels(){
      if(reviewRequest)return;
      reviewRequest=api("/api/reviews/").then(({items})=>{
        reviewed=new Set(items.map(item=>String(item.appointmentId)));
        list.querySelectorAll("[data-review-appointment]").forEach(link=>{
          link.textContent=reviewLabel(link.dataset.reviewAppointment);
        });
      }).catch(()=>{ /* Keep the appointment list and its review links usable. */ })
        .finally(()=>{reviewRequest=null;});
    }
    async function render(){
      const requestVersion=++version;
      try{
        const data=await api("/api/appointments/?status="+encodeURIComponent(filter.value));
        if(requestVersion!==version)return;
        list.innerHTML=data.items.length?data.items.map(x=>{
          const code=window.spaAppointmentCode(x.id);
          const [year,month,day]=x.date.split("-");
          return `<article class="journey-card appointment-card">
            <div class="appointment-heading">
              <time class="appointment-date" datetime="${escape(x.date)}T${escape(x.time)}:00+07:00"><strong>${escape(day)}</strong><span>THÁNG ${escape(month)} · ${escape(year)}</span><span>${escape(x.time)}–${escape(x.end)}</span></time>
              <div><span class="eyebrow">AN NHIÊN / ${code}</span><h2>${escape(x.service)}</h2><p>${escape(x.employee)}</p></div><span class="journey-status">${escape(x.statusLabel)}</span>
            </div>
            <details><summary class="button small">Xem chi tiết</summary><dl class="journey-facts">
              <div><dt>Mã lịch hẹn</dt><dd>${code}</dd></div>
              <div><dt>Ghi chú / Thông báo</dt><dd>${escape(x.note||"Không có ghi chú")}</dd></div>
              <div><dt>Hóa đơn</dt><dd>${x.invoiceStatus?escape(x.invoiceStatus):"Chưa có hóa đơn"}</dd></div>
            </dl></details>
            <div class="journey-actions">
              ${x.invoiceId?`<a class="button filled" href="invoice.html?id=${x.invoiceId}">Xem hóa đơn</a>`:""}
              ${x.status==="completed"?`<a class="button small" data-review-appointment="${x.id}" href="service-detail.html?id=${x.serviceId}&amp;appointment=${x.id}#reviews">${reviewLabel(String(x.id))}</a>`:""}
              ${x.cancellable?`<button class="button" data-cancel="${x.id}">Hủy lịch hẹn</button>`:""}
            </div></article>`;
        }).join(""):'<p class="journey-empty">Bạn chưa có lịch hẹn phù hợp.</p>';
        if(reviewed===null&&list.querySelector("[data-review-appointment]"))refreshReviewLabels();
      }catch(error){if(requestVersion===version)list.textContent=error.message;}
    }
    const requestedStatus=new URLSearchParams(location.search).get("status");
    if([...filter.options].some(option=>option.value===requestedStatus))filter.value=requestedStatus;
    filter.onchange=render;
    window.addEventListener("pageshow",event=>{
      if(event.persisted&&list.querySelector("[data-review-appointment]"))refreshReviewLabels();
    });
    list.addEventListener("click",event=>{
      const button=event.target.closest("[data-cancel]");if(!button)return;
      const modal=document.createElement("dialog");modal.className="logout-dialog";
      modal.innerHTML='<h2>Hủy cuộc hẹn này?</h2><p>Thao tác sẽ hủy lịch hẹn và hóa đơn chưa thanh toán nếu có.</p><p data-error role="alert"></p><div class="logout-actions"><button class="button" data-no>Giữ lịch hẹn</button><button class="button filled" data-yes>Xác nhận hủy</button></div>';
      document.body.append(modal);modal.showModal();modal.querySelector("[data-no]").onclick=()=>modal.close();modal.addEventListener("close",()=>{modal.remove();if(button.isConnected)button.focus();});
      modal.querySelector("[data-yes]").onclick=async()=>{const b=modal.querySelector("[data-yes]");b.disabled=true;try{const data=new FormData();data.set("status","cancelled");await api(`/api/appointments/${button.dataset.cancel}/status/`,data);modal.close();await render();}catch(error){modal.querySelector("[data-error]").textContent=error.message;b.disabled=false;}};
    });render();
  }
})();
