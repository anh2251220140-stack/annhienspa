(async () => {
  const {api, escape: escapeHtml, date} = window.spaLive;
  const savedList = document.querySelector('#review-list');
  const pendingList = document.querySelector('#review-pending');
  const status = document.querySelector('#my-review-status');
  const servicePath = savedList.dataset.servicePath;
  const activeServices = new Set(window.spaCatalog.services.filter(service => service.active).map(service => service.id));
  const profile = window.spaAuth.getProfile();
  const ratings = [1, 2, 3, 4, 5];
  const dateOnly = new Intl.DateTimeFormat('vi-VN', {
    day: '2-digit', month: '2-digit', year: 'numeric', timeZone: 'Asia/Ho_Chi_Minh'
  });

  function serviceUrl(serviceId, appointmentId) {
    const params = new URLSearchParams({id: serviceId});
    if (appointmentId) params.set('appointment', appointmentId);
    return servicePath + '?' + params + '#reviews';
  }

  function reviewCard(review) {
    const stars = ratings.map(number =>
      `<span data-selected="${number <= review.rating}">${window.spaIcon('star')}</span>`
    ).join('');
    const replies = review.replies.map(reply => `
      <div class="review-reply">
        <strong>${escapeHtml(reply.role === 'Admin' ? 'An Nhiên Spa' : review.customer)}</strong>
        <time datetime="${escapeHtml(reply.createdAt)}">${escapeHtml(date(reply.createdAt))}</time>
        <p>${escapeHtml(reply.content)}</p>
      </div>`).join('');
    return `<article class="review-item review-surface" tabindex="-1" data-saved-review="${review.appointmentId}">
      <h2>${escapeHtml(review.service)}</h2>
      <div class="review-byline">
        <span class="account-avatar" data-review-avatar aria-hidden="true"></span>
        <div><strong>${escapeHtml(review.customer)}</strong>
          <span class="review-stars" role="img" aria-label="${review.rating} trên 5 sao">${stars}</span>
        </div>
        <time datetime="${escapeHtml(review.createdAt)}">${dateOnly.format(new Date(review.createdAt))}</time>
      </div>
      ${review.comment ? `<p class="review-comment">${escapeHtml(review.comment)}</p>` : ''}
      <p class="review-note">Lịch hẹn ${window.spaAppointmentCode(review.appointmentId)}</p>
      ${replies ? `<section class="my-review-replies" aria-label="Phản hồi">${replies}</section>` : ''}
      ${activeServices.has(review.serviceId) ? '' : '<p class="review-note">Dịch vụ hiện không hiển thị công khai.</p>'}
      <div class="review-actions">
        <a class="button small" href="${escapeHtml(serviceUrl(review.serviceId, review.appointmentId))}">Chỉnh sửa</a>
        <a class="button small" href="${escapeHtml(serviceUrl(review.serviceId))}">Xem dịch vụ</a>
      </div>
    </article>`;
  }

  function pendingCard(appointment) {
    const choices = ratings.map(number => `<label data-selected="false">
      <input type="radio" name="rating" value="${number}" required aria-label="${number} sao">
      ${window.spaIcon('star')}</label>`).join('');
    const date = appointment.date.split('-').reverse().join('/');
    return `<article class="review-surface">
      <h3>${escapeHtml(appointment.service)}</h3>
      <p class="review-note">Lịch hẹn ${window.spaAppointmentCode(appointment.id)} · Ngày hẹn ${escapeHtml(date)}</p>
      <details>
        <summary>Viết đánh giá</summary>
        <form class="phase4-form" data-create-review="${appointment.id}">
          <fieldset class="review-rating"><legend>Điểm đánh giá (bắt buộc)</legend>${choices}</fieldset>
          <label>Nhận xét (không bắt buộc)<textarea name="comment" maxlength="2000" rows="4"></textarea></label>
          <div class="review-actions"><button class="button small filled" type="submit">Gửi đánh giá</button></div>
          <p class="review-note" role="status" data-form-status hidden></p>
        </form>
      </details>
    </article>`;
  }

  function renderSaved(items) {
    savedList.innerHTML = items.map(reviewCard).join('') ||
      '<p class="review-surface">Bạn chưa gửi đánh giá nào.</p>';
    items.forEach(review => {
      const avatar = savedList.querySelector('[data-saved-review="' + review.appointmentId + '"] [data-review-avatar]');
      window.spaAuth.renderAvatar(avatar, review.customer, profile.avatar);
    });
  }

  function pendingEmpty(eligible) {
    pendingList.innerHTML = '<p class="review-surface">' + (eligible.length
      ? 'Bạn đã đánh giá tất cả lịch hẹn đã hoàn thành.'
      : 'Chưa có lịch hẹn đã hoàn thành để đánh giá.') + '</p>';
  }

  let data;
  try {
    data = await api('/api/reviews/');
    renderSaved(data.items);
    const reviewed = new Set(data.items.map(review => review.appointmentId));
    const pending = data.eligible.filter(appointment => !reviewed.has(appointment.id));
    if (pending.length) pendingList.innerHTML = pending.map(pendingCard).join('');
    else pendingEmpty(data.eligible);
    status.hidden = true;
    document.querySelector('#review-pending-section').hidden = false;
  } catch (error) {
    status.textContent = 'Không tải được danh sách đánh giá. Vui lòng tải lại trang.';
    return;
  }

  pendingList.addEventListener('change', event => {
    if (event.target.name !== 'rating') return;
    event.target.form.querySelectorAll('.review-rating label').forEach(label => {
      label.dataset.selected = Number(label.querySelector('input').value) <= Number(event.target.value);
    });
  });

  pendingList.addEventListener('submit', async event => {
    const form = event.target.closest('[data-create-review]');
    if (!form) return;
    event.preventDefault();
    const button = form.querySelector('[type="submit"]');
    if (button.disabled || !form.reportValidity()) return;
    const feedback = form.querySelector('[data-form-status]');
    button.disabled = true;
    feedback.hidden = true;
    try {
      const {item} = await api('/api/reviews/appointments/' + form.dataset.createReview + '/',
        Object.fromEntries(new FormData(form)));
      data.items = [item, ...data.items.filter(review => review.appointmentId !== item.appointmentId)];
      renderSaved(data.items);
      form.closest('article').remove();
      if (!pendingList.childElementCount) pendingEmpty(data.eligible);
      status.textContent = 'Đã gửi đánh giá.';
      status.hidden = false;
      savedList.querySelector('[data-saved-review="' + item.appointmentId + '"]').focus();
    } catch (error) {
      feedback.textContent = /hóa đơn/i.test(error.message)
        ? 'Chưa xác nhận được đánh giá. Vui lòng tải lại để kiểm tra trước khi gửi lại.'
        : error.message;
      feedback.hidden = false;
      button.disabled = false;
    }
  });
})();
