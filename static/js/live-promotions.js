(() => {
  'use strict';
  const root = document.querySelector('[data-admin-operations="promotions"]');
  if (!root) return;
  const $ = selector => document.querySelector(selector), dialog = $('#ops-dialog');
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const normalize = value => String(value ?? '').toLocaleLowerCase('vi').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd').trim();
  const icon = name => {
    const paths = {edit:'<path d="m16 3 5 5-12 12H4v-5ZM14 5l5 5"/>',power:'<path d="M12 2v10M6 5a9 9 0 1 0 12 0"/>',check:'<path d="m4 12 5 5L20 6"/>'};
    return paths[name] ? `<svg class="line-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name]}</svg>` : window.spaIcon(name);
  };
  const date = value => /^\d{4}-\d{2}-\d{2}$/.test(value || '') ? value.split('-').reverse().join('/') : 'Chưa cập nhật';
  // Trim only insignificant zeroes; never round meaningful decimal digits.
  const decimal = value => String(value).replace(/(\.\d*?)0+$/, '$1').replace(/\.$/, '');
  const money = value => {
    const [whole, fraction] = decimal(value).split('.');
    return whole.replace(/\B(?=(\d{3})+(?!\d))/g, '.') + (fraction ? ',' + fraction : '') + ' VND';
  };
  const discount = row => 'Giảm ' + (row.discount_type === 'percent' ? decimal(row.discount_value) + '%' : money(row.discount_value));
  const labels = {active:'Đang hiệu lực',ending:'Sắp hết hạn',future:'Chưa bắt đầu',expired:'Đã hết hạn',inactive:'Tạm ngừng'};
  const endpoint = id => '/api/admin/promotions/' + (id === undefined ? '' : id + '/');
  let items = [], page = 1, loading = false, returnFocus;
  function status(row) {
    const today = window.spaPromotions.referenceDate;
    if (!row.active) return 'inactive';
    if (row.start_date > today) return 'future';
    if (row.end_date < today) return 'expired';
    return (Date.parse(row.end_date) - Date.parse(today)) / 86400000 <= 7 ? 'ending' : 'active';
  }
  const badge = row => {
    const state = status(row), color = state === 'active' ? 'completed' : ['ending','future'].includes(state) ? 'pending' : 'cancelled';
    return `<span class="admin-status-badge admin-status-${color}">${labels[state]}</span>`;
  };
  function notice(message) { $('#ops-notice').textContent = message; $('#ops-notice').hidden = false; }
  async function api(path, data) {
    const response = await fetch(path, data ? {method:'POST',body:data,headers:{'X-CSRFToken':$('[name="csrfmiddlewaretoken"]').value}} : {});
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = Error(payload.error || Object.values(payload.errors || {}).flat().join(' ') || 'Không thể thực hiện thao tác. Vui lòng kiểm tra đăng nhập và thử lại.');
      error.fields = payload.errors;
      throw error;
    }
    return payload;
  }
  function render() {
    const query = normalize($('#ops-search').value), selected = $('#ops-status').value;
    const filtered = items.filter(row => normalize(row.name + ' ' + row.code).includes(query) && (!selected || status(row) === selected));
    const pages = Math.max(1, Math.ceil(filtered.length / 5));
    page = Math.max(1, Math.min(page, pages));
    const start = (page - 1) * 5, visible = filtered.slice(start, start + 5);
    $('#ops-rows').innerHTML = visible.map(row => `<tr><td class="promotion-code">${esc(row.code)}</td><td class="promotion-program"><strong>${esc(row.name)}</strong><p>${esc(row.description)}</p></td><td><strong class="promotion-discount">${esc(discount(row))}</strong></td><td class="promotion-dates">${date(row.start_date)}<span>đến ${date(row.end_date)}</span></td><td>${badge(row)}</td><td><div class="admin-row-actions">${[['view','eye','Xem'],['edit','edit','Sửa'],['toggle','power',row.active ? 'Tắt' : 'Bật']].map(([action,symbol,label]) => `<button type="button" class="admin-button" data-promotion-${action}="${row.id}" aria-label="${label} ${esc(row.name)}">${icon(symbol)}${label}</button>`).join('')}</div></td></tr>`).join('');
    $('#ops-empty').hidden = filtered.length > 0;
    $('#ops-pagination').innerHTML = `<span>${visible.length} / ${filtered.length} khuyến mãi${filtered.length ? ' · ' + (start + 1) + '–' + (start + visible.length) : ''}</span><div><button type="button" class="admin-button" data-promotion-page="-1" ${page === 1 ? 'disabled' : ''}>Trước</button><span>${page} / ${pages}</span><button type="button" class="admin-button" data-promotion-page="1" ${page === pages ? 'disabled' : ''}>Sau</button></div>`;
  }
  async function refresh() {
    // Use the server's Vietnam calendar date, with the same inclusive validity rules as the User catalog.
    if (!/^\d{4}-\d{2}-\d{2}$/.test(window.spaPromotions?.referenceDate || '')) throw Error('Chưa tải được ngày hiệu lực từ hệ thống. Vui lòng tải lại trang.');
    items = (await api(endpoint())).items;
    $('#ops-stats').innerHTML = [['Tổng chương trình',items.length,'star'],['Đang hiệu lực',items.filter(row => ['active','ending'].includes(status(row))).length,'leaf'],['Tạm ngừng',items.filter(row => !row.active).length,'clock']].map(([label,count,symbol]) => `<article><div><span class="promotion-stat-icon">${icon(symbol)}</span><span>${label}</span></div><strong>${count}</strong></article>`).join('');
    render();
  }
  function open(title, body) {
    if (!dialog.open) returnFocus = document.activeElement;
    dialog.innerHTML = `<header class="admin-service-modal-heading"><span class="admin-service-modal-icon">${icon('star')}</span><div><span class="admin-eyebrow">AN NHIÊN SPA / QUẢN TRỊ</span><h2 id="ops-dialog-title">${esc(title)}</h2></div><button type="button" class="admin-icon-button" data-close aria-label="Đóng">${icon('close')}</button></header>${body}`;
    dialog.querySelectorAll('[data-close]').forEach(button => button.onclick = () => dialog.close());
    dialog.querySelectorAll('[data-live-icon]').forEach(node => node.innerHTML = icon(node.dataset.liveIcon));
    dialog.querySelectorAll('.admin-dialog-actions [data-close]').forEach(button => button.insertAdjacentHTML('afterbegin', icon('close')));
    if (!dialog.open) dialog.showModal();
  }
  dialog.addEventListener('close', () => returnFocus?.isConnected && returnFocus.focus());
  function prepareDetail(row) {
    const body = dialog.querySelector('.admin-service-modal-scroll');
    const summary = document.createElement('section');
    summary.className = 'promotion-summary';
    summary.innerHTML = `<span class="promotion-summary-icon">${icon('star')}</span><h3>${esc(row.name)}</h3>${badge(row)}`;
    body.prepend(summary);
    // Keep server-rendered business conditions/limits/scope intact; format only known display values.
    dialog.querySelectorAll('dt').forEach(label => {
      const name = label.textContent.trim(), value = label.nextElementSibling;
      if (name === 'Tên chương trình') { label.parentElement.remove(); return; }
      if (name === 'Giá trị ưu đãi') value.textContent = discount(row);
      if (name === 'Ngày bắt đầu') value.textContent = date(row.start_date);
      if (name === 'Ngày kết thúc') value.textContent = date(row.end_date);
      if (['Giá trị tối thiểu','Giảm tối đa'].includes(name) && /^\d+(\.\d+)?$/.test(value.textContent.trim())) value.textContent = money(value.textContent.trim());
      if (name === 'Mã thay thế — mỗi dòng một mã' && value.textContent.trim() === 'Chưa cập nhật') value.textContent = 'Không có mã khác';
      // Entry instructions belong to the form, not the read-only detail labels.
      if (name === 'Mã thay thế — mỗi dòng một mã') label.textContent = 'Mã thay thế';
      if (name === 'Điều kiện áp dụng — mỗi dòng một điều kiện') label.textContent = 'Điều kiện áp dụng';
      const symbol = name.startsWith('Ngày') ? 'calendar' : name.includes('Dịch vụ') ? 'leaf' : 'note';
      label.insertAdjacentHTML('afterbegin', icon(symbol));
    });
  }
  function prepareForm(isEdit) {
    const form = dialog.querySelector('form');
    const submit = form.querySelector('[type="submit"]');
    submit.innerHTML = icon('check') + (isEdit ? 'Lưu thay đổi' : 'Lưu');
    // The shared form includes image guidance; Promotions has no image upload.
    form.querySelectorAll('.admin-data-note').forEach(note => {
      if (note.textContent.trim() === 'Các trường * là bắt buộc. Bật/Tắt được quản lý tại danh sách. Ảnh tải lên tối đa 5 MB; chọn ảnh có sẵn sẽ thay ảnh đang hiển thị.') note.textContent = 'Các trường * là bắt buộc.';
    });
    form.querySelectorAll('input[type="date"]').forEach(nativeDate => {
      const control = document.createElement('span'); control.className = 'promotion-date-control';
      const text = document.createElement('input'); text.type = 'text'; text.inputMode = 'numeric';
      text.placeholder = 'dd/mm/yyyy'; text.maxLength = 10; text.autocomplete = 'off';
      text.id = nativeDate.id + '-display'; text.dataset.dateDisplay = nativeDate.name;
      text.value = nativeDate.value ? date(nativeDate.value) : ''; text.required = nativeDate.required;
      const label = form.querySelector(`label[for="${CSS.escape(nativeDate.id)}"]`);
      if (label) label.htmlFor = text.id;
      const picker = document.createElement('button'); picker.type = 'button'; picker.className = 'admin-icon-button';
      picker.setAttribute('aria-label', 'Chọn ' + (nativeDate.name === 'start_date' ? 'ngày bắt đầu' : 'ngày kết thúc'));
      picker.innerHTML = icon('calendar');
      nativeDate.before(control); control.append(text,nativeDate,picker);
      nativeDate.classList.add('promotion-native-date'); nativeDate.tabIndex = -1;
      nativeDate.addEventListener('change', () => { text.value = nativeDate.value ? date(nativeDate.value) : ''; text.setCustomValidity(''); });
      text.addEventListener('input', () => {
        const match = text.value.trim().match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
        const iso = match ? `${match[3]}-${match[2]}-${match[1]}` : '';
        const parsed = new Date(iso + 'T00:00:00Z');
        const valid = iso && !Number.isNaN(parsed.valueOf()) && parsed.toISOString().slice(0,10) === iso;
        nativeDate.value = valid ? iso : '';
        text.setCustomValidity(text.value && !valid ? 'Nhập ngày hợp lệ theo dd/mm/yyyy.' : '');
      });
      picker.onclick = () => { try { nativeDate.showPicker(); } catch (_) { text.focus(); } };
    });
    const group = form.querySelector('.admin-ops-checks');
    if (group) {
      const checks = [...group.querySelectorAll('input[type="checkbox"][name="services"]')];
      const controls = document.createElement('div');
      controls.className = 'promotion-service-controls';
      controls.innerHTML = '<label for="promotion-service-search">Tìm dịch vụ</label><input type="search" id="promotion-service-search" placeholder="Nhập tên hoặc mã dịch vụ..."><p data-service-summary aria-live="polite"></p>';
      group.querySelector('legend').after(controls);
      const empty = document.createElement('p'); empty.textContent = 'Không có dịch vụ khớp tìm kiếm.'; group.append(empty);
      const update = () => {
        const query = normalize(controls.querySelector('input').value), selected = checks.filter(check => check.checked);
        controls.querySelector('[data-service-summary]').textContent = `Đã chọn ${selected.length} dịch vụ${selected.length ? ': ' + selected.map(check => check.closest('label').textContent.trim()).join('; ') : ''}`;
        checks.forEach(check => check.closest('label').hidden = !normalize(check.closest('label').textContent + ' DV-' + String(check.value).padStart(3,'0')).includes(query));
        empty.hidden = !checks.length || checks.some(check => !check.closest('label').hidden);
      };
      controls.addEventListener('input', update);
      checks.forEach(check => check.addEventListener('change', update)); update();
    }
    return form;
  }
  function bind(form, path) {
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const submit = form.querySelector('[type="submit"]'), error = form.querySelector('[data-error]');
      if (submit.disabled) return;
      submit.disabled = true; error.hidden = true;
      form.querySelectorAll('[data-field-error]').forEach(node => node.hidden = true);
      form.querySelectorAll('[aria-invalid]').forEach(node => node.removeAttribute('aria-invalid'));
      try { await api(path, new FormData(form)); dialog.close(); await refresh(); notice('Đã lưu thay đổi.'); }
      catch (err) {
        error.textContent = err.message; error.hidden = false;
        for (const [name,messages] of Object.entries(err.fields || {})) {
          const fields = form.querySelectorAll(`[name="${CSS.escape(name)}"]`);
          fields.forEach(field => field.setAttribute('aria-invalid','true'));
          form.querySelector(`[data-date-display="${CSS.escape(name)}"]`)?.setAttribute('aria-invalid','true');
          const detail = form.querySelector(`[data-field-error="${CSS.escape(name)}"]`);
          if (detail) { detail.textContent = messages.join(' '); detail.hidden = false; }
        }
        error.focus();
      } finally { submit.disabled = false; }
    });
  }
  root.addEventListener('input', event => { if (event.target.closest('.admin-toolbar')) { page = 1; render(); } });
  $('#ops-reset').onclick = () => { $('#ops-search').value = ''; $('#ops-status').value = ''; page = 1; render(); };
  root.addEventListener('click', async event => {
    const button = event.target.closest('button'); if (!button || loading) return;
    if (button.dataset.promotionPage) { page += Number(button.dataset.promotionPage); render(); return; }
    const action = button.id === 'ops-add' ? 'add' : button.hasAttribute('data-promotion-view') ? 'view' : button.hasAttribute('data-promotion-edit') ? 'edit' : button.hasAttribute('data-promotion-toggle') ? 'toggle' : null;
    if (!action) return;
    const id = Number(button.dataset.promotionView || button.dataset.promotionEdit || button.dataset.promotionToggle || 0), row = items.find(row => row.id === id);
    loading = true; button.disabled = true;
    try {
      if (action === 'toggle') {
        open(`${row.active ? 'Tắt' : 'Bật'} khuyến mãi`, `<form><div class="admin-service-modal-scroll"><p>${row.active ? 'Tạm ngừng' : 'Bật lại'} “${esc(row.name)}”?</p><p>Hiệu lực vẫn phụ thuộc ngày áp dụng và điều kiện chương trình. Dữ liệu lịch sử được bảo toàn.</p><input type="hidden" name="_toggle" value="1"><p data-error class="admin-service-error" role="alert" tabindex="-1" hidden></p></div><footer class="admin-dialog-actions"><button type="button" class="admin-button" data-close>Hủy</button><button type="submit" class="admin-button admin-button-primary">${icon('check')}Xác nhận</button></footer></form>`);
        bind(dialog.querySelector('form'), endpoint(id));
      } else {
        const data = await api(endpoint(id) + (action === 'view' ? '?view=1' : ''));
        open(`${action === 'view' ? 'Thông tin' : action === 'edit' ? 'Sửa' : 'Thêm'} khuyến mãi`, data.html);
        if (action === 'view') prepareDetail(row); else bind(prepareForm(Boolean(id)), endpoint(id));
      }
    } catch (err) { notice(err.message); }
    finally { loading = false; button.disabled = false; }
  });
  refresh().catch(err => notice(err.message));
})();
