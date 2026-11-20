# Bàn giao Gemini Free Tier FR-21 FR-22 FR-23

**Bổ sung launcher live (chưa gọi API):** xem [hướng dẫn và giới hạn riêng](gemini-live-launcher-20261115.md). Các kết quả và mô tả staging bên dưới giữ nguyên theo mốc bàn giao ban đầu; chế độ `live` mới yêu cầu xác nhận thủ công Free Tier, chỉ dùng fixture, không bật xuất dữ liệu thật.

Ngày xác minh: 15/11/2026. Đã bổ sung Google Gemini qua SDK chính thức và kiểm thử offline. Chưa nhập/đọc key thật, chưa gọi Gemini API, chưa lập lại chỉ mục thật và chưa phát sinh chi phí. Các kết quả MySQL 69 bài trước đó được giữ nguyên, không chạy lại. Không kết nối MySQL 3306/3310/3311 trong lượt này.

## Kiến trúc và phần được giữ nguyên

`provider_factory.external_provider()` là điểm chọn Provider dùng chung cho FR-21/22/23. `AI_PROVIDER=gemini` chọn `GeminiProvider`; `openai` chọn adapter OpenAI hiện có; `mock` giữ phản hồi cục bộ/fallback. Không tự chuyển sang OpenAI khi Gemini lỗi. Phần kiểm tra nguồn/citation và số liệu được tách thành `GroundedProvider` dùng chung, giữ nguyên quy tắc cũ.

FR-21 tiếp tục dùng ORM công khai → chunk khoảng 400 token ước lượng/overlap khoảng 50 → embedding → vector store SQLite cục bộ → lọc metadata hiện hành → cosine và khớp tên/mã → kiểm tra nguồn trước/sau inference → lưu chat. Gemini dùng task RETRIEVAL_DOCUMENT khi lập chỉ mục và RETRIEVAL_QUERY cho câu hỏi; vector được kiểm tra hữu hạn, khác zero, đúng chiều và chuẩn hóa L2. Không dùng Google File Search/Search/Maps, công cụ agent hoặc lưu file lên Google.

FR-22 chỉ thay điểm chọn adapter; ứng viên, ID, nhu cầu, ngân sách, thời lượng và kiểm tra lại trạng thái vẫn do Django xử lý. JSON sai/timeout chuyển về quy tắc. FR-23 vẫn do Admin có quyền chủ động yêu cầu, kiểm tra cảm xúc/chủ đề/tóm tắt/ưu tiên/hành động và fingerprint review, không tự sửa review hoặc gửi phản hồi. Hai cờ xuất dữ liệu vẫn false, nên luồng người dùng thực tế của FR-22/23 tiếp tục fallback cục bộ cho đến khi có phê duyệt phù hợp.

FR-24 không đổi model, API sở hữu phiên, quota, cooldown, khôi phục lịch sử hoặc phân quyền Admin. Không sửa HTML/CSS/JS, Booking/Billing/Promotions/Reviews gốc, PayOS, model hay migration. Chỉ metadata Provider ở API được cập nhật để không hiển thị AI sẵn sàng khi chưa đủ điều kiện.

## Model và SDK đã xác minh

