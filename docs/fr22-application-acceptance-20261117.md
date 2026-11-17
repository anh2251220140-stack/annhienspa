# FR-22 — chuẩn bị nghiệm thu Gemini qua ứng dụng, 17/11/2026

## Trạng thái

Offline: 40 PASS, 0 FAIL, 0 ERROR. Chưa chạy live, chưa nhập/đọc key thật. Không tuyên bố đã nghiệm thu FR-22 với Gemini thật.

## File mới

- `tools/fr22_application_test.py`: launcher live opt-in, fixture tài khoản/hồ sơ/lịch sử/danh mục giả, Django Test Client xác thực + CSRF, kiểm tra POST/SQLite/readback, chỉ một HTTP request.
- `ai_features/test_recommendation_integration.py`: 12 bài offline đi qua view/service/GeminiProvider/SDK thật, chỉ mock HTTP transport.
- `tools/test_fr22_application_launcher.py`: kiểm tra khởi tạo trong tiến trình Python mới, không nạp dotenv, migration vào SQLite tạm, HTTP mock, dữ liệu giả và cleanup thư mục do test sở hữu.

Không sửa backend ứng dụng, URL production, adapter Gemini, launcher synthetic cũ, .env, model hoặc migration. Không sửa FR-21/23/24 và các chức năng đã PASS.

## Tái sử dụng và giới hạn GET

POST thực tế gọi `assistance_views.recommendations` → `assistance.recommend` → `external_provider` → `GeminiProvider.structured`. Không thay service hoặc provider bằng kết quả giả trong test mới. Offline chỉ thay HTTPX send bằng dispatcher tới MockTransport để runner vẫn chặn socket.

Tái sử dụng `gemini_live.Budget` và `isolation`, `openai_test.hidden_input` và `locked_environment`. Các hàm này chỉ được dùng làm hạ tầng; không chọn/gọi OpenAI.

API production `/api/ai/recommendations/` CHỈ POST; GET hiện trả 405. Bộ nghiệm thu kiểm tra rõ điều này và không tự sửa backend. GET `/acceptance/recommendations/<id>/` chỉ nằm trong URLConf của tiến trình nghiệm thu, đọc AIRecommendation đúng chủ tài khoản để kiểm chứng lưu dữ liệu. GET này không được cài vào website. Một PASS từ launcher không phải bằng chứng production có API GET hay giao diện lịch sử đề xuất; nếu cần chức năng đó phải được duyệt riêng.

## Cô lập và giới hạn

- Fresh settings.configure, không import config.settings hoặc .env. Xóa biến môi trường kế thừa bằng allowlist, không nhận key qua CLI/env/file.
- Tạo thư mục TemporaryDirectory mới, SQLite riêng, media riêng; đóng kết nối và dọn đúng thư mục do launcher sở hữu sau khi hoàn tất.
- Chỉ cho phép default SQLite đã định danh; từ chối ORM alias/vendor/đích khác. Chặn các connector MySQLdb và socket ngoài phạm vi; bao gồm 3306/3307/3310/3311, MariaDB hoặc network phụ.
- Chỉ mở mạng đồng bộ trong HTTP send đã kiểm tra tới HTTPS generativelanguage.googleapis.com:443, đúng endpoint generateContent và model hiện tại; không redirect, embedding hoặc provider thay thế.
- Budget 1: trước mỗi HTTP send kiểm tra số request, origin và giới hạn body; không retry, kể cả 429/lỗi xác thực. Input body tối đa 6000 byte; output tối đa 1500 token theo adapter hiện có.
- AI_PAID_CALLS_APPROVED=False. AI_PERSONALIZATION_EXPORT_APPROVED chỉ True trong override_settings bọc ca nghiệm thu dữ liệu giả, không đổi cấu hình website. AI_REVIEW_EXPORT_APPROVED=False.
- PayOS bị chặn. Không gửi dữ liệu khách hàng thật, key, headers hoặc exception nguyên văn vào báo cáo. Chỉ in trạng thái và kiểm chứng boolean/số lượng, không in lời giải thích Gemini hoặc payload.

## Kết quả offline

1. `.venv/Scripts/python.exe -B tools/ai_tests.py ai_features.test_recommendation_integration.RecommendationApplicationTests ai_features.test_assistance.AssistanceTests`: 39 PASS (12 mới + 27 Assistance). Evidence: `docs/ai-regression-results-20261115-211717638344.json` — tên ngày do runner hiện có sinh.
2. `.venv/Scripts/python.exe -B -m unittest tools.test_fr22_application_launcher -v`: 1 PASS, kiểm tra fresh process startup và cleanup, không gọi main/live.
3. Python AST syntax và git diff --check: PASS. Django check đạt; No changes detected giữa model và migration. Không tạo migration mới, chỉ áp dụng migration hiện có vào SQLite tạm.

Bao phủ: authenticated POST + CSRF; request serialized chỉ có preferences, candidate catalog và completed service IDs giả; ngân sách/nhu cầu/thời lượng/active; lưu mode=ai và items; GET kiểm chứng đúng chủ không phát sinh AI; ngăn user khác; quota/auth/timeout/JSON sai không được coi PASS; dịch vụ ẩn/sai nhu cầu/quá ngân sách/thời lượng bị loại; chưa phê duyệt hoặc thiếu key không gửi HTTP; chặn MySQL/raw socket/alternate origin và HTTP request thứ hai.

## Lệnh live để người dùng chạy SAU khi duyệt

```powershell
Set-Location 'D:\Redesign An Nhiên Spa Home'
.\.venv\Scripts\python.exe -B tools/fr22_application_test.py live
```

Không chạy cùng manage.py hoặc server đang dùng dữ liệu thật. Launcher tự tạo môi trường SQLite mới, không cần bật website hoặc dùng schema MySQL.

Tự kiểm tra dự án của key tại Google AI Studio: Free Tier, billing đã tắt và còn quota model. Khi launcher hỏi, nhập chính xác `FREE TIER VERIFIED; BILLING DISABLED`. Nếu chưa xác minh, không xác nhận. Launcher không có quyền kiểm tra billing Google và không thể bảo đảm miễn phí chỉ bằng cờ.

Nhập key vào dòng getpass ẩn trong terminal, không đưa vào chat, command line, .env hoặc file. Nếu nhập ẩn không khả dụng, công cụ dừng. Sau khi chạy không thực hiện lần hai hoặc thử provider khác tự động.

## Tiêu chí nghiệm thu

PASS của ca ứng dụng chỉ khi tất cả đạt: đúng một HTTP Gemini được chấp nhận; POST HTTP 200 với mode=ai; 1–3 dịch vụ thật trong danh mục giả đáp ứng điều kiện; không trùng ID; reason hợp lệ; một AIRecommendation lưu đúng khách, mode/items/IDs khớp POST; GET nghiệm thu đọc đúng dữ liệu; người khác bị từ chối; GET không tạo thêm request hoặc bản ghi.

HTTP lỗi/timeout/quota/JSON không hợp lệ, mode=rule, sai điều kiện, lưu sai hoặc đọc sai đều FAIL. Key/Free Tier không được xác nhận thì dừng trước gọi API. Production GET vẫn là 405 và được ghi rõ trong report, không tự coi đã triển khai GET production.

Kết quả live hiện tại: NOT TESTED. Chờ duyệt trước một lần gọi thật.
