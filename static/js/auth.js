(() => {
  "use strict";
  const memberPages = new Set([
    "home.html", "products.html", "product-detail.html", "booking.html",
    "appointments.html", "invoice.html", "profile.html", "reviews.html",
    "admin-dashboard.html",
  ]);
  const pageName = (url) => url.pathname.split("/").pop() || "index.html";
  const currentPage = document.documentElement.dataset.page || pageName(new URL(location.href));
  const authPage = currentPage === "login.html" || currentPage === "register.html";
  const publicHome = currentPage === "index.html";

  const serverSession = JSON.parse(document.getElementById("spa-auth-context").textContent);
  function getSession() { return serverSession; }
  // Clear unrelated demo state when identities change. Never persist authentication.
  try {
    const identity = String(serverSession?.id || "guest");
    if (sessionStorage.getItem("spa-ui-identity") !== identity) {
      Object.keys(sessionStorage).filter((key) => key.startsWith("spa-")).forEach((key) => sessionStorage.removeItem(key));
      sessionStorage.setItem("spa-ui-identity", identity);
    }
    sessionStorage.removeItem("spa-auth");
  } catch { /* Server sessions work even when browser storage is disabled. */ }
  function isAuthenticated() {
    return getSession() !== null;
  }
  function landingPage() {
    return getSession()?.role === "Admin" ? "admin-dashboard.html" : "home.html";
  }
  function blockedDestination(path) {
    const page = pageName(new URL(path, location.href));
    if (!memberPages.has(page)) return null;
    const session = getSession();
    if (!session) return "login.html";
    return page === "admin-dashboard.html" && session.role !== "Admin" ? "home.html" : null;
  }
  function urlFor(path) {
    return blockedDestination(path) || path;
  }
  function performLogout() {
    try {
      Object.keys(sessionStorage).filter((key) => key.startsWith("spa-")).forEach((key) => sessionStorage.removeItem(key));
    } catch { /* Logout still runs on the server. */ }
    document.getElementById("spa-logout-form").requestSubmit();
  }
  function logout() {
    window.spaConfirmLogout(performLogout);
  }
  const redirect = blockedDestination(currentPage);
  const allowed = redirect === null;
  function getProfile() {
    let saved;
    try { saved = JSON.parse(sessionStorage.getItem("spa-profile")); } catch { /* Use demo defaults. */ }
    const defaults = {
      name: serverSession?.name || "", username: serverSession?.username || "", email: serverSession?.email || "",
      phone: "", skin: "", needs: "", interests: "", budget: null, avatar: "",
    };
    if (typeof saved === "string") return { ...defaults, name: saved || defaults.name };
    return { ...defaults, ...(saved && typeof saved === "object" && !Array.isArray(saved) ? saved : {}) };
  }
  window.spaAuth = { getSession, isAuthenticated, urlFor, logout, allowed, getProfile };
  if (!allowed) {
    document.documentElement.classList.add("auth-redirecting");
    location.replace(redirect);
    return;
  }
  if (currentPage === "login.html" && isAuthenticated()) {
    location.replace(landingPage());
    return;
  }
  if (!isAuthenticated() && !publicHome && !authPage) {
    document.documentElement.classList.add("auth-header-pending");
  }

  // Delegation also covers protected links added later by filters/related cards.
  document.addEventListener("click", (event) => {
    const link = event.target.closest("a[href]");
    if (!link) return;
    const target = new URL(link.getAttribute("href"), location.href);
    if (target.origin !== location.origin || !memberPages.has(pageName(target))) return;
    const destination = blockedDestination(target.href);
    if (destination) {
      event.preventDefault();
      location.assign(destination);
    }
  }, true);

  document.addEventListener("DOMContentLoaded", () => {
    const signedIn = isAuthenticated();
    const header = document.querySelector(".site-header");
    if (header && (!signedIn || publicHome || authPage)) {
      const navigation = header.querySelector(".navigation");
      navigation.innerHTML = `
        <a href="services.html">Dịch vụ</a>
        <a href="promotions.html">Khuyến mãi</a>
        <a class="button header-book" href="${urlFor("booking.html")}">Đặt lịch</a>`;
      header.querySelector(".header-logout")?.remove();
      if (!header.querySelector("[data-login-link]")) {
        const login = document.createElement("a");
        login.className = "login-link";
        login.dataset.loginLink = "";
        login.href = "login.html";
        login.textContent = "Đăng nhập";
        header.append(login);
      }
      header.querySelector(".brand").href = "index.html";
    }
    if (signedIn && !publicHome && !authPage) {
      document.querySelectorAll('a.brand[href="index.html"], .breadcrumb a[href="index.html"]')
        .forEach((link) => { link.href = landingPage(); });
    }
    if (header && getSession()?.role === "User" && !publicHome && !authPage) {
      const link = header.querySelector('.navigation a[href="profile.html"]');
      if (link) {
        const account = document.createElement("div");
        account.className = "account-menu";
        account.innerHTML = `<button class="account-trigger" type="button" aria-expanded="false" aria-controls="account-dropdown">
          <span class="account-avatar" data-account-avatar aria-hidden="true"></span><span class="account-name" data-account-name></span>
          <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" aria-hidden="true"><path d="m4 6 4 4 4-4"/></svg></button>
          <div class="account-dropdown" id="account-dropdown" hidden>
            <div class="account-identity"><span class="account-avatar" data-account-avatar aria-hidden="true"></span>
              <div><strong data-account-name></strong><span class="membership-badge">Hạng: chờ xác định</span></div></div>
            <a href="profile.html">Xem hồ sơ</a><a href="reviews.html">Đánh giá của tôi</a>
          </div>`;
        link.replaceWith(account);
        const trigger = account.querySelector(".account-trigger");
        const dropdown = account.querySelector(".account-dropdown");
        const close = () => { dropdown.hidden = true; trigger.setAttribute("aria-expanded", "false"); };
        const update = () => {
          const profile = getProfile();
          account.querySelectorAll("[data-account-name]").forEach((node) => { node.textContent = profile.name; });
          account.querySelectorAll("[data-account-avatar]").forEach((node) => {
            node.textContent = String(profile.name || "Lan Anh").trim().split(/\s+/).slice(-2).map((part) => part[0]).join("").toUpperCase();
            if (/^data:image\/(?:png|jpeg|webp);base64,/.test(profile.avatar)) {
              const image = document.createElement("img");
              image.src = profile.avatar;
              image.alt = "";
              node.replaceChildren(image);
            }
          });
        };
        update();
        document.addEventListener("spa-profile-updated", update);
        trigger.addEventListener("click", () => {
          dropdown.hidden = !dropdown.hidden;
          trigger.setAttribute("aria-expanded", String(!dropdown.hidden));
        });
        document.addEventListener("click", (event) => { if (!account.contains(event.target)) close(); });
        account.addEventListener("keydown", (event) => {
          if (event.key === "Escape") { close(); trigger.focus(); }
        });
        account.addEventListener("focusout", (event) => { if (!account.contains(event.relatedTarget)) close(); });
      }
    }
    document.querySelectorAll("a[href]").forEach((link) => {
      const target = new URL(link.getAttribute("href"), location.href);
      if (target.origin !== location.origin) return;
      const destination = blockedDestination(target.href);
      if (destination) link.href = destination;
    });
    document.documentElement.classList.remove("auth-header-pending");

    // Native POST + CSRF + server validation handles the authentication forms.
  });
})();
