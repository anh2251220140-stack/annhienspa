# Nghiệm thu AI và loading UI — 18/11/2026

## Phạm vi đã thực hiện
Theo lựa chọn tiếp theo của người dùng: **chờ duyệt nhãn và quota, hoàn thiện UI/offline trước**. Không gọi Gemini thật, không nhập hoặc đọc key. Không gọi OpenAI/PayOS, không kết nối MySQL, không sửa .env hoặc migration. Không commit/push/Docker. Các thay đổi chưa commit và file cũ được giữ nguyên.

## Kết luận theo từng FR
| Phần | Offline trong lượt này | Nghiệm thu Gemini thật |
|---|---|---|
| FR-21 / FR-24 | PASS kiểm tra loading, lỗi, F5/đóng mở không trùng, giới hạn caption; backend ownership/history và Gemini-only | BLOCKED bộ 30 câu: chờ duyệt nguồn/nhãn/quota, 0 câu chạy live trong lượt này |
| FR-22 | PASS UI AI/rule, loading/disable, lỗi, renderer; 9 dịch vụ / 5 sản phẩm / KH-01/02/03 qua Django/SDK HTTP mock | Các PASS live adapter/application trước đây do người dùng xác nhận được giữ nguyên. Chưa đủ bằng chứng mới để nghiệm thu chất lượng cá nhân hóa cả 3 hồ sơ với prompt/corpus hiện tại; BLOCKED phần này |
| FR-23 | PASS POST/SDK HTTP mock/validation/save/GET/page reload; lỗi quota/auth/400 không retry | BLOCKED bộ 50 mẫu, nhãn chưa duyệt, không có predictions live để tính chỉ số |

Không đánh đồng mode=ai trong test HTTP mock với lời gọi Gemini thật. Không coi adapter probe là nghiệm thu toàn ứng dụng hoặc chất lượng đủ bộ mẫu.

## Hai thay đổi giao diện
1. Chatbot: bỏ thông báo xử lý ở hộp status bên ngoài; thêm bubble Assistant tạm ngay trong log: “Đang trả lời...” và caption “- Đang xử lý”. Bubble được gỡ trong finally khi response/lỗi đến; sau đó đọc hội thoại từ endpoint hiện có. Không tạo bản ghi tạm trong database, không đổi requestId/poll/quota/CSRF/ownership. Cả pending đã lưu cũng dùng cùng kiểu bubble; không thêm delay giả.
2. FR22: spinner + “Đang phân tích...” nằm trong khu vực kết quả khi fetch chưa hoàn thành; nút bị khóa, submit trùng bị bỏ qua, không render kết quả trước response. finally gỡ spinner/mở nút; lỗi giữ thông báo và không tạo kết quả giả. Caption 30 lượt/ngày và 5 giây nhỏ, nhẹ. CSS có reduced-motion.

File source sửa:
- `static/js/app.js`
- `static/css/chat.css`
- `static/css/catalog.css`
- `templates/pages/services.html`
- `tools/test_fr22_browser_ui.cjs`
- `tools/score_ai_reference.py`
- `ai_features/test_reference.py`
- `tools/test_ai_loading_ui.cjs` (mới)

Không sửa backend ứng dụng FR21/22/23/24. tools/score_ai_reference.py chỉ là công cụ chấm điểm offline; thêm confusion matrix (hàng chuẩn, cột dự đoán), precision/recall/F1 từng lớp, macro và weighted F1, danh sách ID sai. Metrics mới chỉ trả khi đủ predictions, mode real, human_reviewed=true. Nhãn chuẩn chưa duyệt thì không sử dụng các chỉ số để nghiệm thu.

## Test mới chạy — không chạy lại bộ lớn
| Lệnh (.venv Python -B) | PASS | FAIL / ERROR | Bằng chứng |
|---|---:|---:|---|
| tools/ai_tests.py ai_features.test_reference ai_features.test_provider_lock ai_features.tests.ChatTests | 29 | 0 / 0 | ai-acceptance-targeted-20261118.txt |
| -m unittest tools.test_fr22_browser | 12 | 0 / 0 | ai-fr22-preview-tests-20261118.txt |
| tools/ai_tests.py + 2 ca ReviewGeminiIntegrationTests: test_post_sdk_validation_database_get_and_page_reload; test_quota_and_authentication_have_safe_status_codes_without_retry | 2 | 0 / 0 | ai-fr23-targeted-20261118.txt |
| node tools/test_fr22_browser_ui.cjs | 11 | 0 / 0 | ai-fr22-loading-tests-20261118.txt |
| node tools/test_ai_loading_ui.cjs | 4 | 0 / 0 | ai-chat-loading-tests-20261118.txt |
| **Tổng test riêng biệt** | **58** | **0 / 0** | Không có SKIP |

Runner dựng schema và chạy migration hiện có chỉ trên SQLite tạm được sở hữu riêng, chặn connector MySQL, socket/HTTP ngoài và PayOS. Không tạo migration mới. Django check, model dry-run và node --check app.js đạt. git diff --check đạt. Đây là kiểm thử mục tiêu, không chạy lại 155/206/65 test đã nghiệm thu toàn bộ.

