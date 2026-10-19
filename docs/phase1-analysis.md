# Phân tích và bàn giao giai đoạn 1 — Python/Django

Ngày kiểm tra: 18/10/2026.

## Nguồn đã đọc

Đã đọc toàn bộ nội dung văn bản và bảng của `D:\SRS_HLD_Nguyễn_Thị_Lan_Anh (1).docx` bằng OOXML; đã xem trực tiếp 4 ảnh nhúng, gồm logo trường, ERD, kiến trúc tổng thể và luồng RAG. Bản trích xuất ở `srs-extracted.txt`, hình ở `srs-media/`. Đã đọc AGENTS.md, kiểm kê HTML/CSS/JS/ảnh và kiểm tra các tham chiếu trong source. Yêu cầu hiện tại cho phép khởi tạo Django, thay thế giới hạn “chưa backend” của giai đoạn frontend; không mở rộng sang nghiệp vụ thật.

## Đối chiếu HLD

| App đã tạo | Bảng dự kiến theo SRS (chưa tạo) | Trang liên quan (.html) | Yêu cầu |
|---|---|---|---|
| accounts | users, customers | login, register, profile, admin-accounts, admin-customers | FR-01–05 |
| services | service_categories, services | services, service-detail, admin-services | FR-06–07 |
| products | care_products, service_products | products, product-detail, admin-products | FR-08–09 |
| employees | employees, employee_services, employee_schedules | admin-employees | FR-10–11 |
| appointments | appointments | booking, appointments, admin-appointments | FR-12–14 |
| promotions | promotions, promotion_services | promotions, promotion-detail, admin-promotions | FR-15 |
| billing | invoices, invoice_details, payments | invoice, admin-invoices, admin-payments | FR-16–17 |
| reviews | reviews, review_replies | reviews, admin-reviews | FR-18–19 |
| dashboard | Không thêm bảng | admin-dashboard, admin-reports | FR-20 |
| ai_features | ai_recommendations, ai_review_analysis | Widget trong các trang User; phân tích trong Admin | FR-21–23 |
| core | Không thêm bảng | index, home; routing preview chung | Thành phần dùng chung |

Tổng cộng 11 app, 19 bảng nghiệp vụ dự kiến. Mỗi app có AppConfig, models.py chưa khai báo model, migrations/__init__.py và urls.py. Chỉ core.urls đang hoạt động, phục vụ toàn bộ trang preview. Các app nghiệp vụ chưa có view/form/service/API thật.

ERD quy định User–Customer một-một, email và username unique; Employee–Service, Promotion–Service, Service–CareProduct có bảng liên kết unique theo cặp. Appointment có một Service, Customer, Employee; Invoice và Review có appointment_id unique; AIReviewAnalysis có review_id unique. InvoiceDetails chứa snapshot dịch vụ và giá, không chứa sản phẩm. Chưa chạy makemigrations, migrate, tạo database hay seed.

Trước migration đầu tiên cần định nghĩa custom User tương thích Django Authentication, db_table users, email unique và role theo ERD; sau đó đặt AUTH_USER_MODEL. Hiện contrib.auth và session/middleware đã cấu hình, nhưng chưa có AUTH_USER_MODEL tùy chỉnh hay endpoint đăng nhập thật. Không chạy migrate ở trạng thái hiện tại để tránh tạo auth_user rồi phải đổi user model. Các bảng hệ thống Django về auth/session/contenttypes cần được phân biệt với 19 bảng nghiệp vụ.

## Quy tắc phải giữ khi triển khai tiếp

- FR-12–14: kiểm tra ca làm/ca nghỉ, dịch vụ được phân công, trùng thời gian của cả nhân viên và khách. Kiểm tra lại trong transaction khi ghi. SRS không quy định chi tiết bước chia slot nên chưa tự đặt số phút/giới hạn.
- Hủy chỉ khi pending/confirmed, trước giờ bắt đầu và chưa thanh toán. Hủy hợp lệ kéo theo hủy hóa đơn chưa thanh toán. completed chỉ do Admin xác nhận, không dựa riêng vào thời gian.
- Hóa đơn tối đa một/lịch đã xác nhận, lưu snapshot. Online chỉ trước giờ bắt đầu; sau đó thanh toán tại Spa. Webhook phải xác minh và idempotent. Chưa gọi payOS.
- Review tối đa một/lịch của chính khách đã completed; 1–5 sao, nội dung tùy chọn tối đa 2.000 ký tự, được sửa không xóa; phản hồi phẳng, không sửa/xóa.
- Sản phẩm chỉ giới thiệu, không giỏ hàng/tồn kho/thanh toán. AI chỉ tư vấn, 1–3 đề xuất, phân tích review; không tự thay đổi nghiệp vụ. RAG không chứa dữ liệu cá nhân/lịch/hóa đơn; vector store không phải một bảng nghiệp vụ mới.

## Kiểm kê và rủi ro chuyển đổi

