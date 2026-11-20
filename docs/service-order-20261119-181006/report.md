# Sửa thứ tự mặc định danh sách dịch vụ — 19/11/2026

## Nguyên nhân đã xác minh
GET /services.html nhúng JSON live-catalog từ FrontendView.get_context_data → core.catalog_data.catalog(). Không có API danh sách công khai riêng được trang này gọi qua fetch; live-data.js chỉ đọc JSON do Django trả về.
Truy vấn Service lọc trạng thái dịch vụ và danh mục nhưng không có order_by; Service.Meta không quy định ordering. Vì vậy thứ tự SQL không được bảo đảm. JSON thực tế trước sửa: [2,6,1,3,5,4,7], khớp lỗi được báo (hiện đã có thêm DV-007). Không có bằng chứng đây là thuật toán gợi ý hay thứ tự tạo; không suy đoán query plan.
Trong catalog-pages.js, render() chỉ sort giá/thời lượng; lựa chọn default giữ nguyên thứ tự đầu vào. Đây là hai vị trí làm lỗi xuất hiện.
Mã DV được tạo từ khóa chính id (admin live-admin.js serviceCode dùng DV + id.padStart); model không có trường mã độc lập. So sánh số id tương ứng mã thực tế, tránh lỗi DV-010 đứng trước DV-002 khi so chuỗi.

## Sửa tối thiểu
- core/catalog_data.py: thêm order_by('pk') vào queryset dịch vụ, vẫn giữ bộ lọc is_active và category__is_active.
- static/js/catalog-pages.js: chỉ khi sort=default, sort toàn bộ mảng kết quả theo id tăng dần trước render. Mảng filter là bản sao, không mutate spaCatalog.services nên không làm đổi dữ liệu dùng cho gợi ý AI. Không thay các nhánh price-asc/price-desc/duration.
- templates/pages/services.html: cache query service-code-order-20261119.
- core/test_service_steps_json.py: cập nhật ORM mock cho chain order_by, xác nhận order và bộ lọc trạng thái.
- tools/test_service_order.js (mới): chạy renderer thật trong môi trường DOM giả lập offline; không cần package/build/frontend framework.
- Runtime: staticfiles/js/catalog-pages.js đã đồng bộ và HTTP trả đúng từng byte so với source sau khi người dùng khởi động lại bằng lệnh/môi trường cũ. Không sửa cấu hình hoặc tự dựng lại server.

## Kết quả
- 11 bài frontend offline PASS, 0 FAIL: đầu vào đảo thứ tự; giữ nguyên mảng nguồn; thêm DV-007/DV-008; DV-010/DV-021; tìm kiếm; lọc; giá tăng/giảm; thời lượng; dịch vụ ẩn; rỗng/reset.
- 15 bài Python mục tiêu PASS, 0 FAIL/ERROR, database connection bị chặn và network bị chặn. Bao gồm đọc catalog, query ordering/status filters, đọc steps và validation để kiểm tra hồi quy file catalog_data.py đã có thay đổi trước.
- Website 8000 qua trình duyệt: mặc định [1,2,3,4,5,6,7]; giá tăng [7,4,3,2,1,5,6]; danh mục Da mặt [2,6]; tìm massage [1,3]; reset [1,2,3,4,5,6,7].
- Phân trang: N/A, trang User hiện render toàn bộ danh sách, không có điều khiển/page slicing; không tự thêm phân trang. Toàn bộ danh sách được sort trước render nên không có lỗi sort riêng từng trang.
- DV-008 và dịch vụ ẩn chỉ dùng fixture offline; không thêm/ẩn dịch vụ thật để thử.
- Python syntax, JS syntax và git diff --check đạt. Hai cảnh báo CRLF ở CSV AI đã tồn tại ngoài phạm vi, không thay các CSV đó.

Không sửa dữ liệu MySQL, giá, ảnh, mô tả, steps hoặc trạng thái. Không migrate/restore, không sửa Admin/AI/PayOS/.env, không gọi API trả phí, không commit/push. AI xếp hạng và endpoint không thay đổi; không gọi Gemini để kiểm tra việc sắp xếp danh mục.
Bằng chứng: frontend-tests.txt, website-verification.json, changes-this-task.patch. Không có phần triển khai còn BLOCKED; chưa tạo DV-008 trên website thật và không có phân trang để nghiệm thu.
