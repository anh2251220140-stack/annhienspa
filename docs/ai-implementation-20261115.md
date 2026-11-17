# Bàn giao AI FR-21 FR-22 FR-23 ngày 15/11/2026

> Cập nhật đợt Gemini: xem [báo cáo Gemini Free Tier](gemini-free-tier-20261115.md). Tài liệu này giữ kết quả lịch sử của đợt OpenAI; Provider/embedding đã được tổng quát hóa và cập nhật chỉ mục nay cần phê duyệt riêng. Chưa bật API thật.

Đã triển khai mã nguồn và kiểm thử hợp đồng AI bằng mock/stub. Chưa nghiệm thu suy luận hoặc chất lượng với Provider thật. Không gọi API có phí, không kết nối MySQL 3306/3310, không truy cập website 8000 hoặc dữ liệu restore GD-3/HD-3. Các thay đổi chưa commit từ lượt trước được giữ nguyên; không commit/push.

## 1. Căn cứ và trạng thái

Đọc bản duy nhất tìm thấy trong Downloads: `An_Nhien_Spa_SRS_HLD_B1_v5.docx`. Không tìm thấy bản v5(2) để thay thế. SHA256: `a020eddb8d5a456c09ec7ac7857850fdfd93befab42889f27de582d356ebe963`.

Căn cứ: SRS FR-21–24, mục 7.1; HLD mục 4.1 API, 5.3–5.4 luồng AI/RAG, mục 7 bảo mật và NFR-03. Giao diện Bước 2 được đối chiếu trực tiếp ở form đề xuất và khu vực phân tích Admin; không chỉnh thư mục Bước 2. Không tìm thấy file bàn giao riêng nên dùng trạng thái đã bàn giao trong hội thoại.

| FR | Đã triển khai | Trạng thái nghiệm thu |
|---|---|---|
| FR-21 | Adapter OpenAI, embedding, kho vector, cosine, truy xuất kết hợp tên/mã, nguồn tham chiếu, kiểm tra dữ liệu hiện hành, timeout/fallback | Hợp đồng và luồng RAG có test; embedding/LLM thật chưa chạy |
| FR-22 | POST recommendations, hồ sơ và lịch sử đúng chủ, kiểm tra ứng viên ở server, JSON có ID/lý do, lưu AIRecommendation, fallback và nhãn AI/quy tắc | Test bằng stub/rule; chưa đánh giá khả năng cá nhân hóa thật |
| FR-23 | Admin chủ động phân tích từng review/lô tối đa 5, cảm xúc/chủ đề/tóm tắt/ưu tiên/hành động, lưu và phát hiện kết quả cũ | Quyền/API/lưu dữ liệu được kiểm thử; suy luận thật chưa chạy |
| FR-24 | Giữ models, API, quyền đọc, khôi phục đúng User và cơ chế chống trùng | 15 bài ChatTests hồi quy PASS trên 3311; không thêm nút Lịch sử/Phiên mới |

## 2. Kiến trúc và luồng dữ liệu

Câu hỏi → kiểm tra đăng nhập/CSRF/đầu vào → giữ nguyên bước đặt chỗ, quota 30/ngày và cooldown 5 giây → đọc dữ liệu công khai → cập nhật những document thay đổi → embedding câu hỏi → lọc metadata hiện hành → cosine similarity và kết hợp tên dịch vụ/mã ưu đãi → loại trùng, lấy 3–5 nguồn → Provider → kiểm tra nguồn và số liệu → kiểm tra lại fingerprint trước khi lưu câu trả lời. Thiếu nguồn, timeout hoặc Provider chưa được phép gọi sẽ trả fallback an toàn.

Kho vector tương đương dùng SQLite cục bộ và exact cosine, phù hợp catalog nhỏ của đồ án, không cần Chroma server/dependency nặng. Đây là chỉ mục phụ, không thay thế MySQL hay hai bảng lịch sử chat. Namespace tách theo engine/tên DB/host/port/model embedding; không dùng chung chỉ mục giữa database test và hệ thống thật.

Document có source_type, object_id, category, status, updated_at và content_hash. Chia khoảng 400 token ước lượng, overlap khoảng 50 token bằng độ dài UTF-8; không tuyên bố là tokenizer chính xác của model. Nguồn gồm danh mục/dịch vụ đang hoạt động, sản phẩm công khai, ưu đãi đang hiệu lực, thông tin Spa và JSON FAQ/chính sách được người quản trị duyệt. Không đưa khách hàng/lịch hẹn/hóa đơn/review vào kho RAG công khai.

