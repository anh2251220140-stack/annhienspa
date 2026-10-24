(async () => {
  const {api,escape:e,date}=window.spaLive, $=s=>document.querySelector(s);
  const admin=Boolean($('[data-admin-quality="reviews"]'));
  let data, page=1;
  const stars=n=>`<span class="review-stars" aria-label="${n} trên 5 sao">${[1,2,3,4,5].map(x=>`<span data-selected="${x<=n}">${window.spaIcon('star')}</span>`).join('')}</span>`;
  const replies=r=>r.replies.map(x=>`<div class="review-reply"><strong>${e(x.name)} · ${x.role==='Admin'?'An Nhiên Spa':'Khách hàng'}</strong><small> · ${e(date(x.createdAt))}</small><p>${e(x.content)}</p></div>`).join('');
  const replyForm=r=>`<form data-reply="${r.id}" class="phase4-form"><label>Phản hồi<textarea name="content" maxlength="2000" required></textarea></label><button class="${admin?'admin-button':'button'}" type="submit">Gửi phản hồi</button><p role="status" data-form-status></p></form>`;
  function reviewForm(a) {
    const r=data.items.find(x=>x.appointmentId===a.id);
    return `<article class="journey-card review-section"><h3>${e(a.service)}</h3><p>LH-${a.id} · ${e(a.date)}</p><form class="phase4-form" data-review="${a.id}"><fieldset class="review-rating"><legend>Điểm đánh giá (bắt buộc)</legend>${[1,2,3,4,5].map(n=>`<label data-selected="${n<=(r?.rating||0)}"><input type="radio" name="rating" value="${n}" required ${r?.rating===n?'checked':''} aria-label="${n} sao">${window.spaIcon('star')}</label>`).join('')}</fieldset><label>Nhận xét (không bắt buộc)<textarea name="comment" maxlength="2000">${e(r?.comment||'')}</textarea></label><button class="button" type="submit">${r?'Lưu thay đổi':'Gửi đánh giá'}</button><p role="status" data-form-status></p></form>${r?replies(r)+replyForm(r):''}</article>`;
  }
  function render() {
    if (!admin) { $('#review-list').innerHTML=data.eligible.map(reviewForm).join('') || '<p>Chưa có lịch hẹn đã hoàn thành để đánh giá.</p>'; return; }
    const from=$('#quality-from').value,to=$('#quality-to').value;
    const error=$('#quality-filter-error');error.hidden=!(from&&to&&from>to);
    if(!error.hidden){error.textContent='Khoảng ngày không hợp lệ.';return;}
    const q=$('#quality-search').value.toLocaleLowerCase('vi'),rating=$('#quality-stars').value;
    const rows=data.items.filter(r=>(!rating||r.rating===Number(rating))&&(!from||r.createdAt.slice(0,10)>=from)&&(!to||r.createdAt.slice(0,10)<=to)&&`${r.customer} ${r.service} ${r.comment}`.toLocaleLowerCase('vi').includes(q));
    const pages=Math.max(1,Math.ceil(rows.length/5)); page=Math.min(page,pages);
    $('#quality-rows').innerHTML=rows.slice((page-1)*5,page*5).map(r=>`<tr><td><strong>DG-${r.id}</strong><span class="admin-table-time">${e(r.customer)}</span></td><td class="admin-quality-service">${e(r.service)}</td><td>${stars(r.rating)}</td><td><p class="admin-quality-comment">${e(r.comment||'Chưa có nhận xét.')}</p></td><td>${e(date(r.createdAt))}</td><td><button class="admin-button" data-view-review="${r.id}">Xem / Phản hồi</button></td></tr>`).join('');
    $('#quality-empty').hidden=!!rows.length;
    $('#quality-pagination').innerHTML=`<span>${rows.length} đánh giá</span><div><button class="admin-button" data-review-page="${page-1}" ${page===1?'disabled':''}>Trước</button><span>${page} / ${pages}</span><button class="admin-button" data-review-page="${page+1}" ${page===pages?'disabled':''}>Sau</button></div>`;
    const average=rows.length?(rows.reduce((s,r)=>s+r.rating,0)/rows.length).toFixed(1):'—';
    $('#quality-stats').innerHTML=[['Điểm trung bình',average],['Tổng đánh giá',rows.length],['Từ 4–5 sao',rows.filter(r=>r.rating>=4).length],['Từ 1–2 sao',rows.filter(r=>r.rating<=2).length]].map(([label,value],i)=>`<article class="admin-finance-stat ${i?'':'is-featured'}"><div class="admin-finance-stat-heading"><span>${label}</span>${window.spaIcon('star')}</div><strong>${value}</strong></article>`).join('');
  }
  function openReview(id) {
    const r=data.items.find(x=>x.id===Number(id)),dialog=$('#quality-dialog');
    dialog.innerHTML=`<header class="admin-service-modal-heading"><div><span class="admin-eyebrow">AN NHIÊN / ĐÁNH GIÁ</span><h2 id="quality-dialog-title">Đánh giá DG-${r.id}</h2></div><button class="admin-button" data-close-review>Đóng</button></header><div class="admin-service-modal-scroll"><h3>${e(r.service)}</h3><p>${e(r.customer)} · ${e(date(r.createdAt))}</p>${stars(r.rating)}<p class="review-comment">${e(r.comment)}</p>${replies(r)}${replyForm(r)}</div>`;
    if(!dialog.open) dialog.showModal();
  }
  async function load(){ data=await api('/api/reviews/'); render(); }
  document.addEventListener('change',event=>{if(event.target.name==='rating'){const form=event.target.form;form.querySelectorAll('.review-rating label').forEach(l=>l.dataset.selected=Number(l.querySelector('input').value)<=Number(event.target.value));}});
  document.addEventListener('submit',async event=>{
    const form=event.target.closest('[data-review],[data-reply]');if(!form)return;
    event.preventDefault();const button=form.querySelector('button');button.disabled=true;
    try { await api(form.dataset.review?`/api/reviews/appointments/${form.dataset.review}/`:`/api/reviews/${form.dataset.reply}/replies/`,Object.fromEntries(new FormData(form)));await load(); if(admin)openReview(form.dataset.reply); }
    catch(error){form.querySelector('[data-form-status]').textContent=error.message;button.disabled=false;}
  });
  if(admin){
    let returnFocus;
    document.addEventListener('click',event=>{const view=event.target.closest('[data-view-review]'),nav=event.target.closest('[data-review-page]');if(view){returnFocus=view;openReview(view.dataset.viewReview);}if(nav&&!nav.disabled){page=Number(nav.dataset.reviewPage);render();}if(event.target.closest('[data-close-review]'))$('#quality-dialog').close();});
    $('#quality-dialog').addEventListener('close',()=>{if(returnFocus?.isConnected)returnFocus.focus();else $('#quality-search').focus();});
    ['#quality-search','#quality-stars','#quality-from','#quality-to'].forEach(s=>$(s).addEventListener('input',()=>{page=1;render();}));
    $('#quality-reset').onclick=()=>{['#quality-search','#quality-stars','#quality-from','#quality-to'].forEach(s=>$(s).value='');render();};
    $('#analysis-run').disabled=true; $('#analysis-mode').disabled=true;
    $('#analysis-results').textContent='Phân tích AI sẽ được triển khai ở giai đoạn riêng.';
  }
  try { await load(); } catch(error){ const node=admin?$('#quality-empty'):$('#review-list');node.hidden=false;node.textContent=error.message; }
})();
