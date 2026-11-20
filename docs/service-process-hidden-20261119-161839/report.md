# Hiện quy trình sau render — 19/11/2026

## Nguyên nhân thực tế
Template service-detail.html đã ẩn ritual-process mặc định; file static/js/catalog-pages.js nguồn có logic hiện/ẩn. Tuy nhiên cổng 8000 phục vụ staticfiles/js/catalog-pages.js bản cũ: SHA256 HTTP khớp bản collected, không khớp source. Bản cũ render li nhưng không gỡ hidden, đồng thời vẫn dùng stepTitles cố định.

## Sửa trong đúng phạm vi
- static/js/catalog-pages.js: sau node.replaceChildren của data-list=steps, gọi node.closest('.ritual-process').toggleAttribute('hidden', node.childElementCount === 0). Có li hợp lệ thì bỏ hẳn thuộc tính, rỗng thì giữ ẩn. Không thay các nhánh benefits/product/booking/reviews hay logic dữ liệu.
- staticfiles/js/catalog-pages.js: đồng bộ riêng asset này theo source; không collectstatic toàn bộ.
- templates/pages/service-detail.html: version JS service-process-visible-20261119.
- tools/check_service_steps_ui.py: thêm 10 bước và tùy chọn output riêng; dùng bản đọc DV-002 hiện hành để không ghi đè bằng chứng cũ.

Sau đồng bộ, server giữ metadata cũ 11511 byte trong khi file mới 11724 byte. Người dùng đã tự restart 8000 bằng môi trường cũ. Sau restart JS HTTP 200, đủ 11724 byte, khớp source và staticfiles (confirmed-response.json). Không thay backend hoặc môi trường kết nối.

## Kết quả
- 48/48 ca Chrome cô lập PASS, 0 FAIL: 12 ca x viewport 1440/768/500/390. Các số bước 4/5/6/8/10/21 đều giữ nguyên nội dung và đánh số đúng; không hard limit. Rỗng, thiếu steps, chỉ dòng trống/prefix đều ẩn section và không có khung trống. Kiểm tra thêm CRLF, HTML escape và dữ liệu thập phân.
- DV-002 thực trên http://127.0.0.1:8000/service-detail.html?id=2: đã mở bằng browser Chromium tích hợp, không đăng nhập hoặc sửa dữ liệu; kiểm tra DOM read-only và ảnh trực tiếp. hidden_attribute=null, visible=true, step_count=8; số thứ tự 01–08 và nội dung đầy đủ như bản công khai.
- Các bước: Kiểm tra tình trạng da và tư vấn liệu trình; Tẩy trang và làm sạch da mặt; Tẩy tế bào chết nhẹ nhàng phù hợp với da; Cân bằng da bằng toner; Massage mặt thư giãn; Đắp mặt nạ dưỡng da; Thoa serum và kem dưỡng ẩm; Tư vấn chăm sóc da tại nhà. Nội dung từ database giữ nguyên, frontend chỉ bỏ prefix khi trình bày.
- GET công khai sau sửa xác nhận steps của DV-002 không đổi và HTML tải version JS mới. Không dùng DOM manipulation để ép hiện section khi nghiệm thu live.
- Ca không có quy trình kiểm tra bằng fixture, không xóa steps của dịch vụ thật để thử.
- node --check, compile Python tool và git diff --check đạt.

## An toàn
Không sửa database/model/migration/nội dung dịch vụ/.env/backend/CSS hoặc các chức năng khác. Không gọi Gemini/OpenAI/PayOS. Không chạy migrate. Kiểm thử fixture chặn mọi database/network thật và dùng Chrome profile tạm; truy cập website 8000 chỉ GET công khai. Không tự khởi động lại website hoặc thay credentials; restart do người dùng thực hiện. Không commit/push. Các thay đổi đang có của các lượt khác được giữ nguyên.

## Bằng chứng và kiểm tra lại
chrome-tests.txt; live-browser-verification.json; confirmed-response.json; served-confirmed.js; changes.patch. Ảnh kiểm thử fixture service-steps-WIDTH.png trong cùng thư mục. Quan sát live nằm trong kết quả browser của lượt này, không đánh đồng ảnh fixture với ảnh website thật.
Lệnh: .venv/Scripts/python.exe -B tools/check_service_steps_ui.py --output <thư mục báo cáo này>.
Mở lại service-detail.html?id=2 và Ctrl+F5 nếu tab cũ còn cache. Không cần restart thêm sau lần vừa thực hiện.
