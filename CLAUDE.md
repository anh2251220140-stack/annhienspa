@AGENTS.md

# Kiến trúc hiện tại

An Nhiên Spa là hệ thống quản lý và đặt lịch Spa chạy bằng Django 5.2 và
MySQL. Giao diện hệ thống dùng Django Templates, HTML, CSS và JavaScript
thuần. Các trang và tài nguyên của Django nằm ở `templates/pages/` và
`static/`. HTML, CSS và JavaScript ở thư mục gốc là bản tham chiếu Bước 2.

`config/` chứa cấu hình Django và định tuyến. Xác thực, phân quyền, đặt lịch,
hóa đơn, webhook payOS, đánh giá và báo cáo do backend xử lý.
`ai_features/` quản lý Gemini, RAG với chỉ mục SQLite ở local hoặc MySQL trên Vercel và tìm kiếm cosine,
đề xuất dịch vụ, phân tích đánh giá và lịch sử hội thoại.

Bản công khai chạy trên Vercel với MySQL bên ngoài và Vercel Private Blob cho
ảnh tải lên. Docker Compose phục vụ môi trường local. Xem [README.md](README.md)
để biết cách chạy, cấu hình AI và triển khai.

Đọc `AGENTS.md` để biết quy ước làm việc và bảo toàn giao diện Bước 2.
Khi sửa website Django, đối chiếu với mã backend và template tương ứng.
Giữ phong cách luxury spa, nội dung tiếng Việt và khả năng hiển thị trên
nhiều kích thước màn hình.
