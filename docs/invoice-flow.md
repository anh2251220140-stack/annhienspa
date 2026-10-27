# Bổ sung giao diện lịch hẹn – hóa đơn – khuyến mãi – thanh toán

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

Ngày 23/10/2026. Tiếp tục Giai đoạn 4, đối chiếu SRS/HLD (`docs/srs-extracted.txt`), `docs/phase4.md` và HTML/CSS/JS Figma gốc. Không sửa 27 HTML gốc, font/ảnh hoặc reset database. Không thay SMTP, tài khoản, khóa bí mật; không commit/push.

## Giao diện

- Lịch hẹn: Xem hóa đơn và Hủy lịch hẹn nằm trong cùng `.journey-actions`; nút chính nền chocolate/ivory, nút hủy kiểu phụ. Mobile giữ nhóm nút linh hoạt, không làm tràn thẻ. Hiển thị link theo `invoiceId` thật; trạng thái hẹn không thay thế quan hệ hóa đơn.
- Hóa đơn: tìm kiếm/trạng thái/Lọc cùng chiều cao; dropdown chọn hóa đơn và phân trang được căn chỉnh gọn. Tìm theo mã HD/LH hoặc dịch vụ, lọc và phân trang qua ORM. URL giữ ID hóa đơn đang chọn để F5 mở lại đúng hóa đơn.
- Dropdown khuyến mãi lấy danh sách hợp lệ từ backend, không nhập mã bắt buộc. Lọc theo hoạt động, thời hạn, dịch vụ, giá snapshot, giá trị tối thiểu và mức giảm tối đa. Điều kiện văn bản cần duyệt thủ công không được tự suy diễn và không đưa vào danh sách tự áp dụng.
- Trước chọn thanh toán: Áp dụng/Xóa mã; sau chọn payOS hoặc tại Spa: dropdown khóa và hiện Đổi khuyến mãi. Hóa đơn paid/cancelled/cần đối soát khóa thay đổi.
- Khu payOS giữ thẻ Figma và hiển thị số tiền + checkout do SDK trả về; không dựng QR giả. Bỏ nút Cập nhật trạng thái/Đóng phiên khỏi User. Đổi khuyến mãi là luồng đóng phiên đúng nghiệp vụ.
- Tự kiểm tra trạng thái mỗi 10 giây khi có lựa chọn thanh toán chưa trả và tab đang hiển thị; cập nhật khi trở lại tab. Với online, backend dùng SDK xác minh trạng thái; SPA chỉ đọc hóa đơn. Không nhận cờ paid từ frontend. Phiên không xác định được trạng thái không được tự mở khóa.

## Luồng backend và an toàn

1. Áp dụng/xóa mã chỉ khi hóa đơn unpaid, lịch confirmed/completed, chưa có khoản thành công/cần đối soát và đang ở bước chỉnh ưu đãi. Tiền dùng Decimal trên giá snapshot. Xóa mã xóa FK/mã snapshot, giảm về 0 và tổng về subtotal; lưu MySQL.
2. Chọn tại Spa lưu `Invoice.payment_preference=spa`, không tạo Payment thành công. Admin vẫn phải nhập số tiền khớp và ghi nhận đã thu. Chọn payOS lưu preference online và giữ reservation/order trước gọi API; yêu cầu lặp tái dùng order đang chờ.
3. Đổi khuyến mãi/chuyển sang tại Spa/thu trực tiếp: khóa Appointment → Invoice → Payment; GET trạng thái payOS bằng SDK, đối chiếu order/amount/link ID. Nếu PENDING và chưa nhận tiền, gọi API cancel và kiểm tra lại phản hồi đã đóng, chưa nhận tiền. CANCELLED/EXPIRED/FAILED chưa nhận tiền được coi là terminal. PAID/PROCESSING/UNDERPAID, trạng thái lạ, mismatch, timeout hoặc phản hồi hủy không đóng đều chặn.
4. Chỉ sau xác nhận đóng phiên, lưu Payment cancelled và mở lại phần ưu đãi (hoặc chuyển SPA). Không sửa giá khi link cũ còn hoạt động. Hủy bên nhà cung cấp là tác động bên ngoài transaction: nếu giao dịch DB rollback sau đó, lần thử lại sẽ GET trạng thái đã đóng trước khi tiếp tục; không giả lập đã hủy.
5. Sau đổi mã, phiên cũ không được hiển thị lại; nhấn payOS mới tạo order mới theo tổng hiện tại. Thanh toán không tự hoàn thành lịch.
6. Webhook vẫn phải được ký hợp lệ. Webhook của order đã đóng hoặc sai phiên tiền hiện tại được lưu trạng thái `review`/cờ đối soát, không ghi nhận paid cho hóa đơn mới hoặc tăng doanh thu. Khi cần đối soát, chặn thu thêm/đổi mã/tạo link. Webhook lặp không tạo bản ghi mới. Nếu có tiền thực tế đến muộn, không thể bảo đảm ngân hàng không nhận hai khoản; hệ thống lưu dấu vết và không ghi nhận hai giao dịch `success` hợp lệ hoặc tự hoàn tiền.

