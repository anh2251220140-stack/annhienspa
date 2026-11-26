# An Nhiên Spa chạy bằng Django

Django 5.2 và MySQL phục vụ hệ thống User/Admin của Bước 3. Django xử lý xác thực, phiên, phân quyền, danh mục, lịch làm việc, đặt lịch, hóa đơn, payOS, đánh giá và báo cáo. App `ai_features` triển khai chatbot, gợi ý dịch vụ, phân tích đánh giá và lịch sử hội thoại. Gemini là nhà cung cấp AI bên ngoài. RAG tính độ tương đồng cosine trong Python với chỉ mục SQLite trên local hoặc MySQL trên Vercel.

## Chạy trên máy local

Làm theo [hướng dẫn cài đặt Django và cấu hình MySQL](README.md#chạy-dự-án-django-trên-máy-local). Khi đã cài các thư viện và điền `.env` riêng trên máy, kiểm tra và khởi động từ thư mục chứa `manage.py`.

```powershell
.\.venv\Scripts\python.exe tools\check_mysql.py
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Django đọc cấu hình MySQL từ `.env` trên máy local. Kiểm tra đúng máy chủ và schema trước khi cân nhắc migration. Model người dùng là `accounts.User`.

Tạo Admin bằng `manage.py createsuperuser` nếu chưa có tài khoản quản trị. Nhập mật khẩu tại lời nhắc trong terminal. Tài khoản chạy bản tham chiếu giao diện thuộc hệ thống mẫu riêng.

Các trang Django dùng `templates/pages/` và `static/`, với đường dẫn như `/login.html`, `/services.html` và `/admin-dashboard.html`. HTML ở thư mục gốc là bản tham chiếu giao diện Bước 2. `settings_preview` dùng lại cấu hình ứng dụng và các kiểm tra quyền của Django.

## AI và bản triển khai công khai

- [Biến môi trường AI](README.md#biến-môi-trường-ai) mô tả cấu hình Gemini, giới hạn chatbot, quyền gửi dữ liệu và đường dẫn chỉ mục.
- [Triển khai lên Vercel](README.md#triển-khai-lên-vercel) hướng dẫn kết nối MySQL ngoài Vercel, kho Private Blob và cấu hình Production.
- [Docker Compose](compose.yaml) mô tả cách chạy Django và Nginx trên máy local.

Các tài liệu [Giai đoạn 2](docs/phase2.md) và [kết quả kiểm thử Giai đoạn 2](docs/phase2-results.txt) lưu mốc lịch sử.
