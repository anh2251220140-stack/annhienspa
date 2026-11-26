(() => {
  "use strict";
  window.spaAppointmentCode = (id) => `LH-${String(id).padStart(6, "0")}`;
  window.spaInvoiceCode = (id) => `HD-${String(id).padStart(6, "0")}`;
  const paths = {
    leaf: '<path d="M5 18C1 9 10 4 20 3c0 10-4 18-13 15M3 21 15 9m-7 7 1-6m3 2h5"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    calendar: '<rect x="4" y="5" width="16" height="16" rx="3"/><path d="M8 3v4m8-4v4M4 10h16m-11 5h2m3 0h2"/>',
    droplet: '<path d="M12 3S5 11 5 15a7 7 0 0 0 14 0c0-4-7-12-7-12Z"/><path d="M9 16c0 2 1 3 3 3"/>',
    heart: '<path d="M12 21S3 15 3 9a5 5 0 0 1 9-3 5 5 0 0 1 9 3c0 6-9 12-9 12Z"/>',
    note: '<rect x="5" y="3" width="14" height="18" rx="3"/><path d="M9 8h6m-6 4h6m-6 4h3"/>',
    star: '<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9Z"/>',
    chat: '<path d="M21 11.5a9 9 0 0 1-9 9 10 10 0 0 1-4-.9L3 21l1.4-5A9 9 0 1 1 21 11.5Z"/><path d="M8 10h8m-8 4h5"/>',
    close: '<path d="m6 6 12 12M6 18 18 6"/>',
    eye: '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
    "eye-off": '<path d="m3 3 18 18M10 5a11 11 0 0 1 2 0c6 0 10 7 10 7a20 20 0 0 1-3 4M6 6a22 22 0 0 0-4 6s4 7 10 7a12 12 0 0 0 5-1M10 10a3 3 0 0 0 4 4"/>',
  };
  window.spaIcon = (name) => `<svg class="line-icon" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.25" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${paths[name] || paths.leaf}</svg>`;

  let dialog;
  let confirmAction;
  let returnFocus;
  window.spaConfirmLogout = (action) => {
    if (!dialog) {
      dialog = document.createElement("dialog");
      dialog.className = "logout-dialog";
      dialog.setAttribute("aria-labelledby", "logout-title");
      dialog.setAttribute("aria-describedby", "logout-description");
      dialog.innerHTML = `<span class="eyebrow">AN NHIÊN SPA</span>
        <h2 id="logout-title">Xác nhận đăng xuất</h2>
        <p id="logout-description">Bạn có chắc chắn muốn đăng xuất khỏi An Nhiên Spa không?</p>
        <div class="logout-actions"><button class="button" type="button" data-logout-cancel autofocus>Không</button>
        <button class="button filled" type="button" data-logout-confirm>Có, đăng xuất</button></div>`;
      document.body.append(dialog);
      dialog.querySelector("[data-logout-cancel]").addEventListener("click", () => dialog.close());
      dialog.querySelector("[data-logout-confirm]").addEventListener("click", () => {
        const action = confirmAction;
        dialog.close();
        action();
      });
      dialog.addEventListener("close", () => {
        document.documentElement.classList.remove("logout-open");
        if (returnFocus?.isConnected) returnFocus.focus({ preventScroll: true });
      });
      dialog.addEventListener("click", (event) => {
        const rect = dialog.getBoundingClientRect();
        if (event.target === dialog && (event.clientX < rect.left || event.clientX > rect.right ||
          event.clientY < rect.top || event.clientY > rect.bottom)) dialog.close();
      });
    }
    confirmAction = action;
    if (!dialog.open) {
      returnFocus = document.querySelector(".header-logout") || document.activeElement;
      document.documentElement.classList.add("logout-open");
      dialog.showModal();
    }
  };

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll('input[type="password"]').forEach((input) => {
      if (input.closest(".password-control")) return;
      const label = input.labels?.[0]?.childNodes[0]?.textContent.trim() || "mật khẩu";
      const wrapper = document.createElement("span");
      wrapper.className = "password-control";
      input.replaceWith(wrapper);
      const button = document.createElement("button");
      button.type = "button";
      button.className = "password-toggle";
      button.setAttribute("aria-controls", input.id);
      const update = (shown) => {
        input.type = shown ? "text" : "password";
        button.innerHTML = window.spaIcon(shown ? "eye-off" : "eye");
        button.setAttribute("aria-label", `${shown ? "Ẩn" : "Hiện"} ${label.toLocaleLowerCase("vi")}`);
        button.setAttribute("aria-pressed", String(shown));
      };
      wrapper.append(input, button);
      update(false);
      button.addEventListener("pointerdown", (event) => event.preventDefault());
      button.addEventListener("click", () => {
        const start = input.selectionStart;
        const end = input.selectionEnd;
        update(input.type === "password");
        input.focus({ preventScroll: true });
        if (start !== null && end !== null) input.setSelectionRange(start, end);
      });
      input.form?.addEventListener("reset", () => update(false));
      input.form?.addEventListener("submit", () => update(false));
      window.addEventListener("pagehide", () => update(false));
      document.addEventListener("visibilitychange", () => { if (document.hidden) update(false); });
    });
  });
})();
