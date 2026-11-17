/* Admin Reviews only. The User review scripts and API contract stay unchanged. */
(async () => {
  'use strict';
  const root=document.querySelector('[data-reviews-admin]');if(!root)return;
  const {api,escape:esc}=window.spaLive,$=s=>root.querySelector(s),dialog=document.querySelector('#quality-dialog');
  const icon=name=>window.spaIcon(name);
  let items=null,page=1,request=0,dialogRequest=0,activeId=null,sending=false,returnFocus,analysisRows=[],analysisVersion=0,analysisSending=false;
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
    if(!items){clearAnalysis();clearRows();stats(null);return;}
    const from=parseDay($('#quality-from').value),to=parseDay($('#quality-to').value),error=$('#quality-filter-error');
    error.hidden=!(from===null||to===null||(from&&to&&from>to));
    for(const side of ['from','to'])$('#quality-'+side).setAttribute('aria-invalid',String(parseDay($('#quality-'+side).value)===null));
    if(!error.hidden){error.textContent=from===null||to===null?'Nhập ngày hợp lệ theo dd/mm/yyyy.':'Ngày bắt đầu không được sau ngày kết thúc.';clearAnalysis();clearRows();stats(null);return;}
    const q=normalize($('#quality-search').value.trim()),rating=Number($('#quality-stars').value);
    const rows=items.filter(r=>(!rating||r.rating===rating)&&(!from||stamp(r.createdAt).day>=from)&&(!to||stamp(r.createdAt).day<=to)&&normalize(`DG-${r.id} ${r.customer} ${r.service} ${r.comment||''}`).includes(q));
    analysisRows=rows;
    const selection=$('#analysis-review').value;
    $('#analysis-review').replaceChildren(...rows.map(r=>new Option(`DG-${r.id} · ${r.customer}`,r.id)));
    if(rows.some(r=>String(r.id)===selection))$('#analysis-review').value=selection;
    restoreAnalysis();
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
  function clearAnalysis(){
    ++analysisVersion;analysisRows=[];
    $('#analysis-review').replaceChildren();
    $('#analysis-results').replaceChildren();$('#analysis-results').setAttribute('aria-busy','false');
    $('#analysis-status').textContent='';$('#analysis-run').disabled=true;
  }
  function selectedAnalysisIds(){
    const from=parseDay($('#quality-from').value),to=parseDay($('#quality-to').value);
    if(!items||from===null||to===null||(from&&to&&from>to))return [];
    const ids=$('#analysis-mode').value==='individual'?[Number($('#analysis-review').value)]:analysisRows.map(r=>r.id);
    return ids.length&&ids.every(id=>Number.isSafeInteger(id)&&id>0&&analysisRows.some(r=>r.id===id))?ids:[];
  }
  const analysisLabels={positive:'Tích cực',neutral:'Trung tính',negative:'Tiêu cực',low:'Thấp',medium:'Vừa',high:'Cao'};
  const textList=value=>Array.isArray(value)?value.filter(x=>typeof x==='string'&&x.trim()):[];
  const modeLabel=a=>a.mode==='ai'?'Phân tích AI':a.mode==='rule'?'Dự phòng theo số sao':'Kết quả cũ chưa xác minh';
  const chip=(label,tone='unknown')=>`<span class="admin-quality-chip is-${tone}">${esc(label)}</span>`;
  function analysisScope(analyses){
    const ids=selectedAnalysisIds();
    if(ids.length>5)return null;
    const byId=new Map();
    for(const a of analyses){
      if(a&&ids.includes(a.reviewId)&&!byId.has(a.reviewId))byId.set(a.reviewId,a);
    }
    const rows=ids.map(id=>{
      const review=analysisRows.find(r=>r.id===id),a=byId.get(id);
      const insufficient=!review.comment?.trim()||a?.analysisState==='insufficient_text';
      return {review,a,insufficient};
    });
    const current=rows.filter(r=>r.a&&!r.a.stale);
    const eligible=current.filter(r=>!r.insufficient);
    // A rule result is a star-based fallback, never content-level sentiment.
    const ai=eligible.filter(r=>r.a.mode==='ai'&&['positive','neutral','negative'].includes(r.a.sentiment));
    const rule=eligible.filter(r=>r.a.mode==='rule');
    const counts={positive:0,neutral:0,negative:0};
    ai.forEach(r=>counts[r.a.sentiment]++);
    const topics=new Map();
    for(const row of ai){
      const seen=new Set();
      for(const label of textList(row.a.themes)){
        const key=label.trim().normalize('NFC').toLocaleLowerCase('vi');
        if(seen.has(key))continue;seen.add(key);
        if(!topics.has(key))topics.set(key,{label:label.trim(),ids:[]});
        topics.get(key).ids.push(row.review.id);
      }
    }
    const actions=new Map();
    for(const row of [...ai,...rule]){
      for(const text of textList(row.a.actions)){
        const key=row.a.mode+':'+text.trim().normalize('NFC').toLocaleLowerCase('vi');
        if(!actions.has(key))actions.set(key,{text:text.trim(),mode:row.a.mode,ids:[]});
        const action=actions.get(key);if(!action.ids.includes(row.review.id))action.ids.push(row.review.id);
      }
    }
    return {rows,current,ai,rule,counts,topics:[...topics.values()],actions:[...actions.values()],
      stale:rows.filter(r=>r.a?.stale).length,missing:rows.filter(r=>!r.a).length,
      insufficient:current.filter(r=>r.insufficient).length};
  }
  function reviewAnalysisCard({review,a,insufficient},single){
    const current=a&&!a.stale;
    const content=current&&!insufficient&&a.mode==='ai';
    const status=!a?'Chưa có kết quả đã lưu':a.stale?'Kết quả cũ, không còn hiện hành':insufficient?'Không đủ căn cứ phân tích văn bản':modeLabel(a);
    const original=review.comment?.trim()?`<blockquote>${esc(review.comment)}</blockquote>`:'<p>Đánh giá chỉ có số sao, chưa có nhận xét.</p>';
    return `<details class="fr23-review-detail" ${single?'open':''}><summary><span>DG-${review.id} · ${esc(review.customer)}</span>${chip(status,content?a.sentiment:'unknown')}</summary><div class="fr23-review-body">
      ${a?.stale?'<p role="alert" class="fr23-stale">Đánh giá đã thay đổi kể từ lần phân tích gần nhất. Vui lòng phân tích lại.</p>':''}
      <div class="admin-analysis-grid"><article><h3>${icon('heart')}Cảm xúc & nhận xét gốc</h3>
      ${chip(content?analysisLabels[a.sentiment]:'Chưa có phân tích cảm xúc hiện hành',content?a.sentiment:'unknown')}
      <p class="admin-data-note">${content?'Diễn giải từ kết quả AI đã lưu; chưa xác minh sự việc.':'Không suy diễn cảm xúc nội dung từ số sao.'}</p>
      <details class="admin-ai-original"><summary>Đọc nhận xét gốc</summary>${original}</details></article>
      <article><h3>${icon('leaf')}Chủ đề được nhắc đến</h3>${content&&textList(a.themes).length?`<div class="admin-topic-chips">${textList(a.themes).map(t=>chip(t,'neutral')).join('')}</div>`:'<p>Chưa có chủ đề nội dung đủ căn cứ. Không tự gán chủ đề.</p>'}<p class="admin-data-note">Không tự xếp chủ đề chính/phụ khi kết quả lưu chưa cung cấp quan hệ này.</p></article></div>
      <section class="fr23-saved-summary"><h3>Tóm tắt ${a?.stale?'đã lưu trước đây':'đã lưu'}</h3><p>${esc(a?.summary||'Chưa có kết quả đã lưu trong phạm vi này.')}</p>
      ${a?`<p class="admin-data-note">${esc(modeLabel(a))} · Thời điểm phân tích: ${esc(stamp(a.analyzedAt).label)}</p>`:''}</section>
      <section class="fr23-priority"><h3>${icon('calendar')}Mức độ ưu tiên</h3>${chip(content?'Ưu tiên: '+analysisLabels[a.priority]:'Cần Admin đọc và xác minh',content?a.sentiment:'unknown')}<p>${content?'Mức ưu tiên do kết quả AI đề xuất; chưa phải xác nhận sự cố.':'Không dùng fallback theo sao hoặc kết quả cũ để kết luận mức độ nghiêm trọng.'}</p></section>
      </div></details>`;
  }
  function showAnalyses(analyses){
    const scope=analysisScope(analyses),target=$('#analysis-results');
    if(!scope||!scope.rows.length){target.innerHTML='<div class="reviews-ai-empty"><h3>Chọn tối đa 5 đánh giá</h3><p>Lọc hoặc chọn một đánh giá để đọc kết quả đã lưu.</p></div>';return;}
    const {rows,ai,rule,counts,topics,actions,stale,missing,insufficient}=scope;
    const breakdown=`${ai.length} kết quả AI · ${rule.length} dự phòng theo sao · ${insufficient} thiếu nội dung · ${stale} lỗi thời đã loại · ${missing} chưa phân tích`;
    const distribution=['positive','neutral','negative'].map(tone=>`<div class="fr23-distribution-row"><span>${chip(analysisLabels[tone],tone)}</span><meter min="0" max="${Math.max(ai.length,1)}" value="${counts[tone]}" aria-label="${analysisLabels[tone]}: ${counts[tone]} trên ${ai.length} kết quả AI"></meter><strong>${counts[tone]}</strong></div>`).join('');
    const patterns=tone=>ai.filter(r=>r.a.sentiment===tone).map(r=>`<div class="admin-ai-pattern"><div><strong>DG-${r.review.id}</strong>${chip(analysisLabels[tone],tone)}</div><p>${esc(r.a.summary)}</p><span class="admin-data-note">Diễn giải từ AI đã lưu; đối chiếu nhận xét gốc bên dưới.</span></div>`).join('');
    target.innerHTML=`<div class="admin-analysis-scope" data-fr23-ai="${ai.length}" data-fr23-rule="${rule.length}" data-fr23-stale="${stale}" data-fr23-insufficient="${insufficient}" data-fr23-missing="${missing}"><span>${rows.length} đánh giá trong phạm vi</span>${chip('Tổng hợp từ kết quả đã lưu','neutral')}</div>
      <section class="admin-ai-spotlight is-${counts.negative?'negative':counts.positive?'positive':counts.neutral?'neutral':'unknown'}"><div class="admin-ai-spotlight-heading"><span class="admin-eyebrow">${icon('star')}ĐIỂM NỔI BẬT</span>${chip(ai.length?'Có '+ai.length+' kết quả AI hiện hành':'Chưa có kết quả AI hiện hành',ai.length?'positive':'unknown')}</div>
      <h3>${ai.length?'Lắng nghe từ những kết quả đã có':'Chưa đủ căn cứ phân tích nội dung'}</h3><p>${esc(breakdown)}</p><span class="admin-ai-boundary">Chỉ tổng hợp tối đa 5 đánh giá. Không tạo suy luận mới, không gọi thêm AI và không tính kết quả lỗi thời.</span></section>
      <section class="admin-ai-distribution"><div class="admin-ai-section-heading"><h3>${icon('heart')}Bức tranh cảm xúc</h3><span>Chỉ từ ${ai.length} kết quả AI hiện hành · Không phải độ tin cậy mô hình</span></div>${distribution}<p class="admin-data-note">Dự phòng theo số sao, thiếu văn bản và kết quả lỗi thời không tham gia phân bố cảm xúc nội dung.</p></section>
      <section class="admin-ai-topic-overview"><h3>${icon('leaf')}Chủ đề được nhắc đến</h3><div class="admin-topic-chips">${topics.map(t=>chip(t.label+' · '+t.ids.length,'neutral')).join('')||'<p>Chưa có chủ đề từ kết quả AI hiện hành.</p>'}</div><p class="admin-data-note">Mỗi chủ đề chỉ đếm một lần trong mỗi đánh giá; không suy ra sắc thái riêng của chủ đề từ cảm xúc chung.</p></section>
      <div class="admin-analysis-grid"><article><h3>${icon('leaf')}Điểm khách hàng hài lòng</h3>${patterns('positive')||'<p>Chưa có kết quả AI tích cực hiện hành. Không tự tạo điểm hài lòng.</p>'}</article><article><h3>${icon('note')}Góp ý cần cải thiện</h3>${patterns('negative')||'<p>Chưa có kết quả AI tiêu cực hiện hành. Admin vẫn cần đọc nhận xét gốc; không kết luận không có vấn đề.</p>'}</article></div>
      <section class="admin-ai-action-section"><div class="admin-ai-section-heading"><h3>${icon('note')}Lộ trình hành động đề xuất</h3><span>Admin xem xét và quyết định</span></div><p class="admin-data-note">Hành động lấy nguyên nội dung đã lưu. Số thứ tự để trình bày, không phải mức ưu tiên tự động.</p>
      <ol class="admin-ai-plan">${actions.map((a,i)=>`<li><span class="admin-ai-step" aria-hidden="true">${String(i+1).padStart(2,'0')}</span><div><h4>Hành động đề xuất · ${esc(a.mode==='ai'?'AI':'Dự phòng theo sao')}</h4><p>${esc(a.text)}</p><span class="admin-data-note">Tham chiếu ${a.ids.map(id=>'DG-'+id).join(', ')}</span></div></li>`).join('')}</ol>${actions.length?'':'<p>Chưa có hành động từ kết quả hiện hành đủ điều kiện. Không tự bổ sung hành động.</p>'}</section>
      <section class="admin-ai-action-section"><div class="admin-ai-section-heading"><h3>${icon('star')}Phân tích từng đánh giá</h3><span>Nhận xét gốc chỉ đọc</span></div>${rows.map(r=>reviewAnalysisCard(r,rows.length===1)).join('')}</section>
      <p class="admin-data-note">AI chỉ hỗ trợ xem xét; không tự gửi phản hồi, sửa đánh giá, hoàn tiền hoặc thay đổi lịch hẹn.</p>`;
  }
  async function restoreAnalysis(){
    const version=++analysisVersion,ids=selectedAnalysisIds(),target=$('#analysis-results'),status=$('#analysis-status');
    target.replaceChildren();target.setAttribute('aria-busy',String(!!ids.length));
    $('#analysis-run').disabled=analysisSending||!ids.length||ids.length>5;
    status.textContent=ids.length?'Đang đọc kết quả đã lưu…':'';
    if(!ids.length)return;
    if(ids.length>5){target.setAttribute('aria-busy','false');showAnalyses([]);status.textContent='Lọc còn tối đa 5 đánh giá hoặc chọn một đánh giá để đọc và tổng hợp.';return;}
    try{
      const saved=[];
      // GET only: never trigger inference or overwrite saved analyses on reload.
      for(const id of ids){
        if(version!==analysisVersion)return;
        const body=await api(`/api/ai/reviews/${id}/analyze/`);
        if(version!==analysisVersion)return;
        if(body.analysis&&body.analysis.reviewId!==id)throw Error('Kết quả không khớp đánh giá.');
        if(body.analysis)saved.push(body.analysis);
      }
      showAnalyses(saved);status.textContent=`Đã đọc ${saved.length} kết quả đã lưu.${ids.length>5?' Lọc còn tối đa 5 đánh giá để phân tích.':''}`;
    }catch(error){if(version===analysisVersion)status.textContent=error.message;}
    finally{if(version===analysisVersion)target.setAttribute('aria-busy','false');}
  }
  $('#analysis-mode').addEventListener('change',()=>{$('#analysis-review-label').hidden=$('#analysis-mode').value!=='individual';restoreAnalysis();});
  $('#analysis-review').addEventListener('change',restoreAnalysis);
  $('#analysis-run').addEventListener('click',async()=>{
    const button=$('#analysis-run'),target=$('#analysis-results'),status=$('#analysis-status');
    const ids=selectedAnalysisIds();
    if(!ids.length||ids.length>5){status.textContent='Chọn một đánh giá hoặc lọc còn tối đa 5 đánh giá trước khi phân tích.';return;}
    if(button.disabled||analysisSending)return;
    const version=++analysisVersion;analysisSending=true;
    button.disabled=true;target.replaceChildren();target.setAttribute('aria-busy','true');status.textContent='Đang phân tích…';
    try{
      const response=await fetch('/api/ai/reviews/analyze/',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':document.querySelector('[name=csrfmiddlewaretoken]')?.value||''},body:JSON.stringify({reviewIds:ids})});
      const body=await response.json();if(!response.ok)throw Error(body.error||'Chưa thể phân tích. Vui lòng thử lại.');
      if(version!==analysisVersion)return;
      if(!Array.isArray(body.items)||body.items.some(a=>!ids.includes(a.reviewId)))throw Error('Kết quả không khớp đánh giá.');
      showAnalyses(body.items);status.textContent=`Đã xử lý ${body.items.length} đánh giá. Kết quả được lưu tại Django.`;
    }catch(error){if(version===analysisVersion)status.textContent=error.message;}
    finally{
      analysisSending=false;const current=selectedAnalysisIds();button.disabled=!current.length||current.length>5;
      if(version===analysisVersion)target.setAttribute('aria-busy','false');
    }
  });
  await load();
})();
