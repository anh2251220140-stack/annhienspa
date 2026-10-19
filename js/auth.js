(() => {
  "use strict";
  // Prototype UI state only. Django must enforce authentication/permissions later.
  const sessionKey = "spa-auth";
  // Public, fictional credentials for Step 2 only; remove when Django is wired.
  const demoAccounts = [
    { email: "user@annhienspa.vn", username: "user", password: "User@123", role: "User" },
    { email: "admin@annhienspa.vn", username: "admin", password: "Admin@123", role: "Admin" },
  ];
  const memberPages = new Set([
    "home.html", "products.html", "product-detail.html", "booking.html",
    "appointments.html", "invoice.html", "profile.html", "reviews.html",
    "admin-dashboard.html",
  ]);
  const pageName = (url) => url.pathname.split("/").pop() || "index.html";
  const currentPage = pageName(new URL(location.href));
  const authPage = currentPage === "login.html" || currentPage === "register.html";
  const publicHome = currentPage === "index.html";

  function getSession() {
    try {
      const session = JSON.parse(sessionStorage.getItem(sessionKey));
      const account = demoAccounts.find((account) =>
        account.username === session?.username && account.email === session?.email &&
        account.role === session?.role);
      return session?.authenticated === true && account ? {
        authenticated: true,
        identifier: account.username,
        username: account.username,
        email: account.email,
        role: account.role,
      } : null;
    } catch {
      return null;
    }
  }
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
      // Clear only this prototype's user data, not unrelated browser session keys.
      for (const key of [sessionKey, "spa-profile", "spa-appointments", "spa-reviews"]) {
        sessionStorage.removeItem(key);
      }
      location.assign("index.html");
    } catch {
      const toast = document.querySelector(".toast");
      if (toast) {
        toast.hidden = false;
        toast.textContent = "Không thể xóa phiên mẫu. Vui lòng kiểm tra quyền lưu trữ của trình duyệt.";
      }
    }
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
      name: "Lan Anh", username: "user", email: "user@annhienspa.vn",
      phone: "", skin: "", needs: "", interests: "", budget: null, avatar: "",
    };
    if (typeof saved === "string") return { ...defaults, name: saved || defaults.name };
    return { ...defaults, ...(saved && typeof saved === "object" && !Array.isArray(saved) ? saved : {}) };
  }
  window.spaAuth = { isAuthenticated, urlFor, logout, allowed, getProfile };
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

    const form = document.querySelector("[data-auth-form]");
    if (!form) return;
    const status = document.querySelector("[data-auth-status]");
    const showError = (text) => {
      status.hidden = false;
      status.textContent = text;
    };
    const registration = currentPage === "register.html";
    const fields = [...form.querySelectorAll("input[required]")];
    const touched = new Set();
    const requiredMessages = {
      identifier: "Vui lòng nhập email hoặc tên đăng nhập.",
      fullName: "Vui lòng nhập họ và tên.",
      email: "Vui lòng nhập email.",
      username: "Vui lòng nhập tên đăng nhập.",
      phone: "Vui lòng nhập số điện thoại.",
      password: "Vui lòng nhập mật khẩu.",
      confirmPassword: "Vui lòng xác nhận mật khẩu.",
    };
    const clearStatus = () => {
      status.hidden = true;
      status.textContent = "";
    };
    const validateField = (input) => {
      let message = "";
      const value = input.value;
      if (!value.trim()) {
        message = requiredMessages[input.name];
      } else if (input.name === "email" &&
        (input.validity.typeMismatch || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim()))) {
        message = "Vui lòng nhập email hợp lệ.";
      } else if (registration && input.name === "password" && value.length < 6) {
        message = "Mật khẩu phải có ít nhất 6 ký tự.";
      } else if (input.name === "confirmPassword" && value !== form.elements.password.value) {
        message = "Xác nhận mật khẩu không khớp.";
      }
      const error = form.querySelector(`[data-field-error="${input.name}"]`);
      error.textContent = message;
      input.setAttribute("aria-invalid", String(Boolean(message)));
      return !message;
    };
    form.addEventListener("focusout", (event) => {
      if (!fields.includes(event.target)) return;
      touched.add(event.target.name);
      validateField(event.target);
    });
    form.addEventListener("input", (event) => {
      const input = event.target;
      if (!fields.includes(input)) return;
      clearStatus();
      if (touched.has(input.name)) validateField(input);
      if (registration && input.name === "password" && touched.has("confirmPassword")) {
        validateField(form.elements.confirmPassword);
      }
    });
    form.addEventListener("reset", () => {
      touched.clear();
      fields.forEach((input) => {
        input.removeAttribute("aria-invalid");
        form.querySelector(`[data-field-error="${input.name}"]`).textContent = "";
      });
      clearStatus();
    });
    if (currentPage === "login.html" && new URLSearchParams(location.search).get("registered") === "demo") {
      showError("Thông tin đăng ký hợp lệ. Vui lòng đăng nhập bằng tài khoản demo.");
    }
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      clearStatus();
      const invalidFields = fields.filter((input) => {
        touched.add(input.name);
        return !validateField(input);
      });
      if (invalidFields.length) {
        invalidFields[0].focus();
        return;
      }
      if (registration) {
        // No account database, and no credentials are persisted or transmitted.
        form.reset();
        location.assign("login.html?registered=demo");
        return;
      }
      const identifier = form.elements.identifier.value.trim();
      const normalizedIdentifier = identifier.toLowerCase();
      const account = demoAccounts.find((account) =>
        (account.username === normalizedIdentifier || account.email === normalizedIdentifier) &&
        account.password === form.elements.password.value);
      if (!account) {
        showError("Thông tin đăng nhập không chính xác.");
        return;
      }
      try {
        sessionStorage.setItem(sessionKey, JSON.stringify({
          authenticated: true,
          identifier: account.username,
          username: account.username,
          email: account.email,
          role: account.role,
        }));
        form.reset(); // Never save the password to storage or a URL.
        location.assign(landingPage());
      } catch {
        showError("Trình duyệt không cho phép lưu phiên mẫu. Vui lòng bật lưu trữ phiên để tiếp tục.");
      }
    });
    // With JavaScript disabled, credentials cannot be submitted by the static form.
    form.querySelector("[data-auth-fields]").disabled = false;
  });
})();
