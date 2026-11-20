# DV-002 — JSON tên bước và mô tả — 19/11/2026

## Kết quả
Đã cập nhật **1 bản ghi (services.id=2), đúng 1 trường steps**, trong MySQL annhien_spa trên 127.0.0.1:3306. Transaction đã commit và xác minh bằng kết nối chỉ đọc mới. Toàn bộ trường khác của DV-002 được so sánh bằng giá trị Python trước/sau và không đổi, gồm tên, giá, thời lượng, category, ảnh, mô tả, giới thiệu, lợi ích, đối tượng, lưu ý, gallery/care_group/is_active và các cột hiện hữu khác.

## Đích database và chốt an toàn
- HOST 127.0.0.1, PORT 3306, DATABASE annhien_spa, tài khoản thực annhien_django@127.0.0.1.
- UUID 7db82c55-cb03-11f1-b4b7-ea7eb5144315, MySQL 8.4.11.
- Bảng services InnoDB, truy vấn metadata không có trigger.
- Kiểm tra cấu hình trước mở socket và identity thực tế trước truy vấn/ghi. Khóa SELECT * FROM services WHERE id=2 FOR UPDATE; kiểm tra đúng tên và old steps khớp snapshot website, tránh ghi đè chỉnh sửa đồng thời.
- Sao lưu giá trị cũ bằng file tạo mới exclusive, flush/fsync và đọc lại kiểm tra trước UPDATE.
- Duy nhất câu ghi: UPDATE services SET steps=%s WHERE id=%s AND steps=%s. rowcount bắt buộc 1. So sánh mọi cột và JSON mới trước commit; sai thì rollback. Không dùng model.save, không gọi signal/index/provider.

## Dữ liệu trước
Trước là TextField 8 dòng CRLF, không có tên/mô tả riêng:
```
Bước 1: Kiểm tra tình trạng da và tư vấn liệu trình.

Bước 2: Tẩy trang và làm sạch da mặt.

Bước 3: Tẩy tế bào chết nhẹ nhàng phù hợp với da.

Bước 4: Cân bằng da bằng toner.

Bước 5: Massage mặt thư giãn.

Bước 6: Đắp mặt nạ dưỡng da.

Bước 7: Thoa serum và kem dưỡng ẩm.

Bước 8: Tư vấn chăm sóc da tại nhà.
```
Bản sao lưu nguyên giá trị, không normalize: dv002-steps-before.json.
SHA256 file backup: dafe665f90117972d89b85f1af6ae81ad8a06122d4add26672074ddbe2d93d02.
Có thể khôi phục trường steps từ old_steps của bản này khi có yêu cầu riêng; chưa thực hiện rollback/restore.

## Dữ liệu sau — JSON array trong chính TextField hiện có
1. **Lắng nghe nhu cầu** — Kiểm tra tình trạng da và tư vấn liệu trình phù hợp với khách hàng.
2. **Làm sạch da** — Tẩy trang và làm sạch da mặt, loại bỏ bụi bẩn và lớp trang điểm.
3. **Tẩy tế bào chết** — Tẩy tế bào chết nhẹ nhàng, phù hợp với tình trạng và loại da.
4. **Cân bằng da** — Sử dụng toner giúp làm dịu và cân bằng da sau bước làm sạch.
5. **Massage thư giãn** — Massage mặt nhẹ nhàng, giúp khách hàng thư giãn trong quá trình chăm sóc.
6. **Đắp mặt nạ** — Lựa chọn và đắp mặt nạ phù hợp với tình trạng da.
7. **Dưỡng da** — Thoa serum và kem dưỡng ẩm phù hợp để chăm sóc da.
8. **Hoàn thiện** — Kiểm tra kết quả sau liệu trình, tư vấn cách chăm sóc và bảo vệ da tại nhà.

Mỗi phần tử có đúng hai key title/description; không đổi kiểu cột, không thêm model/table/migration. Tệp nội dung đầy đủ approved-dv002-steps.json. Chỉ bước 8 có tên Hoàn thiện; không hardcode tên theo vị trí trong renderer.
MySQL tự kiểm tra JSON_VALID(steps)=1, JSON_LENGTH(steps)=8, số title=8, số description=8. Bằng chứng mysql-json-verification.json.

## Thay đổi source
- `core/catalog_data.py`
- `static/js/catalog-pages.js`
- `staticfiles/js/catalog-pages.js`
- `templates/pages/service-detail.html`
- `tools/check_service_steps_ui.py`
- `core/test_service_steps_json.py` (mới)

