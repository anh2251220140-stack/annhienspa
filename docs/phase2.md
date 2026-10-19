# Giai đoạn 2 — Models và xác thực thật

## Thiết lập MySQL tại máy

Chạy trong PowerShell tại project:

```powershell
.\.venv\Scripts\python.exe tools\setup_mysql.py
```

Script yêu cầu mật khẩu quản trị bằng getpass (không hiện ký tự, không ghi command line), tạo database annhien_spa và tài khoản annhien_django@127.0.0.1. Mật khẩu ứng dụng được sinh ngẫu nhiên và lưu vào .env đang được gitignore. Không đưa mật khẩu vào chat. Script dừng nếu .env, database hoặc tài khoản đã tồn tại; không xóa, không đổi mật khẩu tài khoản có sẵn. Nếu một bước DDL lỗi, các bước trước có thể đã commit: không xóa database để thử lại; kiểm tra trạng thái bằng MySQL Workbench. Dùng tài khoản quản trị có quyền CREATE DATABASE, CREATE USER và GRANT trên hai schema.

Tài khoản phát triển được cấp SELECT/INSERT/UPDATE/DELETE/CREATE/ALTER/INDEX/REFERENCES/DROP trong schema ứng dụng và test_annhien_spa riêng cho test runner. Không có quyền toàn server hoặc GRANT OPTION. DROP cần cho migration/test, không được dùng để xóa dữ liệu ứng dụng ở lượt triển khai này. Khi deploy nên tách tài khoản migration khỏi tài khoản runtime (runtime chỉ CRUD).

Nếu đã có database hoặc tài khoản, tự điền MYSQL_DATABASE, MYSQL_USER, MYSQL_PASSWORD, MYSQL_HOST, MYSQL_PORT và DJANGO_SECRET_KEY trong .env tại máy; không ghi đè dữ liệu. Trước migrate phải kiểm tra không có auth_user hoặc schema cũ trái SRS.