Admin lưu/ẩn/xóa catalog → callback sau commit vô hiệu document tương ứng, không gọi Provider trong thao tác lưu. Lượt truy xuất hoặc lệnh `index_spa` upsert những nội dung mới/thay đổi và delete nội dung không còn hợp lệ; không tạo lại toàn bộ embeddings. Quan hệ/phạm vi chương trình thay đổi cũng được phát hiện qua content_hash khi đọc catalog. Nội dung cũ bị loại trước khi chấm cosine và bị kiểm tra lại sau khi sinh câu trả lời, kể cả khi Admin thay đổi giá trong lúc AI xử lý.

OpenAI là adapter đã chọn trong đợt này; chưa có adapter Gemini. Dùng REST qua httpx với origin cố định, không proxy/redirect, không tool call, không retry ngầm, `store=false`, giới hạn đầu ra và deadline. Tham chiếu chính thức: [Embeddings](https://developers.openai.com/api/reference/resources/embeddings/methods/create), [Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create).

## 3. FR-22 và FR-23

FR-22 không tin customer ID/history gửi từ trình duyệt. Lấy Customer từ tài khoản hiện tại; chỉ dùng lịch đã hoàn thành của chính Customer. Các nhóm da mặt, thư giãn, tóc, cơ thể được đối chiếu bằng mã nhóm; sáu nhu cầu Profile giữ ánh xạ đã duyệt và thứ tự đã lưu. Ngân sách/thời lượng được kiểm tra cứng ở server. Loại da đối chiếu sản phẩm liên kết và sở thích/lịch sử giúp xếp hạng; không được coi là chẩn đoán. Provider phải trả 1–3 ID riêng biệt nằm trong tập ứng viên; danh sách sai được bỏ toàn bộ và chuyển rule. Kiểm tra lại trạng thái/điều kiện sau inference. Kết quả rỗng không tạo recommendation giả.

FR-23 yêu cầu Admin đang hoạt động và quyền `ai_features.change_aireviewanalysis`. POST có CSRF, giới hạn lô 1–5 ID; không tự phân tích khi User gửi review, không tự sửa/xóa review hoặc gửi phản hồi. Dữ liệu gửi Provider chỉ có rating/comment, không kèm định danh User/lịch hẹn. Comment có dấu hiệu thông tin liên hệ/bí mật không được xuất. Việc xuất nội dung vẫn cần phê duyệt riêng vì bộ phát hiện không thể nhận diện mọi dữ liệu cá nhân.

Fallback FR-23 được ghi rõ `mode=rule`, chủ đề chưa được phân tích và chỉ đối chiếu số sao; tuyệt đối không coi đây là kết quả NLP/AI. Hash nội dung phát hiện review thay đổi, từ chối lưu kết quả khi review đổi trong lúc phân tích; API GET trả cờ stale cho kết quả cũ.

Giao diện giữ form, các section và CSS Luxury A. Form đề xuất lấy kết quả từ Django, có trạng thái đang phân tích và nhãn AI/quy tắc; không hiển thị điểm tin cậy giả. Admin sử dụng khu vực phân tích hiện có, không có phân tích tự động khi đổi bộ lọc. Widget giữ cơ chế khôi phục, bổ sung nhãn Provider từ server và nguồn trong nội dung trả lời. Không thay CSS hoặc bố cục toàn trang.

## 4. Migration và môi trường

Áp dụng riêng `ai_features.0003_review_analysis_details` trên `127.0.0.1:3311 / annhien_spa_fr14_tests`, UUID `608f399a-e055-11f1-9e4d-d549ecc51722`, tài khoản `annhien_fr14_tests@127.0.0.1`, datadir `D:\AnNhienSpa_MySQL84_Acceptance_Test\data\`.

Guard kiểm tra đúng đích trước socket, danh tính/quyền/datadir trên từng kết nối; kế hoạch chỉ có migration trên và fixture tables phải trống trước ghi. Sáu cột bổ sung vào ai_review_analysis: themes, priority, actions, mode, model_name, source_hash. Bản ghi cũ mặc định mode=legacy và hash rỗng, không tự nhận là AI đã kiểm chứng. Không thêm bảng nghiệp vụ: trước/sau vẫn 30 bảng. Sau test: không còn migration chờ, fixture tables trống. Không tạo lại schema/tài khoản, không flush hoặc DROP DATABASE; dùng cleanup có guard chỉ cho fixture của runner.

Migration chưa được triển khai vào production/restore/Chrome 3307/SQLite 8002. Không sửa migration cũ, config/settings.py hoặc .env. Không chạy lại 69 bài đã nghiệm thu.

## 5. Kết quả kiểm thử thực tế

| Nhóm | Kết quả | Phạm vi bằng chứng |
|---|---|---|
| AI/FR-24 trên MySQL 3311 | 57/57 PASS, 0 FAIL/ERROR/SKIP | Log và results.json trong ai-mysql-acceptance-20261115-132841 |
| Kiểm tra mới bổ sung sau đó | 12/12 PASS | 6 ca freshness/RAG chat, 3 ca chấm bộ tham chiếu offline, 1 render User/Admin, 1 hồi quy model phân tích cũ, 1 ca nhu cầu Profile lưu theo dòng |
| Tổng phương thức test riêng biệt có PASS cuối cùng | 69 | Xem ai-delivery-summary-20261115.json; không cộng các lần chạy lại |
| 20 User đồng thời, MySQL + mock | PASS; p95 0,3489 giây, max 0,3502 giây | Đo luồng service send_question, không phải HTTP/Provider thật |
| Smoke HTTP SQLite tạm | PASS: GET login 200, 5.358 byte; HEAD 405 theo thiết kế GET/POST hiện tại | ai-launcher-smoke-retry-20261115.txt |
| Django check và model/migration dry-run | PASS | System check không lỗi; No changes detected |
| Cú pháp Python/JS và git diff --check | PASS | AST; node --check hai JS; Git check |
| Chrome trực quan 1440/768/500/390 | NOT TESTED | Chưa nghiệm thu bằng trình duyệt, không thay bằng kết quả render template |
| AI thật: 30 câu hỏi đúng >=80%, 50 sentiment >=75% | NOT TESTED | Chưa cấu hình/phê duyệt Provider có phí cho lượt chạy này |
| HTTP đầu cuối + RAG/Provider thật, p95 <=10 giây/20 User | NOT TESTED | Mốc service/mock nêu trên không chứng minh NFR đầy đủ |

Các lỗi phát hiện ở vòng đầu được giữ trong bằng chứng cũ: kết nối SQLite vector không tự đóng trên Windows (đã sửa bằng context manager đóng rõ ràng); fixture 90 phút bị kỳ vọng nhầm vào nhóm >90 (đã sửa dữ liệu kỳ vọng của test); tải 20 User trên SQLite memory bị khóa ghi. Ca đồng thời được chạy đúng trên MySQL và PASS, không sửa nghiệp vụ/giảm assertion để che lỗi. HTTP loopback đầu tiên bị môi trường hạn chế socket, chạy lại đúng smoke trong điều kiện cho phép đã PASS.

Provider thật: 0 lời gọi. Chỉ mock/stub, dữ liệu giả tối thiểu và fixtures được tạo/dọn trong môi trường test. Bộ 30 câu hỏi và 50 review gán nhãn nằm tại `docs/ai-reference/cases-20261115.json`; cần con người rà lại nhãn/chấm nguồn và hallucination trước nghiệm thu AI thật. Scorer offline không cho kết quả mock hoặc chưa đủ mẫu/chưa duyệt được đánh dấu PASS về chất lượng.

## 6. Cấu hình an toàn và kiểm tra tiếp

Không ghi key vào source, Git, .env production, câu lệnh chứa giá trị key hoặc log. Nạp `AI_OPENAI_API_KEY` bằng trình quản lý secret hoặc nhập ẩn trong tiến trình riêng; xóa biến khi tiến trình kết thúc. Chỉ cấu hình sau khi duyệt model và ngân sách. Các biến cần chuẩn bị:

| Biến | Ý nghĩa/mặc định |
|---|---|
| AI_PROVIDER | mock; chọn openai khi được duyệt |
| AI_PAID_CALLS_APPROVED | false; phải true mới có bất kỳ lời gọi có phí |
| AI_OPENAI_API_KEY | Secret riêng, không có giá trị trong repository |
| AI_OPENAI_MODEL | gpt-4o-mini; xác nhận model/quyền tài khoản trước khi bật |
| AI_EMBEDDING_MODEL | text-embedding-3-small |
| AI_RAG_ENABLED | false; bật sau khi chọn nguồn/chỉ mục riêng |
| AI_RAG_DIRECTORY | .rag-index, đã gitignore; nên đặt ngoài public/static và tách môi trường |
| AI_RAG_APPROVED_DOCUMENTS | Đường dẫn JSON FAQ/chính sách đã duyệt, template là mảng rỗng |
| AI_CHAT_SPA_INFORMATION | Thông tin Spa được duyệt, không tự sao chép demo |
| AI_RAG_MIN_SIMILARITY | 0.35, cần hiệu chỉnh bằng bộ tham chiếu thật |
| AI_TIMEOUT_SECONDS | 8 giây deadline xử lý Provider; p95 vẫn cần đo thật |
| AI_ASSISTANCE_ENABLED | false cho phân tích Admin; bật sau migration và cấp quyền |
| AI_PERSONALIZATION_EXPORT_APPROVED | false; phê duyệt xuất thông tin chăm sóc/lịch sử trước FR-22 thật |
| AI_REVIEW_EXPORT_APPROVED | false; phê duyệt xuất nội dung review trước FR-23 thật |

Không chạy manage.py với cấu hình mặc định hiện tại đang trỏ 3306. Đợt này không tạo website AI thật ở 8000 và không sửa cấu hình website. Lệnh index_spa phải chạy trong tiến trình đã xác minh database, thư mục vector, nguồn công khai và ngân sách; không chạy bằng .env mặc định.

Có thể chạy lại ca cụ thể bằng `.\.venv\Scripts\python.exe -B tools/ai_tests.py <test.label>`: luôn SQLite mới, chặn MySQL/mạng/PayOS. Không cần chạy lại toàn bộ test đã PASS. `tools/ai_mysql_acceptance.py` dùng terminal nhập ẩn và guard đúng 3311, kiểm tra plan và schema trống, không create/drop/flush database; chỉ dùng khi thực sự cần hồi quy MySQL mới.

Để xem mock UI trong SQLite mới khi cổng 8003 trống: `.\.venv\Scripts\python.exe -B tools/chat_sqlite.py serve`; nhập mật khẩu tạm tại cửa sổ ẩn. User `chat_demo_user`, Admin `chat_demo_admin`, đăng nhập ở `/login.html`. Tool chỉ tạo fixture nhỏ và luôn khóa Provider thật/MySQL; Admin test được quyền phân tích và đọc chat. Không có review mẫu tự tạo cho lượt xem này; có thể dùng ca chuẩn bị riêng sau đó. Tôi không dừng/khởi động lại server 8003 đang có. SQLite của launcher là tạm; đóng launcher kết thúc và dọn dữ liệu nó sở hữu, không phải môi trường kiểm chứng tính bền vững qua tái tạo database. Tính bền vững FR-24 dùng database giữ nguyên, không dựa vào sessionStorage/localStorage.

Các bước còn lại: duyệt Provider/model/ngân sách và phạm vi xuất dữ liệu; điền nguồn Spa/FAQ đã duyệt; chuẩn bị tiến trình web cô lập có guard và chỉ cho phép endpoint AI được chọn; lập chỉ mục bằng embedding thật; chạy/chấm bộ 30/50, đo HTTP p95 20 User; nghiệm thu Chrome các kích thước, đồng bộ static bằng collectstatic theo quy trình trong cấu hình an toàn. Chưa triển khai Docker/deploy và chưa hoàn thành tích hợp website 8000.

## 7. File thay đổi và bằng chứng

Chỉ diff dưới đây thuộc lượt AI; diff nguồn có thể kiểm tra ngược bằng `git apply --reverse --check` (đã PASS, không áp dụng). Các thay đổi cũ ở Billing/Guard/P2/runner FR-14 được giữ nguyên và không đưa vào patch AI.

- `.gitignore`
- `ai_features/apps.py`
- `ai_features/assistance.py`
- `ai_features/assistance_views.py`
- `ai_features/chat.py`
- `ai_features/config.py`
- `ai_features/integration.py`
- `ai_features/management/__init__.py`
- `ai_features/management/commands/__init__.py`
- `ai_features/management/commands/index_spa.py`
- `ai_features/migrations/0003_review_analysis_details.py`
- `ai_features/models.py`
- `ai_features/providers.py`
- `ai_features/rag.py`
- `ai_features/signals.py`
- `ai_features/test_assistance.py`
- `ai_features/test_rag.py`
- `ai_features/test_reference.py`
- `ai_features/urls.py`
- `ai_features/views.py`
- `docs/ai-reference/approved-spa-documents.example.json`
- `docs/ai-reference/cases-20261115.json`
- `requirements.txt`
- `static/js/app.js`
- `static/js/live-admin-reviews.js`
- `templates/pages/admin-reviews.html`
- `templates/pages/services.html`
- `tools/ai_mysql_acceptance.py`
- `tools/ai_tests.py`
- `tools/chat_sqlite.py`
- `tools/score_ai_reference.py`

Bằng chứng: `docs/ai-delivery-summary-20261115.json`, `docs/ai-source-changes-20261115.patch`, thư mục `docs/ai-mysql-acceptance-20261115-132841/`, các log ai-*-tests và ai-launcher-smoke-retry; trạng thái chất lượng `docs/ai-reference/quality-status-20261115.json`.

Không có thay đổi nghiệp vụ Booking, Billing, Promotions, Reviews gốc hoặc PayOS. Không thay dữ liệu thật, quyền tài khoản thật, không tự gửi phản hồi, không thanh toán, không commit/push. Dừng để nghiệm thu.
