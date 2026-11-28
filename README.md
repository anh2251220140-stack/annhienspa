# An Nhiên Spa — Website quản lý và đặt lịch Spa

Đồ án tốt nghiệp xây dựng hệ thống giới thiệu dịch vụ, đặt lịch và quản lý hoạt động Spa. Phiên bản **Bước 3** sử dụng **Django + MySQL**, kế thừa giao diện HTML/CSS/JavaScript của **Bước 2** và phong cách Luxury A với tông kem, nâu và champagne.

Hệ thống hiện có xác thực, phân quyền, quản lý danh mục, lịch làm việc, đặt lịch, hóa đơn, thanh toán tại Spa/payOS, đánh giá, phản hồi và báo cáo. Các chức năng AI gồm chatbot tư vấn Spa, đề xuất dịch vụ, phân tích đánh giá và lịch sử hội thoại.

- **Mã nguồn Bước 3:** [GitHub · anh2251220140-stack/annhienspa](https://github.com/anh2251220140-stack/annhienspa).
- **Website triển khai:** [An Nhiên Spa trên Vercel](https://annhienspa-sepia.vercel.app/).

## Công nghệ

| Thành phần | Công nghệ hiện tại |
| --- | --- |
| Giao diện | Django Templates, HTML, CSS, JavaScript thuần |
| Backend | Python, Django 5.2 |
| Cơ sở dữ liệu | MySQL qua Django ORM; `mysqlclient` trên Windows và PyMySQL tương thích MySQLdb trên Linux/Vercel |
| Xác thực | Django Authentication + Session; custom User `accounts.User` |
| Thanh toán | SDK payOS, QR nhúng trên hóa đơn, ghi nhận thanh toán tại Spa |
| AI | Google Gemini qua Google Gen AI SDK; chỉ gọi Gemini thật khi cấu hình và quyền cho phép |
| RAG | Dữ liệu Spa công khai, tra cứu trực tiếp hoặc tìm theo cosine trong Python. Chỉ mục mặc định dùng SQLite trên máy local và MySQL trên Vercel |
| Tài nguyên | Static từ `static/` và đầu ra `collectstatic`; upload vào Vercel Private Blob trên Vercel hoặc `media/` khi chạy local |
| Triển khai | Django trên Vercel, kết nối MySQL bên ngoài; Docker Compose + Gunicorn + Nginx cho môi trường local |
| Email | Django email backend, cấu hình SMTP qua biến môi trường |
| Kiểm thử | Django TestCase/TransactionTestCase, runner MySQL cô lập; một số công cụ kiểm tra SQLite/Chrome riêng |

Không sử dụng React, Vue, TypeScript hoặc bước biên dịch frontend. Các dependency Python được khai báo trong `requirements.txt`; không cần npm để chạy website Django.

## Bước 2 và Bước 3

- **Bước 2 — giao diện tham chiếu:** các file HTML tại thư mục gốc cùng `css/`, `js/`, `images/` được giữ lại để bảo toàn thiết kế ban đầu. Các tương tác mẫu và dữ liệu trình duyệt ở bản này phục vụ minh họa giao diện.
- **Bước 3 — hệ thống hoạt động:** Django render `templates/pages/`, phục vụ tài nguyên từ `static/`, sử dụng API và dữ liệu MySQL. Đăng nhập, phân quyền và dữ liệu nghiệp vụ được kiểm tra tại backend.
- Các trang User/Admin có đường dẫn `.html` trên Django. Mở HTML gốc bằng máy chủ tĩnh chỉ chạy bản giao diện tham chiếu; tài khoản và dữ liệu của hệ thống Django nằm trong MySQL.

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

### Chức năng AI

- **FR-21 — Chatbot:** Tra cứu danh mục dịch vụ, sản phẩm, khuyến mãi và thông tin Spa. Khi bật RAG, chatbot ưu tiên tra cứu trực tiếp và dùng chỉ mục SQLite ở local hoặc MySQL trên Vercel cho tìm kiếm ngữ nghĩa bằng cosine. Khi thiếu dữ liệu phù hợp hoặc Gemini gặp lỗi, chatbot có phản hồi dự phòng.
- **FR-22 — Đề xuất cá nhân hóa:** Đề xuất dịch vụ dựa trên nhu cầu, ngân sách, hồ sơ và lịch sử. Backend kiểm tra đề xuất theo danh mục và điều kiện của khách; có chế độ gợi ý theo quy tắc.
- **FR-23 — Phân tích đánh giá:** Quản trị viên được cấp quyền có thể phân tích cảm xúc và tóm tắt đánh giá. Gửi dữ liệu sang Gemini là tùy chọn riêng.
- **FR-24 — Lịch sử hội thoại:** Phiên và tin nhắn được lưu trong MySQL. User xem hội thoại của mình, Admin xem theo quyền.

## Cấu trúc repository

```text
config/             Cấu hình Django, URL gốc, WSGI/ASGI và các backend lưu ảnh
accounts/           Custom User, hồ sơ, xác thực, quyền và đặt lại mật khẩu
services/           Danh mục và dịch vụ
products/           Sản phẩm giới thiệu và quan hệ sản phẩm–dịch vụ
employees/          Nhân viên, phân công dịch vụ và lịch làm việc
appointments/       Đặt lịch, chuyển trạng thái và lịch sử phân công lại
promotions/         Chương trình, điều kiện và giới hạn sử dụng
billing/            Hóa đơn, thanh toán, QR và adapter payOS
reviews/            Đánh giá và phản hồi
dashboard/          API tổng hợp Dashboard và Reports
ai_features/        Chatbot, Gemini, RAG, đề xuất, phân tích đánh giá và lịch sử
core/               Routing trang, dữ liệu catalog, form và API quản trị dùng chung
templates/          Django Templates cho website; các trang trong pages/
static/             CSS, JavaScript, font và ảnh dùng bởi Django
staticfiles/        Đầu ra collectstatic, không phải nơi chỉnh sửa nguồn
media/              Ảnh upload, không lưu vào Git
tools/              Công cụ kiểm tra, thiết lập và runner kiểm thử
docs/               Tài liệu tiến độ và bằng chứng kiểm thử theo giai đoạn
*.html, css/, js/    Giao diện gốc Bước 2 được bảo toàn
manage.py           Điểm chạy lệnh Django
requirements.txt    Dependency Python đang sử dụng
.env.example        Tên biến môi trường và giá trị mẫu an toàn
compose.yaml        Cấu hình Django/Gunicorn và Nginx để chạy Docker local
```

Các báo cáo theo giai đoạn trong `docs/` ghi trạng thái tại thời điểm kiểm thử. Hướng dẫn hiện tại nằm trong README này và [README-DJANGO.md](README-DJANGO.md).

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
| Django | `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` |
| MySQL | `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_HOST`, `MYSQL_PORT` |
| Media local | `DJANGO_LOCAL_MEDIA_ENABLED` |
| Email | `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `EMAIL_USE_SSL`, `DEFAULT_FROM_EMAIL`, `PASSWORD_RESET_TIMEOUT` |
| payOS | `PAYOS_CLIENT_ID`, `PAYOS_API_KEY`, `PAYOS_CHECKSUM_KEY`, `PAYOS_RETURN_URL`, `PAYOS_CANCEL_URL` |
| AI | Xem [biến môi trường AI](#biến-môi-trường-ai) để bật từng tính năng |

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

WhiteNoise phục vụ `/static/` ở local. Để xem ảnh tải lên khi phát triển local, đặt `DJANGO_LOCAL_MEDIA_ENABLED=true` trong `.env` rồi khởi động lại Django. Tuyến `/media/` hoạt động cả khi `DEBUG=False`, chỉ nhận kết nối loopback trực tiếp. Avatar chỉ được trả cho chủ hồ sơ hoặc Admin đã đăng nhập. Docker local dùng tuyến media riêng qua Django. Trên Vercel, dùng Private Blob theo hướng dẫn ở dưới.

## Biến môi trường AI

Thêm các biến cần dùng vào `.env` riêng trên máy hoặc **Settings → Environment Variables** của dự án Vercel. Mặc định chatbot và RAG tắt. Khi bật chatbot với `AI_PROVIDER=mock`, ứng dụng dùng bộ phản hồi nội bộ mà không gọi Gemini.

| Nhóm | Biến và ý nghĩa |
| --- | --- |
| Chatbot | `AI_CHAT_ENABLED=true` bật chatbot. `AI_CHAT_DAILY_LIMIT` và `AI_CHAT_COOLDOWN_SECONDS` mặc định là 30 lượt/ngày và 5 giây. `AI_CHAT_SPA_INFORMATION` là thông tin Spa đã duyệt để sử dụng làm nguồn. |
| Nhà cung cấp | `AI_PROVIDER=gemini` chọn Gemini. `AI_GEMINI_API_KEY` đặt dưới dạng secret. Giá trị mặc định của `AI_PROVIDER` là `mock`. |
| Quyền gọi Gemini | Sau khi xác minh dự án Google trên Free Tier và phạm vi sử dụng, đặt `AI_GEMINI_REQUESTS_APPROVED=true`, `AI_GEMINI_FREE_TIER_CONFIRMED=true`, `AI_GEMINI_FREE_TIER_ONLY=true` và `AI_PAID_CALLS_APPROVED=false`. Các cờ cấu hình ghi nhận quyền và xác nhận của người vận hành. Kiểm tra gói và quota tại Google. |
| Model | `AI_GEMINI_MODEL` mặc định `gemini-3.5-flash-lite`. `AI_GEMINI_EMBEDDING_MODEL` mặc định `gemini-embedding-001`, với `AI_GEMINI_EMBEDDING_DIMENSIONS=768`. Adapter kiểm tra model và số chiều được hỗ trợ. |
| Truy xuất RAG | `AI_RAG_ENABLED=true` bật RAG. `AI_RAG_STORAGE` chọn `mysql` hoặc `sqlite`; mặc định MySQL trên Vercel, SQLite ở các môi trường khác. `AI_RAG_DIRECTORY` chỉ dùng cho SQLite và mặc định là `.rag-index/`. `AI_RAG_INDEX_UPDATE_APPROVED` chỉ bật khi đã duyệt cập nhật vector từ dữ liệu công khai. |
| Đề xuất và đánh giá | `AI_PERSONALIZATION_EXPORT_APPROVED` cho phép gửi dữ liệu dùng để đề xuất. `AI_ASSISTANCE_ENABLED` bật API phân tích đánh giá cho Admin được cấp quyền. `AI_REVIEW_EXPORT_APPROVED` cho phép gửi nội dung đánh giá phù hợp sang Gemini. Chỉ bật các quyền gửi dữ liệu sau khi đã duyệt phạm vi. |

Để lập chỉ mục trên một môi trường đã phê duyệt, dùng `manage.py index_spa` sau khi cấu hình đúng thư mục, nhà cung cấp và các cờ quyền tương ứng. Khi bật nhánh Gemini, thao tác có thể gọi API embedding. Xem [mã cấu hình AI](ai_features/config.py), [adapter Gemini](ai_features/gemini.py) và [chỉ mục RAG](ai_features/rag.py).

## Triển khai lên Vercel

1. Trong Vercel, import repository GitHub và chọn thư mục gốc có `manage.py` và `requirements.txt`. Dùng preset Django/Python tương ứng; Vercel nhận diện ứng dụng Django và đọc cấu hình WSGI/ASGI. Dự án dùng `config/wsgi.py` và có `STATIC_ROOT` cho bước thu thập static của Vercel. [Hướng dẫn Django trên Vercel](https://vercel.com/templates/python/django-hello-world).
2. Vào **Settings → Environment Variables**, chọn **Production** và cấu hình các nhóm sau.

   | Nhóm | Cấu hình Production |
   | --- | --- |
   | Django | `DJANGO_DEBUG=false`, `DJANGO_SECRET_KEY` riêng cho Production, `DJANGO_ALLOWED_HOSTS` chứa hostname thật và `DJANGO_CSRF_TRUSTED_ORIGINS` chứa origin HTTPS của website nếu cần. |
   | MySQL | `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD` theo máy chủ MySQL thực tế mà Vercel có thể kết nối. Chuẩn bị schema qua quy trình migration đã rà soát trước khi kiểm tra website. |
   | Media | Kết nối **Vercel Private Blob** với đúng dự án và môi trường. Để `DJANGO_BLOB_MEDIA_ENABLED` ở mặc định bật trên Vercel hoặc đặt `true`. Dùng thông tin xác thực do tích hợp Blob cấp; yêu cầu `/media/` và kiểm tra quyền avatar đi qua Django. |
   | Email/payOS | Đặt biến SMTP nếu dùng khôi phục mật khẩu. Với payOS, dùng bộ khóa của cùng kênh và URL HTTPS Production cho `PAYOS_RETURN_URL`, `PAYOS_CANCEL_URL`. Đăng ký webhook tại đường dẫn `/api/billing/webhook/payos/` trên tên miền Production. |
   | AI | Chọn biến theo [mục AI](#biến-môi-trường-ai). Lưu khóa và mật khẩu dưới dạng **Secret**. Vercel dùng biến mới từ lần triển khai tiếp theo. |

3. Triển khai từ nhánh Production đã cấu hình. Khi bản mới **Ready**, kiểm tra trang chủ, tài nguyên static, đăng nhập User/Admin và trang lấy dữ liệu từ MySQL. Kiểm tra thêm ảnh, AI hoặc webhook với dữ liệu demo khi bật các tích hợp tương ứng. [Biến môi trường Vercel](https://vercel.com/docs/environment-variables) · [Hồ sơ kỹ thuật Private Blob](docs/vercel-private-blob-20261123.txt).

**RAG trên Vercel.** Chỉ mục dùng bảng MySQL `rag_document_index`, vì các instance Vercel cần đọc chung dữ liệu đã lập chỉ mục. Bảng chỉ chứa đoạn văn và vector từ dữ liệu công khai của spa, có mã băm để tránh trả dữ liệu đã cũ. Thiết lập trên môi trường quản trị tin cậy dùng đúng MySQL và cấu hình model của Production:

1. Xem kế hoạch bằng `python manage.py migrate ai_features 0004_rag_document_index --plan`, rồi áp dụng đúng migration đó sau khi xác nhận database đích. Migration chỉ tạo bảng chỉ mục.
2. Dùng `AI_RAG_ENABLED=true`, `AI_RAG_STORAGE=mysql` và quyền Gemini tương ứng với Production. Chỉ bật thêm `AI_RAG_INDEX_UPDATE_APPROVED=true` trong tiến trình quản trị đã được duyệt, rồi chạy `python manage.py index_spa`. Lệnh gửi các đoạn công khai cần cập nhật đến Gemini để tạo vector.
3. Khi hỏi chatbot, ứng dụng truy xuất chỉ mục MySQL nếu cần tìm theo ngữ nghĩa. Giữ quyền tự cập nhật tắt trên Vercel nếu dùng lệnh quản trị để cập nhật định kỳ. Cập nhật chỉ mục sau thay đổi danh mục để khôi phục khả năng tìm theo ngữ nghĩa cho nội dung mới. Biến `AI_RAG_DIRECTORY` chỉ có tác dụng khi chọn SQLite.

## Kiểm thử và xác minh

Xem [Báo cáo kiểm thử tổng hợp Bước 3](docs/bao-cao-kiem-thu-cuoi.md) để đối chiếu kết quả, phạm vi và bằng chứng của từng đợt nghiệm thu.

### Chạy toàn bộ bộ kiểm thử Django trên Windows

Cài các thư viện Python của dự án và MySQL Community Server 8.4. Từ thư mục dự án ở đúng commit cần kiểm thử, chạy:

```powershell
$testedCommit = git rev-parse HEAD
.\.venv\Scripts\python.exe -B tools\run-django-mysql.py --expect-commit $testedCommit --output-dir "$env:TEMP\annhien-test-results"
```

Dùng `--mysql-bin` nếu các chương trình MySQL 8.4 nằm ngoài thư mục cài mặc định. Trình chạy tạo hai máy chủ MySQL tạm chỉ nghe tại `127.0.0.1`, cổng 43361 và 3311. Các cổng phải trống. Trình chạy không cần thông tin của MySQL nghiệp vụ, không đọc `.env` và chặn các lời gọi mạng bên ngoài từ bộ test.

Các ca Django thông thường chạy trên MySQL. Nhóm quản trị và đồng thời yêu cầu guard chạy trên máy chủ tạm thứ hai. Hai lớp kiểm tra tích hợp SDK được viết cho SQLite chạy riêng bằng SQLite tạm với mạng bị chặn. Thư mục kết quả chứa log từng nhóm và `summary.json` ghi commit, tổng số ca cùng trạng thái theo nhóm. Chạy riêng các kiểm thử JavaScript bằng Node.js nếu cần báo cáo kết quả phía trình duyệt.

### Trình chạy MySQL có guard

Mốc hồi quy MySQL đã nghiệm thu là **205/205 PASS**, gồm `accounts` 17, `core` 101, `billing` 70 và `appointments.test_fr14` 17 ở đợt đó. Dùng lệnh discovery để xem số ca của mã hiện tại.

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

- Giữ `.env`, khóa Gemini/Blob, thông tin MySQL/SMTP/payOS, bản dump, backup, tệp SQLite kiểm thử và media cá nhân ngoài kho Git công khai. Không dùng dữ liệu khách hàng hoặc giao dịch thật làm fixture công khai.
- Sao lưu đồng thời source, migrations, media và database trước khi nâng cấp schema; không reset database hoặc sửa migration cũ để đồng bộ giao diện.
- `docs/` và `tools/` có thể chứa tài liệu/công cụ phục vụ từng thời điểm. Kiểm tra và ẩn danh bằng chứng trước khi công khai; không mặc định toàn bộ file local đều an toàn để commit.
- Font Be Vietnam Pro và Playfair Display được phục vụ cục bộ, kèm giấy phép OFL trong tài nguyên font. Giao diện gốc có ảnh bổ sung từ Unsplash của Lindsay Cash, Štefan Štefančík và Daniil Lobachev; giữ thông tin nguồn và giấy phép khi sử dụng lại.
