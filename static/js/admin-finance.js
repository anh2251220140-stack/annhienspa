(async () => {
  'use strict';
  const main = document.querySelector('[data-admin-finance]');
  if (!main || !window.spaAuth?.isAuthenticated() || window.spaAuth.getSession()?.role !== 'Admin') return;
  const module = main.dataset.adminFinance, $ = s => document.querySelector(s), dialog = $('#finance-dialog');
  const esc = window.spaLive.escape, money = window.spaLive.money;
  const normalize = v => String(v ?? '').toLocaleLowerCase('vi').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/g,'d').trim();
  const appointmentCode = id => 'LH-' + String(id).padStart(6,'0');
  const localDay = value => {
    if (!value) return '';
    if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
    const d = new Date(value); if (Number.isNaN(d.valueOf())) return '';
    const parts = Object.fromEntries(new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Ho_Chi_Minh',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(d).map(p=>[p.type,p.value]));
    return `${parts.year}-${parts.month}-${parts.day}`;
  };
  const dateLabel = value => localDay(value) ? localDay(value).split('-').reverse().join('/') : 'Chưa có';
  const timeLabel = value => value && !Number.isNaN(new Date(value).valueOf()) ? new Date(value).toLocaleTimeString('vi-VN',{hour:'2-digit',minute:'2-digit',timeZone:'Asia/Ho_Chi_Minh'}) : '';
  const timestamp = value => value ? dateLabel(value) + ' · ' + timeLabel(value) : 'Chưa ghi nhận';
  const methodLabel = method => method === 'spa' ? 'Trực tiếp tại Spa' : 'payOS';
  const icon = name => name === 'check' ? '<svg class="line-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="m4 12 5 5L20 6"/></svg>' : window.spaIcon(name);
  const badge = (label,color) => `<span class="admin-status-badge admin-status-${color}">${esc(label)}</span>`;
  const paymentBadge = p => badge(p.requiresReview ? 'Cần đối soát' : ({success:'Thành công',pending:'Đang chờ',cancelled:'Đã hủy',review:'Cần đối soát'}[p.status] || 'Chưa xác định'),p.requiresReview || ['review','cancelled'].includes(p.status) ? 'cancelled' : p.status === 'success' ? 'completed' : 'pending');
  const invoiceBadge = i => badge({paid:'Đã thanh toán',unpaid:'Chưa thanh toán',cancelled:'Đã hủy'}[i.status] || 'Chưa xác định',i.status === 'paid' ? 'completed' : i.status === 'cancelled' ? 'cancelled' : 'pending');
  const appointmentLabels = {pending:'Chờ xác nhận',confirmed:'Đã xác nhận',completed:'Đã hoàn thành',cancelled:'Đã hủy'};
  const paymentMap = p => ({...p,dbId:p.id,id:`GD-${p.id}`,invoiceId:`HD-${p.invoiceId}`,amount:Number(p.amount)});
  const invoiceMap = i => ({...i,dbId:i.id,id:`HD-${i.id}`,appointmentId:appointmentCode(i.appointmentId),subtotal:Number(i.subtotal),priceSnapshot:Number(i.priceSnapshot),discount:Number(i.discount),total:Number(i.total)});
  let invoices = [], payments = [], page = 1, returnFocus, cashBusy = false, opening = false;
  const invoiceFor = p => invoices.find(i=>i.id === p.invoiceId);
  const paymentsFor = i => payments.filter(p=>p.invoiceId === i.id);
  const actionButton = (kind,id,label='Xem') => `<button type="button" class="admin-button" data-finance-view="${kind}" data-record="${esc(id)}">${icon('eye')}${label}</button>`;
  function notice(message) { $('#finance-data-note').textContent=message; $('#finance-error').hidden=!message; }
  function renderStats() {
    // Preserve the existing global accounting criteria. Do not silently adopt
    // Dashboard's extra invoice-paid condition or make KPIs depend on UI filters.
    const successful = payments.filter(p=>p.status === 'success' && !p.requiresReview);
    const paid = invoices.filter(i=>i.status === 'paid');
    const received = successful.reduce((sum,p)=>sum+p.amount,0);
    const stats = module === 'invoices'
      ? [['Tổng thu đã ghi nhận',money(received),'leaf'],['Tổng hóa đơn',invoices.length,'note'],['Đã thanh toán',paid.length,'heart'],['Chưa thanh toán',invoices.filter(i=>i.status === 'unpaid').length,'clock']]
      : [['Thanh toán thành công',money(received),'leaf'],['Tổng giao dịch',payments.length,'note'],['Đang chờ',payments.filter(p=>p.status === 'pending').length,'clock'],['Đã hủy',payments.filter(p=>p.status === 'cancelled').length,'calendar']];
    $('#finance-stats').innerHTML=stats.map(([label,value,symbol],index)=>`<article class="admin-finance-stat${index===0?' is-featured':''}"><div class="admin-finance-stat-heading"><span>${label}</span><span class="finance-stat-symbol">${icon(symbol)}</span></div><strong>${value}</strong></article>`).join('');
  }
  const invoiceRow = i => `<tr><td><strong class="admin-finance-code">${i.id}</strong><span class="admin-table-time">${i.appointmentId}</span></td><td class="admin-finance-description"><strong>${esc(i.customer)}</strong><span class="admin-table-time">${esc(i.service)}</span></td><td class="admin-finance-money">${money(i.subtotal)}</td><td class="admin-finance-money">${money(i.discount)}<span class="admin-table-time">${esc(i.promotion || 'Không áp dụng')}</span></td><td class="admin-finance-money admin-finance-total">${money(i.total)}</td><td>${dateLabel(i.createdAt)}<span class="admin-table-time">${timeLabel(i.createdAt)}</span></td><td>${invoiceBadge(i)}${i.needsReview?'<span class="finance-review-hint">Cần đối soát</span>':''}</td><td><div class="admin-row-actions">${actionButton('invoice',i.id)}</div></td></tr>`;
  const paymentRow = p => {
    const i=invoiceFor(p);
    return `<tr><td><strong class="admin-finance-code">${p.id}</strong><span class="admin-table-time finance-reference">${esc(p.reference || 'Chưa có tham chiếu')}</span></td><td><strong>${esc(p.invoiceId)}</strong><span class="admin-table-time">${i?.appointmentId || 'Chưa xác định'}</span><span class="admin-table-time">${esc(i?.customer || 'Chưa tải được hóa đơn')}</span></td><td class="admin-finance-money admin-finance-total">${money(p.amount)}</td><td><span class="admin-finance-method">${icon(p.method==='spa'?'note':'calendar')}${methodLabel(p.method)}</span></td><td><span class="admin-table-time">Tạo: ${dateLabel(p.createdAt)} · ${timeLabel(p.createdAt)}</span><span class="admin-table-time">Thanh toán: ${p.paidAt?timestamp(p.paidAt):'Chưa ghi nhận'}</span></td><td>${paymentBadge(p)}</td><td><div class="admin-row-actions">${actionButton('payment',p.id)}</div></td></tr>`;
  };
  function render() {
    const query=normalize($('#finance-search').value), day=$('#finance-date').value, status=$('#finance-status').value;
    const basis=module==='payments' ? $('#finance-date-basis').value : 'createdAt';
    const scope=new URLSearchParams(location.search).get('invoice');
    const rows=(module==='invoices'?invoices:payments).filter(record=>{
      const i=module==='invoices'?record:invoiceFor(record);
      if (scope && normalize(scope)===query && i?.id!==scope) return false;
      const state=module==='payments' && record.requiresReview?'review':record.status;
      return (!status || state===status) && (!day || localDay(record[basis])===day) && normalize(`${record.id} ${i?.id || ''} ${i?.appointmentId || ''} ${i?.customer || ''} ${i?.service || ''} ${record.reference || ''}`).includes(query);
    });
    const pages=Math.max(1,Math.ceil(rows.length/5));page=Math.max(1,Math.min(page,pages));
    const start=(page-1)*5,visible=rows.slice(start,start+5);
    $('#finance-rows').innerHTML=visible.map(module==='invoices'?invoiceRow:paymentRow).join('');
    $('#finance-empty').hidden=rows.length>0;
    $('#finance-pagination').innerHTML=`<span>${visible.length} / ${rows.length} ${module==='invoices'?'hóa đơn':'giao dịch'}${rows.length?' · '+(start+1)+'–'+(start+visible.length):''}</span><div><button type="button" class="admin-button" data-finance-page="${page-1}" ${page===1?'disabled':''}>Trước</button><span>${page} / ${pages}</span><button type="button" class="admin-button" data-finance-page="${page+1}" ${page===pages?'disabled':''}>Sau</button></div>`;
  }
  async function loadLedger() {
    const data=await window.spaLive.api('/api/billing/ledger/');
    invoices=data.invoices.map(invoiceMap);payments=data.payments.map(paymentMap);
    renderStats();render();notice('');
  }
  function updateInvoice(raw) {
    const mapped=invoiceMap(raw),index=invoices.findIndex(i=>i.dbId===raw.id);
    if(index<0)invoices.unshift(mapped);else invoices[index]=mapped;
    payments=payments.filter(p=>p.invoiceId!==mapped.id).concat(raw.payments.map(paymentMap)).sort((a,b)=>b.dbId-a.dbId);
    renderStats();render();return mapped;
  }
  const facts = entries => `<dl class="admin-profile-facts admin-ops-facts">${entries.map(([label,value,symbol='note'])=>`<div><dt>${icon(symbol)}${esc(label)}</dt><dd>${esc(value ?? 'Chưa cập nhật')}</dd></div>`).join('')}</dl>`;
  function open(title,body) {
    if(!dialog.open)returnFocus=document.activeElement;
    dialog.innerHTML=`<header class="admin-service-modal-heading"><span class="admin-service-modal-icon">${icon('note')}</span><div><span class="admin-eyebrow">AN NHIÊN SPA / TÀI CHÍNH</span><h2 id="finance-dialog-title">${esc(title)}</h2></div><button type="button" class="admin-icon-button" data-finance-close aria-label="Đóng">${icon('close')}</button></header><div class="admin-service-modal-scroll">${body}</div><footer class="admin-dialog-actions"><button type="button" class="admin-button" data-finance-close>Đóng</button></footer>`;
    if(!dialog.open)dialog.showModal();else dialog.querySelector('[data-finance-close]').focus();
  }
  function cashIssue(i) {
    if(i.status==='paid')return 'Hóa đơn đã thanh toán. Không ghi nhận thêm tiền.';
    if(i.status==='cancelled' || i.appointmentStatus==='cancelled')return 'Hóa đơn hoặc lịch hẹn đã hủy; không được thu tiền.';
    if(!['confirmed','completed'].includes(i.appointmentStatus))return 'Lịch hẹn chưa được xác nhận; chưa được thu tiền.';
    if(i.needsReview || paymentsFor(i).some(p=>p.requiresReview || p.status==='review'))return 'Có khoản thanh toán cần đối soát. Chưa được ghi nhận thêm tiền.';
    if(paymentsFor(i).some(p=>p.status==='success'))return 'Đã có giao dịch thành công. Cần kiểm tra trạng thái hóa đơn trước khi thu thêm.';
    if(['PAID','PROCESSING','UNDERPAID'].includes(i.currentOnline?.providerStatus) || paymentsFor(i).some(p=>p.status==='pending' && ['PAID','PROCESSING','UNDERPAID'].includes(p.providerStatus)))return 'payOS đã nhận tiền hoặc đang xử lý. Cần xác minh trước khi thu thêm.';
    if(i.paymentAllowed!==true)return 'Hóa đơn hiện chưa đủ điều kiện thu tiền. Vui lòng kiểm tra trạng thái và đối soát.';
    return i.cashTimingIssue || '';
  }
  function cashSection(i) {
    const issue=cashIssue(i);
    if(issue)return `<section class="finance-cash-section"><h4>${icon('note')}Thanh toán tại Spa</h4><p class="finance-payment-message" role="status">${esc(issue)}</p></section>`;
    const pending=paymentsFor(i).some(p=>p.method==='online' && p.status==='pending');
    return `<section class="finance-cash-section"><h4>${icon('note')}Ghi nhận thanh toán tại Spa</h4><p>Chỉ xác nhận sau khi đã nhận đủ ${money(i.total)}.</p>${pending?'<p class="finance-payment-message">Có phiên payOS đang chờ. Hệ thống chỉ ghi nhận sau khi xác minh và đóng phiên cũ hợp lệ.</p>':''}<form data-cash-form="${i.dbId}"><label for="finance-cash-amount">Số tiền thực nhận (VND)<input id="finance-cash-amount" name="amount" type="number" min="0" step="0.01" required value="${i.total}"></label><label class="finance-cash-confirm"><input type="checkbox" required data-cash-consent><span>Tôi xác nhận đã nhận đủ tiền trực tiếp tại Spa.</span></label><button type="submit" class="admin-button admin-button-primary">${icon('check')}Xác nhận đã thu tiền tại Spa</button><p data-cash-status role="alert" tabindex="-1" hidden></p></form></section>`;
  }
  function invoiceDetail(i,feedback='') {
    const related=paymentsFor(i);
    open('Chi tiết hóa đơn',`<div class="admin-finance-detail-banner"><div><span class="admin-eyebrow">HÓA ĐƠN DỊCH VỤ</span><h3>${i.id}</h3></div>${invoiceBadge(i)}</div>${feedback?`<p class="finance-payment-message" role="status">${esc(feedback)}</p>`:''}<section class="admin-ops-detail-section"><h4>${icon('note')}Thông tin hóa đơn</h4>${facts([['Mã hóa đơn',i.id],['Khách hàng',i.customer,'heart'],['Ngày lập',timestamp(i.createdAt),'calendar'],['Trạng thái thanh toán',i.statusLabel]])}</section><section class="admin-ops-detail-section"><h4>${icon('calendar')}Lịch hẹn liên quan</h4>${facts([['Mã lịch hẹn',i.appointmentId,'calendar'],['Dịch vụ',i.service,'leaf'],['Chuyên viên',i.employee,'heart'],['Ngày / giờ hẹn',dateLabel(i.date)+' · '+i.time,'calendar'],['Trạng thái lịch hẹn',appointmentLabels[i.appointmentStatus] || 'Chưa xác định']])}</section><section class="admin-finance-breakdown"><h4>${icon('note')}Chi tiết các khoản</h4><dl><div><dt>Giá dịch vụ khi lập hóa đơn</dt><dd>${money(i.priceSnapshot)}</dd></div><div><dt>Mã khuyến mãi</dt><dd>${esc(i.promotion || 'Không áp dụng')}</dd></div><div><dt>Giảm giá</dt><dd>− ${money(i.discount)}</dd></div><div class="admin-finance-grand-total"><dt>Tổng tiền hóa đơn</dt><dd>${money(i.total)}</dd></div></dl></section><section class="admin-ops-detail-section"><h4>${icon('note')}Giao dịch của hóa đơn</h4>${related.length?related.map(p=>`<div class="admin-finance-related"><div><strong>${p.id} · ${money(p.amount)}</strong><span>${methodLabel(p.method)} · ${p.paidAt?timestamp(p.paidAt):'Chưa ghi nhận thanh toán'}</span><span class="finance-reference">${esc(p.reference || 'Chưa có tham chiếu')}</span></div>${paymentBadge(p)}${actionButton('payment',p.id,'Xem giao dịch')}</div>`).join(''):'<p>Chưa ghi nhận giao dịch thanh toán.</p>'}<div class="admin-finance-modal-links"><a class="admin-button" href="admin-payments.html?invoice=${encodeURIComponent(i.id)}">${icon('note')}Đến quản lý thanh toán</a></div></section>${cashSection(i)}`);
  }
  function paymentDetail(p) {
    const i=invoiceFor(p);
    open('Chi tiết thanh toán',`<div class="admin-finance-detail-banner"><div><span class="admin-eyebrow">GIAO DỊCH THANH TOÁN</span><h3>${p.id}</h3></div>${paymentBadge(p)}</div><div class="admin-finance-amount-panel"><span>Số tiền giao dịch</span><strong>${money(p.amount)}</strong></div><section class="admin-ops-detail-section"><h4>${icon('note')}Thông tin giao dịch</h4>${facts([['Mã hóa đơn',p.invoiceId],['Mã lịch hẹn',i?.appointmentId || 'Chưa xác định','calendar'],['Khách hàng',i?.customer || 'Chưa cập nhật','heart'],['Dịch vụ',i?.service || 'Chưa cập nhật','leaf'],['Phương thức',methodLabel(p.method)],['Ngày tạo giao dịch',timestamp(p.createdAt),'calendar'],['Thời điểm thanh toán',timestamp(p.paidAt),'calendar'],[p.method==='spa'?'Tham chiếu tại Spa':'Tham chiếu payOS',p.reference || 'Chưa có'],['Người ghi nhận',p.recordedBy?'Quản trị viên #'+p.recordedBy:p.method==='online'?'Hệ thống payOS':'Chưa ghi nhận'],['Trạng thái nhà cung cấp',p.providerStatus || 'Không áp dụng'],['Trạng thái hóa đơn',i?.statusLabel || 'Chưa xác định']])}<div class="admin-finance-modal-links">${i?actionButton('invoice',i.id,'Xem hóa đơn'):''}<a class="admin-button" href="admin-invoices.html?invoice=${encodeURIComponent(p.invoiceId)}">${icon('note')}Đến quản lý hóa đơn</a></div></section>${p.requiresReview || p.status==='review'?'<p class="finance-payment-message" role="status">Cần đối soát thủ công. Khoản này chưa được tính vào doanh thu.</p>':p.status==='pending'?'<p class="finance-payment-message">Giao dịch đang chờ. Chưa ghi nhận đã thanh toán.</p>':p.method==='online'?'<p class="finance-payment-message">Kết quả thanh toán online được xác nhận qua webhook hợp lệ.</p>':''}`);
  }
  async function view(kind,id) {
    if(opening || cashBusy)return;opening=true;
    try {
      const old=kind==='invoice'?invoices.find(i=>i.id===id):invoiceFor(payments.find(p=>p.id===id) || {});
      if(!old)throw Error('Không tìm thấy hóa đơn liên quan. Vui lòng tải lại danh sách.');
      const raw=(await window.spaLive.api(`/api/billing/${old.dbId}/`)).item;
      const fresh=updateInvoice(raw);
      if(kind==='invoice')invoiceDetail(fresh);
      else {const p=payments.find(p=>p.id===id);if(!p)throw Error('Giao dịch đã thay đổi. Vui lòng tải lại danh sách.');paymentDetail(p);}
    }catch(error){notice(error.message);if(dialog.open){const body=dialog.querySelector('.admin-service-modal-scroll');const p=document.createElement('p');p.className='finance-payment-message';p.setAttribute('role','alert');p.textContent=error.message;body.prepend(p);body.scrollTop=0;}}
    finally{opening=false;}
  }
  // Localized text input backed by the original ISO date value used for filtering.
  const nativeDate=$('#finance-date'),dateText=document.createElement('input'),picker=document.createElement('button'),dateControl=document.createElement('span');
  dateControl.className='finance-date-control';dateText.type='text';dateText.placeholder='dd/mm/yyyy';dateText.inputMode='numeric';dateText.maxLength=10;dateText.id='finance-date-display';dateText.autocomplete='off';
  nativeDate.parentElement.htmlFor=dateText.id;nativeDate.before(dateControl);dateControl.append(dateText,nativeDate,picker);nativeDate.className='finance-native-date';nativeDate.tabIndex=-1;
  picker.type='button';picker.className='admin-icon-button';picker.setAttribute('aria-label','Chọn ngày lọc');picker.innerHTML=icon('calendar');picker.onclick=()=>{try{nativeDate.showPicker();}catch(_){dateText.focus();}};
  dateText.addEventListener('input',()=>{
    const match=dateText.value.trim().match(/^(\d{2})\/(\d{2})\/(\d{4})$/),candidate=match?`${match[3]}-${match[2]}-${match[1]}`:'',parsed=new Date(candidate+'T00:00:00Z');
    const valid=candidate && !Number.isNaN(parsed.valueOf()) && parsed.toISOString().slice(0,10)===candidate;
    nativeDate.value=valid?candidate:'';dateText.setCustomValidity(dateText.value&&!valid?'Nhập ngày hợp lệ theo dd/mm/yyyy.':'');dateText.setAttribute('aria-invalid',String(!!dateText.validationMessage));
    $('#finance-date-error').textContent=dateText.validationMessage;$('#finance-date-error').hidden=!dateText.validationMessage;page=1;render();
  });
  nativeDate.addEventListener('change',()=>{dateText.value=nativeDate.value?dateLabel(nativeDate.value):'';dateText.setCustomValidity('');dateText.removeAttribute('aria-invalid');$('#finance-date-error').hidden=true;page=1;render();});
  dialog.addEventListener('click',event=>{if(event.target.closest('[data-finance-close]')&&!cashBusy)dialog.close();const b=event.target.closest('[data-finance-view]');if(b)view(b.dataset.financeView,b.dataset.record);});
  dialog.addEventListener('cancel',event=>{if(cashBusy)event.preventDefault();});
  dialog.addEventListener('close',()=>{if(returnFocus?.isConnected)returnFocus.focus({preventScroll:true});else $('#finance-search').focus({preventScroll:true});});
  dialog.addEventListener('submit',async event=>{
    const form=event.target.closest('[data-cash-form]');if(!form)return;event.preventDefault();if(cashBusy || !form.reportValidity())return;
    const error=form.querySelector('[data-cash-status]'),button=form.querySelector('[type="submit"]'),original=button.innerHTML,id=Number(form.dataset.cashForm);
    cashBusy=true;button.disabled=true;button.textContent='Đang ghi nhận…';error.hidden=true;dialog.querySelectorAll('[data-finance-close]').forEach(b=>b.disabled=true);
    try {
      const result=await window.spaLive.api(`/api/billing/${id}/cash/`,{amount:form.elements.amount.value});
      const fresh=updateInvoice(result.item);
      invoiceDetail(fresh,'Đã ghi nhận thanh toán tại Spa.');
    }catch(err){
      error.textContent=err.message;error.hidden=false;error.focus();
      // A timeout may follow a committed payment. Re-read MySQL; never retry cash
      // automatically or call payOS status endpoints from this UI.
      try {const raw=(await window.spaLive.api(`/api/billing/${id}/`)).item;const fresh=updateInvoice(raw);if(cashIssue(fresh))invoiceDetail(fresh,err.message);}catch(_){}
    }finally{cashBusy=false;if(button.isConnected){button.disabled=false;button.innerHTML=original;}dialog.querySelectorAll('[data-finance-close]').forEach(b=>b.disabled=false);}
  });
  $('#finance-rows').addEventListener('click',event=>{const b=event.target.closest('[data-finance-view]');if(b){returnFocus=b;view(b.dataset.financeView,b.dataset.record);}});
  $('#finance-pagination').addEventListener('click',event=>{const b=event.target.closest('[data-finance-page]');if(b&&!b.disabled){page=Number(b.dataset.financePage);render();}});
  ['#finance-search','#finance-status','#finance-date-basis'].forEach(selector=>$(selector)?.addEventListener(selector==='#finance-search'?'input':'change',()=>{page=1;render();}));
  $('#finance-reset').onclick=()=>{['#finance-search','#finance-date','#finance-status'].forEach(s=>$(s).value='');if($('#finance-date-basis'))$('#finance-date-basis').value='createdAt';dateText.value='';dateText.setCustomValidity('');dateText.removeAttribute('aria-invalid');$('#finance-date-error').hidden=true;const url=new URL(location.href);url.searchParams.delete('invoice');history.replaceState(null,'',url);page=1;render();};
  $('#finance-retry').onclick=()=>loadLedger().catch(error=>notice(error.message));
  const scope=new URLSearchParams(location.search).get('invoice');if(/^HD-\d+$/.test(scope || ''))$('#finance-search').value=scope;
  try{await loadLedger();}catch(error){notice(error.message);}
})();
