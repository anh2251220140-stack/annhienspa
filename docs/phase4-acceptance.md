# Biên bản nghiệm thu Giai đoạn 4 — bản công khai đã ẩn danh

Ngày cập nhật hồ sơ: **27/10/2026**. Nguồn: kết quả nghiệm thu thủ công do chủ dự
án xác nhận và lượt rà soát chỉ đọc gần nhất. Lượt lập hồ sơ này không chạy lại
tests, không gọi API thanh toán và không sửa dữ liệu.

## Kết luận cuối cùng

- Người dùng xác nhận đã chuyển khoản thật, ngân hàng và payOS ghi nhận thành
  công; User/Admin cùng hiển thị hóa đơn đã thanh toán.
- Rà soát MySQL xác nhận một hóa đơn cho lịch nghiệm thu, đúng **một Payment
  thành công**, số tiền khớp tổng sau ưu đãi. Hai phiên cũ hủy/hết hạn không được
  cộng doanh thu. Lịch hẹn hiện đã hoàn thành; thanh toán không tự hoàn thành lịch.
- Khuyến mãi TESTSPA10: giới hạn hiệu lực một lần/khách, **used=1, reserved=0**
  đối với trường hợp nghiệm thu; không ghi thêm lượt khi nhận webhook lặp.
- QR nhúng từ qrCode provider đã lưu; phiên mới tối đa 600 giây và không vượt
  giờ hẹn. F5 giữ phiên/thời hạn; hết hạn ẩn QR, không tự paid hoặc trả lượt.
- Chủ dự án xác nhận đã cấu hình webhook qua ngrok và kiểm thử từ chối webhook
  giả. Rà soát source/tests xác nhận chữ ký, số tiền, tiền tệ và liên kết giao
  dịch được kiểm tra; webhook muộn/bất thường được đưa sang đối soát.
- Lần hồi quy gần nhất sau cấu hình cuối: **134/134 tests đạt**, **370.059 giây**,
  database test riêng, thanh toán dùng mock. Đây không phải kết quả chạy mới
  trong lượt biên tập tài liệu.
- Django check không lỗi; không migration mới/chờ áp dụng. DEBUG=False,
  WhiteNoise 6.12.0; 59/59 static assets khớp source và được phục vụ thành công.
- Nhánh main trên GitHub đã được đối chiếu trực tiếp ở commit **1552cca**.
  Các tài liệu chưa commit và .env.example không được coi là đã nằm trong commit này.

**Đạt nghiệm thu nghiệp vụ Giai đoạn 4 ở phạm vi đồ án và giao dịch thực tế đã
đối chiếu. Chưa kết luận sẵn sàng vận hành production lâu dài.**

## Các mốc lịch sử

| Mốc | Bằng chứng và phạm vi |
|---|---|
| Triển khai nền Giai đoạn 4 | 84 tests; thanh toán mock, tạo hóa đơn/đánh giá/báo cáo. |
| 23/10/2026 | 99 rồi 105 tests; giao diện hóa đơn và chẩn đoán mã khuyến mãi. |
| 24/10/2026 | 123 tests cho giới hạn lượt; 128 cho phản hồi payOS; 134 cho QR và thời hạn. Các lượt phát triển này chỉ mock. |
| Sau các lượt phát triển | Chủ dự án thực hiện giao dịch thật và cấu hình webhook; không phải hành động của các script kiểm thử. |
| Rà soát ngày 27/10/2026 | Xác nhận kết quả MySQL, main 1552cca và chạy lại 134 tests sau cấu hình cuối. |

Không dùng các nhận định lịch sử “chưa thanh toán/chưa cấu hình/chỉ mock” làm
kết luận hiện tại. Trạng thái hủy của phiên cũ và thành công của phiên sau có thể
cùng tồn tại; chỉ Payment thành công hợp lệ được tính tiền và lượt sử dụng.

## Các giới hạn chưa khắc phục

1. **Cao nếu vận hành lâu dài:** development server/ngrok chưa thay thế máy chủ
   ứng dụng production và địa chỉ HTTPS/webhook ổn định.
2. **Trung bình:** mô phỏng HTTPS qua proxy vào Django HTTP trả CSRF 403 dù token
   hợp lệ; cần xử lý nhận diện HTTPS/origin tin cậy, không tắt CSRF.
3. **Trung bình:** return/cancel URL còn localhost; cần URL đúng môi trường để
   khách trên thiết bị khác quay lại được website.
4. **Trung bình:** check --deploy còn W004 (HSTS), W008 (HTTPS redirect). Cần xử
   lý theo kiến trúc proxy, tránh bật thiếu kiểm chứng gây vòng lặp.
5. **Trung bình:** chưa có giao diện xử lý đối soát/hoàn tiền; khoản chưa xác định
   cần quy trình thủ công. PAID từ truy vấn trạng thái không tự thay webhook.
6. **Thấp:** static chưa dùng manifest/compression; hiện phục vụ đúng.

Các giới hạn này được ghi nhận, **chưa sửa** trong lượt rà soát hoặc biên tập hồ sơ.

## Bảo mật và phạm vi công bố

Không công bố định danh khách hàng, thông tin liên hệ, tài khoản ngân hàng, số
tiền giao dịch thật, mã giao dịch, orderCode, link thanh toán, payload QR, URL
ngrok hiện hành hoặc giá trị bí mật. Mã đối chiếu thật và chứng từ giữ cục bộ.

Rà soát gần nhất không tìm thấy các giá trị bí mật hiện tại trong source/index/
lịch sử Git; .env không được theo dõi. Bảy dòng override_settings nghi vấn là
khóa mock. Kết quả quét giá trị hiện tại không chứng minh mọi bí mật cũ đều vắng mặt.

## Hồ sơ và bước tiếp theo

- [Tổng hợp triển khai và lịch sử](phase4.md)
- [Giao diện hóa đơn](invoice-flow.md)
- [Chẩn đoán khuyến mãi](promotion-diagnostics.md), [Giới hạn lượt](promotion-usage.md)
- [Phản hồi nút payOS](payos-feedback.md), [QR và thời hạn](payos-qr.md)
- [Danh sách công bố chính xác](phase4-publication.md)

Chủ dự án kiểm tra gói tài liệu, tự chọn git add/commit/push. Sau đó tiếp nhận
nguyên văn 5 góp ý giảng viên và đối chiếu SRS/HLD/ERD 21 bảng với code/migrations
hiện có; không đổi schema chỉ để khớp một số lượng bảng trước khi đối chiếu.
