(() => {
  'use strict';
  const host = document.querySelector('#admin-chat');
  const form = host.querySelector('form');
  const status = host.querySelector('[data-chat-status]');
  const list = host.querySelector('[data-chat-list]');
  const pages = host.querySelector('[data-chat-pages]');
  const detail = host.querySelector('[data-chat-detail]');
  const readOnly = host.querySelector('[data-chat-read-only]');
  const base = '/api/ai/admin/chat/sessions/';
  const labels = {pending: 'Đang xử lý', success: 'Thành công', fallback: 'Phản hồi dự phòng', error: 'Lỗi'};
  const date = new Intl.DateTimeFormat('vi-VN', {timeZone: 'Asia/Ho_Chi_Minh', dateStyle: 'short', timeStyle: 'short'});
  let listRequest = 0, detailRequest = 0, timer;

  function node(tag, text = '', className = '') {
    const element = document.createElement(tag);
    element.textContent = text;
    element.className = className;
    return element;
  }

  function button(text, click, disabled = false) {
    const element = node('button', text, 'admin-button');
    element.type = 'button';
    element.disabled = disabled;
    element.addEventListener('click', click);
    return element;
  }

  function badge(result) {
    const element = node('span', labels[result] || 'Chưa có phản hồi', 'chat-result');
    element.dataset.result = result || '';
    return element;
  }

  async function get(path) {
    const response = await fetch(base + path);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw Error(data.error || 'Không thể tải lịch sử. Vui lòng thử lại.');
    return data;
  }

  function paging(data, move, previous, next) {
    return [button(previous, () => move(data.page - 1), data.page <= 1),
      node('span', `${data.page} / ${data.pages}`), button(next, () => move(data.page + 1), data.page >= data.pages)];
  }

  async function open(sessionId, page = 1) {
    const request = ++detailRequest;
    detail.hidden = false;
    detail.replaceChildren(node('p', 'Đang tải nội dung hội thoại…', 'admin-data-note'));
    try {
      const data = await get(`${sessionId}/?page=${page}`);
      if (request !== detailRequest) return;
      const header = node('header');
      header.append(node('h3', 'Nội dung hội thoại'), node('p', `${data.session.name} · @${data.session.username}`),
        node('small', `Phiên #${data.session.id}`));
      const thread = node('div', '', 'chat-thread');
      thread.tabIndex = 0;
      thread.setAttribute('role', 'region');
      thread.setAttribute('aria-label', 'Tin nhắn hội thoại');
      for (const item of data.items) {
        const user = item.role === 'user';
        const row = node('article', '', user ? 'chat-message is-user' : 'chat-message');
        row.append(node('strong', user ? `Khách hàng · ${data.session.name}` : 'Trợ lý An Nhiên'),
          node('small', date.format(new Date(item.createdAt))), node('p', item.content || 'Đang chờ phản hồi…'), badge(item.status));
        thread.append(row);
      }
      if (!data.items.length) thread.append(node('p', 'Phiên chưa có tin nhắn.'));
      detail.replaceChildren(header, thread);
      if (data.pages > 1) {
        const pager = node('div', '', 'chat-pages');
        pager.append(...paging(data, number => open(sessionId, number), 'Mới hơn', 'Cũ hơn'));
        detail.append(pager);
      }
      thread.focus();
    } catch (error) {
      if (request === detailRequest) detail.textContent = error.message;
    }
  }

  function summary(session) {
    const card = node('article', '', 'admin-table-card chat-summary');
    const identity = node('div');
    identity.append(node('h3', session.name), node('small', `@${session.username}`), node('small', `Phiên #${session.id}`));
    const facts = node('dl', '', 'chat-facts');
    for (const [label, value] of [['Bắt đầu', date.format(new Date(session.startedAt))],
      ['Cập nhật', date.format(new Date(session.updatedAt))], ['Số tin nhắn', session.messageCount]]) {
      const fact = node('div');
      fact.append(node('dt', label), node('dd', value));
      facts.append(fact);
    }
    const actions = node('div', '', 'chat-actions');
    actions.append(badge(session.result), button('Xem hội thoại', () => open(session.id)));
    card.append(identity, facts, actions);
    return card;
  }

  async function load(page = 1) {
    const request = ++listRequest;
    ++detailRequest;
    detail.hidden = true;
    detail.replaceChildren();
    list.replaceChildren();
    pages.replaceChildren();
    status.textContent = 'Đang tải các phiên hội thoại…';
    const params = new URLSearchParams(new FormData(form));
    params.set('page', page);
    try {
      const data = await get(`?${params}`);
      if (request !== listRequest) return;
      form.hidden = readOnly.hidden = false;
      list.replaceChildren(...data.items.map(summary));
      if (data.total) pages.append(...paging(data, load, 'Trước', 'Sau'));
      status.textContent = data.items.length ? '' : 'Chưa có phiên hội thoại phù hợp.';
    } catch (error) {
      if (request !== listRequest) return;
      form.hidden = readOnly.hidden = true;
      status.textContent = error.message;
    }
  }

  form.addEventListener('submit', event => { event.preventDefault(); clearTimeout(timer); load(); });
  form.elements.search.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(load, 250); });
  form.elements.result.addEventListener('change', () => { clearTimeout(timer); load(); });
  document.querySelector('[data-customer-tab="chat"]').addEventListener('click', () => load());
})();
