(() => {
  "use strict";

  const alert = document.querySelector("[data-login-alert]");
  if (!alert) return;

  const close = alert.querySelector(".login-alert-close");
  let timer;

  function pause() {
    window.clearTimeout(timer);
  }

  function dismiss() {
    pause();
    const restoreFocus = alert.contains(document.activeElement);
    alert.hidden = true;
    if (restoreFocus) document.getElementById("identifier").focus();
  }

  function schedule() {
    pause();
    if (!alert.hidden && !alert.matches(":hover, :focus-within")) {
      timer = window.setTimeout(dismiss, 5500);
    }
  }

  close.addEventListener("click", dismiss);
  alert.addEventListener("pointerenter", pause);
  alert.addEventListener("pointerleave", schedule);
  alert.addEventListener("focusin", pause);
  alert.addEventListener("focusout", () => window.requestAnimationFrame(schedule));
  close.hidden = false;
  schedule();
})();
