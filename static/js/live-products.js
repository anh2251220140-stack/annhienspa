(() => {
  'use strict';
  const root=document.querySelector('[data-admin-operations="products"]');if(!root)return;
  const $=s=>document.querySelector(s), dialog=$('#ops-dialog');
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const norm=v=>String(v??'').toLocaleLowerCase('vi').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/g,'d').trim();
  const code=id=>'SP-'+String(id).padStart(3,'0');
  const icon=name=>{const paths={edit:'<path d="m16 3 5 5-12 12H4v-5ZM14 5l5 5"/>',power:'<path d="M12 2v10M6 5a9 9 0 1 0 12 0"/>',check:'<path d="m4 12 5 5L20 6"/>'};return paths[name]?`<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true">${paths[name]}</svg>`:window.spaIcon(name);};
  const badge=active=>`<span class="admin-status-badge admin-status-${active?'completed':'cancelled'}">${active?'Hoạt động':'Tạm ngưng'}</span>`;
  const photo=r=>r.image_url?`<img src="${esc(r.image_url)}" alt="" loading="lazy">`:`<span class="product-placeholder" aria-label="Chưa có ảnh">${icon('droplet')}</span>`;
  const endpoint=id=>'/api/admin/products/'+(id===undefined?'':id+'/');
  let items=[],page=1,returnFocus,loading=false;
  function notice(message){$('#ops-notice').textContent=message;$('#ops-notice').hidden=false;}
  async function api(path,data){const options=data?{method:'POST',body:data,headers:{'X-CSRFToken':$('[name="csrfmiddlewaretoken"]').value}}:{};const response=await fetch(path,options);const payload=await response.json().catch(()=>({}));if(!response.ok){const error=Error(payload.error||Object.values(payload.errors||{}).flat().join(' ')||(response.status===401 ? 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.' : response.status===403 ? 'Không có quyền hoặc phiên bảo mật đã hết hạn. Vui lòng tải lại trang.' : response.status===413 ? 'Ảnh vượt giới hạn tải lên của máy chủ. Vui lòng chọn ảnh nhỏ hơn.' : response.status>=500 ? 'Máy chủ không thể xử lý yêu cầu. Vui lòng thử lại sau.' : 'Không thể thực hiện thao tác. Vui lòng kiểm tra dữ liệu.'));error.fields=payload.errors;throw error;}return payload;}
  function images(){dialog.querySelectorAll('img').forEach(img=>img.onerror=()=>{img.hidden=true;});root.querySelectorAll('.product-name img').forEach(img=>img.onerror=()=>{const span=document.createElement('span');span.className='product-placeholder';span.setAttribute('aria-label','Không tải được ảnh');span.innerHTML=icon('droplet');img.replaceWith(span);});}
  function render(){const q=norm($('#ops-search').value),category=$('#ops-category').value,status=$('#ops-status').value;
    const filtered=items.filter(r=>norm(r.name+' '+code(r.id)).includes(q)&&(!category||r.product_type===category)&&(!status||r.active===(status==='active')));
    const pages=Math.max(1,Math.ceil(filtered.length/5));page=Math.max(1,Math.min(page,pages));const start=(page-1)*5,visible=filtered.slice(start,start+5);
    $('#ops-rows').innerHTML=visible.map(r=>`<tr><td class="product-code">${code(r.id)}</td><td><div class="product-name">${photo(r)}<div><strong>${esc(r.name)}</strong><p>${esc(r.description)}</p></div></div></td><td><span class="product-chip">${esc(r.product_type)}</span></td><td>${badge(r.active)}</td><td><div class="admin-row-actions">${[['view','eye','Xem'],['edit','edit','Sửa'],['toggle','power',r.active?'Tắt':'Bật']].map(([action,symbol,label])=>`<button type="button" class="admin-button" data-product-${action}="${r.id}" aria-label="${label} ${esc(r.name)}">${icon(symbol)}${label}</button>`).join('')}</div></td></tr>`).join('');
    $('#ops-empty').hidden=filtered.length>0;
    $('#ops-pagination').innerHTML=`<span>${visible.length} / ${filtered.length} sản phẩm${filtered.length?' · '+(start+1)+'–'+(start+visible.length):''}</span><div><button class="admin-button" data-product-page="-1" ${page===1?'disabled':''}>Trước</button><span>${page} / ${pages}</span><button class="admin-button" data-product-page="1" ${page===pages?'disabled':''}>Sau</button></div>`;images();
  }
  async function refresh(){items=(await api(endpoint())).items;const selected=$('#ops-category').value;$('#ops-category').replaceChildren(new Option('Tất cả danh mục',''),...[...new Set(items.map(r=>r.product_type))].map(v=>new Option(v,v)));$('#ops-category').value=[...$('#ops-category').options].some(o=>o.value===selected)?selected:'';
    $('#ops-stats').innerHTML=[['Tổng sản phẩm',items.length,'droplet'],['Đang hiển thị',items.filter(r=>r.active).length,'leaf'],['Tạm ngưng',items.filter(r=>!r.active).length,'clock']].map(([label,n,symbol])=>`<article><div><span class="product-stat-icon">${icon(symbol)}</span><span>${label}</span></div><strong>${n}</strong></article>`).join('');render();}
  function open(title,body){if(!dialog.open)returnFocus=document.activeElement;dialog.innerHTML=`<header class="admin-service-modal-heading"><span class="admin-service-modal-icon">${icon('droplet')}</span><div><span class="admin-eyebrow">AN NHIÊN SPA / QUẢN TRỊ</span><h2 id="ops-dialog-title">${esc(title)}</h2></div><button type="button" class="admin-icon-button" data-close aria-label="Đóng">${icon('close')}</button></header>${body}`;
    dialog.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>dialog.close());dialog.querySelectorAll('[data-live-icon]').forEach(e=>e.innerHTML=icon(e.dataset.liveIcon));images();if(!dialog.open)dialog.showModal();}
  dialog.addEventListener('close',()=>returnFocus?.isConnected&&returnFocus.focus());
  function prepareForm(isEdit){const form=dialog.querySelector('form'),checks=[...form.querySelectorAll('[name="services"]')],initial=checks.filter(c=>c.checked).map(c=>c.value);
    const group=form.querySelector('.admin-ops-checks');if(group){const controls=document.createElement('div');controls.className='product-link-controls';controls.innerHTML='<p>Chọn các dịch vụ sử dụng sản phẩm này. Có thể để trống.</p><label for="product-service-search">Tìm dịch vụ</label><input id="product-service-search" type="search" data-link-search placeholder="Nhập tên hoặc mã dịch vụ..."><p data-link-summary aria-live="polite"></p>';group.querySelector('legend').after(controls);const options=checks.map(c=>c.closest('label'));
      const empty=document.createElement('p');empty.textContent='Không có dịch vụ khớp tìm kiếm.';group.append(empty);
      const update=()=>{const q=norm(controls.querySelector('input').value),selected=checks.filter(c=>c.checked);controls.querySelector('[data-link-summary]').textContent=`Đã chọn ${selected.length} dịch vụ: ${selected.map(c=>c.closest('label').textContent.trim()).join('; ')||'Chưa liên kết dịch vụ'}`;options.forEach((l,i)=>l.hidden=!norm(l.textContent+' DV-'+String(checks[i].value).padStart(3,'0')).includes(q));empty.hidden=options.some(l=>!l.hidden);};controls.addEventListener('input',update);checks.forEach(c=>c.addEventListener('change',update));update();}
    const warning=document.createElement('p');warning.className='admin-data-note';warning.hidden=true;warning.textContent='Lưu sẽ bỏ một số dịch vụ đã liên kết. Kiểm tra lại lựa chọn trước khi lưu.';form.querySelector('.admin-service-modal-scroll').append(warning);checks.forEach(c=>c.addEventListener('change',()=>warning.hidden=!initial.some(id=>!checks.find(c=>c.value===id)?.checked)));
    const upload=form.querySelector('[name="image"]'),clear=form.querySelector('[name="image-clear"]');let objectURL;
    const current=upload?.closest('.product-upload').querySelector('img'),preview=document.createElement('img');
    preview.className='live-image-preview product-new-preview';preview.alt='Ảnh mới đã chọn';preview.hidden=true;
    if(upload&&!isEdit)upload.classList.add('product-file-simple');
    if(upload&&isEdit){
      upload.classList.add('product-file-native');
      const area=upload.closest('.product-upload'),board=document.createElement('div');board.className='product-upload-board '+(current?'has-current':'is-empty');
      const visual=document.createElement('div');visual.className='product-upload-visual';
      if(current)visual.append(current);else visual.innerHTML='<span class="product-upload-symbol">'+icon('droplet')+'</span><span data-upload-empty>Ảnh đại diện sản phẩm</span>';
      visual.append(preview);
      const actions=document.createElement('div');actions.className='product-upload-actions';
      const picker=document.createElement('button');picker.type='button';picker.className='admin-button product-file-picker';picker.innerHTML=icon('droplet')+(current?'Thay ảnh đại diện':'Tải ảnh từ máy');picker.onclick=()=>upload.click();
      const filename=document.createElement('span');filename.className='product-file-name';filename.setAttribute('role','status');filename.textContent=current?'Ảnh hiện tại được giữ nếu bạn không thay đổi.':'Chọn ảnh sản phẩm để hiển thị trên trang khách hàng.';
      const hint=document.createElement('small');hint.textContent='JPEG, PNG hoặc WebP · tối đa 5 MB';
      actions.append(picker,filename,hint);if(clear)actions.append(clear.closest('label'));
      board.append(visual,actions);upload.after(board);
      upload.addEventListener('change',()=>{
        if(objectURL)URL.revokeObjectURL(objectURL);
        const file=upload.files[0];preview.hidden=!file;
        if(current)current.hidden=Boolean(file);
        visual.querySelectorAll('[data-upload-empty],.product-upload-symbol').forEach(e=>e.hidden=Boolean(file));
        filename.textContent=file?file.name:(current?'Ảnh hiện tại được giữ nếu bạn không thay đổi.':'Chọn ảnh sản phẩm để hiển thị trên trang khách hàng.');
        if(file){objectURL=URL.createObjectURL(file);preview.src=objectURL;}
      });
    }
    dialog.addEventListener('close',()=>{if(objectURL)URL.revokeObjectURL(objectURL);},{once:true});
    if(clear)clear.addEventListener('change',()=>{clear.closest('label').classList.toggle('product-clear-selected',clear.checked);});
    form.querySelectorAll('[name$="_preset"]').forEach(select=>{const img=document.createElement('img');img.className='live-image-preview';img.alt='Ảnh có sẵn đã chọn';select.after(img);const update=()=>{img.hidden=!select.value;if(select.value)img.src='/static/images/'+encodeURIComponent(select.value);};select.onchange=update;update();});
    return form;
  }
  function bind(form,path){form.addEventListener('submit',async e=>{e.preventDefault();const submit=form.querySelector('[type="submit"]');if(submit.disabled)return;submit.disabled=true;const error=form.querySelector('[data-error]');error.hidden=true;form.querySelectorAll('[data-field-error]').forEach(e=>e.hidden=true);form.querySelectorAll('[aria-invalid]').forEach(e=>e.removeAttribute('aria-invalid'));
      try{await api(path,new FormData(form));dialog.close();await refresh();notice('Đã lưu thay đổi.');}catch(err){error.textContent=err.message;error.hidden=false;for(const [name,messages] of Object.entries(err.fields||{})){const field=form.elements.namedItem(name);field?.setAttribute?.('aria-invalid','true');const label=form.querySelector(`[data-field-error="${name}"]`);if(label){label.textContent=messages.join(' ');label.hidden=false;}}error.focus();}finally{submit.disabled=false;}});}
  root.addEventListener('input',e=>{if(e.target.closest('.admin-toolbar')){page=1;render();}});
  $('#ops-reset').onclick=()=>{root.querySelectorAll('.admin-toolbar input,.admin-toolbar select').forEach(e=>e.value='');page=1;render();};
  root.addEventListener('click',async e=>{const b=e.target.closest('button');if(!b||loading)return;if(b.dataset.productPage){page+=Number(b.dataset.productPage);render();return;}const action=b.id==='ops-add'?'add':b.hasAttribute('data-product-view')?'view':b.hasAttribute('data-product-edit')?'edit':b.hasAttribute('data-product-toggle')?'toggle':null;if(!action)return;
    const id=Number(b.dataset.productView||b.dataset.productEdit||b.dataset.productToggle||0),r=items.find(r=>r.id===id);loading=true;b.disabled=true;
    try{if(action==='toggle'){open(`${r.active?'Tắt':'Bật'} sản phẩm · ${code(id)}`,`<form><div class="admin-service-modal-scroll"><p>${r.active?'Tạm ngưng hiển thị':'Hiển thị lại'} “${esc(r.name)}” trên trang khách hàng?</p><p>Dữ liệu lịch sử và dịch vụ liên kết được bảo toàn.</p><input type="hidden" name="_toggle" value="1"><p data-error class="admin-service-error" role="alert" tabindex="-1" hidden></p></div><footer class="admin-dialog-actions"><button class="admin-button" type="button" data-close>Hủy</button><button class="admin-button admin-button-primary" type="submit">${icon('check')}Xác nhận</button></footer></form>`);bind(dialog.querySelector('form'),endpoint(id));}
    else{const data=await api(endpoint(id)+(action==='view'?'?view=1':''));open(`${action==='view'?'Thông tin':action==='edit'?'Sửa':'Thêm'} sản phẩm${id?' · '+code(id):''}`,data.html);if(action==='view'){const summary=document.createElement('section');summary.className='product-summary';summary.innerHTML=`${photo(r)}<div><h3>${esc(r.name)}</h3><p>${code(id)} · ${esc(r.product_type)}</p>${badge(r.active)}</div>`;dialog.querySelector('.admin-service-modal-scroll').prepend(summary);images();}else bind(prepareForm(Boolean(id)),endpoint(id));}}
    catch(err){notice(err.message);}finally{loading=false;b.disabled=false;}});
  refresh().catch(err=>notice(err.message));
})();
