# QR payOS trực tiếp và thời hạn — 24/10/2026

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

## Thiết kế và dữ liệu

Đọc yêu cầu đính kèm và source billing/models, services, gateway, views, frontend.
Payment đã có qr_code, expires_at, order_code, amount, payment_link_id và checkout_url;
không cần migration. Không đổi bảng hoặc dữ liệu thật.

Backend giữ nguyên qrCode mà payOS trả về sau khi kiểm tra orderCode và amount
khớp Payment. Thư viện qrcode==8.2 render chính payload lưu trong MySQL thành PNG
đen/trắng, quiet zone 4 module, không logo/ảnh trang trí. Không ghép tài khoản,
nội dung, số tiền; không gọi dịch vụ QR ngoài. Kiểm tra định dạng đầu EMV và CRC
để tránh hiển thị dữ liệu thiếu/hỏng. Thư viện: https://pypi.org/project/qrcode/8.2/.

Ảnh chỉ được trả qua API hóa đơn đã kiểm tra quyền chủ sở hữu/Admin. Không ghi
ảnh vào thư mục public. QR/checkout không được trả khi giao dịch hủy, cần đối soát,
đã nhận tiền/đang xử lý, sai amount, quá hạn hoặc hóa đơn không còn đủ điều kiện.
Thiếu payload hợp lệ: giữ checkout hiện có nếu phiên còn hợp lệ và báo rõ lý do.

## Thời gian và đối soát

Chỉ Payment mới đặt expires_at = min(now + 600 giây, giờ bắt đầu lịch hẹn).
Giữ quy tắc không online sau giờ hẹn; không gia hạn hoặc sửa phiên cũ. Adapter gửi
expired_at là Unix timestamp của đúng giá trị đã lưu cho SDK payOS.

API trả serverNow/remainingSeconds/expiresAt. Frontend trừ thời gian request một
cách bảo thủ, dùng performance.now thay vì đồng hồ ngày giờ của thiết bị. Khi F5
lấy số giây còn lại từ MySQL; không tạo phiên mới. Đồng hồ hiển thị mm:ss, 00:00
ẩn QR/checkout và khóa tạo phiên, yêu cầu kiểm tra trạng thái cũ. Không tự paid,
cancel hoặc trả lượt. Đồng hồ giao diện chỉ là chỉ dẫn; backend vẫn kiểm tra hạn.

Polling và sự kiện focus/hiện tab chỉ GET dữ liệu MySQL, không tự gọi payOS.
Nút Kiểm tra trạng thái phiên gọi đối soát provider theo yêu cầu rõ ràng. Nếu
provider chưa xác minh đóng phiên, không tự sinh order khác. Đổi khuyến mãi giữ
luồng xác minh/đóng phiên an toàn cũ. TESTSPA10 unpaid giữ lượt, paid mới dùng lượt;
webhook lặp/muộn và nhánh cần đối soát giữ logic đã có.

## Dữ liệu HD-C

Tại lần đọc đầu của lượt này, Payment đã có status cancelled/provider CANCELLED;
hóa đơn vẫn unpaid [số tiền ẩn danh] VND. Đây khác với mô tả phiên đang chờ trong yêu cầu;
không tự suy ra ai/thao tác nào đã hủy. Không sửa, hủy, khôi phục hay tạo lại phiên.
Không hiển thị QR đã hủy. Audit fingerprint được lấy làm mốc đầu/cuối lượt này.

## Files

- billing/qr.py, billing/views.py: render ảnh từ payload và lọc phiên hợp lệ.
- billing/services.py: hạn phiên mới 600 giây (giới hạn bởi giờ hẹn).
- requirements.txt: qrcode==8.2.
- templates/pages/invoice.html, static/css/phase4.css: ảnh QR, đồng hồ, fallback.
- static/js/live-invoice.js, static/js/phase4-api.js: đồng hồ theo backend, GET
  polling, đối soát chủ động, bảo vệ khi hết hạn và phục hồi tab.
- billing/test_qr.py: regression tests QR/hạn/quyền/không mutation.
- tools/audit_payos_button.py: chỉ báo QR/checkout có hay không và thời hạn.

## Kết quả thực thi

- 11/11 tests QR + phản hồi payOS qua; toàn hệ thống **134/134 tests đạt**,
  164.932 giây, log `payos-qr-tests.txt`. Các tests cũ chống đồng thời, webhook
  lặp/muộn, cash, giữ/trả lượt TESTSPA10 tiếp tục đạt.
- Django check 0 issues; makemigrations --check --dry-run không thay đổi;
  migrate --check exit 0; py_compile và git diff --check qua.
- Browser test database riêng: QR hiện, timer 10:00 giảm; F5 cùng payload ảnh,
  09:47 vẫn 09:47. Desktop 1440 và mobile 390 không tràn ngang; ảnh tải thành
  công và Console không có lỗi JS trong các lượt kiểm tra.
- Mô phỏng hết hạn: 00:00, QR và checkout ẩn, nút tạo mới disabled; thiếu QR
  khi phiên còn hạn: thông báo cụ thể và checkout dự phòng còn hiện.
- Log preview chỉ có POST online do click; các lần polling/F5 đều GET MySQL,
  không có POST refresh-online tự động. SDK bị chặn và provider create/get/cancel mock.
- Ảnh trong `payos-qr-ui/` là fixture được ghi rõ KIỂM THỬ MOCK, payload tổng hợp
  không có tài khoản ngân hàng thật. Không dùng làm QR dự phòng trong ứng dụng.
- Đã dừng server preview, dọn fixture database test. Audit cuối 21:40:42 xác
  nhận fingerprint 8 bảng nghiệp vụ không đổi trong lượt; HD-C giữ phiên cũ
  cancelled, có QR lưu, expiry cũ không sửa, unpaid [số tiền ẩn danh] VND.

Chưa thử quét QR mới bằng ứng dụng ngân hàng hoặc tạo phiên thật với hạn mới;
chưa xác minh webhook Internet. Những phần này chỉ làm sau khi được cho phép.
Không có API payOS thật, chuyển tiền, ngrok, commit/push trong lượt này.

## Nghiệm thu thủ công sau khi được phép

Không cần bấm tạo phiên trên HD-C để xem dữ liệu cũ. Nếu phiên đã hủy thì không
hiện QR là đúng. Sau khi cho phép tạo phiên thật mới: chọn hóa đơn đủ điều kiện,
bấm online, kiểm tra QR/tổng tiền, F5 và so sánh thời gian tiếp tục giảm. Khi hết
hạn, QR phải biến mất; chỉ bấm đối soát khi muốn gọi payOS. Không thử chuyển tiền
chỉ để kiểm tra giao diện. Nhánh nhận tiền/webhook thật cần nghiệm thu riêng.
