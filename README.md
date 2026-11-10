# An Nhiên Spa — Website quản lý và đặt lịch Spa

Đồ án tốt nghiệp xây dựng hệ thống giới thiệu dịch vụ, đặt lịch và quản lý hoạt động Spa. Phiên bản **Bước 3** sử dụng **Django + MySQL**, kế thừa giao diện HTML/CSS/JavaScript của **Bước 2** và phong cách Luxury A với tông kem, nâu và champagne.

Hệ thống hiện có xác thực, phân quyền, quản lý danh mục, lịch làm việc, đặt lịch, hóa đơn, thanh toán tại Spa/payOS, đánh giá, phản hồi và báo cáo.

## Công nghệ

| Thành phần | Công nghệ hiện tại |
| --- | --- |
| Giao diện | Django Templates, HTML, CSS, JavaScript thuần |
| Backend | Python, Django 5.2 |
| Cơ sở dữ liệu | MySQL, truy cập qua Django ORM và `mysqlclient` |
| Xác thực | Django Authentication + Session; custom User `accounts.User` |
| Thanh toán | SDK payOS, QR nhúng trên hóa đơn, ghi nhận thanh toán tại Spa |
| Tài nguyên | WhiteNoise cho static; ảnh upload lưu trong `media/` |
| Email | Django email backend, cấu hình SMTP qua biến môi trường |
| Kiểm thử | Django TestCase/TransactionTestCase, runner MySQL cô lập; một số công cụ kiểm tra SQLite/Chrome riêng |

Không sử dụng React, Vue, TypeScript hoặc bước biên dịch frontend. Các dependency Python được khai báo trong `requirements.txt`; không cần npm để chạy website Django.

## Bước 2 và Bước 3

- **Bước 2 — giao diện tham chiếu:** các file HTML tại thư mục gốc cùng `css/`, `js/`, `images/` được giữ lại để bảo toàn thiết kế ban đầu. Các tương tác mẫu và dữ liệu trình duyệt ở bản này phục vụ minh họa giao diện.
- **Bước 3 — hệ thống hoạt động:** Django render `templates/pages/`, phục vụ tài nguyên từ `static/`, sử dụng API và dữ liệu MySQL. Đăng nhập, phân quyền và dữ liệu nghiệp vụ được kiểm tra tại backend.
- Cả 27 trang vẫn có URL `.html`: 15 trang phía khách hàng và 12 trang Admin. Mở HTML gốc bằng máy chủ tĩnh không tương đương chạy hệ thống Django; tài khoản hoặc dữ liệu demo không thay thế tài khoản và dữ liệu trong MySQL.

Các ID hiển thị trên giao diện được định dạng từ ID thật. Không dùng chỉ số của danh sách demo làm khóa dữ liệu Django.

## Chức năng đã triển khai

### Khách hàng

- Xem danh mục, chi tiết dịch vụ, chuyên viên, sản phẩm giới thiệu và chương trình khuyến mãi từ dữ liệu hệ thống. Sản phẩm không có giỏ hàng, bán hàng hoặc quản lý tồn kho.
- Đăng ký, đăng nhập bằng tên đăng nhập/email, đăng xuất và quên mật khẩu bằng liên kết có thời hạn gửi qua email.
- Xem và cập nhật hồ sơ cá nhân.
- Chọn dịch vụ, chuyên viên, ngày và giờ trống để đặt lịch; backend xét chuyên môn, ca làm, khoảng nghỉ và xung đột lịch.
- Xem lịch hẹn của mình; xem danh sách, tìm/lọc và mở chi tiết hóa đơn thuộc tài khoản.
- Áp dụng hoặc bỏ khuyến mãi theo điều kiện backend, bao gồm giới hạn theo khách hàng và cơ chế giữ lượt trên hóa đơn chưa thanh toán.
- Chọn thanh toán tại Spa hoặc thanh toán online bằng payOS khi hóa đơn đủ điều kiện. QR có thời hạn, trạng thái phiên được duy trì khi tải lại trang.
- Đánh giá lịch hẹn đã hoàn thành: 1–5 sao, nhận xét tùy chọn; gửi phản hồi phẳng cùng Admin theo quyền hiện có.

### Quản trị

