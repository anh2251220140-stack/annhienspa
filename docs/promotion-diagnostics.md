# TESTSPA10 không xuất hiện trên HD-B — 23/10/2026

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

**Cập nhật 24/10/2026:** báo cáo này lưu nguyên nhân và kết quả của lần chẩn đoán trước. Cơ chế giới hạn lượt tự động đã được bổ sung theo yêu cầu mới; xem [promotion-usage.md](promotion-usage.md) để biết hành vi hiện tại.

## Kết luận từ MySQL thật

Đã đối chiếu source hiện có, quy tắc hóa đơn/khuyến mãi trong `docs/srs-extracted.txt` (bản trích SRS/HLD), các bảng `promotions`, `promotion_services`, `invoices`, lịch hẹn và thanh toán. Không sửa dữ liệu nghiệp vụ.

- Database: `annhien_spa`; mã TESTSPA10, ID 1. Hoạt động, hiệu lực 20–31/10/2026; giảm 10%, tối thiểu 0 đồng, tối đa [số tiền ẩn danh] đồng.
- Liên kết đúng dịch vụ ID 1, Massage đá nóng thư giãn toàn thân. Dịch vụ và danh mục đều đang hoạt động.
- HD-B thuộc LH-C và [khách hàng ẩn danh], lịch [ngày/giờ hẹn đã ẩn danh], đã xác nhận; subtotal/total [số tiền ẩn danh] đồng, discount 0, unpaid, chưa chọn phương thức, không có giao dịch.
- Không có hóa đơn nào hiện gắn TESTSPA10. Model hiện không có cấu hình giới hạn tổng lượt hoặc số lượt/khách; không có bộ đếm để loại mã vì hết lượt.
- `conditions` có nội dung **Áp dụng cho dịch vụ được chọn**. `promotions.services.evaluate_code` coi mọi nội dung không rỗng trong trường này là điều kiện văn bản cần kiểm tra thủ công: `eligible=False`, `requiresManualReview=True`, không trả số tiền giảm. Đây là nguyên nhân thực tế bị loại, dù nội dung trùng với phạm vi dịch vụ đã liên kết.
- `note` là **Mỗi khách hàng chỉ sử dụng mã một lần. Không áp dụng đồng thời với chương trình khác.** Giới hạn mỗi khách một lần chưa được backend thực thi. Hóa đơn chỉ lưu một mã, nhưng hệ thống chưa đánh giá những chương trình ngoài cấu trúc đó. Không được hiểu các câu văn này là quy tắc đã được tự động xác minh.
- Lần kiểm tra trước giờ hẹn không bị chặn bởi giờ hẹn hay trạng thái lịch. Sau giờ bắt đầu, quy tắc hiện có chặn tạo phiên payOS mới; đây không phải nguyên nhân loại mã được ghi nhận.

Trước sửa, API danh sách lặng lẽ bỏ mã bị loại và JS chỉ báo “Hiện chưa có khuyến mãi phù hợp”. Nhãn “Đang hiệu lực” trên catalog thể hiện trạng thái/ngày, không bảo đảm đủ mọi điều kiện áp vào một hóa đơn.

## Sửa code

- `billing/services.py`: thêm `promotion_choices`, trả `items`, `unavailable` (mã/lý do), `message` khi hóa đơn/lịch/phương thức đang khóa sửa ưu đãi. Giữ nguyên kiểm tra điều kiện văn bản; không tự suy diễn câu văn thành quy tắc máy.
- `billing/views.py`: endpoint `/api/billing/<id>/promotions/` trả lý do trên, giữ giới hạn quyền theo chủ hóa đơn/Admin.
- `static/js/live-invoice.js`: hiển thị lý do ngay dưới dropdown bằng `textContent`, tránh chèn HTML; xóa thông báo cũ khi đổi hóa đơn. Bổ sung thông báo lịch chưa xác nhận/đã hủy khi không được thanh toán.
- `billing/test_promotion_diagnostics.py`: thêm 6 regression tests, không thêm model/migration/dependency.

API thật của HD-B sau sửa vẫn trả `items: []`, kèm TESTSPA10 với lý do cần Spa kiểm tra và đúng nội dung điều kiện. Không tự áp mã hoặc thay đổi hóa đơn thật.

## Admin xử lý cấu hình qua giao diện

