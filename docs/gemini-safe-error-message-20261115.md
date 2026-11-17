# google_error_message_safe — chưa gọi Gemini thật

## Các trường đã đọc trực tiếp

SDK `.venv/Lib/site-packages/google/genai/errors.py` dòng 89 gọi `_get_message(response_json)` để gán APIError.message. Helper tại dòng 121 lấy `message` ở top-level, hoặc `error.message` nếu không có top-level. SDK không tự lọc bí mật. Exception string chứa cả details, vì vậy không được in str(exc)/repr(exc)/traceback.

Launcher `safe_error_payload` đọc message của object lỗi đã chuẩn hóa: payload.error.message hoặc payload.message. `safe_sdk_error` truyền exc.message làm fallback khi message thiếu trong object đó. Đường HTTP thông thường được chặn và phân tích trước khi SDK tạo APIError. Trước lượt này, trường `message` của diagnostics đã cố ý thay nội dung gốc bằng vài thông báo cố định; không phải exc.message bị SDK xóa.

## Thay đổi

- `tools/gemini_live.py`: thêm `safe_google_message()` và trường `google_error_message_safe` trong mọi kết quả phân tích lỗi, kể cả thiếu message, JSON hỏng hoặc body quá lớn. Không sửa request builder hay tham số.
- Hàm chỉ nhận diện một số mẫu lỗi kỹ thuật; đầu ra gồm status enum đã kiểm tra, nhãn phân loại cố định và tên/đường dẫn API thuộc allowlist. Các nhãn gồm INVALID_JSON_PAYLOAD, UNKNOWN_JSON_FIELD, UNSUPPORTED_PARAMETER, UNSUPPORTED_REQUEST_FEATURE, VALUE_OUT_OF_RANGE, MISSING_REQUIRED_FIELD, INVALID_FINAL_TURN, INVALID_API_KEY, INVALID_ARGUMENT. Đây là **phân loại cục bộ của thông báo**, không phải Google ErrorInfo.reason và không được xem là nguyên nhân thật đã xác nhận.
- Chuẩn hóa tên snake_case sang camelCase và chỉ số array thành `[]`. Không giữ giá trị tham số, đoạn input, schema property tùy ý, key, URL, headers, prompt, tên/email/số điện thoại hoặc từ ngữ tự do trong message.
- Không in bản sao message sau regex xóa một phần, vì không bảo đảm tìm hết thông tin nhạy cảm. Chỉ các chuỗi cố định và tên trường được phê duyệt mới đi ra ngoài.
- Message không nhận diện được, không có, sai kiểu, có Unicode lỗi hoặc vượt 8192 byte: chỉ ghi loại lỗi và thông báo giữ kín nguồn. Body lỗi vẫn giới hạn 16384 byte. Legacy field `message` giữ hành vi cũ cho tương thích.

Ví dụ hoàn toàn từ mock, không phải thông báo Google của người dùng:

```json
{
  "google_error_message_safe": "INVALID_ARGUMENT: UNSUPPORTED_PARAMETER; fields=generationConfig.responseMimeType. Original text/values omitted."
}
```

Nếu không thể lọc an toàn:

```json
{
  "google_error_message_safe": "INVALID_ARGUMENT: source message withheld (unrecognised or unavailable)."
}
```

Không dùng labels trên để tự sửa model/config hoặc suy ra rằng API key thật sai. Khi thông báo không khớp mẫu, công cụ cố ý không giữ thêm nội dung.

## File và kiểm thử

Sửa `tools/gemini_live.py`, bổ sung assertion trong `tools/test_gemini_live.py`, thêm `tools/test_gemini_safe_message.py`; tài liệu này và liên kết trong hướng dẫn launcher. Không sửa adapter Gemini/OpenAI, FR-21/22/23/24, prompt, model, SDK, API version, giao diện, .env hoặc migration.

| Nhóm thực sự chạy | PASS | FAIL/ERROR |
| --- | ---: | ---: |
| Safe message mới | 10 | 0 |
| SDK diagnostics và RPC details | 16 | 0 |
| Launcher/generate-only helper dưới mock | 29 | 0 |
| SDK request compatibility | 7 | 0 |
| Tổng phương thức riêng biệt | **62** | **0** |

Log: `gemini-safe-message-offline-20261115.txt` (26 test gồm message/SDK/details), `gemini-safe-message-final-offline-20261115.txt` (10 message chạy lại sau bổ sung Unicode), `gemini-safe-message-launcher-offline-20261115.txt` (29), `gemini-safe-message-request-compat-offline-20261115.txt` (7). Không cộng trùng 10 bài chạy lại. Cú pháp Python và git diff --check đạt.

Mock bao gồm nested/flat message, exc.message fallback, thiếu message, unsupported parameter, unknown JSON field, field path, lỗi khoảng giá trị, thông báo chứa key/header/prompt/email/điện thoại giả, unknown text, JSON lỗi/quá lớn và Unicode lỗi. Test parity vẫn xác nhận request không thay đổi; không retry. Các giá trị key trong test đều là chuỗi giả do mock, không nhập/đọc key thật.

Không chạy CLI live/generate-only, không Gemini/OpenAI/PayOS API thật, không kết nối MySQL, không migration, không sửa .env, không commit/push. Không chạy bài staging fallback có migrate nội bộ. Chỉ mục vector SQLite tạm trong test RAG giữ tách biệt dữ liệu hiện có.

**Nguyên nhân HTTP 400 thật vẫn chưa xác định/BLOCKED.** Đây là bổ sung diagnostics đã kiểm thử offline, chưa phải bằng chứng đã sửa lỗi provider. Dừng chờ phê duyệt, không tự gọi lại Google.
