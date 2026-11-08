// Employees schedule presentation; API payloads retain ISO dates and existing rules.
window.spaSchedule=async (employee,{open,api,dialog,notify,employeeName=''})=>{
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const date=s=>/^\d{4}-\d{2}-\d{2}$/.test(s||'')?s.slice(8,10)+'/'+s.slice(5,7)+'/'+s.slice(0,4):s||'—';
  const iso=s=>{const m=/^(\d{2})\/(\d{2})\/(\d{4})$/.exec(s);if(!m)return '';const v=m[3]+'-'+m[2]+'-'+m[1],d=new Date(v+'T12:00:00Z');return !isNaN(d)&&d.toISOString().slice(0,10)===v?v:'';};
  const icon=name=>window.spaIcon(name),path=`/api/admin/employees/${employee}/schedules/`;
  const identity=`${employeeName} · NV-${String(employee).padStart(3,'0')}`;
  let child=false,saving=false,returnTrigger;
  const [data,appointments]=await Promise.all([api(path),api(`/api/appointments/?employee=${employee}`)]);
  const cancel=e=>{if(child){e.preventDefault();if(!saving)parent();}};
  const cleanup=()=>{dialog.removeEventListener('cancel',cancel);dialog.removeEventListener('close',onClose);};
  const onClose=()=>{if(!dialog.open)cleanup();};
  dialog.addEventListener('cancel',cancel);dialog.addEventListener('close',onClose);
  function heading(){const title=dialog.querySelector('#ops-dialog-title');const sub=document.createElement('p');sub.className='employee-schedule-identity';sub.textContent=identity;title.after(sub);}
  function parent(){child=false;open('Lịch làm việc',`<div class="admin-service-modal-scroll employee-schedule-content"><div class="admin-row-actions"><button type="button" class="admin-button admin-button-primary" data-plan="weekly">Thiết lập lịch tuần</button><button type="button" class="admin-button" data-plan="day">Đổi ca một ngày</button><button type="button" class="admin-button" data-plan="leave">Nghỉ phép / nghỉ đột xuất</button></div>
    <section class="employee-schedule-section"><h3>${icon('calendar')}Ca đang áp dụng</h3><div class="admin-table-scroll employee-shift-scroll" tabindex="0" role="region" aria-label="Ca đang áp dụng, tối đa năm dòng trước khi cuộn"><table class="admin-data-table employee-shift-table"><thead><tr><th scope="col">Ngày</th><th scope="col">Giờ</th><th scope="col">Trạng thái</th><th scope="col">Ghi chú</th></tr></thead><tbody>${data.items.map(s=>`<tr><td>${esc(date(s.date))}</td><td>${esc(s.start)}–${esc(s.end)}</td><td><span class="admin-status-badge admin-status-${s.status==='Làm việc'?'completed':'cancelled'}">${esc(s.status)}</span></td><td><span class="employee-schedule-note" title="${esc(s.note||'')}">${esc(s.note||'—')}</span></td></tr>`).join('')}</tbody></table></div>${data.items.length?'':'<p>Chưa có ca làm việc.</p>'}</section>
    <section class="employee-schedule-section"><h3>${icon('note')}Lịch hẹn đã đặt</h3><div class="admin-table-scroll"><table class="admin-data-table employee-booked-table"><thead><tr><th>Mã lịch hẹn</th><th>Khách hàng</th><th>Ngày / giờ</th><th>Trạng thái</th></tr></thead><tbody>${appointments.items.map(a=>`<tr><td>LH-${String(a.id).padStart(6,'0')}</td><td>${esc(a.customer)}</td><td>${esc(date(a.date))} · ${esc(a.time)}–${esc(a.end)}</td><td><span class="admin-status-badge admin-status-${['pending','confirmed','completed','cancelled'].includes(a.status)?a.status:'pending'}">${esc(a.statusLabel)}</span></td></tr>`).join('')}</tbody></table>${appointments.items.length?'':'<p>Chưa có lịch hẹn đã đặt.</p>'}</div></section></div><div class="admin-dialog-actions"><button class="admin-button" type="button" data-close>Đóng</button></div>`);
    heading();
    const scroller=dialog.querySelector('.employee-shift-scroll'),table=scroller.querySelector('table');
    function fit(){const rows=[...table.tBodies[0].rows];scroller.style.maxHeight=rows.length>5?(table.tHead.getBoundingClientRect().height+rows.slice(0,5).reduce((h,r)=>h+r.getBoundingClientRect().height,0)+Math.max(0,scroller.offsetHeight-scroller.clientHeight)+1)+'px':'';}
    fit();requestAnimationFrame(fit);
    dialog.querySelectorAll('[data-plan]').forEach(b=>b.onclick=()=>{returnTrigger=b.dataset.plan;edit(b.dataset.plan);});
    if(returnTrigger)dialog.querySelector(`[data-plan="${returnTrigger}"]`)?.focus();
  }
  const dateField=(label,name)=>`<label>${label}<span class="employee-date-control"><input type="text" data-date-display="${name}" placeholder="dd/mm/yyyy" inputmode="numeric" maxlength="10" required autocomplete="off"><input type="date" name="${name}" class="employee-date-picker" tabindex="-1" min="${esc(window.spaPromotions.referenceDate)}"><button type="button" class="admin-icon-button" data-pick="${name}" aria-label="Chọn ${label.toLocaleLowerCase('vi')}">${icon('calendar')}</button></span></label>`;
  function edit(mode){child=true;const leave=mode==='leave';
    open(({weekly:'Thiết lập lịch tuần',day:'Đổi ca một ngày',leave:'Nghỉ phép / nghỉ đột xuất'})[mode],`<form class="admin-service-form admin-ops-form live-business-form"><div class="admin-service-modal-scroll"><fieldset class="admin-ops-form-section"><legend>${icon('calendar')}Thời gian áp dụng</legend><div class="admin-service-form-grid">${dateField(mode==='day'?'Ngày':'Từ ngày','start_date')}${mode!=='day'?dateField('Đến ngày','end_date'):''}</div></fieldset>${mode==='weekly'?`<fieldset class="admin-ops-checks"><legend>Ngày làm việc hằng tuần</legend><div class="admin-ops-choice-grid">${['Thứ Hai','Thứ Ba','Thứ Tư','Thứ Năm','Thứ Sáu','Thứ Bảy','Chủ Nhật'].map((v,i)=>`<label><input type="checkbox" name="weekdays" value="${i}">${v}</label>`).join('')}</div></fieldset>`:''}${!leave?`<fieldset class="admin-ops-form-section"><legend>${icon('clock')}Ca làm việc</legend><div data-intervals="work"></div><button class="admin-button" type="button" data-add="work">Thêm ca</button></fieldset><fieldset class="admin-ops-form-section"><legend>${icon('clock')}Khoảng nghỉ giữa ca</legend><div data-intervals="breaks"></div><button class="admin-button" type="button" data-add="breaks">Thêm khoảng nghỉ</button></fieldset>`:''}<label>Ghi chú / lý do<textarea name="note" rows="3" maxlength="1000"></textarea></label><p class="admin-data-note">Thay lịch trong khoảng ngày đã chọn. Ca cũ được lưu lịch sử. Hệ thống chặn lịch hẹn bị ảnh hưởng; không tự hủy hoặc đổi nhân viên. Tối đa 366 ngày mỗi lần.</p><p class="admin-service-error" data-error role="alert" tabindex="-1" hidden></p></div><div class="admin-dialog-actions"><button class="admin-button" data-close type="button">Hủy</button><button class="admin-button admin-button-primary" type="submit">Áp dụng lịch</button></div></form>`);
    heading();dialog.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>{if(!saving)parent();});
    const form=dialog.querySelector('form');
    form.querySelectorAll('[data-date-display]').forEach(text=>{const hidden=form.elements[text.dataset.dateDisplay];
      const sync=()=>{hidden.value=iso(text.value.trim());text.setCustomValidity(!hidden.value?'Nhập ngày hợp lệ theo dd/mm/yyyy.':hidden.min&&hidden.value<hidden.min?'Ngày không được trước '+date(hidden.min)+'.':'');};
      text.addEventListener('input',sync);hidden.onchange=()=>{text.value=date(hidden.value);sync();};
      form.querySelector(`[data-pick="${text.dataset.dateDisplay}"]`).onclick=()=>{try{hidden.showPicker();}catch{text.focus();}};
    });
    function add(kind){const row=document.createElement('div');row.className='live-schedule-row';row.innerHTML='<label>Bắt đầu<input type="time" data-start required></label><label>Kết thúc<input type="time" data-end required></label><button class="admin-button" type="button" data-remove>'+icon('close')+'Bỏ dòng</button>';row.querySelector('[data-remove]').onclick=()=>row.remove();form.querySelector(`[data-intervals="${kind}"]`).append(row);}
    form.querySelectorAll('[data-add]').forEach(b=>b.onclick=()=>add(b.dataset.add));if(!leave)add('work');
    form.onsubmit=async event=>{event.preventDefault();if(saving||!form.reportValidity())return;saving=true;const submit=form.querySelector('[type=submit]');submit.disabled=true;
      const values=new FormData(form),plan={mode,start_date:values.get('start_date'),end_date:values.get('end_date')||values.get('start_date'),weekdays:values.getAll('weekdays'),note:values.get('note')};
      for(const kind of ['work','breaks'])plan[kind]=[...form.querySelectorAll(`[data-intervals="${kind}"] .live-schedule-row`)].map(row=>[row.querySelector('[data-start]').value,row.querySelector('[data-end]').value]);
      const body=new FormData();body.set('plan',JSON.stringify(plan));
      try{const result=await api(path+'plan/',body);child=false;cleanup();await window.spaSchedule(employee,{open,api,dialog,notify,employeeName});notify(`Đã áp dụng ${result.days} ngày, ${result.shifts} khoảng làm/nghỉ.`);}catch(error){const el=form.querySelector('[data-error]');el.textContent=error.message;el.hidden=false;el.focus();}finally{saving=false;submit.disabled=false;}
    };
  }
  parent();
};
