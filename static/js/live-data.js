// Server-supplied ORM data. Never fall back to sessionStorage/catalog fixtures.
window.spaCatalog = JSON.parse(document.getElementById("live-catalog").textContent);
window.spaPromotions = JSON.parse(document.getElementById("live-promotions").textContent);