| Hạng mục | Lựa chọn | Bằng chứng |
|---|---|---|
| Nội dung/JSON FR-21/22/23 | `gemini-3.5-flash-lite` | [Model chính thức](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite), hỗ trợ structured output |
| Embedding | `gemini-embedding-001`, 768 chiều | [Model chính thức](https://ai.google.dev/gemini-api/docs/models/gemini-embedding-001), input 2.048 token, các chiều khuyến nghị 768/1536/3072 |
| Free Tier | Standard text input/output của model chat và input embedding được liệt kê miễn phí | [Bảng giá Google](https://ai.google.dev/gemini-api/docs/pricing#gemini-3.5-flash-lite), [embedding pricing](https://ai.google.dev/gemini-api/docs/pricing#gemini-embedding) |
| Vòng đời | Không mặc định chọn model 2.5 cho dự án mới; embedding-001 có lịch shutdown 14/05/2028 | [2.5 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash-lite), [deprecations](https://ai.google.dev/gemini-api/docs/deprecations) |
| SDK | `google-genai==2.34.0` | [SDK Google chính thức](https://github.com/googleapis/python-genai), [PyPI](https://pypi.org/project/google-genai/2.34.0/) |

Đã cài SDK vào `.venv` và pin trong requirements.txt. Lựa chọn bản 2.x giữ tương thích httpx hiện tại; không cài SDK cũ google-generativeai và không cập nhật các thư viện ứng dụng đang có. Các dependency mới được cài từ PyPI; không phải lời gọi Gemini API. `pip check` PASS. Đã kiểm tra chữ ký/type của SDK cài thực tế; model chưa được gọi để xác nhận quyền tài khoản. Giá, model và quota cần kiểm tra lại ngay trước bước live, không coi tài liệu là bằng chứng tài khoản đã có quyền truy cập.

SDK sử dụng Developer API ở origin cố định `https://generativelanguage.googleapis.com`, API version v1beta, enterprise=false/vertexai=false, key truyền tường minh, không ADC hoặc credential Google Cloud, không proxy/redirect và chỉ một attempt. JSON có giới hạn đầu ra, không function calling/tools; timeout và lỗi auth/quota/server/JSON được đổi thành lỗi an toàn, không phản chiếu payload/secret.

## Cấu hình thống nhất

| Biến | Mặc định/lựa chọn | Ý nghĩa |
|---|---|---|
| AI_PROVIDER | mock trong ứng dụng mặc định; gemini trong launcher riêng | Chọn Provider cho cả ba FR |
| AI_GEMINI_API_KEY | Chưa cấu hình | Chỉ nạp sau phê duyệt riêng; không đọc GEMINI_API_KEY/GOOGLE_API_KEY ngầm |
| AI_GEMINI_MODEL | gemini-3.5-flash-lite | Model nội dung |
| AI_GEMINI_EMBEDDING_MODEL | gemini-embedding-001 | Model embedding |
| AI_GEMINI_EMBEDDING_DIMENSIONS | 768 | Chấp nhận các chiều khuyến nghị 768/1536/3072 |
| AI_GEMINI_EMBEDDING_VERSION | 001 | Nhãn revision cho chỉ mục; không phải kết quả tự truy vấn version từ Google |
| AI_GEMINI_FREE_TIER_ONLY | true | Từ chối nếu tắt chính sách free-only |
| AI_GEMINI_REQUESTS_APPROVED | false | Khóa mọi request Gemini trước khi đọc key/tạo client |
| AI_GEMINI_FREE_TIER_CONFIRMED | false | Chờ người quản trị xác nhận đúng dự án Free Tier, không billing |
| AI_PAID_CALLS_APPROVED | false | Gemini từ chối nếu cờ trả phí được bật |
| AI_PERSONALIZATION_EXPORT_APPROVED | false | Giữ khóa xuất thông tin chăm sóc/lịch sử |
| AI_REVIEW_EXPORT_APPROVED | false | Giữ khóa xuất nhận xét khách hàng |
| AI_RAG_INDEX_UPDATE_APPROVED | false | Phê duyệt độc lập cho upsert/delete/rebuild embedding |
| AI_RAG_ENABLED | Chỉ bật trong fixture staging hoặc môi trường sau phê duyệt | Không tự bật trên website hiện tại |
| AI_RAG_DIRECTORY | Thư mục vector riêng mỗi môi trường | Không public/static, không dùng chung dữ liệu test/thật |
| AI_RAG_MIN_SIMILARITY | 0.35 | Giữ cấu hình hiện có, cần hiệu chỉnh với Gemini sau phép đo thật |

Các model có thể được chọn bằng biến môi trường; adapter chỉ cho các ID Free Tier đã xác minh trong allowlist. Model/alias khác bị từ chối trước request, không tự chọn model cao cấp hay model thay thế. Muốn đổi sang ID mới phải xác minh tài liệu và cập nhật allowlist có kiểm thử.

AI_GEMINI_FREE_TIER_CONFIRMED chỉ là xác nhận của người vận hành, không phải kiểm tra billing từ Google. SDK không có cơ chế của ứng dụng này để bảo đảm project thực tế không bị tính phí nếu project đã gắn billing. Vì vậy hiện vẫn khóa mọi request. Không thiết lập hoặc nâng cấp Cloud Billing. Xem [billing/tier chính thức](https://ai.google.dev/gemini-api/docs/billing).

## Vector store và bảo toàn chỉ mục cũ

Namespace v2 bao gồm engine/database/host/port, Provider, model, revision, số chiều, loại task và normalization. OpenAI và Gemini, hoặc hai chiều/revision khác nhau, luôn dùng file khác. Mỗi file giữ embedding_config và metadata embedding ở document; kiểm tra kích thước lúc ghi, đọc và truy vấn. Dữ liệu sai dimension/non-finite/zero bị từ chối; không trộn hoặc âm thầm chấm điểm vector sai chiều.

Không mở, sửa hoặc xóa file namespace cũ. Test đã tạo marker giả ở vị trí legacy để xác minh nội dung giữ nguyên. Rollback OpenAI cũng có namespace v2 riêng, không tự chuyển đổi hoặc nhập file legacy. Nếu cần dùng lại legacy phải có phương án đối chiếu/phê duyệt riêng.

Không tự lập chỉ mục khi đổi Provider. `AI_RAG_INDEX_UPDATE_APPROVED=false` chặn cập nhật ngay trước khi gọi embedding hoặc xóa document; chỉ mục mới/rỗng trả fallback. Chỉ mục đã có và khớp metadata có thể được đọc mà không reindex. Khi được phê duyệt, index_spa/cơ chế upsert vẫn chỉ xử lý document thay đổi. Callback catalog chỉ vô hiệu nội dung thuộc namespace hiện tại, không gọi Google; lớp lọc live/fingerprint vẫn bảo vệ nội dung đã ẩn/đổi giá. Chỉ mục thật không được mở hoặc lập lại trong lượt này; chỉ test file mới trong vùng cô lập.

## Free Tier, hạn mức và dữ liệu

RPM/TPM/RPD phụ thuộc model/dự án; không dùng một con số từ ví dụ tài liệu làm quota tài khoản. Google áp dụng quota theo project, không theo từng key; RPD reset theo giờ Pacific. Cần xem quota của dự án sau phê duyệt. 30 câu hỏi/tài khoản/ngày và 5 giây của Spa vẫn giữ nguyên; một lượt RAG có thể cần cả query embedding và generation, ngoài các lượt lập chỉ mục. Xem [rate limits](https://ai.google.dev/gemini-api/docs/rate-limits).

Unpaid Services có thể dùng input/output để cải thiện sản phẩm và có người rà soát. Không đưa dữ liệu cá nhân, bí mật hoặc nhận xét thật chưa được phép vào Free Tier. Nội dung công khai/FAQ cũng phải được rà soát trước khi gửi. [Điều khoản Google](https://ai.google.dev/gemini-api/terms#data-use-unpaid).

Không có bước gọi Google để xác minh model/key/quota/billing trong lượt này. Chỉ đọc tài liệu chính thức và tải SDK từ PyPI. Nếu hết quota hoặc model/tài khoản không hỗ trợ, trả fallback; không nâng cấp gói hoặc chuyển Provider trả phí.

## Launcher và các lệnh đã chuẩn bị

Launcher mới `tools/gemini_test.py` tái sử dụng công cụ staging cũ, không có chế độ live, nhập key, đọc clipboard hoặc tham số key. Nó bỏ qua `.env`, khóa mạng/SDK, giữ các cờ false và tạo SQLite/vectors mới trong `.gemini-test/<ngày-giờ-UUID>/`. Các lượt cũ và `.openai-test/` được giữ nguyên; `.gemini-test/` và `.env.gemini-test` bị Git bỏ qua. Không tạo Invoice/Payment và không dùng MySQL cho các fixture này.

```powershell
Set-Location -LiteralPath 'D:\Redesign An Nhiên Spa Home'
.\.venv\Scripts\python.exe -B tools/gemini_test.py plan
.\.venv\Scripts\python.exe -B tools/gemini_test.py fallback --feature fr21
.\.venv\Scripts\python.exe -B tools/gemini_test.py fallback --feature fr22
.\.venv\Scripts\python.exe -B tools/gemini_test.py fallback --feature fr23
```

FR-21 trả fallback vì chỉ mục/request chưa được phép. FR-22/23 trả rule fallback vì quyền xuất dữ liệu chưa được phép. Đây là kết quả đúng của giai đoạn khóa mạng, không phải bằng chứng AI đã suy luận thành công.

Sau khi có phê duyệt riêng: xác nhận dự án không billing và quota/model; chọn dữ liệu tổng hợp/công khai đã duyệt; bổ sung launcher live giới hạn endpoint và số request; nạp AI_GEMINI_API_KEY bằng nhập ẩn/secret manager chỉ trong tiến trình. Không lưu key vào source/.env production, command line, clipboard automation, log hoặc Git. Chỉ sau đó mới xét phê duyệt request và index; vẫn không bật AI_PAID_CALLS_APPROVED. Việc cho FR-22/23 gửi dữ liệu cần phê duyệt độc lập; không tự bật hai cờ xuất dữ liệu.

Chưa tạo đường nhập key cho Gemini trong lượt này. Không dùng launcher OpenAI hoặc gỡ block_network của bộ regression để gọi Google. Không chạy manage.py theo .env mặc định. Kiểm thử live đầu tiên, chất lượng bộ 30/50 và p95 cần lượt nghiệm thu được phép riêng.

## Kết quả kiểm thử và bằng chứng

| Nhóm | Kết quả thực tế |
|---|---|
| AI/FR-24, Gemini adapter, vector và hồi quy liên quan | 89 phương thức riêng biệt PASS; lượt đầu 88, thêm 1 ca metadata; 2 ca timeout chạy lại sau sửa thông báo |
| Launcher Gemini và tương thích launcher OpenAI | 9/9 PASS |
| Tổng phương thức riêng biệt | 98 PASS, 0 FAIL/ERROR/SKIP cuối cùng |
| Cú pháp Python, Django check, model/migration dry-run | PASS; không có thay đổi model cần migration |
| pip check | PASS; SDK 2.34.0 import được, không tạo client thật |
| Git diff --check | PASS |
| Request Gemini/OpenAI/PayOS thật | 0 |
| Key/model/quota/billing tài khoản thật | BLOCKED/NOT TESTED: chưa được phê duyệt request hoặc key |
| Chất lượng >=80% chatbot, >=75% sentiment, p95 Gemini thật | NOT TESTED; không suy ra từ mock |

Các ca bao gồm: không đọc key khi chưa duyệt; thiếu key; SDK Developer API thay vì Cloud credentials; timeout/auth 401/403/quota 429/server 503; JSON rỗng/sai/NaN; citations/số liệu không có nguồn; document/query embedding task; chuẩn hóa và dimension; namespace/provider/revision; không xóa legacy; không tự reindex; ràng buộc ID/ngân sách/nhu cầu; bảo toàn review; các cờ xuất dữ liệu false; lịch sử đúng chủ, CSRF, quota và cooldown. Nhánh AI được kiểm tra bằng stub/policy reader giả lập trên dữ liệu tổng hợp, không bật các cờ runtime/launcher để gọi thật.

Bằng chứng từng phương thức: `docs/gemini-verification-20261115.json` và `docs/gemini-test-cases-20261115.csv`. Log: `docs/gemini-offline-first-20261115.txt`, `docs/gemini-offline-final-targeted-20261115.txt`, `docs/gemini-launcher-offline-20261115.txt`. Diff chỉ thuộc lượt này: `docs/gemini-changes-20261115.patch`.

## File mới và chỉnh sửa

Mới: ai_features/gemini.py, ai_features/provider_factory.py, ai_features/test_gemini.py, tools/gemini_test.py, tools/test_gemini_test.py và báo cáo này.

Chỉnh sửa: ai_features/integration.py, providers.py, assistance.py, rag.py, views.py, management/commands/index_spa.py, test_rag.py, test_assistance.py; tools/ai_tests.py và tools/openai_test.py; requirements.txt và .gitignore. Hai tài liệu cũ ai-implementation/openai-test-launcher chỉ thêm thông báo liên kết tới mốc Gemini; không sửa kết quả lịch sử hoặc ai-delivery-summary cũ. Các thay đổi chưa commit từ trước được giữ nguyên.

Rollback: AI_PROVIDER=mock cho phản hồi cục bộ/fallback. AI_PROVIDER=openai giữ tương thích adapter và kiểm tra đầu ra trước đây, nhưng AI_PAID_CALLS_APPROVED=false tiếp tục chặn OpenAI thật. Không tự bật quyền trả phí để rollback. Chưa nghiệm thu live, Chrome, Docker hoặc deploy; không commit/push. Dừng chờ phê duyệt kiểm thử Gemini thực tế.