## HD-A và LH-B

Đã đọc trực tiếp MySQL trước sửa: [khóa bản ghi đã ẩn danh], unpaid, giá snapshot [số tiền ẩn danh] VND; liên kết lịch [ngày/giờ hẹn đã ẩn danh], [chuyên viên ẩn danh], Massage đá nóng thư giãn toàn thân. Dropdown hiển thị HD-A; Cuộc hẹn hiển thị LH-B. Không đổi khóa chính.

Từ giờ bắt đầu lịch đã đối chiếu trở đi, LH-B không còn được tạo phiên online mới theo SRS. Kiểm thử nhánh online dùng lịch tương lai trong database test, không sửa ngày lịch thật để ép điều kiện.

## Migrations và bảo toàn

- Backup mới đã xác minh trước sửa: `backups/phase4-20261023-144610` (source/dump/manifest).
- `billing/0004_invoice_payment_preference.py`: thêm lựa chọn chưa chọn/online/spa để duy trì giao diện sau F5; không thêm bảng nghiệp vụ.
- `billing/0005_remove_payment_payment_valid_status_and_more.py`: thêm trạng thái Payment review và mở rộng check constraint tương ứng; không sửa/xóa giao dịch hiện có.
- So sánh 26 bảng trên các cột cũ với backup mới; kết quả tại `docs/invoice-flow-data-verification.json`. Không tạo fixture/giao dịch thử trong annhien_spa.

## File chỉnh sửa

- `billing/models.py`, `services.py`, `views.py`, `urls.py`; migrations 0004/0005.
- `static/js/live-booking.js`, `live-invoice.js`, `admin-finance.js`; `static/css/phase4.css`.
- `templates/pages/appointments.html`, `invoice.html`, thêm trạng thái đối soát trong `admin-payments.html`.
- `billing/test_phase4.py` bổ sung mock GET/cancel đầy đủ theo SDK và phân loại đối soát; `billing/test_invoice_flow.py` gồm 15 tests mới, kể cả cạnh tranh đồng thời.
- Tài liệu này, báo cáo tests và ảnh bằng chứng bổ sung.

## Kiểm thử

Nhóm billing: 35/35 đạt trước kiểm tra trình duyệt. Bộ kiểm thử toàn hệ thống **99/99 đạt**, chạy thực tế 118,150 giây; log `docs/invoice-flow-full-tests.txt` (84 tests cũ + 15 mới). Tests mô phỏng create/get/cancel, ký webhook bằng SDK với khóa giả; không gọi payOS thật.

Bao phủ: dropdown điều kiện/snapshot, áp dụng/xóa/F5, SPA không tự paid, đổi QR cũ và tạo order mới đúng tiền, các trạng thái đang xử lý/đã nhận tiền/không xác định, timeout, provider mismatch, phản hồi hủy bị race, phiên expired, chuyển phương thức, webhook ký hợp lệ/lặp/đến muộn, chặn hai success, phân quyền, mapping HD/LH, tìm kiếm/lọc/phân trang; hai request tạo link đồng thời và đổi mã đua với webhook.

## Nghiệm thu

