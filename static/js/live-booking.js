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
    const catalog=window.spaCatalog, status=document.querySelector("[data-slot-status]"), submit=form.querySelector('[type="submit"]');
    form.elements.name.value=window.spaAuth.getSession()?.name||"";form.elements.phone.value=window.spaAuth.getSession()?.phone||"";
    form.elements.service.replaceChildren(new Option("Chọn dịch vụ",""),...catalog.services.map(x=>new Option(`${x.name} · ${x.duration}`,x.id)));
    form.elements.date.min=window.spaPromotions.referenceDate;
    let generation=0;
    async function slots(){
      const version=++generation;form.elements.time.disabled=true;submit.disabled=true;
      form.elements.time.replaceChildren(new Option("Chọn chuyên viên và ngày hẹn",""));
      if(!form.elements.employee.value||!form.elements.date.value)return;
      status.textContent="Đang kiểm tra khung giờ…";
      try{
        const params=new URLSearchParams({service:form.elements.service.value,employee:form.elements.employee.value,date:form.elements.date.value});
        const data=await api("/api/appointments/available-slots/?"+params);if(version!==generation)return;
        form.elements.time.replaceChildren(new Option("Chọn giờ hẹn",""),...data.slots.map(t=>new Option(t,t)));
        form.elements.time.disabled=!data.slots.length;status.textContent=data.slots.length?"Chọn khung giờ phù hợp. Lịch sẽ được kiểm tra lại khi xác nhận.":"Không có khung giờ phù hợp trong ngày này.";
      }catch(error){if(version===generation)status.textContent=error.message;}
    }
    function employees(){
      const people=catalog.staff.filter(x=>x.serviceIds.includes(Number(form.elements.service.value)));
      form.elements.employee.replaceChildren(new Option("Chọn chuyên viên",""),...people.map(x=>new Option(x.name,x.id)));
      form.elements.employee.disabled=!people.length;slots();
    }
    form.elements.service.onchange=employees;form.elements.employee.onchange=slots;form.elements.date.onchange=slots;
    form.elements.time.onchange=()=>submit.disabled=!form.elements.time.value||!form.elements.employee.value;
    const selected=new URLSearchParams(location.search).get("service");if(selected)form.elements.service.value=selected;employees();
    form.addEventListener("submit",async event=>{
      event.preventDefault();if(!form.reportValidity())return;submit.disabled=true;
      try{
        const {item}=await api("/api/appointments/book/",new FormData(form));form.hidden=true;
        const result=document.querySelector("#booking-result");
        for(const [key,value]of Object.entries({service:item.service,employee:item.employee,date:item.date,time:`${item.time}–${item.end}`}))result.querySelector(`[data-booking-${key}]`).textContent=value;
        result.hidden=false;result.tabIndex=-1;result.focus();
      }catch(error){await slots();status.textContent=error.message;}
    });
  }
  const list=document.querySelector("#appointment-list");
  if(list){
    const filter=document.querySelector("[data-appointment-filter]");
    async function render(){
      try{
        const data=await api("/api/appointments/?status="+encodeURIComponent(filter.value));
        list.innerHTML=data.items.length?data.items.map(x=>`<article class="journey-card appointment-card"><div class="appointment-heading"><time class="appointment-date"><strong>${escape(x.date.slice(-2))}</strong><span>${escape(x.date.slice(0,7))}</span><span>${escape(x.time)}–${escape(x.end)}</span></time><div><span class="eyebrow">AN NHIÊN / CUỘC HẸN</span><h2>${escape(x.service)}</h2><p>${escape(x.employee)}</p></div><span class="journey-status">${escape(x.statusLabel)}</span></div><details><summary class="button small">Xem chi tiết</summary><dl class="journey-facts"><div><dt>Mã lịch hẹn</dt><dd>LH-${x.id}</dd></div><div><dt>Ghi chú / Thông báo</dt><dd>${escape(x.note||"Không có ghi chú")}</dd></div><div><dt>Hóa đơn</dt><dd>${x.invoiceStatus?escape(x.invoiceStatus):"Chưa có hóa đơn"}</dd></div></dl></details>${x.cancellable?`<div class="journey-actions"><button class="button" data-cancel="${x.id}">Hủy lịch hẹn</button></div>`:""}</article>`).join(""):'<p class="journey-empty">Bạn chưa có lịch hẹn phù hợp.</p>';
      }catch(error){list.textContent=error.message;}
    }
    filter.value=new URLSearchParams(location.search).get("status")||"";filter.onchange=render;
    list.addEventListener("click",event=>{
      const button=event.target.closest("[data-cancel]");if(!button)return;
      const modal=document.createElement("dialog");modal.className="logout-dialog";
      modal.innerHTML='<h2>Hủy cuộc hẹn này?</h2><p>Thao tác sẽ hủy lịch hẹn và hóa đơn chưa thanh toán nếu có.</p><p data-error role="alert"></p><div class="logout-actions"><button class="button" data-no>Giữ lịch hẹn</button><button class="button filled" data-yes>Xác nhận hủy</button></div>';
      document.body.append(modal);modal.showModal();modal.querySelector("[data-no]").onclick=()=>modal.close();modal.addEventListener("close",()=>{modal.remove();if(button.isConnected)button.focus();});
      modal.querySelector("[data-yes]").onclick=async()=>{const b=modal.querySelector("[data-yes]");b.disabled=true;try{const data=new FormData();data.set("status","cancelled");await api(`/api/appointments/${button.dataset.cancel}/status/`,data);modal.close();await render();}catch(error){modal.querySelector("[data-error]").textContent=error.message;b.disabled=false;}};
    });render();
  }
})();
