# Sửa deadline Gemini theo lỗi Google đã xác nhận

## Nguyên nhân và rà soát

Người dùng đã cung cấp thông báo Google: deadline đặt tay 8 giây thấp hơn tối thiểu 10 giây. Source SDK 2.34.0 `_api_client.py` thực sự chuyển HttpOptions.timeout (ms) thành header X-Server-Timeout (giây, làm tròn lên). Do đó timeout=8000 tạo deadline 8 giây, đúng nguyên nhân đã có bằng chứng, không còn suy đoán từ JSON/model.

Các vị trí cần sửa:

- ai_features/gemini.py: trước dùng max(1, int(remaining()*1000)), có thể chỉ có 8 giây hoặc ngắn hơn.
- ai_features/config.py: time_budget trước giới hạn 8 giây cho tất cả provider, không đủ cho một Gemini request hợp lệ, càng không đủ ba bước FR-21.
- tools/gemini_live.py: chưa bọc chung toàn bộ chuỗi thử bằng budget tổng; mỗi lời gọi độc lập không chứng minh được hạn toàn chuỗi.
- tools/gemini_studio_probe.py: đặt timeout=8000 trực tiếp; budget xử lý stream 15 giây.
- tools/gemini_test.py không tự đặt timeout, chỉ gọi launcher. index_spa dùng adapter chung; không có timeout 8 giây riêng. Timeout SQLite 3 giây, smoke HTTP local và subprocess tests không phải deadline Gemini, không sửa.

## Chính sách mới

| Mục | Cũ | Mới |
| --- | --- | --- |
| Gemini HttpOptions.timeout | Thường 8000 hoặc nhỏ hơn; Studio cố định 8000 | Mặc định 12000ms; không chấp nhận cấu hình dưới 10000ms |
| Gemini tổng time_budget | Tối đa 8 giây | Mặc định/tối đa 40 giây, riêng provider Gemini |
| OpenAI/mock time_budget | Tối đa 8 giây | Giữ nguyên |
| Studio stream probe | Request 8 giây, loop 15 giây sau setup | Request 12 giây; tổng xử lý 15 giây tính cả setup, có kiểm tra sau kết thúc |
| Nested context | Có thể đặt lại mốc kết thúc | Không bao giờ nới deadline cha |

Hàm gemini_timeout_ms không dùng max(10000, remaining_ms). Nó cấp phát min(timeout yêu cầu, số giây còn lại sau dự trù 250ms), làm tròn xuống giây nguyên để SDK ceil không làm server deadline vượt phần còn lại. Ví dụ còn 11.8 giây → cấp 11000ms; còn 10.5 → 10000ms; còn 10.1 → fallback trước khi tạo client. Mặc định yêu cầu 12000ms.

Các biến tùy chọn mới, không ghi vào .env: AI_GEMINI_TIMEOUT_SECONDS mặc định 40, bị chặn trên 40; AI_GEMINI_HTTP_TIMEOUT_MS mặc định 12000, thấp hơn 10000 bị từ chối. Cấu hình thấp vẫn phải fail closed, không tự tăng lên để vượt budget. AI_TIMEOUT_SECONDS tiếp tục quản lý giới hạn 8 giây của provider cũ.

Request hook HTTPX kiểm tra lại X-Server-Timeout ngay trước gửi, chặn deadline <10 giây hoặc vượt remaining sau setup/serialization. Không log header. Kiểm tra remaining sau phản hồi ngăn dùng kết quả đến muộn. Không retry, không nâng deadline cha, không gửi request tiếp khi phần còn lại quá ngắn. Các timeout I/O vẫn chịu cơ chế HTTPX/SDK; đây không phải tuyên bố Python đồng bộ có hard real-time cancellation ở cấp hệ điều hành.

FR-21 thường có tối đa 3 bước trong probe: document embedding → query embedding → generation; 3 × 12 = 36 giây, còn 4 giây dự trù trong tổng 40. Luồng website có thể chỉ cần query + generation nếu index đã sẵn. Khi cập nhật index gồm nhiều tài liệu, số embedding có thể lớn hơn 1; budget tổng không tự mở rộng, lượt tiếp theo sẽ fallback khi không đủ thời gian. Không thay quy tắc danh mục, chỉ mục hoặc chọn dịch vụ.

## Phạm vi bắt lỗi và diagnostics

_client chỉ tổng quát hóa lỗi khởi tạo client (không có HTTP), không còn except Exception bao quanh yield. SDK APIError phát sinh trong request có thể tới lớp launcher để đọc an toàn. structured/embed vẫn chuyển lỗi thành ProviderUnavailable/TimeoutError với thông điệp cố định, không đưa exception gốc ra User.