1. Mở Django cổng 8000, Ctrl+F5. Lịch pending không có link hóa đơn; confirmed/completed/cancelled có hóa đơn cũ thì vẫn được xem theo quyền. Xem hóa đơn và Hủy cùng hàng nếu đủ điều kiện hủy.
2. Tìm HD-A/LH-B, đổi trạng thái lọc và phân trang. Chọn hóa đơn rồi F5 phải giữ đúng ID/liên kết và số tiền đã lưu.
3. Chọn ưu đãi hợp lệ → Áp dụng → kiểm tra giảm/tổng → F5 → Xóa mã → về giá gốc. Nếu không có ưu đãi phù hợp trong MySQL, dropdown chỉ có Không áp dụng, không tự sinh mã mẫu.
4. Chọn tại Spa: còn unpaid, hiện hướng dẫn và Đổi khuyến mãi. Đổi mã/bỏ mã → Áp dụng → chọn tại Spa lại. Chỉ Admin ghi nhận đã thu; sau đó User không đổi mã hoặc phương thức.
5. Nhánh payOS: trong môi trường mock có lịch tương lai, chọn online → thấy số tiền/checkout → Đổi khuyến mãi → xác nhận provider cũ đã đóng → đổi/bỏ mã → chọn online lại → order/số tiền mới. Kiểm tra timeout/PAID/PROCESSING phải khóa, webhook đến muộn phải đối soát.

Chưa kiểm thử API/webhook payOS qua Internet hoặc chuyển tiền thật. Ba khóa của đúng kênh An Nhiên Spa vẫn do người dùng tự cấu hình trong `.env`; không gửi vào chat. Không mở ngrok hoặc thay webhook URL. Chỉ nghiệm thu kết nối thật ở bước riêng được người dùng cho phép.

## Kết quả trình duyệt thực tế

Preview cổng 8001 chỉ dùng test_annhien_spa; mọi hàm network payOS được mock. Checkout .invalid có nhãn MOCK, không chuyển tiền. Đã kiểm tra 1440×1000 và 390×844:

- Nút Xem hóa đơn/Hủy cùng tọa độ hàng, cao 40px; màu nút chính rgb(58,36,25), chữ ivory rgb(255,248,241). Pending không có link; cancelled/completed có hóa đơn vẫn có link.
- Input tìm kiếm, trạng thái và Lọc đều cao 46px và cùng đáy trên desktop. Mobile scrollWidth 375px, viewport 390px, không tràn ngang.
- Áp dụng LIVE10 → [số tiền ẩn danh] VND → F5 còn số tiền → Xóa mã → [số tiền ẩn danh] VND.
- Checkout mock [số tiền ẩn danh] → Đổi mã → link cũ bị ẩn sau backend xác nhận đóng → LIVE20 → checkout order khác [số tiền ẩn danh] → F5 vẫn đúng.
- Chuyển online sang tại Spa → F5 còn lựa chọn → Đổi mã, bỏ mã → giá gốc → chọn online lại.
- Hai phiên cookie tách theo localhost/127.0.0.1: Admin thu đúng tiền sau đóng online mock; User tự thấy paid sau chu kỳ kiểm tra, không F5 hoặc bấm cập nhật. Ưu đãi/phương thức khóa; F5 vẫn còn lịch sử thu tại Spa.
- Tìm HD, lọc unpaid, trạng thái rỗng và chọn lại đúng hóa đơn đã chạy qua UI. Phân trang nhiều bản ghi được kiểm tra bằng API test riêng.
- Không thấy lỗi JavaScript trong log tab kiểm tra. So sánh với cấu trúc/CSS Figma gốc; không có phiên Figma cloud để tuyên bố đối chiếu pixel tuyệt đối.

Ảnh trong `docs/invoice-flow-ui/`: appointments-desktop/mobile, invoice-online-desktop/mobile, invoice-spa-mobile, invoice-auto-paid-mobile. Các số tiền và mã trong ảnh là fixture database test.

Kết thúc: Django 8000 đang chạy (HTTP 200), server runserver hiện có dùng autoreload. Checks/migrations/diff qua, quét bí mật không phát hiện giá trị khóa trong source/tài liệu thay đổi. Dữ liệu test preview đã dọn riêng; không tạo giao dịch tại annhien_spa. Không commit/push.
