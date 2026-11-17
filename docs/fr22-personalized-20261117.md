# FR-22 cá nhân hóa — 17/11/2026

## Bàn giao và giới hạn

Hoàn thiện mã nguồn FR-22 và launcher 8004 hiện có, không tạo môi trường nghiệm thu song song. 65 bài khác nhau PASS, 0 FAIL, 0 ERROR sau sửa. Không gọi Gemini thật thêm; không coi mock PASS là chứng minh chất lượng suy luận Gemini thật với prompt mới. Responsive Chrome 1440/768/449/390px chưa nghiệm thu (BLOCKED).

## File đã sửa trong lượt này

- `ai_features/assistance.py`: chỉ phần FR-22, helpers lịch sử/sản phẩm, prompt FR-22 và validation; giữ phần review_fingerprint/FR-23 trở đi.
- `static/js/app.js`: chỉ khu vực form và kết quả FR-22, nhãn mode, sản phẩm từ server, loại trùng phương án.
- `static/css/catalog.css`: responsive giới hạn danh sách dịch vụ và khu vực recommendation, ảnh sản phẩm.
- `templates/pages/services.html`: tăng phiên bản cache JS/CSS.
- `tools/fr22_browser_test.py`: mở rộng fixture/đổi hồ sơ ngay trong launcher đã có, giữ mock transport và các chốt network/database.
- `tools/test_fr22_browser.py`: kiểm thử hồ sơ/hành vi thực tế qua Django/SDK HTTP mock.
- `tools/test_fr22_browser_ui.cjs`: bổ sung test render sản phẩm, ảnh/thành phần và loại trùng.
- `ai_features/test_recommendation_integration.py`: bổ sung từ chối giá bịa, số lượt bị dùng làm giá và cam kết y khoa.
- `ai_features/test_gemini.py`: cập nhật fixture SimpleNamespace/patch linked_care_products trong bài deadline FR-22; không giảm assertion deadline hoặc sửa FR-23.

Không sửa adapter Gemini, OpenAI adapter, FR-21/23/24, model, migration, URL, launcher live đã PASS, .env hoặc cấu hình website chính. API giữ endpoint/method; bổ sung trường `history`, `products`, `caution` trong item và `alternatives`, `budgetScope` ở response theo cách tương thích với client cũ.

## Dữ liệu chỉ trong SQLite nghiệm thu

9 dịch vụ thuộc face/body/relax/hair, giá 180000–590000 VND, thời lượng 30–90 phút, có suitable/benefits/steps/note theo thông số giả lập. Dịch vụ chuyên sâu ghi rõ không áp dụng cho da nhạy cảm; các trường hợp thiếu căn cứ giữ thông báo cần chuyên viên xác nhận, không tự đưa chống chỉ định mới.

5 sản phẩm: sữa dưỡng thể, kem dưỡng ẩm, dầu massage, chăm sóc tóc, chăm sóc da sau liệu trình. Có 8 ServiceProduct thực tế, thành phần/công dụng/hướng dẫn ghi rõ là thông số giả lập, không cam kết điều trị. Giá minh họa 120000–220000 VND ghi trong description và được UI hiển thị theo nguồn đó. CareProduct hiện không có trường price: API trả price=null, không bịa giá cấu trúc hoặc tạo migration. Mô tả giá giả không phải bảng giá sản phẩm thật.

| Hồ sơ | Loại da | Nhu cầu | Ngân sách/liệu trình | Lịch sử giả |
| --- | --- | --- | ---: | --- |
| KH-01 | Da thường | Cơ thể | 300000 | 3 lượt chăm sóc cơ thể |
| KH-02 | Da nhạy cảm | Da mặt/cấp ẩm | 500000 | 4 lượt chăm sóc da cơ bản |
| KH-03 | Da khô | Thư giãn/massage | 700000 | 3 lượt massage đá nóng |

Mỗi hồ sơ có sở thích riêng. Banner 8004 có liên kết chuyển KH-01/KH-02/KH-03; chỉ đăng nhập tài khoản thuộc whitelist fixture, không sửa đăng nhập website chính. Cookie riêng như launcher trước. Không xóa cooldown khi đổi scenario. Không dùng dữ liệu khách hàng thật.

## Cá nhân hóa và bảo vệ kết quả

