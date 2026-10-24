(async () => {
  'use strict';
  const {api,escape:esc,money,date}=window.spaLive;
  const $=selector=>document.querySelector(selector);
  const select=$('[data-invoice-select]'), promo=$('#invoice-promo-code');
  let invoice=null, page=1, pages=1, busy=false, busyAction='', revision=0, timer, polling=false, notice='';
  let options=[], unavailable=[], promotionMessage='';
  const initialId=new URLSearchParams(location.search).get('id');
  let clockKey='',deadline=0;
  function drawQr() {
    const current=invoice?.currentOnline;
    const key=current?`${invoice.id}:${current.orderCode}:${current.serverNow}`:'';
    if(key!==clockKey){clockKey=key;deadline=(current?.receivedAt||performance.now())+Math.max(0,current?.remainingSeconds||0)*1000;}
    const left=current?Math.max(0,Math.ceil((deadline-performance.now())/1000)):0;
    const expired=current&&(current.expired||left===0);
    const url=!expired&&invoice?checkout(invoice):'';
    const image=$('[data-payment-qr-image]');
    const src=!expired&&url?current?.qrImage:'';
    $('[data-payment-qr]').hidden=!current||invoice.status!=='unpaid'||invoice.needsReview;
    image.hidden=!src;
    if(src){if(image.getAttribute('src')!==src)image.src=src;}else image.removeAttribute('src');
    $('[data-payment-qr-help]').hidden=!src;
    $('[data-payment-countdown]').textContent=current?`${String(Math.floor(left/60)).padStart(2,'0')}:${String(left%60).padStart(2,'0')}`:'';
    $('[data-payment-qr-status]').textContent=expired?'Mã QR đã hết hạn. Cần kiểm tra trạng thái phiên cũ trước khi tạo mã mới.':src?'Đang chờ thanh toán. Quét QR không tự xác nhận đã thanh toán.':url?'Không có dữ liệu QR hợp lệ của phiên này. Vui lòng mở trang thanh toán payOS.':'Phiên chưa sẵn sàng hoặc cần đối soát. Không thanh toán thêm trước khi kiểm tra trạng thái.';
    $('[data-payment-qr] h3').textContent=expired?'Mã QR đã hết hạn':'Đang chờ thanh toán';
    if(expired&&!notice)$('[data-payment-message]').textContent='Mã QR đã hết hạn. Nhấn Kiểm tra trạng thái phiên để đối soát; hóa đơn chưa được ghi nhận thanh toán.';
    const link=$('[data-payment-checkout]');link.hidden=!url;
    if(url)link.href=url;else link.removeAttribute('href');
    $('[data-payment-online]').disabled=busy||!!expired||['PAID','PROCESSING','UNDERPAID','CANCELLED','EXPIRED','FAILED'].includes(current?.providerStatus);
    $('[data-payment-refresh]').disabled=busy;
  }
  function checkout(i) {
    const current=i.currentOnline;
    if(!current?.checkoutUrl || !i.onlineEligible || ['PAID','PROCESSING','UNDERPAID'].includes(current.providerStatus)) return '';
    try {const url=new URL(current.checkoutUrl);return url.protocol==='https:'?url.href:'';} catch {return '';}
  }
  function paint(i) {
    invoice=i;
    $('[data-invoice-empty]').hidden=true; $('[data-invoice-content]').hidden=false;
    $('[data-invoice-content]').setAttribute('aria-busy',String(busy));
    for(const [key,value] of Object.entries({service:i.service,code:`HD-${i.id}`,status:i.statusLabel,appointment:`LH-${i.appointmentId} · ${i.date} ${i.time}`,employee:i.employee,price:money(i.priceSnapshot),subtotal:money(i.subtotal),promotion:i.promotion||'Không áp dụng',discount:money(i.discount),total:money(i.total)})) $(`[data-invoice-${key}]`).textContent=value;
    if(!Array.from(select.options).some(o=>o.value===String(i.id))) select.add(new Option(`HD-${i.id} · ${i.service} · ${i.statusLabel}`,i.id));
    select.value=String(i.id);select.disabled=busy;
    $('[data-invoice-promo]').hidden=!i.paymentAllowed;
    promo.disabled=busy||!i.promotionEditable;
    $('[data-promo-apply]').hidden=!i.promotionEditable;
    $('[data-promo-apply]').disabled=busy;
    $('[data-promo-remove]').hidden=!i.promotionEditable||!i.promotion;
    $('[data-promo-remove]').disabled=busy;
    $('[data-payment-edit]').hidden=i.promotionEditable||!i.paymentAllowed;
    $('[data-payment-edit]').disabled=busy;
    $('#invoice-promo-status').textContent=promotionMessage || (i.promotionEditable
      ? [options.length?'Chọn ưu đãi phù hợp hoặc không áp dụng khuyến mãi.':'Hiện chưa có khuyến mãi phù hợp với hóa đơn này.',
          ...unavailable.map(p=>`${p.code}: ${p.reason}`)].join(' ')
      : 'Nhấn Đổi khuyến mãi để chọn lại ưu đãi trước khi thanh toán.');
    if(i.promotion && i.promotionUsage?.limit && i.status==='unpaid')
      $('#invoice-promo-status').textContent+=' Mã đang giữ một lượt cho hóa đơn này; chỉ tính đã sử dụng khi thanh toán thành công. Xóa mã hoặc hủy lịch hợp lệ để trả lượt.';
    $('[data-payment-options]').hidden=!i.paymentAllowed;
    $('[data-payment-online]').hidden=!i.onlineEligible;
    const processing=['PAID','PROCESSING','UNDERPAID'].includes(i.currentOnline?.providerStatus);
    $('[data-payment-online]').disabled=busy||processing;
    $('[data-payment-online]').textContent=busy&&busyAction==='online'?'Đang tạo phiên payOS…':'Thanh toán online bằng payOS';
    $('[data-payment-spa]').disabled=busy||processing;
    const url=checkout(i);
    $('[data-payment-qr]').hidden=!url;
    $('[data-payment-checkout]').removeAttribute('href');
    if(url) $('[data-payment-checkout]').href=url;
    $('[data-payment-amount]').textContent=money(i.currentOnline?.amount||i.total);
    const paid=i.payments.find(p=>p.status==='success'&&!p.requiresReview);
    $('[data-payment-receipt]').hidden=!paid;
    if(paid){$('[data-payment-method]').textContent=paid.method==='spa'?'Trực tiếp tại Spa':'payOS';$('[data-payment-date]').textContent=date(paid.paidAt);$('[data-payment-reference]').textContent=paid.reference;}
    const message=i.needsReview?'Khoản thanh toán cần Spa đối soát. Chưa thể thay đổi ưu đãi hoặc thanh toán thêm.'
      :i.status==='paid'?'Đã ghi nhận thanh toán.':i.status==='cancelled'?'Hóa đơn đã hủy.'
      :!i.paymentAllowed?'Lịch hẹn chưa được xác nhận hoặc đã hủy; không được áp dụng khuyến mãi hay thanh toán.'
      :processing?'payOS đang xử lý hoặc đã nhận tiền. Vui lòng chờ Spa xác minh; không thanh toán thêm.'
      :i.currentOnline?(url?'Phiên payOS đã sẵn sàng. Quét QR bên dưới hoặc mở trang thanh toán payOS. Hóa đơn vẫn chưa thanh toán.':'Phiên payOS đang chờ xác minh hoặc đã hết hạn. Nhấn Kiểm tra trạng thái phiên để đối soát trước khi tạo mã mới.')
      :i.paymentPreference==='spa'?`Bạn đã chọn thanh toán trực tiếp tại Spa: ${money(i.total)}. Spa sẽ ghi nhận sau khi nhận đủ tiền.`
      :i.onlineEligible&&i.payosConfigured===false?'Thanh toán payOS chưa được cấu hình. Vui lòng chọn thanh toán tại Spa.'
      :i.onlineEligible?'Nhấn Thanh toán online bằng payOS để tạo phiên và mở trang QR thanh toán.':'Vui lòng thanh toán trực tiếp tại Spa.';
    const feedback=$('[data-payment-message]');
    feedback.setAttribute('role',notice?'alert':'status');
    feedback.textContent=notice||(busy&&busyAction==='online'?'Đang tạo phiên payOS, vui lòng chờ. Chưa ghi nhận thanh toán.':message);
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
  async function open(id){
    clearTimeout(timer);const version=++revision;notice='';
    const result=await api(`/api/billing/${id}/`);
    if(version!==revision)return;
    options=[];unavailable=[];promotionMessage='';paint(result.item);paintPromotions();
    const url=new URL(location.href);url.searchParams.set('id',result.item.id);history.replaceState(null,'',url);
    await loadPromotions(result.item.id,version);schedule();
  }
  async function load(){
    clearTimeout(timer);const version=++revision;notice='';
    const result=await api('/api/billing/?'+new URLSearchParams({page,status:$('#invoice-status-filter').value,search:$('#invoice-search').value}));
    if(version!==revision)return;
    page=result.page;pages=result.pages;
    select.innerHTML=result.items.map(i=>`<option value="${i.id}">HD-${i.id} · ${esc(i.service)} · ${esc(i.statusLabel)}</option>`).join('');
    $('[data-invoice-picker]').hidden=!result.items.length;
    $('#invoice-page').textContent=`${page} / ${pages}`;
    $('#invoice-prev').disabled=page<=1;$('#invoice-next').disabled=page>=pages;
    if(result.items.length)await open(result.items[0].id);
    else {invoice=null;$('[data-invoice-content]').hidden=true;$('[data-invoice-empty]').hidden=false;$('[data-invoice-empty]').textContent='Chưa có hóa đơn phù hợp. Hóa đơn được tạo khi Spa xác nhận lịch hẹn.';}
  }
  function error(error){notice=error.message;const feedback=$('[data-payment-message]');feedback.setAttribute('role','alert');feedback.textContent=notice;feedback.focus();if(!invoice){$('[data-invoice-empty]').hidden=false;$('[data-invoice-empty]').textContent=notice;}}
  async function action(name,data={}){
    if(busy||!invoice)return;
    busy=true;busyAction=name;clearTimeout(timer);const id=invoice.id,version=++revision;notice='';paint(invoice);
    try{
      const result=await api(`/api/billing/${id}/${name}/`,data);
      const fresh=result.item?result:await api(`/api/billing/${id}/`);
      if(version!==revision)return;
      paint(fresh.item);await loadPromotions(id,version);
      if(name==='edit-promotion')promo.focus();
      if(name==='online'&&checkout(invoice))$('[data-payment-checkout]').focus();
    }catch(e){
      // A failed create request can still reserve an order. Re-read local state
      // without calling the provider or submitting a second creation request.
      try{const fresh=await api(`/api/billing/${id}/`);if(version===revision)paint(fresh.item);}catch{}
      error(e);
    }
    finally{busy=false;busyAction='';if(invoice)paint(invoice);if(name==='edit-promotion'&&invoice?.promotionEditable)promo.focus();schedule();}
  }
  async function poll(){
    if(polling||busy||!invoice)return;
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
  select.addEventListener('change',e=>{if(!busy)open(e.target.value).catch(error);});
  $('#invoice-filter').addEventListener('submit',e=>{e.preventDefault();if(!busy){page=1;load().catch(error);}});
  $('#invoice-prev').onclick=()=>{if(!busy){page--;load().catch(error);}};
  $('#invoice-next').onclick=()=>{if(!busy){page++;load().catch(error);}};
  $('[data-invoice-promo]').addEventListener('submit',e=>{e.preventDefault();action('promotion',{code:promo.value});});
  $('[data-promo-remove]').onclick=()=>action('remove-promotion');
  $('[data-payment-edit]').onclick=()=>action('edit-promotion');
  $('[data-payment-online]').onclick=()=>action('online');
  $('[data-payment-spa]').onclick=()=>action('select-spa');
  $('[data-payment-refresh]').onclick=()=>action('refresh-online');
  let countdown=setInterval(drawQr,250);
  window.addEventListener('pageshow',()=>{clearInterval(countdown);countdown=setInterval(drawQr,250);if(invoice)poll();});
  window.addEventListener('focus',()=>{if(invoice&&!busy)poll();});
  document.addEventListener('visibilitychange',()=>{if(!document.hidden&&invoice&&!busy)poll();});
  window.addEventListener('pagehide',()=>{clearTimeout(timer);clearInterval(countdown);});
  try{await load();if(initialId&&String(invoice?.id)!==initialId)await open(initialId);}
  catch(e){invoice=null;$('[data-invoice-content]').hidden=true;error(e);}
})();
