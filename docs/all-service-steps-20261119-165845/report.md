# Đồng bộ quy trình toàn bộ dịch vụ — 19/11/2026

## Kết quả dữ liệu thật
Đã kiểm kê toàn bộ bảng services, gồm cả bản ghi tạm ngừng: tổng cộng 2 dịch vụ.
Xác minh trước socket: host 127.0.0.1, port 3306, schema annhien_spa, user annhien_django.
Danh tính thực tế: annhien_django@127.0.0.1; UUID 7db82c55-cb03-11f1-b4b7-ea7eb5144315.

| Dịch vụ | Trước | Sau | Thay đổi |
|---|---|---|---|
| DV-001 Massage đá nóng thư giãn toàn thân | Văn bản, 4 bước, chưa có mô tả riêng | JSON 4 title + 4 description | Chỉ steps |
| DV-002 Chăm sóc da mặt cơ bản | JSON 8 bước đầy đủ | Giữ nguyên chính xác chuỗi dữ liệu cũ | Không thay đổi |

Đã chuyển 1 dịch vụ; 1 dịch vụ đạt chuẩn từ trước; hiện 2/2 đạt chuẩn; 0 dịch vụ thiếu dữ liệu quy trình. Không thêm/xóa bước và không thêm dịch vụ vào MySQL.
Tên 4 bước DV-001 giữ nguyên nội dung công đoạn: Tư vấn tình trạng cơ thể → Làm sạch và chuẩn bị → Massage với đá nóng → Nghỉ ngơi và thưởng trà. Chỉ bỏ tiền tố số và dấu chấm phẩy phân dòng; mô tả viết riêng cho massage đá nóng, không dùng mô tả chăm sóc da DV-002.

## Sao lưu và ghi an toàn
Backup services-steps-before.json chứa steps cũ của cả hai dịch vụ và hash các trường còn lại. SHA256: a1a153f18fe9bf0a560e58d177987f184a0f3d5f7154b4f40a828862831de9a6.
Đã kiểm tra InnoDB và không có trigger trên services; SELECT FOR UPDATE; UPDATE có điều kiện id=1 và steps khớp bản cũ; xác nhận đúng 1 bản ghi. So sánh mọi trường khác của cả 2 dịch vụ trước/sau không thay đổi. Commit rồi mở kết nối chỉ đọc mới để xác minh JSON_VALID, JSON_LENGTH và chuỗi DV-002 giữ nguyên.
Không dùng ORM save cho thao tác chuyển đổi dữ liệu thật. Không migrate, không sửa model, không tạo bảng/schema trong MySQL, không gọi API trả phí.

## Cơ chế dùng chung cho Admin và User
- Form Admin thêm/xóa từng bước, tên + mô tả riêng, nút Lên/Xuống; số thứ tự cập nhật theo vị trí.
- Submit serialize JSON vào TextField steps hiện có; không có số bước cố định.
- Cả trình duyệt và ServiceForm kiểm tra từng bước đủ tên/mô tả; tên Hoàn thiện chỉ được dùng ở bước cuối.
- Quy trình rỗng vẫn được lưu là [] và User không hiển thị khung trống.
- Reader core/catalog_data.py và renderer catalog-pages.js từ lượt trước được giữ nguyên, tiếp tục đọc JSON mới và văn bản cũ. Khi mở form dữ liệu cũ, tiêu đề được đưa vào editor và mô tả để trống để Admin bổ sung, không tự suy diễn mô tả rồi ghi xuống database.
- Chỉ thêm CSS cục bộ cho bộ nhập trong modal; không đổi bố cục User, màu sắc hoặc bảng desktop.
- Đã đồng bộ live-admin.js và admin-services-luxury.css vào staticfiles, tăng query version; sau khi người dùng khởi động lại 8000, HTTP trả đầy đủ, khớp byte với source.

## File sửa trong lượt này
1. core/business_forms.py — nhãn và validation JSON steps.
2. templates/partials/business_form.html — vùng nhập quy trình, tái sử dụng form/CSRF hiện có.
3. static/js/live-admin.js — editor, thêm/xóa/đổi thứ tự và serialize trước FormData.
4. static/css/admin-services-luxury.css — CSS giới hạn trong editor.
5. templates/pages/admin-services.html — cache version CSS/JS.
6. core/test_service_steps_json.py — validation và tạo/sửa dịch vụ qua API Django trong SQLite tạm.
7. tools/check_admin_services_ui.py — kiểm thử editor bằng Chrome + API mock; khung 390px thực để tránh sai lệch minimum window width của headless Chrome.
Runtime copies: staticfiles/js/live-admin.js, staticfiles/css/admin-services-luxury.css.
Không sửa core/catalog_data.py hoặc catalog-pages.js thêm trong lượt này vì khả năng hiển thị JSON đã có và kiểm thử lại đạt.

## Kiểm thử
- Unit/SQLite: 12 PASS, 0 FAIL, 0 ERROR. Network bị chặn; MySQL driver bị chặn; không dotenv. Dùng schema của model hiện có trong SQLite tạm, không gọi migrate.
- Chrome User: 19 ca × 4 viewport = 76 PASS; legacy/JSON 4,5,6,8,10,21 bước; rỗng, xuống dòng, escaping, tiêu đề/mô tả/số thứ tự.
- Chrome Admin: 7 viewport PASS, tổng 513 assertions; thêm 21 bước, lên/xuống/xóa, chặn thiếu nội dung không POST, tạo JSON và mở/sửa lại dữ liệu đã lưu, modal và editor không tràn. Đã xem ảnh 390px sau khi sửa công cụ đo viewport.
- Kiểm thử create/edit: Chrome dùng API mock; kiểm thử SQLite riêng gọi đúng records → ServiceForm → lưu → đọc lại, 201/200/400. Không tạo dịch vụ thử trên database thật.
- Website 8000: DV-001 hiện đủ 4 h3 + 4 p, số 01–04; DV-002 hiện đủ 8 h3 + 8 p, số 01–08; section visible. Đây là toàn bộ danh mục hiện tại.
- Python syntax, JavaScript syntax và git diff --check đạt. Git cảnh báo CRLF tại 2 CSV AI đã sửa từ trước; không liên quan lượt này.

Tổng: 12 bài Python/SQLite + 76 tình huống User + 7 cấu hình Admin = 95 PASS, 0 FAIL. Không đánh đồng assertions với số bài.

## Giới hạn nghiệm thu
Chưa thực hiện thêm dịch vụ thật bằng tài khoản Admin trên 8000 để tránh sinh dữ liệu ngoài yêu cầu chuyển đổi steps. Nghiệm thu tạo mới/sửa/lưu đã được chứng minh bằng Chrome mock và API Django/SQLite riêng, chưa phải E2E trình duyệt → MySQL trên production.
Người dùng có thể mở Admin → Dịch vụ → Sửa → Nội dung chi tiết liệu trình → Quy trình thực hiện để kiểm tra; chỉ nhấn Lưu khi muốn thay đổi dữ liệu. Mở /service-detail.html?id=1 và ?id=2; Ctrl+F5 nếu trình duyệt còn cache.
Không thay .env, model, migration, nghiệp vụ Booking/Billing/PayOS, không gọi AI, không commit/push. Các thay đổi Git có sẵn được bảo toàn. Diff chỉ riêng lượt này: changes-this-task.patch.