| Trang | Phạm vi đã kết nối Django/MySQL |
| --- | --- |
| Dashboard | KPI theo phạm vi thống kê, biểu đồ doanh thu, trạng thái lịch hẹn, dịch vụ được đặt nhiều và lịch hẹn gần đây |
| Tài khoản | Xem, tìm kiếm, lọc, phân trang, khóa/mở khóa; bảo vệ tài khoản quản trị và tài khoản đang đăng nhập |
| Khách hàng | Danh sách và hồ sơ chỉ đọc từ User Profile; loại trừ tài khoản quản trị khỏi danh sách khách hàng |
| Dịch vụ | Quản lý danh mục và dịch vụ, giá, thời lượng, ảnh và trạng thái hiển thị |
| Sản phẩm | Quản lý thông tin, ảnh, nhóm chăm sóc, trạng thái và liên kết nhiều dịch vụ |
| Nhân viên | Hồ sơ, ảnh, nhiều dịch vụ phụ trách, lịch tuần, đổi ca, khoảng nghỉ và nghỉ phép |
| Lịch hẹn | Xác nhận, hoàn thành, hủy có lý do, ghi nhận khách không đến đúng điều kiện; phân công lại ngoại lệ với sự đồng ý của khách và lịch sử truy vết FR-14 |
| Khuyến mãi | Quản lý chương trình, phạm vi nhiều dịch vụ, thời hạn, điều kiện và trạng thái |
| Hóa đơn | Chi tiết giá lịch sử, khuyến mãi, tổng tiền, giao dịch và ghi nhận tiền thực thu tại Spa |
| Thanh toán | Tra cứu giao dịch, lọc ngày tạo/ngày thanh toán, xem chi tiết và trạng thái cần đối soát |
| Đánh giá | Giao diện Luxury A, KPI từ số sao thật, tìm/lọc, chi tiết đánh giá và phản hồi User/Admin FR-18/FR-19 |
| Báo cáo | Giao diện Luxury A, lọc kỳ/trạng thái lịch, doanh thu theo ngày, cơ cấu lịch hẹn, dịch vụ, phân bố sao và bảng tổng hợp |

Các trang Admin được bảo vệ bằng xác thực và quyền phía Django; không dựa vào guard JavaScript.

### Hóa đơn, thanh toán và thống kê

- Xác nhận lịch hẹn tạo hóa đơn theo nghiệp vụ, chống tạo trùng. Giá và tên dịch vụ được lưu snapshot cho hóa đơn lịch sử.
- **Khách chọn thanh toán tại Spa không đồng nghĩa Admin đã nhận tiền.** Admin phải ghi nhận số tiền thực thu qua thao tác riêng và các kiểm tra backend.
- Tạo QR không đánh dấu hóa đơn đã thanh toán. Backend xử lý xác minh chữ ký webhook, số tiền, tham chiếu giao dịch, thông báo lặp/muộn và các trường hợp cần đối soát.
- Trạng thái lịch hẹn tách biệt trạng thái thanh toán; thanh toán thành công không tự hoàn thành lịch hẹn.
- Báo cáo cộng các khoản thanh toán thành công hợp lệ trên hóa đơn đã thanh toán, loại khoản cần đối soát; ngày thanh toán tính theo giờ Việt Nam. Lịch hẹn tính theo ngày hẹn; đánh giá tính theo ngày gửi. Bộ lọc trạng thái lịch không tự lọc lại doanh thu.

## Cấu trúc repository

```text
config/             Cấu hình Django, URL gốc, WSGI/ASGI và media local
accounts/           Custom User, hồ sơ, xác thực, quyền và đặt lại mật khẩu
services/           Danh mục và dịch vụ
products/           Sản phẩm giới thiệu và quan hệ sản phẩm–dịch vụ
employees/          Nhân viên, phân công dịch vụ và lịch làm việc
appointments/       Đặt lịch, chuyển trạng thái và lịch sử phân công lại
promotions/         Chương trình, điều kiện và giới hạn sử dụng
billing/            Hóa đơn, thanh toán, QR và adapter payOS
reviews/            Đánh giá và phản hồi
dashboard/          API tổng hợp Dashboard và Reports
ai_features/        Model chuẩn bị cho chức năng AI
core/               Routing trang, dữ liệu catalog, form và API quản trị dùng chung
templates/          Django Templates; 27 trang chính trong pages/
static/             CSS, JavaScript, font và ảnh dùng bởi Django
staticfiles/        Đầu ra collectstatic, không phải nơi chỉnh sửa nguồn
media/              Ảnh upload, không lưu vào Git
tools/              Công cụ kiểm tra, thiết lập và runner kiểm thử
docs/               Tài liệu tiến độ và bằng chứng kiểm thử theo giai đoạn
*.html, css/, js/    Giao diện gốc Bước 2 được bảo toàn
manage.py           Điểm chạy lệnh Django
requirements.txt    Dependency Python đang sử dụng
.env.example        Tên biến môi trường và giá trị mẫu an toàn
```