ProbeProvider trong tools/gemini_live.py thu diagnostics SDK bằng bộ lọc hiện có trước khi lớp structured/embed tổng quát hóa. Lỗi HTTP đã được transport ghi nhận không bị ghi trùng. Không in str(exc), raw response, headers, prompt hoặc key. Timeout không đủ sẽ không gọi SDK client/transport; fallback FR-22/23 vẫn dùng quy tắc như trước.

## File source thay đổi trong lượt này

1. ai_features/config.py — policy, budget riêng Gemini, pre-send check.
2. ai_features/gemini.py — timeout allocation, hook và phạm vi xử lý lỗi quanh yield.
3. tools/gemini_live.py — budget chung cho chuỗi, observer diagnostics SDK.
4. tools/gemini_studio_probe.py — 12 giây/request và kiểm tra budget 15 giây cả setup/stream completion.
5. ai_features/test_gemini.py — thêm kiểm thử deadline và fallback bằng mocks, cập nhật kỳ vọng timeout cũ.
6. tools/test_gemini_live.py — hỗ trợ đồng hồ giả trong transport fixture.
7. tools/test_gemini_request_compat.py — kiểm tra X-Server-Timeout và điều chỉnh fixture legacy để vẫn giữ public exception boundary.
8. tools/test_gemini_studio_probe.py — assertion timeout mới, kiểm thử completion đến muộn.

Không sửa SDK, model, API version, JSON prompt/payload, adapter OpenAI, logic Booking/Billing/PayOS, FR-24, settings.py, .env hoặc migration. Tài liệu Studio cũ được đính chính timeout, không tạo launcher mới.

## Kiểm thử và bằng chứng

**116 phương thức riêng biệt cuối cùng PASS, 0 FAIL/ERROR còn lại.**

- Policy/Gemini adapter/OpenAI provider: 36 phương thức (35 trong gemini-timeout-policy-final-20261115.txt và bài biên HTTP 10/12 giây trong gemini-timeout-wire-boundaries-20261115.txt).
- Launcher/generate-only/FR-21/22/23 dưới mock: 29 trong gemini-timeout-launcher-offline-20261115.txt.
- Studio: 17 (16 trong gemini-timeout-studio-offline-20261115.txt, bài late_stream_completion chạy riêng trên terminal).
- Serialization/safe-message/SDK errors/RPC details: 34; log gemini-timeout-compat-offline-20261115.txt và bản sửa fixture gemini-timeout-compat-final-20261115.txt. Không cộng trùng các bài chạy lại.

Các ca thực sự kiểm tra: cấu hình 8000 bị chặn trước tạo client; 10000/12000 tạo header 10/12 ở SDK thực dưới mock; ba bước FR-21 giả lập mỗi bước 12 giây nằm trong tổng 40, chỉ còn 4 thì request mới bị từ chối; parent budget không nới; slow setup/serialization bị chặn; FR-22/23 fallback không gọi SDK khi parent còn 8; SDK error vẫn đọc được ở launcher, User không nhận raw error; OpenAI giữ 8; response stream đến muộn không được PASS.

Các lỗi kiểm thử ban đầu đã giữ log: fixture legacy từng dựa vào _client tổng quát hóa lỗi, đã sửa fixture để giữ public boundary; bài wire sequence từng bị hai HTTP guard lồng không cùng budget chặn trước transport, đã chạy lại với guard socket chặn mạng thật và mock transport sở hữu đúng budget. Lần cuối không còn lỗi. Không sửa nghiệp vụ để làm test xanh.

FR-24 không sửa code lịch sử, CSRF, ownership hoặc quyền Admin. **Không chạy lại integration FR-24 có database** trong lượt này vì không được migration; không lấy việc đọc source làm PASS integration. MySQL/concurrency/Chrome/provider thật đều chưa chạy.

Không migration kể cả SQLite, không MySQL 3306/3310/3311, không PayOS hoặc Gemini/OpenAI thật, không nhập key thật. Test vector dùng SQLite tạm cô lập, không dữ liệu thật. Cú pháp Python và git diff --check được kiểm tra. Không commit/push.

## Nghiệm thu còn lại

Sau phê duyệt riêng: (1) Studio probe một request, xác nhận header deadline hợp lệ và nhận OK; (2) FR-21 generate-only một request; (3) FR-21 đầy đủ ba request với index giả riêng; (4) FR-22 và FR-23 mỗi lần một request với dữ liệu giả; (5) kiểm tra Chrome/history và quyền trên môi trường cô lập đã được chuẩn bị, không migration hoặc đụng dữ liệu hiện có tự ý. Không tự bật xuất dữ liệu thật hoặc billing. Dừng chờ duyệt.
