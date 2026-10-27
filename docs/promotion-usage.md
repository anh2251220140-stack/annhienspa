# Giới hạn lượt khuyến mãi theo khách hàng

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

Tiếp tục phần đã triển khai ngày 23/10, kiểm tra lại ngày 24/10/2026. SRS/HLD (bản trích `srs-extracted.txt`) mô tả bảng promotions/promotion_services, hóa đơn lưu giá và khuyến mãi lịch sử, thanh toán idempotent; không quy định cụ thể giữ lượt. Quy tắc giữ lượt bên dưới thực hiện theo yêu cầu bổ sung của người dùng.

## Quy tắc đã triển khai

- Mỗi hồ sơ Customer có giới hạn riêng cho mỗi Promotion; alias dùng chung Promotion nên không tạo thêm lượt. Admin áp mã cũng tính cho khách sở hữu hóa đơn, không tính cho tài khoản Admin.
- Hóa đơn unpaid có mã là một lượt **đang giữ**, kể cả chưa chọn phương thức, chọn tại Spa, phiên payOS hết hạn hoặc lỗi kết nối. Không tự trả lượt theo thời gian.
- Hóa đơn paid tính một lượt **đã sử dụng**. Đếm hóa đơn, không đếm số lần gọi API hoặc webhook. Hóa đơn đang giữ không tính đồng thời là lượt đã dùng.
- Tổng lượt đã dùng và đang giữ ở hóa đơn khác phải nhỏ hơn giới hạn mới được áp mã. Áp lại cùng hóa đơn không chiếm thêm lượt.
- Xóa/đổi mã chỉ được thực hiện khi không có thanh toán chờ, thành công hoặc cần đối soát. Nếu có phiên online, phải dùng Đổi khuyến mãi và xác minh phiên cũ đã đóng, chưa nhận tiền trước. Hủy lịch hợp lệ cũng phải đóng phiên cũ an toàn.
- Trạng thái payOS PAID/PROCESSING/UNDERPAID, đã nhận một phần tiền, trạng thái lạ hoặc lỗi mạng đều không cho đóng phiên và trả lượt. Kết quả đóng không rõ ràng cũng bị chặn.
- Webhook lặp không dùng thêm lượt. Webhook muộn của phiên đã đóng được lưu `review`, không tự trả hóa đơn về paid, không cộng doanh thu hoặc lượt đã dùng. Khi mã vẫn gắn với hóa đơn có giao dịch cần đối soát, lượt tiếp tục bị giữ. Nếu mã đã được xóa hợp lệ trước webhook muộn, khoản tiền cũ được đối soát riêng, không tự gắn mã lại hoặc chiếm lượt hóa đơn mới.
- Các trường hợp dữ liệu cũ có nhiều hóa đơn cùng giữ quá giới hạn bị chặn thanh toán; webhook tiền đến được đưa vào đối soát thay vì tự hoàn tất một lượt vượt giới hạn.
- Giao dịch áp mã khóa Appointment → Invoice → Promotion trong transaction MySQL. Khóa Promotion tuần tự hóa kiểm tra lượt giữa các hóa đơn. Cash, tạo phiên online và webhook thành công đều kiểm tra lại giới hạn dưới khóa. Không dùng JavaScript làm cơ chế chống trùng.

## Điều kiện tự động và điều kiện cần xem xét

Giữ nguyên kiểm tra dịch vụ liên kết/hoạt động, danh mục hoạt động, ngày hiệu lực, giá tối thiểu và mức giảm tối đa. Tính giảm trên subtotal lịch sử của hóa đơn. Điều kiện được kiểm tra khi áp lại mã; hóa đơn đã giữ giá hợp lệ vẫn có thể được thanh toán theo snapshot nếu chương trình hết hạn sau đó.

Chỉ ba câu sau được nhận diện chính xác (chuẩn hóa chữ hoa/thường, khoảng trắng, Unicode; phân tách dấu chấm/chấm phẩy/xuống dòng):

1. “Áp dụng cho dịch vụ được chọn”: kiểm tra bảng promotion_services và trạng thái dịch vụ.
2. “Mỗi khách hàng chỉ sử dụng mã một lần”: giới hạn hiệu lực bằng 1, kiểm tra cả lượt giữ và lượt đã sử dụng.
3. “Không áp dụng đồng thời với chương trình khác”: mỗi hóa đơn chỉ có một Promotion; thay mã thay thế ưu đãi cũ, không cộng dồn.

Câu khác trong **Điều kiện áp dụng** hoặc **Lưu ý** vẫn cần Spa xem xét, trả `requiresManualReview`, không áp mã tự động. Không dùng suy đoán ngôn ngữ hay AI để bỏ qua điều kiện. Chưa có nút Admin duyệt ngoại lệ rồi ép áp mã; điều kiện chưa hỗ trợ cần được xác minh và chuyển thành quy tắc rõ ràng ở bước sau.

## Schema, giao diện và bảo toàn dữ liệu

Migration `promotions.0003_promotion_per_customer_limit_and_more` chỉ thêm cột nullable `per_customer_limit` và ràng buộc >= 1 nếu có giá trị; không tạo bảng mới, không RunPython cập nhật dữ liệu. Migration đã áp dụng trong lượt trước; lượt tiếp tục xác nhận `[X]`, không áp lại/reset.

Admin có trường **Giới hạn lượt mỗi khách (tùy chọn)** trong form khuyến mãi và ghi chú giải thích. Để trống không vô hiệu hóa câu giới hạn một lần đang có trong nội dung; nếu cả số và câu đều có, dùng giới hạn chặt hơn. Catalog hiển thị giới hạn hiệu lực; hóa đơn User hiển thị rõ đang giữ lượt.