- Gemini nhận các preferences hiện có, completedServiceIds tương thích cũ, serviceHistory (count, firstUsed, lastUsed theo từng dịch vụ), phạm vi lịch sử và dữ liệu ứng viên từ ORM.
- Count tính tất cả lượt completed cho từng dịch vụ trong tối đa 20 nhóm dùng gần nhất. Không suy chưa từng dùng từ việc vắng mặt trong phạm vi giới hạn. Không gửi tên/email/phone/customer ID.
- Prompt yêu cầu cân nhắc đồng thời da/nhu cầu/ngân sách/thời lượng/sở thích/lịch sử, cân nhắc bổ sung, không mặc định ưu tiên lặp lại. Fallback bỏ điểm thưởng lịch sử cũ, dùng tần suất làm tiêu chí giảm ưu tiên khi các điều kiện khác ngang nhau.
- Chưa có nguồn lịch sử dùng sản phẩm được xác nhận trong model: gửi productUsageHistory.available=false. Không biến ServiceProduct thành lịch sử khách đã sử dụng.
- Chỉ chấp nhận 1–3 ID thuộc ứng viên, không trùng, reason giới hạn/không thông tin riêng tư, không field tên/giá/sản phẩm do mô hình tự thêm. Kiểm tra số liệu với dữ kiện, kiểm tra riêng giá để count/ID không trở thành giá tiền, chặn các mẫu cam kết/điều trị đã biết; recheck dữ liệu dịch vụ trước khi trả về.
- Các kiểm tra trên không phải bộ chứng minh ngữ nghĩa mọi câu tự nhiên. Lý do AI vẫn cần Admin/chuyên viên đối chiếu; chưa khẳng định loại được mọi diễn giải sai hay mọi câu y khoa.
- Tên/giá/thời lượng từ database, products chỉ từ liên kết đang hoạt động, đúng nhóm, có tag loại da hoặc không áp dụng phù hợp; da nhạy cảm cần tag trực tiếp và không trái lưu ý đã nhận diện. Thiếu dữ liệu không phải xác nhận phù hợp y khoa.
- Alternatives từ tập ứng viên được backend lọc lại, loại toàn bộ ID đã chọn. Frontend chặn trùng lần nữa. Hỗ trợ sản phẩm liên quan cho tất cả dịch vụ chính, khử trùng sản phẩm.
- Ngân sách giữ đúng nghiệp vụ mỗi liệu trình; không coi 2–3 đề xuất là một gói tổng tiền dưới cùng giới hạn. UI nói rõ điều này.
- Label UI: Đề xuất bởi AI / Đề xuất theo quy tắc, không đánh đồng.

## Bằng chứng test cuối

| Nhóm | PASS | Bằng chứng |
| --- | ---: | --- |
| RecommendationApplicationTests + AssistanceTests + bài deadline liên quan | 43 | docs/fr22-personalized-backend-20261117.txt; docs/ai-regression-results-20261115-224821924966.json |
| Browser fixture, ba hồ sơ thật qua API/SDK mock | 12 | docs/fr22-personalized-preview-20261117.txt |
| Renderer app.js thật trong DOM mock | 9 | docs/fr22-personalized-ui-20261117.txt |
| Fresh process/SQLite/cleanup/SDK mock | 1 | docs/fr22-personalized-fresh-20261117.txt |

Ca ba hồ sơ được chạy lại sau khi thêm assertion KH-01 trả 2 lựa chọn nhưng từng lựa chọn không vượt ngân sách; PASS, không cộng trùng tổng test. Profile test xác nhận lịch sử riêng (3/4 lượt), thời điểm, candidate cần khác nhau theo nhóm, kết quả đầu có thể bổ sung thay vì lặp lại. Không sửa backend để mock xanh.

Bao phủ tối thiểu 7 tình huống: ngân sách thấp/nhiều lựa chọn theo từng liệu trình, da nhạy cảm, massage, lặp nhiều lượt, phương án bổ sung, không đủ ngân sách, không có sản phẩm liên kết. Kiểm tra thêm stale service eligibility, giá bịa, cam kết y khoa, privacy/owner, CSRF/cooldown, quota/timeout/JSON lỗi, GET/F5 không tự AI.

Python/JS syntax, Django check, model/migration dry-run và git diff --check đạt. Không tạo migration mới. Runner tự động dựng SQLite tạm bằng migration hiện có; riêng server 8004 vẫn tạo schema trực tiếp, không chạy migrate và không có django_migrations. Không chạm database thật.

## Responsive còn chờ

Đã thêm CSS: danh mục 2 cột <=900px và 1 cột <=600px; thẻ FR-22 một cột trên điện thoại, wrap chữ/nút, ảnh giới hạn chiều rộng. Desktop giữ 3 cột. Chưa xác minh trực quan tại 1440/768/449/390px vì Computer Use dừng do không xác định được URL Chrome đủ chắc chắn. Không vượt chốt, không có ảnh hoặc responsive PASS mới.

## Một lệnh nghiệm thu

```powershell
.\.venv\Scripts\python.exe -B tools/fr22_browser_test.py serve
```

URL: http://127.0.0.1:8004/acceptance/fr22/

Nếu server 8004 bản cũ đang chạy, người dùng Ctrl+C tại terminal đó rồi chạy lại cùng lệnh để có bộ dữ liệu mới. Không tự dừng tiến trình không xác định, không ghi đè SQLite cũ hoặc đụng port 3306. Đổi hồ sơ/scenario ở banner; đó là HTTP mock và dữ liệu giả, không phải lời gọi Gemini Live mới. Không cần key. Dừng Ctrl+C để dọn thư mục tạm do launcher sở hữu.

Chờ nghiệm thu Chrome và phê duyệt riêng nếu muốn kiểm tra Gemini thật với payload/prompt cá nhân hóa mới. Không commit/push.