- core/catalog_data.py: helper service_steps nhận diện JSON array đúng title/description, trả object cho client; plain text vẫn tách dòng như cũ. Schema JSON không nhận diện hoặc JSON lỗi giữ nguyên cách hiển thị text cũ, không âm thầm bỏ dữ liệu. Không tự chuyển đổi các bản ghi cũ.
- catalog-pages.js: phân biệt string legacy và object mới. Object mới -> h3 title + p description; string cũ -> h3 như trước, không thêm p rỗng. Escape cả hai trường; đánh số động, bỏ hidden sau render nếu có li. Không đổi CSS/markup bố cục.
- staticfiles/js/catalog-pages.js đồng bộ riêng asset runtime, không collectstatic toàn bộ. Template chỉ đổi query version service-steps-json-20261119. Đã kiểm tra 8000 phục vụ đủ 12150 byte đúng source trước khi ghi DB; không cần yêu cầu restart thủ công trong lượt này.
- ServiceForm giữ TextField hiện tại; test chứng minh initial và clean của trường steps giữ nguyên JSON. Không bổ sung editor Admin hoặc đổi thiết kế form trong lượt này.

## Kiểm thử offline
- 7 unit tests PASS: đọc line cũ; JSON hai trường; số bước 4/5/6/8/10/21; rỗng; JSON lỗi/schema lạ giữ text cũ; form Admin bảo toàn JSON; catalog thực đọc cả hai định dạng qua ORM mock, không đổi object gốc. Chạy unittest trong tools.chat_sqlite.configure + chặn BaseDatabaseWrapper.ensure_connection. Không migrate, không truy cập DB trong unit test.
- 76 ca Chrome PASS (19 ca x viewport 1440/768/500/390): các số bước trên cho cả legacy/JSON, hidden rỗng, thiếu dữ liệu, CRLF, escape HTML ở title và description, so sánh exact nội dung/numbers, p riêng cho JSON và không p cho legacy, không lỗi JS/tràn nội dung. Log chrome-tests.txt.
- **Tổng offline 83 PASS, 0 FAIL/ERROR**. Không chạy lại bộ AI hoặc nghiệp vụ lớn đã PASS.
- Python compile, node --check catalog-pages.js, git diff --check đạt.

## Nghiệm thu website 8000 và dữ liệu thật
- DV-002: browser Chromium tích hợp mở trực tiếp URL id=2, không sửa DOM hoặc giả dữ liệu. Section visible=true, hidden=null, có đúng 8 li, 8 h3, 8 p; số 01–08; nội dung khớp 8 bước người dùng đã duyệt. Đã xem ảnh hiển thị trực tiếp.
- DV-001: mở trực tiếp URL id=1, dữ liệu cũ vẫn hiển thị đủ 4 bước: Tư vấn tình trạng cơ thể; Làm sạch và chuẩn bị; Massage với đá nóng; Nghỉ ngơi và thưởng trà. Có 0 p mới trong bước legacy, section vẫn hiện. Snapshot GET trước/sau xác nhận steps của ID=1 không đổi.
- website-after.json xác nhận payload công khai DV-002 khớp toàn bộ JSON đã duyệt; không nhầm tệp fixture với dữ liệu database.
- database-update-result.json ghi commit + reread từ kết nối mới, danh sách fields_changed=[steps], row count=1, hash backup/new value. mysql-json-verification.json là xác minh trực tiếp bằng hàm JSON MySQL.

## Bảo toàn và bàn giao
Không sửa model/migration/schema, không migrate/restore, không đổi .env hoặc CSS, không gọi Gemini/OpenAI/PayOS/API phí. Không tạo dịch vụ hoặc sửa nội dung trường khác. Không cập nhật RAG index. Mọi thao tác ghi MySQL trong lượt này giới hạn ở UPDATE steps của ID=2 đã được phê duyệt; test dùng dữ liệu giả và không ghi MySQL. Không commit/push. Các file AI/CSV/CSS đang có thay đổi trước lượt này được giữ nguyên.

File changes.patch chỉ gồm diff lượt này so với before-source.json; git-status.txt lưu trạng thái workspace. Ctrl+F5 service-detail.html?id=2 để xem lại. Không cần migration hoặc chỉnh thiết kế. Khi sửa steps bằng form Admin hiện tại, trường vẫn là textarea: giữ JSON hợp lệ để bảo toàn tên/mô tả riêng, hoặc nhập line legacy nếu muốn giữ kiểu dữ liệu cũ.
