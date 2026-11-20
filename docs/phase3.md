# Giai đoạn 3 — tiến độ và kiểm chứng

Cập nhật ngày 20/10/2026. Tiếp tục source hiện có, không khởi tạo lại dự án.

## Tài liệu và bảo toàn dữ liệu

- Đã đọc SRS/HLD DOCX và bản trích `srs-extracted.txt`, ERD, yêu cầu bổ sung trong file Pasted text và frontend gốc.
- Bảng kiểm kê từng trường trước khi bổ sung: `phase3-figma-inventory.md`.
- Hai bản sao lưu trước triển khai tại `backups/phase3-20261019-130524/` và `backups/phase3-figma-20261019-211805/`. Đã kiểm tra ZIP CRC, SQL hoàn tất và checksum; chưa thử phục hồi trên máy khác. Không chứa `.env`; không công bố file SQL.
- Bốn migrations bổ sung đã áp dụng. `phase3-migration-verification.json` ghi nhận dữ liệu/cột cũ của 26 bảng không đổi sau migration.
- Lượt rà soát 20/10 không ghi dữ liệu nghiệp vụ, không reset database/migration, không commit hoặc push. Fixture UI chỉ nằm trong `test_annhien_spa`, đã dừng server thử và dọn sau khi kiểm tra.

## Chức năng đã kết nối

| Nhóm | Kết quả |
|---|---|
| Dịch vụ, danh mục | Danh sách/thêm/sửa/xem/bật tắt; đầy đủ nội dung liệu trình, ảnh upload và ảnh có sẵn; accordion; không có checkbox trạng thái trong form |
| Sản phẩm | Nhóm thông tin sản phẩm/chăm sóc, textarea nhiều dòng, ảnh, dịch vụ liên kết; nhãn Danh mục nhất quán trong bộ lọc User |
| Nhân viên | Hồ sơ/liên hệ, email, chuyên môn nhiều dòng, dịch vụ checkbox từ MySQL; không tự sinh tài khoản hoặc ca làm |
| Khuyến mãi | Nội dung, điều kiện, ghi chú, nhãn/màu, mã thay thế, phạm vi, min/max; kiểm tra mã tại backend |
| Lịch làm việc | Lặp các thứ trong khoảng ngày, nhiều ca, nghỉ giữa ca, nghỉ theo khoảng, đổi ca một ngày; lưu lịch sử; chặn thay đổi ảnh hưởng lịch hẹn |
| Tài khoản | Danh sách, tìm/lọc/phân trang/thống kê, xem, khóa/mở User; bảo vệ Admin/superuser/staff/chính mình; tài khoản bị khóa không dùng được phiên cũ |
| Khách hàng | Chỉ Customer có tài khoản User và không phải superuser; bộ lọc áp dụng ở backend, kể cả URL chi tiết; Admin chỉ xem |
| Hồ sơ User | Lưu thông tin cá nhân/chăm sóc và ảnh thật; Admin xem được; không tự gán hạng thành viên |
| Đặt lịch | Bắt buộc chuyên viên; tính giờ theo ca/nghỉ/thời lượng; transaction và khóa dòng kiểm tra trùng nhân viên lẫn khách; xem lịch riêng |
| Admin lịch hẹn | Lọc ngày/trạng thái/nhân viên; Xem và Xử lý riêng; xác nhận giữ chuyên viên; đổi ngoại lệ cần đồng ý/lý do, kiểm tra chuyên môn/xung đột; lịch kết thúc không tùy tiện sửa |

Các file chính: `core/business_forms.py`, `core/business_layout.py`, `core/business_views.py`, `core/catalog_data.py`, `accounts/admin_views.py`, `accounts/profile_forms.py`, `employees/scheduling.py`, `employees/views.py`, `appointments/services.py`, `appointments/views.py`, `promotions/services.py`; các models/migrations tương ứng; `templates/partials/business_*.html`; `static/js/live-*.js`, `static/css/live-admin.css` và templates liên quan.

## Kiểm chứng thực tế ngày 20/10

