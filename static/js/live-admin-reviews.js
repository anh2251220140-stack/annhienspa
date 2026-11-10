/* Admin Reviews only. The User review scripts and API contract stay unchanged. */
(async () => {
  'use strict';
  const root=document.querySelector('[data-reviews-admin]');if(!root)return;
  const {api,escape:esc}=window.spaLive,$=s=>root.querySelector(s),dialog=document.querySelector('#quality-dialog');
  const icon=name=>window.spaIcon(name);
  let items=null,page=1,request=0,dialogRequest=0,activeId=null,sending=false,returnFocus;
  const normalize=value=>String(value??'').toLocaleLowerCase('vi').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/g,'d');
  const parts=value=>Object.fromEntries(new Intl.DateTimeFormat('vi-VN',{timeZone:'Asia/Ho_Chi_Minh',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date(value)).map(p=>[p.type,p.value]));
  function stamp(value){if(!value||!Number.isFinite(Date.parse(value)))return {label:'—',day:''};const p=parts(value);return {label:`${p.day}/${p.month}/${p.year} ${p.hour}:${p.minute}`,day:`${p.year}-${p.month}-${p.day}`};}
  function parseDay(value){
    if(!value)return '';
    const m=/^(\d{2})\/(\d{2})\/(\d{4})$/.exec(value);if(!m)return null;
    const iso=`${m[3]}-${m[2]}-${m[1]}`,d=new Date(iso+'T00:00:00Z');
    return Number.isFinite(d.getTime())&&d.toISOString().slice(0,10)===iso?iso:null;
  }
  const stars=n=>`<span class="admin-quality-stars" aria-label="${n} trên 5 sao">${[1,2,3,4,5].map(x=>`<span class="${x<=n?'is-filled':''}">${icon('star')}</span>`).join('')}</span>`;
  function stats(rows){
    const entries=[['Điểm trung bình',rows?(rows.length?(rows.reduce((s,r)=>s+r.rating,0)/rows.length).toLocaleString('vi-VN',{minimumFractionDigits:1,maximumFractionDigits:1}):'—'):'—','Trên thang 5 sao','star'],['Tổng đánh giá',rows?rows.length:'—','Toàn bộ kết quả lọc','note'],['Đánh giá tích cực',rows?rows.filter(r=>r.rating>=4).length:'—','4–5 sao · theo số sao','heart'],['Nhóm cần quan tâm',rows?rows.filter(r=>r.rating<=2).length:'—','1–2 sao · theo số sao','calendar']];
    $('#quality-stats').innerHTML=entries.map(([label,value,description,symbol],i)=>`<article class="admin-finance-stat ${i?'':'is-featured'}"><div class="admin-finance-stat-heading"><span>${label}</span>${icon(symbol)}</div><strong>${value}</strong><p>${description}</p></article>`).join('');
  }
  function clearRows(){ $('#quality-rows').replaceChildren();$('#quality-pagination').replaceChildren();$('#quality-empty').hidden=true; }
  function render(){
    if(!items){clearRows();stats(null);return;}
    const from=parseDay($('#quality-from').value),to=parseDay($('#quality-to').value),error=$('#quality-filter-error');
    error.hidden=!(from===null||to===null||(from&&to&&from>to));
    for(const side of ['from','to'])$('#quality-'+side).setAttribute('aria-invalid',String(parseDay($('#quality-'+side).value)===null));
    if(!error.hidden){error.textContent=from===null||to===null?'Nhập ngày hợp lệ theo dd/mm/yyyy.':'Ngày bắt đầu không được sau ngày kết thúc.';clearRows();stats(null);return;}
    const q=normalize($('#quality-search').value.trim()),rating=Number($('#quality-stars').value);
    const rows=items.filter(r=>(!rating||r.rating===rating)&&(!from||stamp(r.createdAt).day>=from)&&(!to||stamp(r.createdAt).day<=to)&&normalize(`DG-${r.id} ${r.customer} ${r.service} ${r.comment||''}`).includes(q));
    const pages=Math.max(1,Math.ceil(rows.length/5));page=Math.max(1,Math.min(page,pages));stats(rows);
    $('#quality-rows').innerHTML=rows.slice((page-1)*5,page*5).map(r=>`<tr><td><strong class="reviews-code">DG-${r.id}</strong><span class="admin-table-time">${esc(r.customer)}</span></td><td class="admin-quality-service">${esc(r.service)}</td><td>${stars(r.rating)}</td><td><p class="admin-quality-comment${r.comment?'':' is-empty'}">${esc(r.comment||'Chỉ chấm sao, không có nhận xét.')}</p>${r.replies.length?`<small class="reviews-reply-count">${r.replies.length} phản hồi</small>`:''}</td><td><time datetime="${esc(r.createdAt)}">${stamp(r.createdAt).label}</time></td><td><div class="admin-row-actions"><button class="admin-button" type="button" data-view-review="${r.id}">${icon('eye')}Xem / Phản hồi</button></div></td></tr>`).join('');
    $('#quality-empty').hidden=!!rows.length;
    $('#quality-empty h3').textContent=items.length?'Không tìm thấy đánh giá':'Chưa có đánh giá';
    $('#quality-empty p').textContent=items.length?'Thử thay đổi từ khóa, số sao hoặc khoảng thời gian.':'Đánh giá của khách sẽ xuất hiện tại đây sau khi được gửi.';
    const start=rows.length?(page-1)*5+1:0,end=Math.min(page*5,rows.length);
    $('#quality-pagination').innerHTML=`<span>${end-start+(rows.length?1:0)} / ${rows.length} đánh giá${rows.length?` · ${start}–${end}`:''}</span><div><button class="admin-button" type="button" data-review-page="${page-1}" ${page===1?'disabled':''}>Trước</button><span>${page} / ${pages}</span><button class="admin-button" type="button" data-review-page="${page+1}" ${page===pages?'disabled':''}>Sau</button></div>`;
  }
  function modalHeading(){return `<header class="admin-service-modal-heading"><span class="reviews-modal-symbol">${icon('heart')}</span><div><span class="admin-eyebrow">AN NHIÊN / ĐÁNH GIÁ</span><h2 id="quality-dialog-title">Chi tiết đánh giá</h2></div><button class="admin-icon-button" type="button" data-close-review aria-label="Đóng chi tiết đánh giá">${icon('close')}</button></header>`;}
  const footer=()=>`<footer class="admin-dialog-actions"><span>Đánh giá gốc chỉ đọc</span><button type="button" class="admin-button" data-close-review>Đóng</button></footer>`;
  function fillDialog(r,message=''){
    const replies=r.replies.map(x=>`<article class="review-reply"><div class="reviews-reply-byline"><strong>${esc(x.name)}</strong><span class="admin-quality-chip ${x.role==='Admin'?'is-positive':'is-unknown'}">${x.role==='Admin'?'Quản trị viên':'Chủ đánh giá'}</span><time datetime="${esc(x.createdAt)}">${stamp(x.createdAt).label}</time></div><p>${esc(x.content)}</p></article>`).join('');
    dialog.innerHTML=modalHeading()+`<div class="admin-service-modal-scroll"><div class="reviews-detail-banner"><div><span class="reviews-code">DG-${r.id}</span><h3>${esc(r.customer)}</h3></div>${stars(r.rating)}</div><dl class="reviews-facts"><div><dt>${icon('leaf')}Dịch vụ</dt><dd>${esc(r.service)}</dd></div><div><dt>${icon('calendar')}Thời điểm đánh giá</dt><dd>${stamp(r.createdAt).label}</dd></div><div><dt>${icon('note')}Lịch hẹn</dt><dd>LH-${String(r.appointmentId).padStart(6,'0')}</dd></div></dl><section class="reviews-detail-comment"><h3>${icon('note')}Chia sẻ của khách</h3><p>${esc(r.comment||'Chỉ chấm sao, không có nhận xét.')}</p></section><section class="reviews-thread"><h3>${icon('heart')}Phản hồi <span>(${r.replies.length})</span></h3><div class="reviews-thread-list" role="region" aria-label="Danh sách phản hồi" tabindex="0">${replies||'<p class="reviews-no-replies">Chưa có phản hồi.</p>'}</div><form data-admin-review-reply="${r.id}"><label for="review-reply-content">Nội dung phản hồi</label><textarea id="review-reply-content" name="content" maxlength="2000" rows="4" required placeholder="Lắng nghe và phản hồi khách hàng…" aria-describedby="review-reply-status"></textarea><p class="reviews-reply-hint">Tối đa 2.000 ký tự</p><div class="reviews-reply-actions"><button class="admin-button admin-button-primary" type="submit" ${sending?'disabled':''}>${icon('note')}Gửi phản hồi</button></div><p id="review-reply-status" role="status" aria-live="polite">${esc(message)}</p></form></section></div>`+footer();
  }
  async function load(){
    const version=++request;$('#reviews-panel').setAttribute('aria-busy','true');$('#quality-loading').hidden=false;$('#quality-api-error').hidden=true;items=null;render();
    try{const result=await api('/api/reviews/');if(version!==request)return;if(!Array.isArray(result.items))throw Error('Không đọc được danh sách đánh giá.');items=result.items;render();}
    catch(error){if(version===request){$('#quality-api-error p').textContent=error.message;$('#quality-api-error').hidden=false;}}
    finally{if(version===request){$('#quality-loading').hidden=true;$('#reviews-panel').setAttribute('aria-busy','false');}}
  }
  async function openReview(id){
    const version=++dialogRequest;activeId=id;
    dialog.innerHTML=modalHeading()+'<div class="admin-service-modal-scroll"><p role="status">Đang tải đánh giá và phản hồi…</p></div>'+footer();
    if(!dialog.open)dialog.showModal();
    try{
      const result=await api('/api/reviews/');if(version!==dialogRequest||!dialog.open)return;
      if(!Array.isArray(result.items))throw Error('Không đọc được danh sách đánh giá.');
      items=result.items;render();const r=items.find(r=>r.id===id);if(!r)throw Error('Đánh giá không còn khả dụng. Vui lòng tải lại danh sách.');fillDialog(r);
    }catch(error){if(version===dialogRequest&&dialog.open)dialog.innerHTML=modalHeading()+`<div class="admin-service-modal-scroll"><p role="alert">${esc(error.message)}</p></div>`+footer();}
  }
  root.addEventListener('click',event=>{
    const view=event.target.closest('[data-view-review]'),nav=event.target.closest('[data-review-page]');
    if(view){returnFocus=view;openReview(Number(view.dataset.viewReview));}
    if(nav&&!nav.disabled){page=Number(nav.dataset.reviewPage);render();}
  });
  dialog.addEventListener('click',event=>{if(event.target.closest('[data-close-review]'))dialog.close();});
  dialog.addEventListener('close',()=>{if(dialog.open)return;++dialogRequest;activeId=null;if(returnFocus?.isConnected)returnFocus.focus();else $('#quality-search').focus();});
  dialog.addEventListener('submit',async event=>{
    const form=event.target.closest('[data-admin-review-reply]');if(!form)return;event.preventDefault();if(sending||!form.reportValidity())return;
    const id=Number(form.dataset.adminReviewReply),version=dialogRequest,button=form.querySelector('[type=submit]'),status=form.querySelector('#review-reply-status');
    sending=true;button.disabled=true;status.setAttribute('role','status');status.textContent='Đang gửi phản hồi…';
    try{
      const result=await api(`/api/reviews/${id}/replies/`,{content:form.elements.content.value});
      if(!result.item)throw Error('Chưa xác minh được phản hồi. Vui lòng mở lại đánh giá trước khi gửi thêm.');
      if(items)items=items.map(r=>r.id===id?result.item:r);render();
      if(dialog.open&&activeId===id&&version===dialogRequest)fillDialog(result.item,'Đã gửi phản hồi.');
    }catch(error){if(form.isConnected){status.setAttribute('role','alert');status.textContent=error.message;}}
    finally{sending=false;const current=dialog.querySelector('[type=submit]');if(current)current.disabled=false;}
  });
  ['#quality-search','#quality-stars','#quality-from','#quality-to'].forEach(selector=>$(selector).addEventListener('input',()=>{page=1;if(selector==='#quality-from'||selector==='#quality-to')$(selector+'-picker').value=parseDay($(selector).value)||'';render();}));
  for(const side of ['from','to'])$('#quality-'+side+'-picker').addEventListener('change',event=>{$('#quality-'+side).value=event.target.value.split('-').reverse().join('/');page=1;render();});
  $('#quality-reset').onclick=()=>{for(const selector of ['#quality-search','#quality-stars','#quality-from','#quality-to','#quality-from-picker','#quality-to-picker'])$(selector).value='';page=1;render();};
  $('#quality-retry').onclick=load;
  document.querySelector('[data-quality-sparkle]').innerHTML=icon('star');
  $('#analysis-results').innerHTML=`<div class="reviews-ai-empty">${icon('star')}<h3>Phân tích AI chưa được kết nối</h3><p>FR-23 sẽ được triển khai riêng. Hiện chưa có kết quả phân tích cảm xúc hoặc gợi ý từ AI.</p></div>`;
  await load();
})();
