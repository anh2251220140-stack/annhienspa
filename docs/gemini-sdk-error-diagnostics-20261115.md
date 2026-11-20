# SDK 2.34.0: chuẩn hóa diagnostics HTTP 400

## A. SDK thực sự lưu lỗi như thế nào

Đọc trực tiếp `.venv/Lib/site-packages/google/genai/errors.py`, không gọi API. Phiên bản cài thực tế được xác minh là google-genai 2.34.0.

- Dòng 85: nếu response_json là list đúng một phần tử, SDK unwrap phần tử đó.
- Dòng 88: `self.details = response_json`. Vì vậy details có thể là **toàn bộ response JSON** dạng `{"error": {...}}`, hoặc object lỗi phẳng; không mặc định là danh sách RPC `error.details`.
- Dòng 89–91: message/status lấy từ helper; code ưu tiên đối số constructor nếu khác 0, nếu không lấy từ JSON.
- `_get_status` dòng 110, `_get_message` dòng 121: hỗ trợ thuộc tính top-level và thuộc tính trong error. Các trường top-level được SDK ưu tiên nếu có.
- `raise_for_response` dòng 152: đọc JSON của response rồi chuyển nguyên payload cho `raise_error` dòng 190; HTTP 4xx tạo ClientError.
- Exception string của SDK chứa details; tuyệt đối không dùng str(exc), repr(exc), exc_info hoặc traceback để báo diagnostics.

Mock với ClientError(400, payload) xác nhận `exc.details is payload`, là dict; `exc.code=400`, `exc.status=INVALID_ARGUMENT`, message là string giả. Không in message/details. Code constructor có thể khác error.code trong JSON; diagnostics phân biệt http_status với google_error_code, không gộp hai giá trị.

## B. Vì sao có thể nhận details rỗng trước đây

Các điều xác minh được từ source trước sửa:

1. safe_google_error chỉ đọc `response.json().get("error")`: response lỗi dạng phẳng không được nhận diện. Mock tái hiện được thiếu sót này; sau sửa đọc được code/status/details.
2. safe_error_details chỉ nhận list RPC. Nếu truyền **toàn bộ** exc.details dạng dict vào hàm này sẽ trả `[]`, vì truyền sai cấp JSON. Cần unwrap object error trước, sau đó mới lấy trường details của object lỗi.
3. Tuy nhiên, launcher hiện có đọc non-200 ngay tại HTTP transport **trước khi SDK tạo exception**, và đường HTTP này đã đọc được payload nested chuẩn từ lượt trước. Không có bằng chứng đường cũ thực sự truyền exc.details vào safe_error_details trong lần chạy của người dùng. Vì vậy không được khẳng định việc hiểu sai SDK là nguyên nhân chính xác của details rỗng trong lần chạy thật.
4. Google không gửi details, body quá lớn/sai JSON, hoặc tất cả detail/type/reason/field nằm ngoài allowlist cũng cho kết quả rỗng có chủ đích. Không thể phân biệt các khả năng lịch sử này nếu chưa có diagnostics thật phù hợp.

## C. Cách sửa và những gì đọc được

Chỉ chỉnh công cụ kiểm thử, giữ nguyên request và nghiệp vụ:

- `tools/gemini_live.py`: thêm `safe_error_payload` làm bộ chuẩn hóa dùng chung. Nhận envelope `{"error": {...}}`, object phẳng, và list singleton như SDK. Ưu tiên error bên trong nếu có, không ghép metadata top-level không liên quan vào object lỗi.
- `safe_google_error`: wrapper HTTP, giữ giới hạn 16384 byte trước parse.
- `safe_sdk_error`: chỉ nhận google.genai.errors.APIError; đọc toàn bộ exc.details qua bộ chuẩn hóa; chỉ dùng code/status/message riêng của SDK làm fallback cho trường thiếu. Không dùng exception string. Payload SDK cũng bị giới hạn kích thước, JSON sai kiểu hoặc quá lớn bị loại an toàn.
- Nhánh lỗi transport có thể xử lý APIError thông qua safe_sdk_error nếu exception dạng này xuất hiện. Non-200 HTTP đã được ghi nhận không tạo diagnostics trùng. Adapter chung vốn tổng quát hóa lỗi vẫn giữ nguyên; không sửa nó để tiết lộ exception.
- Các trường đầu ra giữ nguyên allowlist: http_status, google_error_code/status, operation, api_method/model, message được chiếu sang thông báo cố định, và details đã lọc.
- ErrorInfo: reason/domain/service thuộc danh sách cho phép; loại consumer/project ID/key và metadata còn lại.
- BadRequest: chỉ tên field công khai, chuẩn hóa snake_case và chỉ số array. Không lưu description/giá trị input/schema property tùy ý.
- Thiếu details thì giữ `[]`; unknown reason không được tự dịch thành nguyên nhân. Danh sách RPC trực tiếp không được nhầm với toàn bộ response JSON của SDK.

Không đổi model, SDK, API version, prompt, JSON mode, tham số request, adapter Gemini/OpenAI, FR-21/22/23, FR-24 hoặc UI. Không sửa .env.

## D. Kiểm thử offline thực sự đã chạy

| Nhóm | PASS | FAIL/ERROR |
| --- | ---: | ---: |
| SDK exception payload + allowlist details | 16 | 0 |
| Serialization/request compatibility | 7 | 0 |
| Launcher, generate-only helpers, fallback và no retry dưới mock | 29 | 0 |
| Tổng phương thức riêng biệt | **52** | **0** |

Log: `gemini-sdk-error-diagnostics-offline-20261115.txt`, `gemini-sdk-error-diagnostics-compat-20261115.txt`, `gemini-sdk-error-diagnostics-launcher-20261115.txt`.

Bao gồm nested/flat HTTP và SDK; ErrorInfo; BadRequest.fieldViolations; không details; payload singleton; JSON hỏng/quá lớn; body code khác HTTP code; nested error ưu tiên top-level; key/consumer/prompt giả bị loại; APIError đi qua lớp transport vẫn có diagnostics, đúng một request mock, không retry. Test serialization xác nhận request không bị thay đổi.

Không chạy CLI live/generate-only hoặc hỏi nhập key. Các hàm launcher trong unit test dùng mock confirmation/getpass/HTTP; không đọc key thật. Không kết nối MySQL 3306/3310/3311, không migration, không Gemini/OpenAI/PayOS API thật. Test RAG dùng vector SQLite tạm như trước; không đọc dữ liệu hiện có. Không commit/push.

## E. Kết luận giới hạn

**BLOCKED phần nguyên nhân HTTP 400 thật.** Đã xác minh/sửa bộ đọc cấu trúc lỗi, không khẳng định đã sửa lỗi Gemini. ErrorInfo trong fixture như API_KEY_INVALID/API_KEY_SERVICE_BLOCKED chỉ là dữ liệu giả để kiểm tra allowlist, không phải chẩn đoán key của người dùng.

Chưa có payload/diagnostics thực tế đủ bằng chứng xác định tham số, quyền key hoặc cấu hình dự án nào bị từ chối. Dừng chờ phê duyệt trước bất kỳ lần gọi Gemini thật nào; không yêu cầu gửi key vào chat.