- `manage.py check`: không lỗi.
- `makemigrations --check --dry-run`: không thay đổi model chưa có migration.
- `migrate --check`: không còn migration chờ áp dụng trên database cấu hình.
- Toàn bộ 57 tests đã đạt sau khi dọn fixture kiểm thử cũ. Log lần chạy cuối: `phase3-final-tests.txt`.
- Lượt đầu dùng `--keepdb` thất bại do fixture UI còn lưu từ lượt trước (trùng username, sai số đếm); không phải lỗi dữ liệu nghiệp vụ. Đã tách server thử và dọn đúng database thử trước khi chạy lại.
- Tests bao phủ CRUD, phân quyền, CSRF, ảnh, trường modal, tài khoản khóa/phiên, khách hàng loại Admin, profile, lịch làm/nghỉ, cảnh báo lịch bị ảnh hưởng, đặt lịch đồng thời, chuyển trạng thái và bất biến dữ liệu.
- Test render đủ 27/27 trang đúng vai trò, kiểm tra đường dẫn/static và checksum frontend gốc/CSS/ảnh.
- Trình duyệt: mở 27 trang; ảnh lưu `phase3-ui/`, tổng quan `phase3-admin-overview.png`, `phase3-user-overview.png`. Kiểm tra cả trạng thái rỗng/thiếu ID và truy cập chi tiết qua liên kết dịch vụ/sản phẩm/khuyến mãi có dữ liệu thử. Log tiêu đề và console: `phase3-browser-audit.json` (lượt đầu chi tiết không có ID hiển thị thông báo không tìm thấy đúng thiết kế).
- Khóa User, tải lại vẫn khóa, mở khóa và đăng nhập lại thành công. Admin không xuất hiện trong hai khách hàng thử.
- Đặt lịch 23/10/2026: ca 09–12 và 13–17, dịch vụ 60 phút. UI có 11:00/13:00, không có 11:01/12:00. Đặt 10–11 thành công, tải lại danh sách vẫn còn.
- Admin Xem chỉ đọc; Xử lý xác nhận thành công, giữ chuyên viên A sau tải lại. Nghỉ đúng ngày này bị chặn, hiển thị LH-96 và thời gian/khách liên quan. Ảnh `phase3-final-appointment.png`.
- Hồ sơ User: chọn Da khô và nhu cầu Thư giãn, lưu rồi tải lại vẫn được chọn.
- Kiểm tra booking tại chiều rộng 390px: form một cột, không tràn ngang; đã trả viewport về mặc định.
- Các sửa nhỏ cuối: gắn đúng thuộc tính module cho modal để CSS Figma áp dụng, dùng bố cục facts hai cột và nhóm ngoại lệ cho lịch hẹn; đồng bộ nhãn Danh mục sản phẩm.

## Giới hạn còn lại

- Rà soát hình ảnh tổng thể và các luồng trọng tâm, chưa đối chiếu từng pixel/từng trạng thái của cả 27 trang trên mọi thiết bị. Không tuyên bố toàn bộ hệ thống nghiệp vụ đã hoàn chỉnh.
- Dashboard, báo cáo, hóa đơn/thanh toán, đánh giá và đổi mật khẩu trên profile vẫn có phần giao diện/demo ngoài phạm vi; không coi các thống kê đó là dữ liệu MySQL thật.
- Hạng thành viên chưa có quy tắc áp dụng; không tự gán hạng.
- Khuyến mãi có điều kiện văn bản yêu cầu xét thủ công, không suy diễn thành điều kiện máy; chưa áp dụng vào hóa đơn.
- Lịch tuần được tạo trong khoảng ngày Admin chọn (tối đa 366 ngày/lần), không tự sinh lịch vô hạn.
- Không triển khai payOS, AI/RAG hoặc tự tạo dữ liệu mẫu trong database nghiệp vụ.
- `/favicon.ico` chưa có nên trình duyệt có thể yêu cầu và nhận 404; không ảnh hưởng tài nguyên giao diện hoặc nghiệp vụ.

## Bước tiếp theo

Nghiệm thu dữ liệu thật do Admin nhập cho dịch vụ/chuyên viên/ca làm, sau đó triển khai hóa đơn và thanh toán theo SRS trong giai đoạn riêng. Cần chốt các quy tắc hạng thành viên/điều kiện ưu đãi nếu muốn tự động hóa. Không commit/push trước khi người dùng xác nhận.
