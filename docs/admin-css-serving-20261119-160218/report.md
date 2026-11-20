# CSS thực phục vụ và DevTools dock phải — 19/11/2026

## Nguyên nhân đã chứng minh bằng HTTP
- Source: D:/Redesign An Nhiên Spa Home/static/css/admin-services-luxury.css.
- File thực cổng 8000 phục vụ: D:/Redesign An Nhiên Spa Home/staticfiles/css/admin-services-luxury.css.
- Trước sửa: HTTP URL gốc và URL ?v=table-columns-20261119 đều khớp SHA256 bản staticfiles cũ cc3924ce13bbe58bb637b9273ff06cbdd87aa7fa7a7fa6c5a6e254a6010281f1, khác source. Nội dung có td overflow-wrap:anywhere. Đây là bản collected static cũ, không chỉ cache Chrome.
- Khi đồng bộ riêng asset, server đang chạy vẫn giữ metadata kích thước cũ 3319 byte và cắt Response trước các rule mới. Người dùng đã khởi động lại server 8000 bằng môi trường cũ. Không thay backend/cấu hình.
- Sau restart: HTTP 200, 5079 byte; URL gốc và URL version mới khớp từng byte source và staticfiles. SHA256: 45650a278ee6673defb3e809befb4bb660c73914e02014aee8435254e18715a6. Bằng chứng confirmed-response.json và confirmed-plain.css/confirmed-versioned.css.

## CSS thực đã tải
```css
[data-admin-services] .admin-data-table td {
  word-break: normal;
  overflow-wrap: break-word;
}
[data-admin-services] #panel-services :is(th,td):nth-child(3) {
  min-width: 180px;
  white-space: normal;
}
[data-admin-services] .admin-service-category-chip {
  max-width: 100%;
  word-break: normal;
  overflow-wrap: break-word;
}
[data-admin-services] .admin-data-table :is(.admin-service-name,.admin-service-description) {
  word-break: normal;
  overflow-wrap: break-word;
}
```
Giữ nguyên min-width bảng Danh mục 1000px, Dịch vụ 1240px, cột thao tác 300px và vùng admin-table-scroll overflow-x:auto, max-width:100%, min-width:0. Không dùng overflow:hidden để che lỗi.

## Rà cascade
admin.css có overflow-wrap:anywhere trực tiếp trên .admin-service-name và .admin-service-description; đã ghi đè có scope riêng cho bảng dịch vụ ở CSS tải sau. live-admin.css chỉ định dạng form, không ghi đè rule td này. Các anywhere dành cho Accounts/Customers/Finance không áp dụng lên bảng dịch vụ. Rule anywhere còn lại trong admin-services-luxury.css thuộc #service-dialog .admin-service-modal-scroll, không thuộc ô bảng; giữ nguyên để tránh thay modal ngoài phạm vi.

## File sửa
1. static/css/admin-services-luxury.css — source break-word và override các con của ô bảng.
2. staticfiles/css/admin-services-luxury.css — đồng bộ đúng một asset đang phục vụ; đã lưu bản trước sửa. Không chạy collectstatic toàn bộ.
3. templates/pages/admin-services.html — version ?v=table-wrap-20261119-2.
4. tools/check_admin_services_ui.py — assertions break-word/word-break, thêm tùy chọn output trong docs để không ghi đè bằng chứng cũ.

## Kiểm thử
- Chrome headless fixture cô lập 7/7 kịch bản PASS; log offline-chrome-tests.txt. Số assertion mỗi kích thước: 1920x1080: 58, 1440x1000: 58, 1050x950: 62, 768x950: 62, 500x950: 62, 390x950: 62, 1440x560: 58. Tổng 422 assertions.
- Kiểm tra cả hai tab, độ rộng mỗi cột, computed overflow-wrap=break-word và word-break=normal, cuộn ngang thực sự hoạt động và không tràn trang; giữ tìm kiếm/lọc/phân trang/Xem/Sửa/Thêm/Ẩn bằng API mock.
- **Chrome thật / website 8000 / DevTools dock bên phải: PASS quan sát.** Đã xác nhận đúng URL admin-services.html, Network có admin-services-luxury.css?v=table-wrap-20261119-2 HTTP 200, resource khoảng 5.1kB. Vùng website rất hẹp khi dock phải; cuộn dọc tới bảng, cuộn ngang ngay trong bảng để đưa cột Danh mục vào vùng nhìn. Hai dòng “Massage thư giãn” và “Chăm sóc da mặt” rõ, không bị ngắt từng ký tự. Không nhấn Xem/Sửa/Ẩn/Thêm trên dữ liệu thật. Ảnh quan sát nằm trong kết quả Computer Use của lượt này; không tạo file ảnh giả cho ca native.
- Python compile và git diff --check đạt. Không chạy test backend hoặc migration vì không sửa backend.

## Bảo toàn
Không sửa .env/settings/backend/models/migration, không kết nối MySQL trực tiếp, không gửi thao tác ghi API nghiệp vụ. Không đổi dữ liệu dịch vụ, Booking/Billing/PayOS/AI. Người dùng tự restart tiến trình web; agent không dừng hoặc dựng lại website/môi trường kết nối. Không commit/push. staticfiles thường bị Git ignore; thay đổi bền vững nằm ở source static, asset được đồng bộ riêng để nghiệm thu website hiện tại.

Không cần restart lại sau lần người dùng vừa thực hiện. Ctrl+F5 nếu một tab khác còn giữ CSS cũ. Response CSS đầy đủ đã xác nhận ở confirmed-versioned.css; changes.patch ghi riêng thay đổi lượt này.
