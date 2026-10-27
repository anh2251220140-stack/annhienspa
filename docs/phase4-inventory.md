# Kiểm kê Giai đoạn 4 trước triển khai

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

| Figma | Django/MySQL đã có | Phần cần nối |
|---|---|---|
| Invoice User: dịch vụ, lịch, tiền, ưu đãi, trạng thái, phương thức, QR | Invoice/InvoiceDetail/Payment, constraints tiền và OneToOne lịch | Tạo snapshot lúc xác nhận; API theo chủ sở hữu; bỏ QR/mô phỏng demo |
| Admin invoices/payments: thống kê, tìm kiếm/ngày/trạng thái, bảng, phân trang, modal chi tiết & giao dịch liên quan | Models; chưa có API | ORM danh sách, chi tiết, thu trực tiếp, payOS |
| User reviews: chọn lịch, sao, nội dung, sửa, phản hồi | Review OneToOne, rating1–5, comment2000, ReviewReply phẳng | Chặn lịch chưa hoàn thành, ownership, CRUD không xóa |
| Admin reviews: bộ lọc sao/dịch vụ/tìm kiếm, modal, phản hồi | Chưa nối backend | ORM và danh tính phiên thật |
| Dashboard: 4 KPI, biểu đồ tháng/trạng thái/dịch vụ, lịch gần đây | App dashboard trống | Thống kê ngày thanh toán và ngày hẹn tách biệt |
| Reports: khoảng ngày, biểu đồ, bảng, bộ lọc | JS demo | Thống kê và trạng thái rỗng từ ORM |

Tái sử dụng 19 bảng; chỉ bổ sung metadata giao dịch, người thu và snapshot mã ưu đãi. Sản phẩm không bán. Không sinh dữ liệu demo trong annhien_spa. Không mở ngrok (đã tìm thấy executable WindowsApps). Không gọi payOS thật hoặc đăng ký webhook trong lượt code. SRS: hóa đơn khi confirmed; online chỉ trước giờ hẹn; webhook là nguồn xác nhận online; review chỉ completed. Phản hồi User trên đánh giá của mình và Admin; chưa mở diễn đàn công khai thông tin khách.
