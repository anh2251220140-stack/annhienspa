(async () => {
  'use strict';
  const {api,escape:esc,money}=window.spaLive;
  const invoiceCode=window.spaInvoiceCode;
  const $=selector=>document.querySelector(selector);
  const list=$('[data-invoice-list]'), promo=$('#invoice-promo-code');
  let invoice=null, page=1, pages=1, busy=false, busyAction='', revision=0, timer, polling=false, notice='';
  let options=[], unavailable=[], promotionMessage='';
  const params=new URLSearchParams(location.search);
  const requestedId=params.get('invoice_id')||params.get('id')||'';
  const initialId=/^[1-9]\d*$/.test(requestedId)&&Number.isSafeInteger(Number(requestedId))?Number(requestedId):null;
  const paymentReturn=initialId&&(params.has('invoice_id')||params.has('orderCode'));
  let retryId=null,records=[],loading=false,total=0,appliedSearch=params.get('search')||'',appliedStatus=params.get('status')||'';
  if(!['','unpaid','paid','cancelled'].includes(appliedStatus))appliedStatus='';
  if(initialId&&!['search','status','page'].some(key=>params.has(key)))appliedSearch=invoiceCode(initialId);
  page=/^[1-9]\d*$/.test(params.get('page')||'')?Number(params.get('page')):1;
  // Provider status is not a list filter or proof of payment. Open only the
  // requested invoice and fetch its authenticated server state.
  if(paymentReturn){appliedSearch=invoiceCode(initialId);appliedStatus='';page=1;}
  $('#invoice-search').value=appliedSearch;$('#invoice-status-filter').value=appliedStatus;
  const appointmentCode=id=>`LH-${String(id).padStart(6,'0')}`;
  const appointmentDate=i=>`${(i.date||'').split('-').reverse().join('/')} ${i.time||''}`.trim();
  function timestamp(value){
    if(!value)return '—';
    const stamp=new Date(value);if(Number.isNaN(stamp.getTime()))return '—';
    const parts=Object.fromEntries(new Intl.DateTimeFormat('vi-VN',{timeZone:'Asia/Ho_Chi_Minh',day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(stamp).map(p=>[p.type,p.value]));
    return `${parts.day}/${parts.month}/${parts.year} ${parts.hour}:${parts.minute}`;
  }
  function syncControls(){
    for(const button of list.querySelectorAll('button'))button.disabled=busy||loading;
    $('#invoice-prev').disabled=busy||loading||page<=1;$('#invoice-next').disabled=busy||loading||page>=pages;
    $('#invoice-filter button').disabled=busy||loading;$('#invoice-reset').disabled=busy||loading;
    $('#invoice-search').disabled=busy;$('#invoice-status-filter').disabled=busy;
    list.setAttribute('aria-busy',String(loading));
  }
  function renderCards(){
    list.innerHTML=records.map(i=>`<article class="journey-card user-invoice-row${invoice?.id===i.id?' is-selected':''}" data-invoice-row="${i.id}">
      <div><h3>${esc(i.service)}</h3><p class="user-invoice-code">${invoiceCode(i.id)} · ${appointmentCode(i.appointmentId)}${invoice?.id===i.id?' <span class="user-invoice-selected">Đang xem</span>':''}</p>
        <dl><div><dt>Ngày lập</dt><dd>${timestamp(i.createdAt)}</dd></div><div><dt>Ngày giờ hẹn</dt><dd>${esc(appointmentDate(i))}</dd></div></dl></div>
      <div class="user-invoice-summary"><strong>${money(i.total)}</strong><span class="journey-status" data-status="${esc(i.status)}">${esc(i.statusLabel)}</span>
        <button class="button small" type="button" data-invoice-open="${i.id}" aria-label="Xem chi tiết hóa đơn ${invoiceCode(i.id)}" ${invoice?.id===i.id?'aria-current="true"':''}>Xem chi tiết</button></div></article>`).join('');
    syncControls();
  }
  function updateUrl(){
    const url=new URL(location.href);url.searchParams.delete('id');
    url.searchParams.delete('invoice_id');
    if(paymentReturn)for(const key of ['code','cancel','orderCode'])url.searchParams.delete(key);
    if(invoice)url.searchParams.set('id',invoice.id);
    for(const [key,value] of Object.entries({search:appliedSearch,status:appliedStatus,page:page>1?String(page):''})){
      if(value)url.searchParams.set(key,value);else url.searchParams.delete(key);
    }
    history.replaceState(null,'',url);
  }
  function clearDetail(){invoice=null;options=[];unavailable=[];promotionMessage='';$('[data-invoice-content]').hidden=true;}

  let clockKey='',deadline=0,qrExpired=false;
  function drawQr() {
    const current=invoice?.currentOnline;
    const key=current?`${invoice.id}:${current.orderCode}:${current.serverNow}`:'';
    if(key!==clockKey){clockKey=key;deadline=(current?.receivedAt||performance.now())+Math.max(0,current?.remainingSeconds||0)*1000;}
    const left=current?Math.max(0,Math.ceil((deadline-performance.now())/1000)):0;
    const expired=current&&(current.expired||left===0);
    qrExpired=!!expired;
    const url=!expired&&invoice?checkout(invoice):'';
    const image=$('[data-payment-qr-image]');
    const src=!expired&&url?current?.qrImage:'';
    $('[data-payment-qr]').hidden=!current||invoice.status!=='unpaid'||invoice.needsReview;
    image.hidden=!src;
    if(src){if(image.getAttribute('src')!==src)image.src=src;}else image.removeAttribute('src');
    $('[data-payment-qr-help]').hidden=!src;
    $('[data-payment-countdown]').textContent=current?`${String(Math.floor(left/60)).padStart(2,'0')}:${String(left%60).padStart(2,'0')}`:'';
    $('[data-payment-qr-status]').textContent=expired?(invoice.onlineEligible?'Mã QR cũ đã hết hạn và không thể sử dụng lại. Bạn có thể làm mới mã QR trên hóa đơn này.':'Mã QR cũ đã hết hạn và không thể sử dụng lại. Vui lòng liên hệ Spa để thanh toán.'):src?'Đang chờ thanh toán. Quét QR không tự xác nhận đã thanh toán.':url?'Không có dữ liệu QR hợp lệ của phiên này. Vui lòng mở trang thanh toán payOS.':'Phiên chưa sẵn sàng hoặc cần đối soát. Không thanh toán thêm trước khi kiểm tra trạng thái.';
    $('[data-payment-qr] h3').textContent=expired?'Mã QR đã hết hạn':'Đang chờ thanh toán';
    if(expired&&!notice&&invoice.status==='unpaid'&&!invoice.needsReview)$('[data-payment-message]').textContent=invoice.onlineEligible?'Mã QR đã hết hạn. Nhấn Làm mới mã QR để thanh toán tiếp trên hóa đơn này.':'Mã QR đã hết hạn. Hóa đơn vẫn chưa thanh toán; vui lòng liên hệ Spa.';
    const link=$('[data-payment-checkout]');link.hidden=!url;
    if(url)link.href=url;else link.removeAttribute('href');
    const processing=['PAID','PROCESSING','UNDERPAID'].includes(current?.providerStatus);
    const canRenew=!!expired&&invoice?.onlineEligible&&!invoice.needsReview&&!processing;
    const onlineButton=$('[data-payment-online]');
    onlineButton.disabled=busy||loading||processing||(!canRenew&&(!!expired||['CANCELLED','EXPIRED','FAILED'].includes(current?.providerStatus)));
    onlineButton.textContent=busy&&busyAction==='renew-online'?'Đang làm mới mã QR…':busy&&busyAction==='online'?'Đang tạo phiên payOS…':canRenew?'Làm mới mã QR':'Thanh toán online bằng payOS';
    $('[data-payment-refresh]').disabled=busy||loading;
  }
  function checkout(i) {
    const current=i.currentOnline;
    if(!current?.checkoutUrl || !i.onlineEligible || ['PAID','PROCESSING','UNDERPAID'].includes(current.providerStatus)) return '';
    try {const url=new URL(current.checkoutUrl);return url.protocol==='https:'?url.href:'';} catch {return '';}
  }
  function paint(i) {
    invoice=i;
    // A previous request/promotion error must not mask a confirmed receipt.
    if(i.status==='paid'&&!i.needsReview)notice='';
    $('[data-invoice-empty]').hidden=true; $('[data-invoice-content]').hidden=false;
    $('[data-invoice-content]').setAttribute('aria-busy',String(busy||loading));
    for(const [key,value] of Object.entries({service:i.service,code:invoiceCode(i.id),status:i.statusLabel,issued:timestamp(i.createdAt),appointment:`${appointmentCode(i.appointmentId)} · ${appointmentDate(i)}`,employee:i.employee,price:money(i.priceSnapshot),subtotal:money(i.subtotal),promotion:i.promotion||'Không áp dụng',discount:money(i.discount),total:money(i.total)})) $(`[data-invoice-${key}]`).textContent=value;
    records=records.map(row=>row.id===i.id?i:row);renderCards();
    $('[data-invoice-promo]').hidden=!i.paymentAllowed;
    promo.disabled=busy||loading||!i.promotionEditable;
    $('[data-promo-apply]').hidden=!i.promotionEditable;
    $('[data-promo-apply]').disabled=busy||loading;
    $('[data-promo-remove]').hidden=!i.promotionEditable||!i.promotion;
    $('[data-promo-remove]').disabled=busy||loading;
    $('[data-payment-edit]').hidden=i.promotionEditable||!i.paymentAllowed;
    $('[data-payment-edit]').disabled=busy||loading;
    $('#invoice-promo-status').textContent=promotionMessage || (i.promotionEditable
      ? [options.length?'Chọn ưu đãi phù hợp hoặc không áp dụng khuyến mãi.':'Hiện chưa có khuyến mãi phù hợp với hóa đơn này.',
          ...unavailable.map(p=>`${p.code}: ${p.reason}`)].join(' ')
      : 'Nhấn Đổi khuyến mãi để chọn lại ưu đãi trước khi thanh toán.');
    if(i.promotion && i.promotionUsage?.limit && i.status==='unpaid')
      $('#invoice-promo-status').textContent+=' Mã đang giữ một lượt cho hóa đơn này; chỉ tính đã sử dụng khi thanh toán thành công. Xóa mã hoặc hủy lịch hợp lệ để trả lượt.';
    const selectedSpa=i.paymentPreference==='spa';
    $('[data-payment-options]').hidden=!i.paymentAllowed||i.status!=='unpaid'||(selectedSpa&&!i.onlineEligible);
    $('[data-payment-spa]').hidden=selectedSpa;
    $('[data-payment-online]').hidden=!i.onlineEligible;
    const processing=['PAID','PROCESSING','UNDERPAID'].includes(i.currentOnline?.providerStatus);
    $('[data-payment-refund]').hidden=i.status!=='paid'||i.needsReview||!!i.currentOnline;
    $('[data-payment-online]').disabled=busy||loading||processing;
    $('[data-payment-online]').textContent=busy&&busyAction==='online'?'Đang tạo phiên payOS…':'Thanh toán online bằng payOS';
    $('[data-payment-spa]').disabled=busy||loading||processing;
    const url=checkout(i);
    $('[data-payment-qr]').hidden=!url;
    $('[data-payment-checkout]').removeAttribute('href');
    if(url) $('[data-payment-checkout]').href=url;
    $('[data-payment-amount]').textContent=money(i.currentOnline?.amount||i.total);
    const paid=i.payments.find(p=>p.status==='success'&&!p.requiresReview);
    $('[data-payment-receipt]').hidden=!paid;
    if(paid){$('[data-payment-method]').textContent=paid.method==='spa'?'Trực tiếp tại Spa':'payOS';$('[data-payment-date]').textContent=timestamp(paid.paidAt);$('[data-payment-reference]').textContent=paid.reference;}
    const message=i.needsReview?'Khoản thanh toán cần Spa đối soát. Chưa thể thay đổi ưu đãi hoặc thanh toán thêm.'
      :i.status==='paid'?'Đã ghi nhận thanh toán.':i.status==='cancelled'?'Hóa đơn đã hủy.'
      :!i.paymentAllowed?'Lịch hẹn chưa được xác nhận hoặc đã hủy; không được áp dụng khuyến mãi hay thanh toán.'
      :processing?'payOS đang xử lý hoặc đã nhận tiền. Vui lòng chờ Spa xác minh; không thanh toán thêm.'
      :i.currentOnline?(url?'Phiên payOS đã sẵn sàng. Quét QR bên dưới hoặc mở trang thanh toán payOS. Hóa đơn vẫn chưa thanh toán.':'Phiên payOS đang chờ xác minh hoặc đã hết hạn. Nhấn Kiểm tra trạng thái phiên để đối soát trước khi tạo mã mới.')
      :i.appointmentStatus==='completed'&&i.status==='unpaid'
        ?`Chưa ghi nhận thanh toán. Nếu bạn đã trả tiền, vui lòng liên hệ Spa để kiểm tra và xác nhận.${selectedSpa?' Bạn đã chọn thanh toán tại Spa; lựa chọn này chưa xác nhận đã thu tiền.':''}`
      :selectedSpa?`Bạn đã chọn thanh toán tại Spa: ${money(i.total)}. Chưa ghi nhận thanh toán; chỉ Admin xác nhận sau khi Spa nhận đủ tiền.`
      :i.onlineEligible&&i.payosConfigured===false?'Thanh toán payOS chưa được cấu hình. Vui lòng chọn thanh toán tại Spa.'
      :i.onlineEligible?'Nhấn Thanh toán online bằng payOS để tạo phiên và mở trang QR thanh toán.':'Vui lòng thanh toán trực tiếp tại Spa.';
    const feedback=$('[data-payment-message]');
    feedback.setAttribute('role',notice?'alert':'status');
    feedback.textContent=notice||(busy&&busyAction==='renew-online'?'Đang kiểm tra phiên cũ và tạo mã QR mới trên hóa đơn này…':busy&&busyAction==='online'?'Đang tạo phiên payOS, vui lòng chờ. Chưa ghi nhận thanh toán.':message);
    drawQr();
  }
  function paintPromotions() {
    promo.replaceChildren(new Option('Không áp dụng khuyến mãi',''),...options.map(p=>new Option(`${p.code} · ${p.name} · giảm ${money(p.discount)}`,p.code)));
    // Retain a stored historical code even if the promotion has since expired.
    if(invoice?.promotion&&!options.some(p=>p.code===invoice.promotion))promo.add(new Option(`${invoice.promotion} · đã lưu trên hóa đơn`,invoice.promotion));
    promo.value=invoice?.promotion||'';
  }
  async function loadPromotions(id,version){
    const result=await api(`/api/billing/${id}/promotions/`);
    if(version!==revision||invoice?.id!==id)return;
    options=result.items;unavailable=result.unavailable||[];promotionMessage=result.message||'';paintPromotions();paint(invoice);
  }
  function schedule(){clearTimeout(timer);if(invoice?.status==='unpaid'&&!invoice.needsReview&&(invoice.currentOnline||invoice.paymentPreference))timer=setTimeout(poll,10000);}
  async function open(id,focus=false){
    clearTimeout(timer);const version=++revision;notice='';loading=true;retryId=id;clearDetail();renderCards();
    $('#invoice-retry').hidden=true;$('[data-invoice-empty]').hidden=true;
    $('[data-invoice-count]').textContent='Đang tải chi tiết hóa đơn…';
    try{
      const result=await api(`/api/billing/${id}/`);
      if(version!==revision)return;
      paint(result.item);paintPromotions();updateUrl();
      try{await loadPromotions(result.item.id,version);}catch(e){if(version===revision)error(e);}
      if(version!==revision)return;
      $('[data-invoice-count]').textContent=`${records.length} / ${total} hóa đơn · Trang ${page} / ${pages}`;
      if(focus){$('#invoice-title').focus({preventScroll:true});$('#invoice-detail').scrollIntoView({block:'start',behavior:'instant'});}
    }catch(e){
      if(version!==revision)return;
      clearDetail();renderCards();updateUrl();error(e);$('#invoice-retry').hidden=false;
    }finally{if(version===revision){loading=false;if(invoice)paint(invoice);else syncControls();schedule();}}
  }
  async function load(preferred=invoice?.id){
    clearTimeout(timer);const version=++revision;notice='';loading=true;retryId=null;clearDetail();records=[];renderCards();
    $('[data-invoice-count]').textContent='Đang tải danh sách hóa đơn…';
    $('[data-invoice-empty]').hidden=true;$('#invoice-retry').hidden=true;
    try{
      const result=await api('/api/billing/?'+new URLSearchParams({page,status:appliedStatus,search:appliedSearch}));
      if(version!==revision)return;
      page=result.page;pages=result.pages;total=result.total;records=result.items;renderCards();
      $('#invoice-page').textContent=`${page} / ${pages}`;
      if(records.length){const selected=records.find(i=>i.id===preferred)||records[0];await open(selected.id);}
      else{
        $('[data-invoice-count]').textContent='0 hóa đơn';$('[data-invoice-empty]').hidden=false;
        $('[data-invoice-empty]').textContent='Chưa có hóa đơn phù hợp. Hóa đơn được tạo khi Spa xác nhận lịch hẹn.';updateUrl();
      }
    }catch(e){
      if(version!==revision)return;
      $('#invoice-page').textContent='';$('[data-invoice-count]').textContent='Không thể tải danh sách hóa đơn.';
      error(e);$('#invoice-retry').hidden=false;
    }finally{if(version===revision){loading=false;syncControls();}}
  }
  function error(error){notice=error.message;if(!invoice)$('[data-invoice-count]').textContent='Không thể tải hóa đơn.';const feedback=$('[data-payment-message]');feedback.setAttribute('role','alert');feedback.textContent=notice;if(invoice)feedback.focus();else{const empty=$('[data-invoice-empty]');empty.hidden=false;empty.setAttribute('role','alert');empty.textContent=notice;empty.focus();}}
  async function action(name,data={}){
    if(busy||loading||!invoice)return;
    if(name==='renew-online'&&(!qrExpired||!invoice.onlineEligible||invoice.needsReview||invoice.status!=='unpaid'||['PAID','PROCESSING','UNDERPAID'].includes(invoice.currentOnline?.providerStatus)))return;
    busy=true;busyAction=name;clearTimeout(timer);const id=invoice.id,version=++revision;notice='';paint(invoice);
    try{
      const result=await api(`/api/billing/${id}/${name}/`,data);
      const fresh=result.item?result:await api(`/api/billing/${id}/`);
      if(version!==revision)return;
      paint(fresh.item);await loadPromotions(id,version);
      if(name==='edit-promotion')promo.focus();
      if((name==='online'||name==='renew-online')&&checkout(invoice))$('[data-payment-checkout]').focus();
    }catch(e){
      // A failed create request can still reserve an order. Re-read local state
      // without calling the provider or submitting a second creation request.
      try{const fresh=await api(`/api/billing/${id}/`);if(version===revision)paint(fresh.item);}catch{}
      error(e);
      if(name==='renew-online')$('[data-payment-message]').scrollIntoView({block:'center'});
    }
    finally{busy=false;busyAction='';if(invoice)paint(invoice);if(name==='edit-promotion'&&invoice?.promotionEditable)promo.focus();schedule();}
  }
  async function poll(){
    if(polling||busy||loading||!invoice)return;
    if(document.hidden){schedule();return;}
    polling=true;const id=invoice.id,version=revision;
    try{
      // Automatic refresh reads MySQL only; provider checks require a user action.
      const fresh=await api(`/api/billing/${id}/`);
      if(version===revision){if(fresh.item.status==='paid')notice='';paint(fresh.item);}
    }catch(e){
      if(version===revision){
        // A signed webhook may already have arrived while a provider status call timed out.
        try{const fresh=await api(`/api/billing/${id}/`);if(version===revision)paint(fresh.item);}catch{}
        if(invoice?.status!=='paid')error(e);
      }
    }finally{polling=false;schedule();}
  }
  list.addEventListener('click',e=>{const button=e.target.closest('[data-invoice-open]');if(button&&!busy&&!loading)open(Number(button.dataset.invoiceOpen),true);});
  $('#invoice-filter').addEventListener('submit',e=>{e.preventDefault();if(!busy&&!loading){page=1;appliedSearch=$('#invoice-search').value.trim();appliedStatus=$('#invoice-status-filter').value;load();}});
  $('#invoice-reset').onclick=()=>{if(!busy&&!loading){page=1;appliedSearch='';appliedStatus='';$('#invoice-search').value='';$('#invoice-status-filter').value='';load();}};
  $('#invoice-prev').onclick=()=>{if(!busy&&!loading&&page>1){page--;load();}};
  $('#invoice-next').onclick=()=>{if(!busy&&!loading&&page<pages){page++;load();}};
  $('#invoice-retry').onclick=()=>{if(!busy&&!loading){if(retryId)open(retryId);else load();}};
  $('[data-invoice-promo]').addEventListener('submit',e=>{e.preventDefault();action('promotion',{code:promo.value});});
  $('[data-promo-remove]').onclick=()=>action('remove-promotion');
  $('[data-payment-edit]').onclick=()=>action('edit-promotion');
  $('[data-payment-online]').onclick=()=>action(qrExpired?'renew-online':'online');
  $('[data-payment-spa]').onclick=()=>action('select-spa');
  $('[data-payment-refresh]').onclick=()=>action('refresh-online');
  let countdown=setInterval(drawQr,250);
  window.addEventListener('pageshow',()=>{clearInterval(countdown);countdown=setInterval(drawQr,250);if(invoice)poll();});
  window.addEventListener('focus',()=>{if(invoice&&!busy)poll();});
  document.addEventListener('visibilitychange',()=>{if(!document.hidden&&invoice&&!busy)poll();});
  window.addEventListener('pagehide',()=>{clearTimeout(timer);clearInterval(countdown);});
  await load(initialId);
})();
