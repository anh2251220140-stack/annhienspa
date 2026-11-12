(async()=>{
  const {api,escape:e}=window.spaLive,$=s=>document.querySelector(s);
  const section=$('[data-service-reviews]');if(!section)return;
  const params=new URLSearchParams(location.search);
  const id=params.get('id');
  const unavailable=section.hasAttribute('data-service-unavailable');
  let page=1,own;
  const pendingReplies=new Set();
  const stars=n=>`<span class="review-stars" role="img" aria-label="${n} trên 5 sao">${[1,2,3,4,5].map(x=>`<span data-selected="${x<=n}">${window.spaIcon('star')}</span>`).join('')}</span>`;
  function reviewTime(value, withTime=false){
    const options={timeZone:'Asia/Ho_Chi_Minh',day:'2-digit',month:'2-digit',year:'numeric'};
    const date=new Date(value);
    const label=withTime
      ? date.toLocaleString('vi-VN',{...options,hour:'2-digit',minute:'2-digit'})
      : date.toLocaleDateString('vi-VN',options);
    return `<time datetime="${e(value)}">${e(label)}</time>`;
  }
  function replyThread(replies){
    if(!replies.length)return '';
    return `<section class="review-thread"><h3>Phản hồi</h3>
      <div class="review-thread-list" role="region" aria-label="Danh sách phản hồi" tabindex="0">${replies.map(reply=>`
        <div class="review-reply"><strong>${e(reply.name)}</strong>
          ${reply.role==='Admin'?'<span class="review-reply-role">Quản trị viên</span>':
            reply.role==='User'?'<span class="review-reply-role">Chủ đánh giá</span>':''}
          ${reviewTime(reply.createdAt,true)}<p>${e(reply.content)}</p></div>`).join('')}</div></section>`;
  }
  function reviewCard(r){
    const initials=r.name.trim().split(/\s+/).slice(-2).map(part=>part.charAt(0)).join('').toLocaleUpperCase('vi');
    return `<article class="review-item">
      <div class="review-byline"><span class="account-avatar" aria-hidden="true">${e(initials)}</span>
        <div><strong>${e(r.name)}</strong>${stars(r.rating)}</div>${reviewTime(r.createdAt)}</div>
      ${r.comment ? `<p class="review-comment">${e(r.comment)}</p>` : ''}
      <div data-service-reply-thread>${replyThread(r.replies)}</div>
      ${r.replyUrl ? `<form class="service-reply-form" method="post" data-reply-url="${e(r.replyUrl)}">
        <label>Nội dung phản hồi<textarea name="content" rows="3" maxlength="2000" required></textarea></label>
        <button type="submit" class="button filled small">Gửi phản hồi</button>
        <p class="review-note" data-reply-status role="status"></p>
      </form>` : ''}
    </article>`;
  }
  async function load(){
    const d=await api(`/api/reviews/services/${id}/?page=${page}`);
    $('[data-review-average]').textContent=d.total?Number(d.average).toFixed(1)+' / 5':'— / 5';$('[data-review-count]').textContent=`${d.total} đánh giá`;
    $('#review-list').innerHTML=d.items.map(reviewCard).join('')||'<div class="review-empty"><p>Chưa có đánh giá cho liệu trình này.</p></div>';
    const pagination=$('#service-review-pages');
    pagination.hidden=d.pages<=1;
    pagination.innerHTML=pagination.hidden?'':`<button class="button small" type="button" data-review-nav="${page-1}" ${page===1?'disabled':''}>Trước</button><span>${page} / ${d.pages}</span><button class="button small" type="button" data-review-nav="${page+1}" ${page===d.pages?'disabled':''}>Sau</button>`;
  }
  function showHistoricalReview(review) {
    $('#review-list').innerHTML=review ? reviewCard({
      ...review,
      name:review.customer,
      replies:review.replies.map(reply=>({...reply,name:reply.role==='Admin'?'An Nhiên Spa':review.customer})),
      replyUrl:`/api/reviews/${review.id}/replies/`
    }) : '';
  }
  const form=$('#review-form'),status=$('[data-review-status]');
  section.addEventListener('submit',async event=>{
    const replyForm=event.target.closest('[data-reply-url]');
    if(!replyForm)return;
    event.preventDefault();
    const url=replyForm.dataset.replyUrl;
    if(pendingReplies.has(url))return;
    const field=replyForm.elements.content;
    const button=replyForm.querySelector('[type=submit]');
    const feedback=replyForm.querySelector('[data-reply-status]');
    const content=field.value.trim();
    if(!content || content.length>field.maxLength){
      feedback.textContent='Vui lòng nhập phản hồi từ 1 đến 2.000 ký tự.';
      field.focus();
      return;
    }
    pendingReplies.add(url);
    button.disabled=true;
    field.readOnly=true;
    feedback.textContent='Đang gửi phản hồi…';
    try{
      const {item}=await api(url,{content});
      const replies=item.replies.map(reply=>({...reply,name:reply.role==='Admin'?'An Nhiên Spa':item.customer}));
      const current=section.querySelector(`[data-reply-url="${CSS.escape(url)}"]`);
      if(current){
        const thread=current.closest('.review-item').querySelector('[data-service-reply-thread]');
        thread.innerHTML=replyThread(replies);
        const list=thread.querySelector('.review-thread-list');
        if(list)list.scrollTop=list.scrollHeight;
        if(current===replyForm)replyForm.reset();
        current.querySelector('[data-reply-status]').textContent='Đã gửi phản hồi.';
      }
    }catch(error){
      feedback.textContent=/hóa đơn/i.test(error.message)
        ? 'Chưa xác nhận được phản hồi. Vui lòng tải lại để kiểm tra trước khi gửi lại.' : error.message;
    }finally{
      pendingReplies.delete(url);
      button.disabled=false;
      field.readOnly=false;
    }
  });
  const appointment=form.elements.appointment;
  const open=$('[data-review-open]');
  const submit=form.querySelector('[type="submit"]');
  const selectedReview=()=>own?.items.find(review=>review.appointmentId===Number(appointment.value) && review.serviceId===Number(id));
  function showRating(){
    const rating=Number(form.elements.rating.value);
    form.querySelectorAll('.review-rating label').forEach(label=>{
      label.dataset.selected=Number(label.querySelector('input').value)<=rating;
    });
  }
  function fill(){
    const r=selectedReview();
    form.elements.rating.value=r?.rating||'';
    form.elements.message.value=r?.comment||'';
    submit.textContent=r?'Lưu thay đổi':'Gửi đánh giá';
    showRating();
  }
  section.addEventListener('click',async event=>{const b=event.target.closest('[data-review-nav]');if(b&&!b.disabled){page=Number(b.dataset.reviewNav);try{await load();}catch(ex){status.textContent=ex.message;}}});
  function setEditorOpen(expanded){
    form.hidden=!expanded;
    open.setAttribute('aria-expanded',String(expanded));
    if(expanded)fill();
  }
  open.onclick=()=>setEditorOpen(true);
  $('[data-review-cancel]').onclick=()=>{
    setEditorOpen(false);
    open.focus();
  };
  appointment.onchange=fill;
  form.querySelectorAll('[data-rating-icon]').forEach(n=>n.innerHTML=window.spaIcon('star'));
  form.addEventListener('change',event=>{
    if(event.target.name==='rating')showRating();
  });
  form.addEventListener('submit',async event=>{
    event.preventDefault();
    if(submit.disabled || !form.reportValidity())return;
    submit.disabled=true;
    status.textContent='';
    try{
      const {item}=await api(`/api/reviews/appointments/${appointment.value}/`,{
        rating:form.elements.rating.value,comment:form.elements.message.value
      });
      own.items=[item,...own.items.filter(review=>review.appointmentId!==item.appointmentId)];
      if(appointment.disabled)open.textContent='Chỉnh sửa đánh giá';
      setEditorOpen(false);
      open.focus();
      status.textContent='Đã lưu đánh giá.';
      try{
        if(unavailable)showHistoricalReview(item);
        else await load();
      }catch{
        status.textContent='Đã lưu đánh giá. Vui lòng tải lại để cập nhật danh sách.';
      }
    }catch(error){
      status.textContent=/hóa đơn/i.test(error.message)
        ? 'Chưa xác nhận được đánh giá. Vui lòng tải lại để kiểm tra trước khi gửi lại.'
        : error.message;
    }finally{
      submit.disabled=false;
    }
  });
  try{
    if(!unavailable)await load();
    if(window.spaAuth?.getSession()?.role==='User'){
      own=await api('/api/reviews/');
      const eligible=own.eligible.filter(a=>a.serviceId===Number(id));
      const pinned=eligible.find(item=>String(item.id)===params.get('appointment'));
      if(unavailable && !pinned)return;
      appointment.replaceChildren(...eligible.map(item=>new Option(
        window.spaAppointmentCode(item.id)+' · '+item.date.split('-').reverse().join('/'),item.id
      )));
      open.hidden=!eligible.length;
      if(pinned){
        appointment.value=pinned.id;
        appointment.disabled=true;
        $('[data-review-appointment]').hidden=true;
        const summary=$('[data-review-appointment-summary]');
        summary.textContent=`Cuộc hẹn · ${window.spaAppointmentCode(pinned.id)} · ${pinned.date.split('-').reverse().join('/')}`;
        summary.hidden=false;
        if(selectedReview())open.textContent='Chỉnh sửa đánh giá';
        if(unavailable){
          section.querySelector('.review-overview').hidden=true;
          $('[data-review-eligibility]').hidden=true;
          $('#service-reviews-title').textContent='Đánh giá của bạn';
          showHistoricalReview(selectedReview());
          section.hidden=false;
        }
        setEditorOpen(true);
        form.elements.message.focus({preventScroll:true});
        form.scrollIntoView({block:'nearest'});
      }else if(params.has('appointment')){
        status.textContent='Lịch hẹn này chưa đủ điều kiện để viết hoặc sửa đánh giá.';
      }
    }
  }catch(ex){status.textContent=ex.message;}
})();
