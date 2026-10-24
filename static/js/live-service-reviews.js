(async()=>{
  const {api,escape:e,date}=window.spaLive,$=s=>document.querySelector(s);
  const section=$('[data-service-reviews]');if(!section)return;
  const id=new URLSearchParams(location.search).get('id');let page=1,own;
  const stars=n=>`<span class="review-stars" aria-label="${n} trên 5 sao">${[1,2,3,4,5].map(x=>`<span data-selected="${x<=n}">${window.spaIcon('star')}</span>`).join('')}</span>`;
  async function load(){
    const d=await api(`/api/reviews/services/${id}/?page=${page}`);
    $('[data-review-average]').textContent=d.total?Number(d.average).toFixed(1)+' / 5':'— / 5';$('[data-review-count]').textContent=`${d.total} đánh giá`;
    $('#review-list').innerHTML=d.items.map(r=>`<article class="review-item"><div class="review-byline"><div><strong>${e(r.name)}</strong>${stars(r.rating)}</div><time>${e(date(r.createdAt))}</time></div><p class="review-comment">${e(r.comment)}</p>${r.replies.map(x=>`<div class="review-reply"><strong>${e(x.name)}</strong><small> · ${e(date(x.createdAt))}</small><p>${e(x.content)}</p></div>`).join('')}</article>`).join('')||'<p>Chưa có đánh giá cho liệu trình này.</p>';
    $('#service-review-pages').innerHTML=`<button class="button small" data-review-nav="${page-1}" ${page===1?'disabled':''}>Trước</button><span>${page} / ${d.pages}</span><button class="button small" data-review-nav="${page+1}" ${page===d.pages?'disabled':''}>Sau</button>`;
  }
  const form=$('#review-form'),status=$('[data-review-status]');
  function fill(){const r=own?.items.find(x=>x.appointmentId===Number(form.elements.appointment.value));form.elements.rating.value=r?.rating||'';form.elements.message.value=r?.comment||'';form.querySelectorAll('.review-rating label').forEach(l=>l.dataset.selected=Number(l.querySelector('input').value)<=Number(form.elements.rating.value));}
  section.addEventListener('click',async event=>{const b=event.target.closest('[data-review-nav]');if(b&&!b.disabled){page=Number(b.dataset.reviewNav);try{await load();}catch(ex){status.textContent=ex.message;}}});
  $('[data-review-open]').onclick=()=>{form.hidden=false;fill();$('[data-review-open]').setAttribute('aria-expanded','true');};
  $('[data-review-cancel]').onclick=()=>{form.hidden=true;$('[data-review-open]').setAttribute('aria-expanded','false');};
  form.elements.appointment.onchange=fill;
  form.querySelectorAll('[data-rating-icon]').forEach(n=>n.innerHTML=window.spaIcon('star'));
  form.addEventListener('change',event=>{if(event.target.name==='rating')form.querySelectorAll('.review-rating label').forEach(l=>l.dataset.selected=Number(l.querySelector('input').value)<=Number(form.elements.rating.value));});
  form.addEventListener('submit',async event=>{event.preventDefault();const b=form.querySelector('[type=submit]');b.disabled=true;try{await api(`/api/reviews/appointments/${form.elements.appointment.value}/`,{rating:form.elements.rating.value,comment:form.elements.message.value});own=await api('/api/reviews/');await load();form.hidden=true;status.textContent='Đã lưu đánh giá.';}catch(ex){status.textContent=ex.message;}finally{b.disabled=false;}});
  try{await load();if(window.spaAuth?.getSession()?.role==='User'){own=await api('/api/reviews/');const eligible=own.eligible.filter(a=>a.serviceId===Number(id));form.elements.appointment.innerHTML=eligible.map(a=>`<option value="${a.id}">LH-${a.id} · ${e(a.date)}</option>`).join('');$('[data-review-open]').hidden=!eligible.length;}}catch(ex){status.textContent=ex.message;}
})();
