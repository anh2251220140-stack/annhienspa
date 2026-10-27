# Nút thanh toán payOS — 24/10/2026

> **Phạm vi công khai — cập nhật hồ sơ ngày 27/10/2026.** Kết luận hiện tại nằm trong
> [Biên bản nghiệm thu cuối Giai đoạn 4](phase4-acceptance.md): thanh toán thật đã
> được xác nhận, chỉ ghi nhận một lần; khuyến mãi dùng đúng một lượt; hồi quy gần
> nhất 134/134 đạt; code main tại 1552cca. Lượt này chỉ cập nhật tài liệu, không
> chạy lại tests hoặc gọi payOS.
>
> **Toàn bộ nội dung lịch sử bên dưới phản ánh thời điểm ghi trong từng mục**, không
> phải trạng thái hiện tại. Các câu “chưa thanh toán”, “chỉ mock”, “chưa push” hoặc
> “chưa có giới hạn lượt” chỉ có hiệu lực tại mốc đó. Không dùng hướng dẫn cũ để
> thao tác trên hóa đơn đã thanh toán. Hành vi hiện tại: QR nhúng, hạn tối đa 600
> giây (không vượt giờ hẹn), polling chỉ đọc MySQL, đối soát provider chủ động.
>
> Mã HD-A/HD-B/HD-C và LH-A/LH-B/LH-C/LH-D là bí danh trong tài liệu, không phải ID
> để truy vấn. HD-TEST/LH-TEST là fixture. Định danh người, số tiền và ngày/giờ hẹn
> đã được ẩn danh; diễn biến kỹ thuật và các mốc kiểm thử được giữ lại. JSON/log/ảnh
> được nhắc tới là chứng cứ cục bộ, không thuộc gói Markdown công khai.

## Hồ sơ lịch sử (giữ theo mốc triển khai)

## Chẩn đoán và sửa lỗi

Nút gọi POST `/api/billing/<id>/online/` để tạo hoặc tái sử dụng phiên payOS,
không chỉ chọn phương thức. Lần chẩn đoán đầu thiếu cả ba khóa nên backend trả
400 trước khi tạo Payment. Trình duyệt test bản cũ có nhận thông báo, không có
lỗi Console; chưa tái hiện được tình huống hoàn toàn im lặng trên trình duyệt
riêng của người dùng. Giao diện cũ thiếu nhãn đang xử lý và polling có thể xóa lỗi.

Đã bổ sung nhãn đang tạo phiên, khóa nút khi chạy, focus vào lỗi/checkout,
thông báo cấu hình thiếu rõ ràng, giữ lỗi qua polling, đọc lại trạng thái local
sau lỗi API và hướng dẫn mở trang payOS để xem QR khi thành công. Không vẽ QR
demo, không đổi hóa đơn sang paid khi chỉ tạo phiên. Amount lấy từ backend;
phiên cũ và lượt khuyến mãi được giữ theo cơ chế chống trùng đã có.

Sau khi người dùng điền .env, kiểm tra lúc 21:05 (Việt Nam): Django nạp đủ
PAYOS_CLIENT_ID, PAYOS_API_KEY, PAYOS_CHECKSUM_KEY. Chỉ kiểm tra có/thiếu, chưa
xác minh tính hợp lệ với nhà cung cấp. RETURN_URL/CANCEL_URL chưa khai báo riêng
trong môi trường, settings có mặc định về invoice.html trên localhost:8000.

HD-C / LH-D vẫn confirmed, unpaid, TESTSPA10, tổng [số tiền ẩn danh] VND, chưa có Payment.
Hash tám bảng nghiệp vụ không đổi so với lần chẩn đoán trước. Công cụ audit chỉ
SELECT, không gọi POST hoặc SDK. Không sửa .env, SMTP hoặc dữ liệu thật.

## Files

