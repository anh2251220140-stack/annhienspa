"""Check the real Services template and scripts in Chrome without a server or database."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    (["Dưỡng ẩm, cải thiện da khô"], "face"),
    (["Kiểm soát dầu, chăm sóc da mụn"], "face"),
    (["Làm sáng da, cải thiện da xỉn màu"], "face"),
    (["Thư giãn, giảm căng thẳng"], "relax"),
    (["Chăm sóc tóc và da đầu"], "hair"),
    (["Chăm sóc cơ thể, giảm mệt mỏi"], "body"),
    (["Chăm sóc tóc và da đầu", "Thư giãn, giảm căng thẳng"], "hair"),
    (["Thư giãn, giảm căng thẳng", "Chăm sóc tóc và da đầu"], "relax"),
    ([], ""),
    ("Ghi chú cũ về massage và da mặt", ""),
    ([None, 123, "Ghi chú cũ", " Chăm sóc cơ thể , giảm mệt mỏi "], "body"),
]
CHECK = r"""
<script>
window.addEventListener('error', (event) => {
  if (event.error) document.documentElement.dataset.scriptError = event.message;
});
</script>
"""
DRIVER = r"""
<iframe title="Isolated Services page" style="border:0;height:850px"></iframe><pre id="result"></pre>
<script>
(async () => {
  const frame = document.querySelector('iframe'), result = document.querySelector('#result');
  const assert = (ok, reason) => { if (!ok) throw Error(reason); };
  const read = (index, width) => new Promise(resolve => {
    frame.width = width;
    frame.onload = () => resolve(frame.contentDocument);
    frame.src = `${index}.html`;
  });
  const ids = (doc, attr) => [...doc.querySelectorAll(`[${attr}]`)].map(el => Number(el.getAttribute(attr))).join(',');
  const change = (doc, control, value) => {
    control.value = value;
    control.dispatchEvent(new doc.defaultView.Event('input', {bubbles:true}));
    control.dispatchEvent(new doc.defaultView.Event('change', {bubbles:true}));
  };
  const cases = __EXPECTED__;
  try {
    for (const width of [1440, 768, 500, 390]) {
      for (const [index, expected] of cases.entries()) {
        const doc = await read(index, width), form = doc.querySelector('[data-recommendation-form]');
        assert(doc.defaultView.innerWidth === width, `viewport ${width}`);
        assert(!doc.documentElement.dataset.scriptError, doc.documentElement.dataset.scriptError);
        assert(!form.closest('[data-recommendation]').hidden, 'recommendation visible');
        assert(form.elements.needs.value === expected, `case ${index + 1} at ${width}: expected ${expected}, got ${form.elements.needs.value}`);
        if (index !== 0) continue;
        form.requestSubmit();
        assert(ids(doc, 'data-recommended-service') === '3,4,5', 'top three in face group, excluding inactive service');
        change(doc, form.elements.needs, 'hair');
        form.requestSubmit();
        assert(ids(doc, 'data-recommended-service') === '1', 'manual selection overrides Profile');
        assert(doc.defaultView.spaAuth.getProfile().needs[0] === 'Dưỡng ẩm, cải thiện da khô', 'Profile remains unchanged');
        const filters = doc.querySelector('.catalog-toolbar').elements;
        change(doc, filters.category, 'Danh mục A');
        assert(ids(doc, 'data-card-id') === '1,2', 'catalog filters by category, independent of recommendation group');
        change(doc, filters.search, 'Thử 2');
        assert(ids(doc, 'data-card-id') === '2', 'category and search work together');
        assert(ids(doc, 'data-recommended-service') === '1', 'catalog filters do not change the recommendation');
        const rect = form.elements.needs.getBoundingClientRect();
        assert(rect.width > 0 && rect.left >= 0 && rect.right <= width, 'dropdown fits viewport');
      }
    }
    result.textContent = 'PASS ' + (cases.length * 4) + ' mapping cases; recommendation, manual selection and category filters at all four widths';
  } catch (error) { result.textContent = `FAIL ${error.message}`; }
})();
</script>
"""


def main():
    chrome = shutil.which("chrome") or Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    sys.path.insert(0, str(ROOT))
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
    import django
    from django.db.backends.base.base import BaseDatabaseWrapper
    from django.template.loader import render_to_string

    services = [
        dict(id=i, name=f"Liệu trình Thử {i}", careGroup=group, active=i != 7,
             category="Danh mục A" if i < 3 else "Danh mục B", priceValue=i * 100_000,
             price=f"{i}00.000 VND", minutes=60, duration="60 phút", description="Dữ liệu cô lập",
             image=(ROOT / "static/images/facial.jpg").as_uri())
        for i, group in enumerate(("hair", "relax", "face", "face", "face", "face", "face", "body"), 1)
    ]
    csp = ('<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
           "script-src 'unsafe-inline' file:; style-src 'unsafe-inline' file:; "
           "img-src file: data:; font-src file:; form-action 'none'\">")
    with tempfile.TemporaryDirectory(prefix="annhien-recommendation-") as tmp:
        temp = Path(tmp)
        with patch.object(BaseDatabaseWrapper, "ensure_connection", side_effect=AssertionError("Database forbidden")):
            django.setup()
            for index, (needs, _) in enumerate(CASES):
                html = render_to_string("pages/services.html", {
                    "auth_ui": {"id": 1, "role": "User", "profile": {"name": "Kiểm thử", "needs": needs}},
                    "live_catalog": {"services": services, "products": [], "staff": [], "relations": []},
                    "live_promotions": [],
                })
                html = html.replace("<head>", "<head>" + csp + CHECK, 1)
                html = html.replace('"/static/', '"' + (ROOT / "static").as_uri() + "/")
                (temp / f"{index}.html").write_text(html, encoding="utf-8")
        driver = temp / "verify.html"
        driver.write_text('<!doctype html><meta charset="utf-8">' + DRIVER.replace(
            "__EXPECTED__", json.dumps([expected for _, expected in CASES])), encoding="utf-8")
        run = subprocess.run([str(chrome), "--headless", "--disable-gpu", "--disable-background-networking",
                              "--no-first-run", "--allow-file-access-from-files", "--no-proxy-server",
                              f"--user-data-dir={temp / 'chrome'}", "--window-size=1500,900",
                              "--virtual-time-budget=15000", "--dump-dom", driver.as_uri()],
                             capture_output=True, encoding="utf-8", errors="replace", timeout=60)
        match = re.search(r'<pre id="result">([^<]*)</pre>', run.stdout)
        if not match or not match[1]:
            print(f"FAIL Chrome did not finish the isolated checks (exit {run.returncode})", file=sys.stderr)
            print(run.stderr[-1500:], file=sys.stderr)
            return 1
        message = match[1]
        print(message)
        return 0 if run.returncode == 0 and message.startswith("PASS ") else 1


if __name__ == "__main__":
    raise SystemExit(main())
