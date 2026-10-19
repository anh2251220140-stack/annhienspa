# An Nhiên Spa — Django

Giai đoạn 2 dùng MySQL và Django Authentication + Session thật. Xem [hướng dẫn thiết lập và phạm vi](docs/phase2.md), [kết quả kiểm tra](docs/phase2-results.txt).

```powershell
.\.venv\Scripts\python.exe tools\check_mysql.py
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Database/user/mật khẩu đọc từ .env. Nếu chưa có, chạy tools/setup_mysql.py trực tiếp trên máy theo hướng dẫn. Chỉ migrate sau khi đã kiểm tra schema. AUTH_USER_MODEL đã đặt là accounts.User trước migration đầu tiên.

Tạo Admin thật bằng `manage.py createsuperuser` với mật khẩu nhập tại terminal. Không có tài khoản mặc định. Các tài khoản demo trong source frontend gốc không dùng được trong Django.

Tất cả 27 trang giữ tên URL .html. Giao diện gốc ở root được giữ nguyên; Django dùng templates/pages và static/. Đăng ký/đăng nhập/đăng xuất/phân quyền là backend thật; các chức năng nghiệp vụ khác vẫn là giao diện demo cho đến giai đoạn tiếp theo. settings_preview chỉ còn là alias settings thật, không bỏ qua quyền.