1. Đăng nhập Admin → Quản lý khuyến mãi → chọn TESTSPA10 → Sửa → nhóm **Nội dung & điều kiện**.
2. Kiểm tra **Điều kiện áp dụng — mỗi dòng một điều kiện** và **Lưu ý**, cùng nhóm **Phạm vi dịch vụ áp dụng**.
3. Nếu chương trình thực sự chỉ giới hạn bằng dịch vụ, thời hạn, giá tối thiểu và mức giảm đã cấu hình, Admin có thể chuyển câu “Áp dụng cho dịch vụ được chọn” sang **Ghi chú phạm vi áp dụng**, để trống **Điều kiện áp dụng**, giữ dịch vụ được chọn rồi lưu. Phải rà soát và thống nhất lại lời hứa “mỗi khách một lần” trước khi bật áp mã tự động; không chỉ xóa trường điều kiện để bỏ qua chính sách này.
4. Nếu muốn giữ giới hạn mỗi khách một lần hoặc điều kiện cần xét duyệt, giữ nguyên cấu hình. Cần bổ sung quy tắc giới hạn lượt có kiểm tra backend và đồng thời trước khi tự động áp mã. Hiện chưa có thao tác Admin phê duyệt riêng cho điều kiện văn bản; không tuyên bố luồng đó đã triển khai.
5. User mở HD-B và Ctrl+F5 để thấy lý do. Khi một mã đã đủ điều kiện tự động và hóa đơn chưa bị khóa, chọn mã → Áp dụng → kiểm tra tổng; Xóa mã trả lại giá gốc. Nếu đã chọn phương thức, dùng Đổi khuyến mãi để đóng phiên cũ an toàn.

Không thực hiện bước chỉnh cấu hình nào trên database thật trong lượt này.

## Kiểm thử và bảo toàn dữ liệu

- Backup trước sửa: `backups/phase4-20261023-152503` gồm source ZIP, MySQL dump và SHA-256; script xác minh thành công.
- `manage.py test --noinput --keepdb`: **105/105 đạt**, 130,559 giây, database riêng `test_annhien_spa`; gồm 6 tests mới. Log: `promotion-diagnostics-tests.txt`.
- Tests mới: điều kiện văn bản bị chặn và có lý do sau tải lại; giá snapshot [số tiền ẩn danh], giảm [số tiền ẩn danh], tổng [số tiền ẩn danh]; áp/xóa và đọc lại MySQL; tối thiểu/ngày/trạng thái hoạt động/phạm vi; lịch pending; yêu cầu đổi phương thức rõ ràng; hóa đơn paid không được sửa; User khác/khách không được đọc hoặc sửa.
- `manage.py check`, `makemigrations --check --dry-run`, `migrate --check`, `git diff --check`: đạt; không có migration mới hay migration chờ.
- Trình duyệt thật: desktop 1440×1000, mobile 390×844. Dữ liệu test mô phỏng điều kiện TESTSPA10 hiển thị đúng lý do sau reload. Bản ghi chỉ trong test được bỏ điều kiện/lưu ý để nghiệm thu nhánh hợp lệ: dropdown có mã; áp giảm [số tiền ẩn danh]/tổng [số tiền ẩn danh]; F5 giữ kết quả; xóa mã và F5 về [số tiền ẩn danh]. Không thấy lỗi console; không tràn ngang mobile. Ảnh: `promotion-diagnostics-ui/` (ID HD-TEST/LH-TEST trong ảnh là dữ liệu test, không phải HD-B thật).
- Đã đóng preview 8001, dọn fixture chỉ trong `test_annhien_spa`, giữ server 8000. Không gọi payOS thật; preview chặn mọi create/get/cancel bên ngoài.
- Chẩn đoán production gọi view trực tiếp bằng RequestFactory, không tạo session đăng nhập production; SQL được chặn thao tác ghi. Đối chiếu tất cả bảng với dump trước sửa: **không thay đổi**. Bằng chứng: `promotion-diagnostics-data.json` (không có mật khẩu/khóa).
- Không sửa `.env`, SMTP, tài khoản, lịch, hóa đơn, khuyến mãi thật. Không reset database/migrations, không commit/push.

Giới hạn còn lại: TESTSPA10 thật vẫn cần Admin quyết định cấu hình/chính sách như trên; chưa triển khai giới hạn mỗi khách một lượt hoặc quy trình duyệt điều kiện văn bản.