## Chrome / Preview
Preview tạm 8004 đã khởi động và GET /login.html HTTP 200 với 9 dịch vụ, 5 sản phẩm, 3 hồ sơ, HTTP mock. Trong tiến trình kiểm tra riêng đã bật widget chat để chuẩn bị quan sát; không ghi cấu hình này vào website hay launcher.

**Kiểm tra trực quan BLOCKED**: người dùng dừng Computer Use bằng Escape trước khi mở được tab Preview. Không có ảnh nghiệm thu mới, không xác nhận responsive 1440/768/500/390 hoặc Console Chrome PASS. Kiểm thử DOM offline không thay thế quan sát Chrome. Đã dừng tiến trình Preview do lượt này khởi chạy, xác minh cổng 8004 không còn LISTEN. Không dừng website hiện có khác.

Để nghiệm thu FR22 UI bằng launcher hiện có:
```
.\.venv\Scripts\python.exe -B tools/fr22_browser_test.py serve
```
Mở http://127.0.0.1:8004/acceptance/fr22/. Chuyển ba hồ sơ và các chế độ mock/fallback/quota/invalid. Không cần key. Để xem chatbot, dùng launcher SQLite 8003 hiện có (`tools/chat_sqlite.py serve`), nhập mật khẩu tài khoản giả trong terminal ẩn; không nhập API key. Không cần restart website chính trong lượt này. Dùng Ctrl+F5 để tải JS/CSS mới khi nghiệm thu.

## Bộ chuẩn cần duyệt
- fr21-acceptance-30-20261118.csv có đủ câu hỏi, đáp án chuẩn nháp, kết quả Gemini trống, accuracy trống, BLOCKED. Q19 giờ mở cửa và Q20 ngày mở cửa đã có sẵn, không thêm câu trùng. Nguồn Spa chưa có giờ/ngày/địa chỉ/contact cụ thể: phải phê duyệt nguồn trước, thiếu nguồn thì fallback đúng chứ không bịa.
- Giá facial trong bộ tham chiếu FR21 là 390.000 VND; fixture FR22 hiện có dịch vụ cơ bản 300.000 VND. Hai corpus độc lập, không dùng chéo đáp án hoặc coi chênh lệch là lỗi giá website.
- fr23-label-review-50-20261118.csv giữ nguyên nhãn nháp 20 positive / 20 negative / 10 neutral. Tất cả NEEDS_HUMAN_APPROVAL. Ưu tiên R36 (câu hỏi phí), R43/R44/R45/R50 (hỗn hợp), R47 (chưa thấy khác biệt). Không tự đổi nhãn. Bộ hiện chỉ có nhãn sentiment, chưa có nhãn chuẩn themes/summary/priority/actions; các phần này cần rubric và người duyệt, không dùng kết quả Gemini làm đáp án.
- ai-acceptance-metrics-20261118.json giữ metrics null/NOT TESTED; số đúng/sai, Precision/Recall/F1 và Confusion Matrix thực tế **chưa xác định**, không phải 0% hoặc 100%. Bộ test phép tính bằng dữ liệu giả đạt.

## Quota và bước live còn chờ
Không gửi request thật trong lượt này. Dự toán 114 ban đầu là trường hợp một document embedding; không phải trần được bảo đảm cho mọi corpus. VectorIndex.sync hiện gọi embed theo từng tài liệu thay đổi. Gọi D là số lần embedding tài liệu thật sự cần, tối đa sơ bộ cho 30 câu là D + 30 query embeddings + 30 generations; cộng 3 FR22 và 50 FR23 thành D+113. Các câu bị từ chối bởi ứng dụng/thiếu nguồn không gọi generation và phải ghi là rule/fallback, không Gemini PASS.

Không tự gộp 50 đánh giá thành prompt mới để tiết kiệm request: batch API Admin tối đa 5 review vẫn xử lý riêng từng review. Lượt này không đổi kiến trúc/nghiệp vụ hay tuyên bố đã có Google Batch API. Lần duyệt tiếp theo cần chốt corpus D, tái sử dụng index đúng provider/model/dimensions nếu có, chỉ chạy ID chưa có kết quả hợp lệ, lưu tiến độ, không retry hoặc chạy lại ID đã PASS. Phải xác nhận Free Tier/billing và quota tại terminal trước request thật; không thể chứng minh miễn phí chỉ bằng biến môi trường.

## Bàn giao
- Diff riêng của lượt này: ai-acceptance-ui-changes-20261118.patch, so với snapshot trước sửa; không trộn các thay đổi cũ với thay đổi mới.
- Git status toàn workspace: ai-acceptance-git-status-20261118.txt. Còn nhiều thay đổi/file chưa theo dõi từ các lượt trước; không reset/stash/commit.
- Còn chờ: kiểm tra Chrome trực quan/loading/responsive/Console; duyệt dữ liệu và nhãn; phê duyệt quota rồi nghiệm thu Gemini thật đủ 30 câu, 3 hồ sơ và 50 reviews. **Chưa đủ điều kiện tuyên bố hoàn tất nghiệm thu AI toàn hệ thống hoặc chuyển Docker với trạng thái AI đã PASS toàn bộ.**
