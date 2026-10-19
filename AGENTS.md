# An Nhiên Spa — hướng dẫn làm việc

## Kiến trúc

Project sử dụng HTML + CSS + JavaScript thuần. Không dùng React, TypeScript,
Vite, Tailwind hoặc framework frontend khác. Không cần Node.js, npm, pnpm,
package manifest hay bước biên dịch để hiển thị giao diện.

## Cấu trúc chuẩn

- `index.html`: Home công khai cho khách chưa đăng nhập.
- `home.html`: Home User đã đăng nhập, giữ nguyên thiết kế đã chốt.
- `login.html`, `register.html`: đăng nhập và đăng ký giao diện mẫu.
- `services.html`, `service-detail.html`: danh sách và chi tiết dịch vụ.
- `products.html`, `product-detail.html`: sản phẩm giới thiệu, không mua hàng.
- `booking.html`, `appointments.html`, `invoice.html`, `profile.html`: các trang khách hàng.
- `promotions.html`, `reviews.html`, `admin-dashboard.html`: ưu đãi, đánh giá và quản trị mẫu.
- `promotion-detail.html`: chi tiết ưu đãi và dịch vụ áp dụng, công khai cho khách.
- `js/promotions-data.js`, `js/promotions.js`, `css/promotions.css`: dữ liệu,
  trạng thái hiệu lực và giao diện khuyến mãi, không tính giá dịch vụ sau giảm.
- `css/style.css`: toàn bộ styling, font, palette, responsive và hiệu ứng.
- `css/fonts.css`, `css/fonts/`: hai font công khai hiện có, phục vụ cục bộ
  kèm giấy phép OFL để bảo đảm chữ tiếng Việt và italic tải ổn định.
- `js/app.js`: các tương tác JavaScript thuần.
- `js/ui.js`: icon line-art dùng chung, hiện/ẩn mật khẩu và modal xác nhận đăng xuất.
- `js/auth.js`, `css/auth.css`: trạng thái phiên mẫu, điều hướng theo quyền
  và styling riêng cho trang đăng nhập/đăng ký.
- `js/catalog.js`: dữ liệu giới thiệu tĩnh cho chi tiết và đặt lịch.
- `images/`: hình ảnh và logo.
- `.figma/make/`: công cụ phục vụ preview và đóng gói trong Figma Make,
  không phải dependency của giao diện.

Đọc file liên quan trước; chỉ theo liên kết hoặc đọc thêm khi cần.
Không tạo lại `src/`, JSX/TSX, cấu hình framework hoặc package manager.

## Bảo toàn thiết kế

- Giữ phong cách luxury spa tối, ấm, editorial, ảnh lớn, tiêu đề serif và italic.
- Palette: chocolate `#3A2419`, gần đen `#17110E`, ivory `#FFF8F1`,
  champagne `#C6A07E`.
- Không đổi thiết kế, nội dung tiếng Việt, ảnh hoặc tương tác khi chỉ dọn cấu hình.
- Giữ header, footer và navigation nhất quán giữa các trang.
- CSS và JavaScript tách riêng; HTML semantic, tag đóng đầy đủ và code rõ ràng.
- Giữ responsive desktop, tablet, mobile, hover và hỗ trợ reduced motion.

## Preview và kiểm tra

- Mỗi trang có thể mở trực tiếp bằng trình duyệt với các đường dẫn tương đối.
- Trong Figma Make, máy chủ tĩnh Python được môi trường quản lý trên `$PORT`
  (mặc định 8443); không tự khởi chạy thêm máy chủ.
- Máy chủ tĩnh không có HMR; tải lại preview khi cần xem thay đổi.
- Không chạy npm/pnpm, Vite, typecheck hoặc build framework.
- Kiểm tra các trang, liên kết, fragment, tài nguyên và JavaScript liên quan.
- Khi sửa công cụ môi trường, dùng verifier của Figma Make.
- `.figma/make/build` chỉ sao chép các trang và `css/`, `js/`, `images/` vào
  `dist/` để đóng gói, không biên dịch và không cần thiết để xem giao diện.

## Giới hạn và Django

Không triển khai backend, database, API, thanh toán hoặc xác thực thật.
Tương tác mẫu chỉ dùng `sessionStorage`; không coi trang quản trị là cơ chế bảo mật.
Không lưu tên hoặc số điện thoại từ form đặt lịch.
`spa-auth` lưu trạng thái đăng nhập mẫu và định danh minh họa, không lưu mật khẩu.
Khách được xem Home, dịch vụ/chi tiết dịch vụ và khuyến mãi. Trang User và các
chức năng yêu cầu tài khoản chuyển đến đăng nhập nếu chưa có phiên.
Chỉ hai tài khoản cố định trong `js/auth.js` được đăng nhập mẫu: User chuyển
đến `home.html`, Admin chuyển đến `admin-dashboard.html`. User không được vào
dashboard Admin; phiên mẫu cũ không có vai trò hợp lệ phải đăng nhập lại.
Đăng xuất phải mở modal xác nhận; “Không” giữ nguyên phiên, “Có, đăng xuất”
xóa dữ liệu phiên của spa và trở về `index.html`.
Guard JavaScript không ngăn truy cập source HTML và không
thay thế Django Authentication, session hay phân quyền backend.

Sau này tách header/footer thành `base.html` và include; đưa trang vào templates,
đưa `css/`, `js/`, `images/` vào static, thay đường dẫn bằng `{% url %}` và
`{% static %}`. Chỉ thay dữ liệu và form mẫu bằng Django khi được yêu cầu.