Có 15 trang phía khách (bao gồm Guest/auth) và 12 trang Admin. Danh sách đầy đủ ở core/pages.py và templates/pages/. Có 6 CSS, 13 JS; font và giấy phép nằm trong css/fonts/. Ảnh nằm trong images/. node_modules và .figma/.figaro có sẵn là phần môi trường thiết kế, không được Django sử dụng; không chạy npm hay build frontend. public/favicon.svg không được các trang gốc tham chiếu và được giữ nguyên.

Giữ nguyên byte của toàn bộ HTML/CSS/JS/font/ảnh nguồn, kiểm chứng bằng docs/frontend-manifest.json. Các file trong static/css, static/js, static/images là bản sao byte-identical. Không chỉnh layout, tiếng Việt, màu sắc, ảnh, dữ liệu hoặc logic demo. HTML gốc có các thẻ đóng img dư; giữ nguyên trong lượt này để không trộn sửa markup với chuyển backend.

Template dùng `{% load static %}`, `{% static %}` và `{% url %}`. URL .html giữ ở root để location.pathname, liên kết động, query id/service/code/appointment và fragment hoạt động như cũ. Kết quả reverse URL được bỏ dấu / đầu bằng slice trong thuộc tính href, vì auth.js có selector so khớp nguyên chuỗi href tương đối. Cách này chỉ dành cho cấu hình triển khai ở root hiện tại; khi đổi sang URL nghiệp vụ /accounts/... phải chuyển đồng bộ JS. Route /images/... chuyển hướng đến /static/images/... cho đường dẫn ảnh được JS tạo động; không sửa catalog hay cấu trúc dữ liệu demo. CSS @import/url tương đối tiếp tục hoạt động dưới /static/css/.

Chưa tách header/footer thành include: các biến thể Guest/User/Admin chưa hoàn toàn giống nhau và JS thay đổi DOM; giữ từng template là bước ít rủi ro. Việc tái sử dụng layout sẽ làm sau với kiểm thử hồi quy.

Demo cần giữ tạm: auth.js dùng hai tài khoản cố định và spa-auth; app.js dùng spa-profile/spa-appointments/spa-reviews cùng chatbot/đề xuất mẫu; catalog.js và promotions-data.js giữ dữ liệu tĩnh; admin*.js dùng dữ liệu minh họa và sessionStorage như spa-admin-services, spa-admin-operations, spa-admin-account-status. Đây không phải dữ liệu MySQL, không dùng để seed ngầm và không coi guard JS là phân quyền backend. Toàn bộ route preview chỉ GET/HEAD/OPTIONS, tắt khi DEBUG=False; chưa có route quản trị Django mặc định.

## Kiểm tra thực tế

- Python 3.12.6, venv riêng .venv; Django 5.2.18, mysqlclient, python-dotenv, Pillow đã cài. Phiên bản tái lập nằm ở requirements-lock.txt. Django 5.2 là LTS: https://www.djangoproject.com/download/ .
- manage.py check: không lỗi.
- 5 SimpleTestCase: đạt; không tạo test database. Render index/home/admin-dashboard trước, sau đó toàn bộ 27 trang. So sánh HTML render với gốc sau khi loại đúng tiền tố static; kiểm tra liên kết, fragment, tài nguyên JS/CSS, checksum nguồn và static copy, từ chối POST/URL lạ và tắt preview ngoài DEBUG.
- Server local chạy tại 127.0.0.1:8000 với config.settings_preview. 75/75 HTTP request đạt 200, gồm /, 27 trang, 46 static files và alias ảnh. Chi tiết docs/http-smoke.json.
- Trình duyệt thực đã mở index, đăng nhập demo User tới home, mở modal và xác nhận đăng xuất, đăng nhập demo Admin tới dashboard. Đã xem ảnh màn hình ở chiều rộng mobile; console không ghi error. Chưa kiểm thử tương tác chi tiết của cả 27 trang hay toàn bộ breakpoint desktop/tablet.
- MySQL mới cấu hình. Thử kết nối 127.0.0.1:3306 trả lỗi 2002/10061 (connection refused). Chưa xác minh server cài sẵn hay không, chưa có user/password .env. Không tạo database hoặc dùng SQLite thay thế.
- Lỗi quyền thư mục TEMP khi ensurepip đã xử lý bằng thư mục tạm workspace. PyPI và socket local bị sandbox chặn ban đầu; cài dependency và HTTP kiểm tra được sau khi chạy với quyền ngoài sandbox. Đây không phải lỗi ứng dụng còn tồn tại.

## Việc tiếp theo

Triển khai Models/MySQL theo ERD, bắt đầu accounts.User/Customer trước migration đầu tiên; bổ sung constraints và kiểm thử, rồi Authentication + Session và phân quyền server. Tiếp theo catalog/employees/promotions, đặt lịch chống trùng, billing/reviews, cuối cùng payOS và AI/RAG. Chưa cần API key ở giai đoạn này.
