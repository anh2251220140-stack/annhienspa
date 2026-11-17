# FR-22 — môi trường Chrome offline, 17/11/2026

## Khởi chạy

Từ thư mục dự án, chạy duy nhất:

```powershell
.\.venv\Scripts\python.exe -B tools/fr22_browser_test.py serve
```

Mở Chrome tại:

`http://127.0.0.1:8004/acceptance/fr22/`

URL này đăng nhập vào tài khoản User giả trong SQLite tạm rồi đưa tới trang Dịch vụ thật, section Một liệu trình, đúng với bạn. Không cần nhập mật khẩu hoặc API key. Nếu cổng 8004 đang được dùng, công cụ dừng; không chiếm/dừng tiến trình khác.

## Cách nghiệm thu

1. Đợi terminal in Ready và xác nhận HTTP 200 bằng readiness probe loopback trước khi mở trang.
2. Kiểm tra banner ghi SQLite tạm, dữ liệu giả, HTTP mock, không Gemini thật. Có 7 dịch vụ đang hoạt động và 3 sản phẩm liên kết do fixture tạo.
3. Ở AI mock, gửi form: giao diện phải hiện Gợi ý AI và 1–3 dịch vụ hợp lệ kèm lý do giả lập, có thông tin sản phẩm liên quan nếu khớp.
4. Chọn Timeout → dự phòng, Quota → dự phòng hoặc JSON lỗi → dự phòng trong banner rồi gửi lại form: phải hiện Gợi ý theo quy tắc, không giả danh kết quả Gemini Live mới.
5. Giữ khoảng cách 5 giây giữa các lần POST. Đổi chế độ không xóa/bỏ qua cooldown.
6. Thử ngân sách 1 VND: không có dịch vụ đủ điều kiện, không gọi SDK mock. F5 không tự gửi form hoặc gọi provider.
7. Ctrl+C trong terminal để dừng. Server chờ các request đang xử lý, đóng SQLite và dọn đúng TemporaryDirectory do chính launcher tạo. Mỗi lần chạy là một bộ dữ liệu mới; không xóa dữ liệu ngoài thư mục này.

## Luồng và nguồn dữ liệu

Giữ nguyên templates/pages/services.html, static/js/app.js và API production. Form đã POST tới `/api/ai/recommendations/`, do đó không sửa frontend/backend đã PASS.

Luồng preview: cookie User giả → template và catalog ORM thật → app.js thật → Django recommendations view/service thật → GeminiProvider/SDK thật → HTTPX MockTransport nội bộ → validation thật → AIRecommendation trong SQLite.

Không replay một phản hồi Google thật chưa được cung cấp. HTTP mock tạo JSON theo hợp đồng đã được nghiệm thu, dùng ID dịch vụ giả đã được backend lọc. Đây là kiểm thử nối giao diện/nhãn và fallback; bằng chứng Gemini Live trước đó được giữ nguyên, không phát sinh bằng chứng chất lượng mô hình thật mới.

Fixture: 7 dịch vụ thuộc face/relax/body/hair, giá/thời lượng khác nhau để thử điều kiện; 3 sản phẩm với ServiceProduct liên kết; hồ sơ User giả Da khô, nhu cầu cấp ẩm, ngân sách 600000. Không sao chép hồ sơ hoặc danh mục thật.

## Cô lập

Tái sử dụng tools/chat_sqlite.configure để chặn dotenv, MySQL, socket/HTTP bên ngoài và PayOS; cấu hình trong chính tiến trình trỏ SQLite tạm. Không sửa .env/settings mặc định.

Không chạy migrate/makemigrations. create_fixture_schema dùng schema_editor với models hiện tại chỉ khi default database là SQLite mới chưa có bảng. Test xác nhận không có bảng django_migrations.

Chỉ HTTPX send được thay bằng dispatcher nội bộ tới MockTransport; không khôi phục sender mạng thật. Target khác Gemini generateContent bị chặn. Key là chuỗi giả cố định, không đọc key môi trường. Các cờ xuất preferences và cho phép SDK chỉ có trong tiến trình chứa dữ liệu giả; AI_REVIEW_EXPORT_APPROVED=False và AI_PAID_CALLS_APPROVED=False.

SESSION_COOKIE_NAME=annhien_fr22_preview_session; CSRF_COOKIE_NAME=annhien_fr22_preview_csrf. Không ảnh hưởng cookie của website khác trên cùng host. Phiên/chế độ chỉ thuộc môi trường preview loopback.

## File mới và kiểm thử

- tools/fr22_browser_test.py: launcher/browser fixture, không sửa source ứng dụng.
- tools/test_fr22_browser.py: 8 test offline qua Django Test Client, template/API thật; kiểm tra schema không migration, 7/3 dữ liệu, AI và các fallback, CSRF/cooldown, GET không provider, cookie và socket guard.
- tools/test_fr22_browser_ui.cjs: 6 test chạy trực tiếp đoạn JS form gợi ý đang dùng trong app.js bằng DOM mock; kiểm tra hiển thị AI/rule, lý do, sản phẩm, lỗi cooldown, danh sách rỗng, escaping và không POST khi khởi tạo/F5.

Lệnh đã chạy:

```powershell
.\.venv\Scripts\python.exe -B -m unittest tools.test_fr22_browser -v
node tools/test_fr22_browser_ui.cjs
git diff --check
```

Kết quả cuối: 14 PASS, 0 FAIL, 0 ERROR. Cú pháp Python/JS và git diff --check đạt. Không chạy lại bộ Assistance hoặc toàn bộ backend đã PASS. Các lỗi test setup ban đầu do Host testserver và backend đăng nhập không khớp cấu hình đã được sửa trong công cụ nghiệm thu, không thay đổi authentication ứng dụng.

Chưa mở Chrome trong lượt này; chưa ghi nhận PASS trực quan/responsive hoặc startup smoke qua socket. Readiness probe được chạy khi người dùng chủ động khởi động serve. Không tự gọi Gemini Live, không MySQL, không API ngoài, không migration hoặc commit/push.