Một số tài liệu giai đoạn trước mô tả trạng thái tại thời điểm đó; không dùng mô tả demo trong tài liệu cũ để suy ra rằng các API hiện tại chưa được triển khai.

## Chạy dự án Django trên máy local

Các lệnh dưới đây dùng PowerShell tại thư mục chứa `manage.py`. Chuẩn bị Python (môi trường phát triển hiện dùng Python 3.12), MySQL và công cụ cần thiết để cài `mysqlclient` nếu máy chưa có wheel phù hợp.

### 1. Môi trường Python

Nếu chưa có virtual environment:

```powershell
python -m venv .venv
```

Cài dependency trong virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2. Cấu hình riêng tại máy

Nếu chưa có `.env`, sao chép file mẫu bằng lệnh không ghi đè file hiện có:

```powershell
if (-not (Test-Path -LiteralPath .env)) { Copy-Item -LiteralPath .env.example -Destination .env }
```

Điền cấu hình trực tiếp vào `.env` tại máy; không gửi giá trị bí mật qua chat hoặc đưa vào Git.

| Nhóm | Biến được source sử dụng |
| --- | --- |
| Django | `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS` |
| MySQL | `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_HOST`, `MYSQL_PORT` |
| Media local | `DJANGO_LOCAL_MEDIA_ENABLED` |
| Email | `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `EMAIL_USE_SSL`, `DEFAULT_FROM_EMAIL`, `PASSWORD_RESET_TIMEOUT` |
| payOS | `PAYOS_CLIENT_ID`, `PAYOS_API_KEY`, `PAYOS_CHECKSUM_KEY`, `PAYOS_RETURN_URL`, `PAYOS_CANCEL_URL` |

Cấu hình mẫu dùng database `annhien_spa` tại `127.0.0.1:3306`. Dùng tài khoản MySQL riêng có quyền phù hợp, không dùng root làm tài khoản chạy website. Với bản cài đã có dữ liệu, giữ nguyên cấu hình kết nối và SECRET_KEY hiện có; không chạy lại công cụ thiết lập để tạo lại database.

Với bản cài mới, đặt SECRET_KEY ngẫu nhiên và giữ riêng tại máy. `DJANGO_DEBUG=true` trong file mẫu chỉ dành cho phát triển. Khi `DEBUG=False`, source yêu cầu SECRET_KEY và bật cookie Secure; môi trường triển khai cần HTTPS phù hợp. Không nới cấu hình bảo mật chỉ để xử lý lỗi đăng nhập.

SMTP phải được cấu hình để luồng quên mật khẩu gửi email thực tế. Không bật đồng thời `EMAIL_USE_TLS` và `EMAIL_USE_SSL`. Ba khóa payOS phải thuộc cùng kênh; cấu hình khóa không tự tạo giao dịch. Webhook hiện có tại `/api/billing/webhook/payos/`; dùng URL HTTPS được cấu hình riêng khi triển khai, không tự mở tunnel chỉ để chạy website.

### 3. Kiểm tra database và migrations

```powershell
.\.venv\Scripts\python.exe tools\check_mysql.py
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py showmigrations
.\.venv\Scripts\python.exe manage.py migrate --plan
```

Các lệnh trên kiểm tra kết nối/cấu hình và trạng thái migration, không áp dụng migration. Nếu database đã có dữ liệu, sao lưu và rà soát kế hoạch trước khi thay đổi schema.

**Chỉ với database mới hoặc sau khi đã phê duyệt kế hoạch migration:**

```powershell
.\.venv\Scripts\python.exe manage.py migrate
```

Nếu chưa có Admin, tạo bằng lệnh dưới đây và nhập thông tin trực tiếp tại terminal:

```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
```

Manager của `accounts.User` gán role Admin cho superuser. Không có tài khoản/mật khẩu Admin mặc định và không cần tạo lại tài khoản đang có.

### 4. Static, media và khởi động

Khi đặt `DJANGO_DEBUG=false` trong `.env` (`DEBUG=False`), chạy `collectstatic` để sao chép tài nguyên từ `static/` sang `staticfiles/`, nơi WhiteNoise phục vụ tài nguyên. Chạy lại lệnh này sau khi cập nhật CSS/JS và khởi động lại Django để nạp bản mới:

```powershell
.\.venv\Scripts\python.exe manage.py collectstatic --noinput
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Truy cập [Home](http://127.0.0.1:8000/), [Đăng nhập](http://127.0.0.1:8000/login.html), hoặc [Admin Dashboard](http://127.0.0.1:8000/admin-dashboard.html) sau khi đăng nhập đúng quyền. Website Django cần MySQL hoạt động; mở HTML gốc không kiểm chứng được backend.

WhiteNoise phục vụ `/static/`, không phục vụ ảnh upload. Khi cần xem ảnh upload trên máy local với `DEBUG=False`, có thể chủ động đặt `DJANGO_LOCAL_MEDIA_ENABLED=true` trong `.env` rồi khởi động lại Django. Route này chỉ cho kết nối loopback trực tiếp, chặn proxy/tunnel và chỉ phục vụ ảnh hợp lệ trong `services/`, `products/`, `employees/` dưới `MEDIA_ROOT`; không bao phủ mọi thư mục upload. Giữ biến này `false` khi triển khai, phục vụ media qua giải pháp riêng phù hợp.

## Kiểm thử và xác minh

Runner hồi quy hiện khai báo **205 tests**: `accounts` 17, `core` 101, `billing` 70, `appointments.test_fr14` 17. Kết quả hồi quy MySQL gần nhất được nghiệm thu là **205/205 PASS**; đây là mốc đã chạy, không có nghĩa mọi thay đổi sau đó tự động được kiểm thử lại hoặc mọi trường hợp đều được bao phủ.

Discovery không kết nối database:

```powershell
.\.venv\Scripts\python.exe -B tools\fr14_tests.py discover
```

Xác minh môi trường MySQL kiểm thử riêng, nhập mật khẩu ẩn tại terminal:

```powershell
.\.venv\Scripts\python.exe -B tools\fr14_tests.py verify
```

Runner cố định database `annhien_spa_fr14_tests` và tài khoản `annhien_fr14_tests`, kiểm tra danh tính/quyền trước khi chạy, chặn kết nối ngoài phạm vi và chặn các lệnh gọi payOS bên ngoài chưa được mock. Database và tài khoản kiểm thử phải được chuẩn bị riêng; `verify` không chạy tests hoặc dọn dữ liệu.

**Chỉ khi đã xác minh database kiểm thử có thể bỏ dữ liệu và đồng ý làm sạch**, chạy:

```powershell
.\.venv\Scripts\python.exe -B tools\fr14_tests.py run
```

`run` và `regression` cùng chạy bộ kiểm thử hồi quy đầy đủ; hướng dẫn này dùng `run`, phù hợp với lần kiểm thử 205/205 PASS đã được nghiệm thu. Lệnh này yêu cầu xác nhận `CLEAN` theo đúng lời nhắc và sẽ chạy migration/flush trong database kiểm thử. Không dùng database nghiệp vụ, bản phục hồi cần bảo vệ hoặc chạy `manage.py test` tùy tiện với cấu hình mặc định.

Reviews và Reports có công cụ kiểm tra riêng như `tools/check_reviews_contract.py`, `tools/check_reports_contract.py` và các công cụ UI trực tiếp liên quan. Kết quả của các kiểm tra cô lập này tách biệt với bộ hồi quy 205 tests; công cụ chụp UI phụ thuộc Chrome và đường dẫn môi trường local, cần đọc trước khi dùng trên máy khác.

## Bảo quản dữ liệu và tài nguyên

- Giữ `.env`, thông tin MySQL/SMTP/payOS, bản dump, backup và media cá nhân ngoài kho Git công khai. Không dùng dữ liệu khách hàng hoặc giao dịch thật làm fixture công khai.
- Sao lưu đồng thời source, migrations, media và database trước khi nâng cấp schema; không reset database hoặc sửa migration cũ để đồng bộ giao diện.
- `docs/` và `tools/` có thể chứa tài liệu/công cụ phục vụ từng thời điểm. Kiểm tra và ẩn danh bằng chứng trước khi công khai; không mặc định toàn bộ file local đều an toàn để commit.
- Font Be Vietnam Pro và Playfair Display được phục vụ cục bộ, kèm giấy phép OFL trong tài nguyên font. Giao diện gốc có ảnh bổ sung từ Unsplash của Lindsay Cash, Štefan Štefančík và Daniil Lobachev; giữ thông tin nguồn và giấy phép khi sử dụng lại.