```powershell
.\.venv\Scripts\python.exe tools\check_mysql.py
.\.venv\Scripts\python.exe manage.py check --database default
.\.venv\Scripts\python.exe manage.py migrate --plan
.\.venv\Scripts\python.exe manage.py migrate --noinput
.\.venv\Scripts\python.exe manage.py test accounts core --keepdb --verbosity 2
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

createsuperuser hỏi mật khẩu tại máy và tạo role Admin; không có Admin mặc định hay mật khẩu cố định. Form đăng ký công khai luôn tạo User + Customer trong một transaction, bỏ qua mọi role/is_staff/is_superuser gửi từ client. Test runner chỉ dùng schema test_annhien_spa, không seed database nghiệp vụ. --keepdb giữ schema test để tránh tự xóa; không dùng lại schema test nếu đang chứa dữ liệu quan trọng.

## Mô hình dữ liệu

Giữ 19 db_table và field/quan hệ trong ERD của DOCX:

| App | Bảng |
|---|---|
| accounts | users, customers |
| services | service_categories, services |
| products | care_products, service_products |
| employees | employees, employee_services, employee_schedules |
| appointments | appointments |
| promotions | promotions, promotion_services |
| billing | invoices, invoice_details, payments |
| reviews | reviews, review_replies |
| ai_features | ai_recommendations, ai_review_analysis |

AUTH_USER_MODEL=accounts.User được đặt trước 0001_initial. User kế thừa AbstractUser để dùng password hashing, last_login, is_staff/is_superuser và group/permission của Django. Các field/bảng hệ thống auth_permission/auth_group/contenttypes/session/migrations và hai bảng nối users_groups/users_user_permissions là hạ tầng Django, không phải thêm bảng nghiệp vụ. Không có auth_user.

Invoice.appointment, Review.appointment, Customer.user và AIReviewAnalysis.review là OneToOne. Ba bảng nối có unique theo cặp. FK dùng PROTECT để không vô tình cascade xóa lịch sử. Field tiền DECIMAL(12,2), thời gian theo Asia/Ho_Chi_Minh với USE_TZ=True. ImageField giữ đường dẫn file, không lưu blob vào MySQL.

CHECK ở DB: role/status hợp lệ, tiền không âm, duration/quantity dương, end > start (ca/lịch), ngày kết thúc khuyến mãi >= ngày bắt đầu, phần trăm không vượt 100, tổng hóa đơn/chi tiết đúng phép tính, rating 1–5. Field độ dài như review.comment 2000 được kiểm tra bởi model và MySQL strict mode. transaction_code unique nullable cho phép nhiều giao dịch chưa có mã.

Model clean kiểm tra thêm phân công/ca làm/trùng lịch, ca chồng lấn, hóa đơn sau xác nhận và bảo toàn hóa đơn đã thanh toán, review thuộc đúng khách/dịch vụ đã completed; AI trả 1–3 đề xuất. Save thông thường gọi full_clean. Save lịch/ca dùng transaction và khóa Employee (rồi Customer đối với Appointment) trước kiểm tra, tránh hai writer cùng vượt qua kiểm tra trùng. QuerySet.update/bulk/raw SQL bỏ qua model clean/locking; các service nghiệp vụ sau này không được dùng chúng để lách kiểm tra. Chưa có endpoint đặt/hủy lịch, duyệt completed, thanh toán hay review thật; ràng buộc chuyển trạng thái, quyền actor và webhook sẽ nằm trong service/API tương ứng.

SRS để status dạng VARCHAR: mã triển khai giữ các mã frontend như pending/confirmed/completed/cancelled, unpaid/paid/cancelled, online/spa và positive/neutral/negative; lịch nhân viên dùng working/off để thể hiện làm/nghỉ. Đây là cách mã hóa trạng thái, không thêm nghiệp vụ. Không tạo bảng vector store/chat/message.

## Xác thực và giao diện

/login.html, /register.html và alias /accounts/login/, /accounts/register/ hỗ trợ GET/POST thật. POST /accounts/logout/ có CSRF; GET không đăng xuất. Modal cũ “Không” chỉ đóng, “Có, đăng xuất” gửi form POST, session được flush và trở lại index.html. Mật khẩu không được đưa vào HTML trả về, sessionStorage hoặc URL.

Đăng nhập chấp nhận username hoặc email không phân biệt hoa thường, từ chối tài khoản inactive, sai mật khẩu hoặc định danh mơ hồ. Role Admin đi dashboard; User đi home. Server chặn Guest ở trang riêng, chặn User ở toàn bộ 12 trang Admin và chặn Admin ở trang riêng User. Dữ liệu spa-auth hoặc cookie giả không cấp quyền. Các trang chứa session gửi Cache-Control no-store/private để hạn chế cache sau logout.

static/js/auth.js chỉ đọc dữ liệu trình bày do Django xuất bằng json_script. Không ghi authentication vào sessionStorage; các JS demo còn lại đọc spaAuth.getSession() để biết danh tính trên màn hình. Dữ liệu demo spa-* được xóa khi đổi tài khoản/đăng xuất để không lẫn giữa các người dùng. Backend không nhận dữ liệu demo này.

HTML/CSS/JS gốc ở root, css/, js/, images/ không sửa; static CSS/font/ảnh giữ nguyên checksum. 27 template chỉ đổi các phần kỹ thuật: session context, form POST/CSRF/errors, base URL chính xác từng trang để alias không phá liên kết tương đối. Password tối thiểu 8 ký tự theo validator Django; không đổi layout. Chưa nối profile/update password, catalog CRUD, booking, invoice, payment, review và AI vào dữ liệu thật.

## Kiểm thử

accounts/tests.py kiểm tra registration transaction/role/hash, duplicate, password, login email/username, inactive/demo rejection, CSRF, logout xóa session, redirect an toàn. core/tests.py kiểm tra nguồn gốc/visual assets, 27 trang và phân quyền Guest/User/Admin; core/test_models.py kiểm tra 19 bảng thật, unique/CHECK/FK, overlap, invoice snapshot, review, product/promotion links và AI.

Kết quả chạy cụ thể sẽ được ghi ở docs/phase2-results.txt sau kiểm thử MySQL. Không coi manage.py check hoặc tạo file migration là đã migrate database.
