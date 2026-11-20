# FR-23 responsive — 17/11/2026

## File source thay đổi trong lượt này

- `static/css/admin-reviews-luxury.css`: thêm quy tắc chỉ tại max-width 768px/600px, giới hạn trong Admin Reviews.
- `templates/pages/admin-reviews.html`: chỉ tăng phiên bản URL CSS để trình duyệt nhận bản mới. Không đổi cấu trúc hoặc thứ tự nội dung.

Không sửa JS, backend, API, model, migration hoặc cấu hình. Các thay đổi chưa commit từ trước được giữ nguyên.

## Nguyên nhân và cách xử lý

1. Bảng đã có min-width 1000px và overflow-x:auto từ CSS chung; không phải thiếu hoàn toàn cơ chế cuộn. Tuy nhiên vùng chứa chưa có ràng buộc co chiều rộng minh bạch trong CSS riêng, và nhận xét bị giới hạn hai dòng/max-height/overflow:hidden. Bổ sung min-width:0/max-width:100% cho vùng chứa và viewport bảng, width:100%/overflow-x:auto/overscroll-behavior-x:contain; giữ bảng tối thiểu 1000px. Bỏ clamp nhận xét ở tablet/mobile để toàn bộ nội dung có thể đọc trong bảng cuộn riêng. Tương tác layout thực tế sau sửa cần Chrome xác nhận.
2. Summary từng review dùng flex, tên flex:1, nhãn dài có thể chiếm gần hết chiều rộng; overflow-wrap:anywhere khiến tên xuống dòng quá hẹp. Trên <=600px chuyển summary sang grid: dấu mở/đóng và tên ở hàng một, trạng thái ở hàng hai, nhãn được wrap trong toàn bộ chiều rộng khả dụng. Đặc biệt phù hợp các nhãn dài của stale/insufficient_text.
3. Bổ sung một cột cho card/lộ trình trên điện thoại; select/button giới hạn 100% chiều rộng, nút được xuống dòng và giữ chiều cao tối thiểu 44px. Không đặt overflow-x:hidden cho cả trang để che lỗi.

Mọi quy tắc layout mới đều nằm trong breakpoint <=768px hoặc <=600px; không thay CSS Desktop 1440px. Việc giữ nguyên hiển thị Desktop vẫn cần xác nhận trực quan, không coi đọc source là PASS trình duyệt.

## Kiểm thử thực tế

- `node tools/test_admin_review_analysis.cjs`: 20 PASS, 0 FAIL (frontend DOM/mock). Kiểm tra tổng hợp, stale/thiếu nội dung, GET/F5, giới hạn, race và escaping. Không phải kiểm thử layout browser.
- `git diff --check`: PASS.
- Không chạy lại 47 test backend vì không sửa backend.
- Chrome sau sửa tại 1440/768/500/390px: BLOCKED cả bốn. Computer Use dừng do không xác định được URL Chrome đủ chắc chắn. Không dùng phương thức khác vượt chốt. Việc đọc loopback fixture cũng bị giới hạn socket WinError 10013; đã dừng máy chủ fixture.
- Không có ảnh trước/sau sau sửa; không tuyên bố responsive PASS.

## Preview trước/sau để người dùng nghiệm thu

Đã tạo artifact HTML offline từ template thật và fixture giả sẵn có, không render bằng database:

- `docs/fr23-ui-20261117-140628/before.html`
- `docs/fr23-ui-20261117-140628/after.html`
- CSS trước/sau, log 20 test và `responsive.patch` cùng thư mục.

Mở từng HTML bằng Google Chrome, dùng Device Toolbar chọn Responsive rồi nhập lần lượt chiều rộng 1440, 768, 500, 390, zoom 100%. Ở bảng, vuốt/cuộn ngang bên trong bảng để xem các cột. Mở DG-4/DG-5 để xem nhãn và nội dung. So sánh Desktop trước/sau và kiểm tra thanh cuộn toàn trang không bị tràn ngang.

HTML dùng dữ liệu giả trong bộ nhớ và đường dẫn file cục bộ; CSP chặn connect/form submission. Không cần Django/MySQL hoặc key. Các artifact chưa được xác nhận hiển thị trên Chrome trong lượt này; nếu trình duyệt áp dụng hạn chế file cục bộ, có thể chạy Preview bằng `python -B tools/review_ui_fixture.py` và mở URL loopback được in ra. Lưu ý chạy mới runner sẽ lấy source hiện tại làm mốc before; dùng hai artifact HTML đã lưu để so sánh chính xác bản trước/sau của lượt sửa này.

Không đọc key, sửa .env, bật quyền xuất dữ liệu, gọi Gemini/PayOS, kết nối MySQL, migration hoặc commit/push. Dừng chờ nghiệm thu trực quan.
