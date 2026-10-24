window.spaLive = (() => {
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const money = value => new Intl.NumberFormat('vi-VN').format(value || 0) + ' VND';
  async function api(url, data) {
    const started=performance.now();
    const options = {credentials:'same-origin', headers:{Accept:'application/json'}};
    if (data !== undefined) {
      options.method='POST'; options.body=new URLSearchParams(data);
      options.headers['X-CSRFToken']=document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    }
    const controller=new AbortController();options.signal=controller.signal;
    const timeout=setTimeout(()=>controller.abort(),25000);
    let response;
    try{response=await fetch(url,options);}
    catch(error){throw Error(error.name==='AbortError'?'Yêu cầu quá thời gian chờ. Hãy tải lại hóa đơn để kiểm tra phiên đã tạo trước khi thử lại.':'Không thể kết nối máy chủ. Hãy kiểm tra mạng và tải lại hóa đơn; chưa xác nhận thanh toán.');}
    finally{clearTimeout(timeout);}
    if(response.status===403)throw Error('Phiên bảo mật đã hết hạn hoặc bạn không có quyền. Vui lòng tải lại trang và đăng nhập lại.');
    let body; try { body=await response.json(); } catch { throw Error('Không thể xử lý yêu cầu. Vui lòng tải lại hoặc đăng nhập lại.'); }
    if (!response.ok) throw Error(body.error || Object.values(body.errors || {}).flat().join(' ') || 'Yêu cầu không được phép.');
    // Subtract the whole request duration conservatively; never trust device wall time.
    for(const item of body.item?[body.item]:(body.items||[])){
      if(item.currentOnline){
        item.currentOnline.remainingSeconds=Math.max(0,item.currentOnline.remainingSeconds-(performance.now()-started)/1000);
        item.currentOnline.receivedAt=performance.now();
      }
    }
    return body;
  }
  const date = value => value ? new Date(value).toLocaleString('vi-VN',{timeZone:'Asia/Ho_Chi_Minh'}) : '—';
  return {api,escape,money,date};
})();