TESTSPA10 thật giữ nguyên `per_customer_limit=NULL`, conditions/note và các giá trị cũ. Nhờ ba câu đã được hỗ trợ, giới hạn hiệu lực là 1 mà không cần cập nhật bản ghi. Kiểm tra chỉ đọc HD-B trả TESTSPA10 trong danh sách: subtotal [số tiền ẩn danh], giảm dự kiến [số tiền ẩn danh], tổng dự kiến [số tiền ẩn danh] đồng. Không áp mã vào HD-B; tổng đang lưu vẫn [số tiền ẩn danh] đồng. Với ngày hẹn của HD-B đã đối chiếu, sau giờ hẹn không được tạo phiên payOS mới; thanh toán tại Spa vẫn theo quy tắc cũ.

Backup trước thay đổi: `backups/phase4-20261023-153703` đã được xác minh ở lượt trước. Công cụ `tools/audit_promotion_usage.py` chỉ cho SQL đọc, không tạo session production, lưu hash/count thay vì xuất dữ liệu tài khoản. Bằng chứng mới: `promotion-usage-audit.json`.

## File liên quan

- `promotions/models.py`, `services.py`, `views.py`, migration 0003: cấu hình, điều kiện, đếm lượt và khóa khi ghi.
- `billing/services.py`, `views.py`: áp mã, đối soát thanh toán và dữ liệu trạng thái lượt.
- `core/business_forms.py`, `business_layout.py`, `catalog_data.py`, `templates/partials/business_form.html`: Admin và catalog.
- `static/js/live-invoice.js`: thông báo giữ lượt, giữ bố cục hiện có.
- `billing/test_promotion_usage.py`: hồi quy nghiệp vụ và các cuộc gọi đồng thời. Tests cũ có điều chỉnh fixture để phân biệt nội dung chưa hỗ trợ với ba câu được hỗ trợ.

## Giới hạn còn lại

- Điều kiện văn bản ngoài ba câu trên không tự động được chấp nhận.
- Đối soát khoản tiền đến muộn/bất thường và các hóa đơn cũ vượt giới hạn cần Admin xử lý; chưa có luồng tự động hoàn tiền hoặc duyệt ngoại lệ.
- payOS chỉ kiểm thử mock/chữ ký thử, không xác minh giao dịch thực, không mở ngrok.

Không đổi dữ liệu thật, `.env`, mật khẩu hay SMTP; không commit/push.

## Nghiệm thu

Kết quả chạy lại 24/10/2026:

- `compileall` các module promotions/billing/core: không lỗi cú pháp. Không tìm thấy file ghi dở qua kiểm tra nội dung các hàm vừa sửa.
- `manage.py check`, `migrate --check`, `makemigrations --check --dry-run`: đạt, không có thay đổi model chưa tạo migration; `showmigrations promotions` xác nhận 0001–0003 đều `[X]`.
- Toàn bộ **123/123 tests đạt**, 395,435 giây, trên `test_annhien_spa`. Log `promotion-usage-full-tests.txt`; nhóm 39 tests ở lượt trước cũng đạt nhưng kết quả toàn hệ thống lần này đã được chạy mới.
- Trình duyệt ở preview 8001: TESTSPA10 xuất hiện; áp trên HD-TEST-A thử, giảm [số tiền ẩn danh], tổng [số tiền ẩn danh], F5 vẫn giữ mã và thông báo giữ lượt. HD-TEST-B thử bị loại mã với đúng lý do lượt ở hóa đơn khác, vẫn đúng sau F5. Xóa mã trên HD-TEST-A làm TESTSPA10 xuất hiện lại trên HD-TEST-B. Tất cả ID này thuộc database test, không phải hóa đơn thật.
- Kiểm tra desktop và mobile 390×844: không thấy lỗi console; mobile không tràn ngang (content 375, viewport 390). Ảnh ở `promotion-usage-ui/`: `reserved-desktop.jpg`, `blocked-mobile.jpg`, `released-desktop.jpg`.
- Đã dừng preview và dọn fixture chỉ trong database test. Audit HD-B thật trước/sau lưu trong `promotion-usage-audit.json`; không áp/xóa mã hoặc tạo giao dịch thật.

1. User mở HD-B, Ctrl+F5: TESTSPA10 xuất hiện nếu chưa có hóa đơn khác của khách giữ/dùng lượt và các điều kiện vẫn đạt. Chỉ chọn Áp dụng khi người dùng muốn thay đổi hóa đơn thật.
2. Sau áp mã, giảm [số tiền ẩn danh] và tổng [số tiền ẩn danh] đồng được lưu; thông báo cho biết mã đang giữ lượt. F5 không mất trạng thái.
3. Một hóa đơn đủ điều kiện khác của cùng khách sẽ giải thích lượt đang giữ và không cho áp mã qua cả UI lẫn API. Khách khác có giới hạn riêng.
4. Chỉ xóa mã/đổi khuyến mãi hoặc hủy lịch theo thao tác hợp lệ; nếu phiên payOS chưa rõ kết quả, phải giữ nguyên và chờ đối soát.
5. Sau khi Admin thực sự nhận tiền và xác nhận thanh toán tại Spa, lượt chuyển sang đã dùng; hóa đơn khác không dùng lại. Không dùng thao tác thu tiền thật để tạo dữ liệu thử.
6. Với tình huống cần ghi dữ liệu hoặc thử đồng thời, dùng bộ tests và database test riêng. Không nhập khóa payOS vào chat và không gọi thanh toán thật để nghiệm thu nhánh mock.
