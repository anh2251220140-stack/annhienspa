// Display only: preserve the ORM payload and all promotion calculations.
(() => {
  "use strict";
  if (document.documentElement.dataset.page !== "home.html") return;
  document.querySelectorAll("[data-home-discount]").forEach((label) => {
    label.textContent = label.textContent.replace(/(\d+)\.(\d+)(\s*%)/g, (_, whole, fraction, suffix) => {
      const significant = fraction.replace(/0+$/, "");
      return whole + (significant ? "." + significant : "") + suffix;
    });
  });
})();