- billing/gateway.py, billing/views.py: kiểm tra cấu hình và boolean trả cho UI.
- static/js/live-invoice.js, static/js/phase4-api.js: loading, lỗi, timeout, focus.
- templates/pages/invoice.html: hướng dẫn checkout, accessibility, cache version.
- billing/test_payos_feedback.py: 5 tests mới, mock thành công/lỗi/thiếu khóa/CSRF.
- tools/audit_payos_button.py, tools/audit_git_secrets.py: audit chỉ đọc, không xuất bí mật.
- docs/payos-button-audit.json, docs/payos-feedback-tests.txt: bằng chứng.

Không có migration mới. Giữ các thay đổi chưa commit từ những lượt trước.

## Kiểm tra Git và hệ thống

Kiểm tra 24/10/2026: .env được Git ignore, không nằm trong index và không có
đường dẫn .env trong lịch sử commit. Quét file tracked/untracked không bị ignore,
index và mọi blob thuộc lịch sử các refs: không tìm thấy giá trị hiện tại của ba
khóa payOS, DJANGO_SECRET_KEY, MYSQL_PASSWORD hoặc EMAIL_HOST_PASSWORD.
Đây là kiểm tra các bí mật hiện có, không phải chứng minh mọi chuỗi bất kỳ trong
lịch sử đều không phải bí mật cũ. Không commit/push.

Django check: 0 issues. makemigrations --check --dry-run: No changes detected.
migrate --check: exit 0. py_compile các file Python liên quan: qua.

## Kết quả nghiệm thu mock

Chạy lại toàn hệ thống sau khi người dùng nhập khóa: **128/128 tests đạt**, 206.599s,
database test riêng. Trong đó 5 regression tests kiểm tra thiếu từng khóa/chuỗi
trắng, CSRF, thành công với amount backend [số tiền ẩn danh], chống giả amount frontend,
tái sử dụng order và lỗi API vẫn giữ reservation TESTSPA10, không tính đã dùng.
Các tests cũ về đồng thời, webhook lặp/đến muộn và thanh toán tại Spa cũng đạt.

Trình duyệt localhost:8001 / test_annhien_spa (SDK bị chặn, create/get/cancel mock):

- Thiếu cấu hình: POST online 400, hiển thị đúng lỗi; không có lỗi JS Console.
- Lỗi API: nút disabled và nhãn đang xử lý; HTTP 400 hiện thông báo giữ giao dịch
  để thử lại an toàn; không chuyển paid.
- Thành công mock: POST 200, hiển thị liên kết checkout giả lập example.invalid
  (không mở), tổng [số tiền ẩn danh], unpaid. Sau F5 vẫn giữ phiên và TESTSPA10.
- Desktop 1440px và mobile 390px: bố cục giữ nguyên, thông báo và liên kết đọc được,
  không tràn ngang. Ảnh trong payos-feedback-ui; đây là fixture, không phải HD-C.
- Có request favicon.ico 404 sẵn có, không ảnh hưởng thanh toán; không có lỗi
  JavaScript Console ở các lượt kiểm tra.

Đã dừng server mock và dọn fixture trong database test. Audit cuối lúc 21:12 xác
nhận tám bảng nghiệp vụ không đổi, HD-C vẫn chưa có Payment, tổng [số tiền ẩn danh] VND.
Không có gọi API payOS thật, giao dịch tiền thật, ngrok, commit hoặc push.

Kết luận: sẵn sàng bước thử **tạo link/QR thật có kiểm soát sau khi được đồng ý**;
chưa xác minh khóa hợp lệ, kết nối nhà cung cấp hay webhook thật. Không kết luận
toàn bộ thanh toán production đã hoàn tất.

## Điều kiện thử QR thật

Sau khi hoàn tất kiểm thử mock và được người dùng đồng ý, có thể thử tạo link
trên hóa đơn đủ điều kiện. Cần phân biệt tạo link với nhận tiền: hóa đơn chỉ paid
khi backend xác minh kết quả hợp lệ. Checkout dẫn tới QR của payOS; không tự
mở link thanh toán trong lượt chẩn đoán. Cần nghiệm thu kết nối và webhook công
khai riêng trước khi kết luận thanh toán thật hoàn chỉnh. Không mở ngrok hoặc
thực hiện giao dịch tiền thật trong lượt này.
