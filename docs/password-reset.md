# Quên mật khẩu — 21/10/2026

## Đã thực hiện

- Thêm liên kết Quên mật khẩu? dưới trường mật khẩu, căn phải; tái sử dụng shell đăng nhập, ảnh, màu, font và responsive hiện có.
- Dùng PasswordResetView/PasswordResetForm/PasswordResetConfirmView và token mặc định của Django, tương thích accounts.User. Không tự tạo bảng/token storage.
- Token mặc định 3600 giây, cấu hình PASSWORD_RESET_TIMEOUT. Sau khi đổi mật khẩu token mất hiệu lực; phiên đăng nhập cũ cũng mất hiệu lực. Không tự đăng nhập sau reset.
- Email không tồn tại, tài khoản khóa hoặc mật khẩu unusable đều nhận cùng phản hồi, không gửi thư cho những tài khoản này. Django gửi thư đồng bộ; phản hồi thống nhất không có nghĩa đã loại bỏ mọi suy luận qua thời gian đáp ứng.
- Confirm kiểm tra lại tài khoản active và token bên trong transaction/select_for_update trước khi lưu, bảo vệ trường hợp bị khóa sau khi cấp liên kết và gửi đồng thời. Không đổi role/is_active hoặc quyền quản trị.
- Mật khẩu mới dùng validators Django và giới hạn 128 ký tự tương thích form login hiện tại.
- Source chỉ tạo một nút mắt. CSS ẩn ::-ms-reveal/::-ms-clear của Edge; không tắt autofill/password manager. UI initializer tránh tạo trùng nút, giữ aria-label/aria-pressed và thao tác bàn phím. Tự che lại khi submit/reset/rời trang/ẩn tab.
- Không chỉnh source Figma gốc hoặc CSS gốc. Không sửa models/migrations, không reset database nghiệp vụ, không thay đổi mật khẩu tài khoản thật. Chưa commit/push.

## File thuộc thay đổi này

- accounts/password_reset.py (mới), accounts/urls.py.
- accounts/test_password_reset.py (mới).
- config/settings.py, .env.example (chỉ giá trị mẫu).
- templates/accounts/password_reset.html, password_reset_email.txt, password_reset_subject.txt (mới).
- templates/pages/login.html, register.html, profile.html (liên kết/CSS hỗ trợ).
- static/css/password-reset.css (mới), static/js/ui.js.
- docs/password-reset.md, password-reset-tests.txt, password-reset-login.png, password-reset-mobile.png.

## Kiểm thử

- 7 tests mới: thư reset và đổi thành công; đăng nhập mật khẩu mới/mật khẩu cũ bị từ chối; phiên cũ/token dùng lại bị từ chối; phản hồi giống nhau sau khi loại CSRF ngẫu nhiên; tài khoản khóa/unusable; hết hạn/uid/token sai; validation/CSRF; Admin giữ nguyên quyền; template/liên kết.
- Toàn bộ 64 tests trên test_annhien_spa; kết quả lần cuối trong password-reset-tests.txt. Dùng email backend in-memory, không gửi thư tới người thật.
- Django check không lỗi, makemigrations --check không có thay đổi; Node --check ui.js đạt.
- Browser trên localhost: liên kết hoạt động; một nút mắt; Enter hiện/Space che mật khẩu; screenshot desktop và mobile 390px, không tràn ngang. Chưa kiểm tra từng extension trên trình duyệt cá nhân; nếu extension tự chèn nút thì CSS trang không đảm bảo kiểm soát được.
- Chưa kiểm chứng gửi email qua SMTP đến hộp thư thật vì .env hiện không có cấu hình SMTP. Không coi email in-memory là email đã gửi thật.

## Cấu hình email trên máy

Điền trực tiếp vào .env (không gửi bí mật trong chat):

- EMAIL_HOST: máy chủ SMTP của nhà cung cấp.
- EMAIL_PORT: thường 587 với STARTTLS hoặc 465 với SSL, theo nhà cung cấp.
- EMAIL_HOST_USER và EMAIL_HOST_PASSWORD: tài khoản SMTP và mật khẩu ứng dụng/SMTP.
- EMAIL_USE_TLS=true / EMAIL_USE_SSL=false cho STARTTLS; nếu dùng SSL thì đảo lại. Không bật cả hai.
- DEFAULT_FROM_EMAIL: địa chỉ gửi đã được nhà cung cấp cho phép.
- EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend.
- PASSWORD_RESET_TIMEOUT=3600 (giây).

Khởi động lại Django sau khi cập nhật .env. Sau đó tự nhập email tài khoản đang hoạt động qua Quên mật khẩu? và kiểm tra hộp thư/thư rác. Khi chưa có SMTP, giao diện vẫn phản hồi chung; lỗi gửi thư được Django ghi log phía máy chủ. Không dùng console backend ở môi trường thật vì chứa liên kết reset.

Liên kết lấy scheme/domain từ request với ALLOWED_HOSTS hiện có. Khi triển khai online cần domain thật, HTTPS và cấu hình reverse proxy tin cậy để liên kết email dùng đúng HTTPS. Localhost chỉ mở được trên máy đang chạy Django.
