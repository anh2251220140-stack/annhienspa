# Đối chiếu request Gemini 3.5 Flash-Lite

## Kết luận có bằng chứng và giới hạn

Phát hiện trực tiếp `ai_features/gemini.py`, dòng 72 trước sửa, đặt `temperature=0` trong GenerateContentConfig. SDK 2.34.0 thực sự serialize nó thành `generationConfig.temperature: 0.0`; không chỉ là giá trị nằm ở Python. Hướng dẫn model liên kết tới trang [API changes and parameter updates](https://ai.google.dev/gemini-api/docs/whats-new-gemini-3.6#api-changes-and-parameter-updates), yêu cầu loại bỏ temperature/top_p/top_k cho Gemini 3.5 Flash-Lite. Đã bỏ đúng một tham số này ở adapter Gemini; không sao chép cấu hình OpenAI vào Gemini.

**Không đủ bằng chứng kết luận temperature là nguyên nhân duy nhất/chắc chắn của HTTP 400 người dùng gặp.** Tài liệu Google hiện nói sampling controls deprecated và bị bỏ qua ở các model này, còn các thế hệ tương lai mới trả lỗi. Request thực tế có 400 INVALID_ARGUMENT nhưng chưa có thông báo gốc xác định tham số. Vì vậy đây là sửa sai lệch với hướng dẫn migration có bằng chứng, không phải xác nhận live rằng HTTP 400 đã hết. Mock trả 400 cho request cũ là fixture kiểm thử, không phải tái hiện response Google thật hoặc chứng minh quan hệ nhân quả. Không tự đổi model, endpoint, SDK, max_output_tokens hoặc JSON mode để đoán lỗi.

Nguồn chính thức đã đối chiếu:

- [Model](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite): structured outputs và thinking được hỗ trợ, output tối đa 65536 token.
- [API changes](https://ai.google.dev/gemini-api/docs/whats-new-gemini-3.6#api-changes-and-parameter-updates): yêu cầu bỏ sampling controls; request kết thúc bằng non-empty model turn bị 400.
- [Migration riêng Flash-Lite](https://ai.google.dev/gemini-api/docs/whats-new-gemini-3.6#migrate-to-gemini-3-5-flash-lite): thinking minimal mặc định, loại bỏ tham số deprecated.

Chỉ truy cập tài liệu công khai qua công cụ duyệt web; không có request inference/embedding thực tế tới Gemini.

## Đối chiếu từng trường từ JSON SDK dưới mock

| Trường | Trước sửa | Sau sửa / nhận định |
| --- | --- | --- |
| temperature | 0.0 được serialize | Không gửi, theo hướng dẫn migration |
| top_p / top_k | Không gửi | Không gửi |
| frequency_penalty / presence_penalty | Không gửi | Không gửi; không có bằng chứng đây là nguyên nhân |
| response_mime_type | application/json | Giữ nguyên; model hỗ trợ structured output |
| response_schema / response_json_schema | Không gửi | Giữ nguyên; hợp đồng JSON nằm trong instruction, không tự thêm schema |
| max_output_tokens | 1500 | Giữ nguyên, dưới output limit công bố; chưa có bằng chứng bị từ chối vì trường này |
| thinking_config | Không gửi | Giữ mặc định model, không thêm thinking_budget |
| contents | Một Content role user | Giữ nguyên |
| parts | Mỗi Part có text dạng string | Giữ nguyên, không ảnh/tool/attachment |
| turn cuối | user | Không có model prefill bị cấm |
| systemInstruction | Text Part riêng | Giữ nguyên |
| tools | Không gửi | Giữ nguyên; automatic function calling bị tắt tại SDK |

SDK cài trong `.venv`: `google-genai==2.34.0`, kiểm tra bằng importlib.metadata và test. HttpOptions dùng API `v1beta`, endpoint cố định Developer API, attempts=1, không proxy/redirect. Không nâng cấp thư viện hoặc chuyển Interactions API. SDK nhận temperature không đồng nghĩa model còn khuyến nghị dùng nó; cần kiểm tra JSON wire và tài liệu model riêng.

## File thay đổi và cách sửa

- `ai_features/gemini.py`: bỏ `temperature=0` ở GenerateContentConfig, thêm giải thích. Cấu hình hiện tại ở dòng 74; dòng 79 vẫn gọi generate_content với chuỗi JSON dữ liệu được SDK chuyển thành user Content.
- `tools/test_gemini_request_compat.py`: 5 test mới, SDK thật/HTTPTransport mock: hình dạng Content, tham số serialize, request cũ so với mới chỉ khác temperature, 400 vẫn an toàn, SDK/API version không đổi.
- `docs/gemini-generate-only-20261115.md`, `docs/gemini-live-launcher-20261115.md`: cập nhật cấu hình và liên kết báo cáo này.

Không thay đổi tools/gemini_live.py, adapter OpenAI, dữ liệu, FR-24, UI, model, migration hoặc .env trong lượt này. Các nghiệp vụ FR-21/22/23 giữ nguyên; cả ba dùng adapter Gemini chung nên cùng nhận cấu hình đã bỏ tham số deprecated. Fallback và kiểm tra nguồn/JSON vẫn hoạt động.

## Kiểm thử thực sự đã chạy

| Nhóm | PASS | FAIL/ERROR | Log |
| --- | ---: | ---: | --- |
| SDK wire compatibility mới | 5 | 0 | gemini-request-compat-offline-20261115.txt |
| Launcher / generate-only / FR-21/22/23 / chặn DB / diagnostics | 28 | 0 | gemini-request-compat-launcher-regression-20261115.txt |
| GeminiAdapterTests và OpenAI ProviderTests hiện có | 24 | 0 | gemini-request-compat-adapter-regression-20261115.txt |
| Tổng phương thức riêng biệt | **57** | **0** | Không chạy lại 69 bài MySQL |

Không sử dụng runner tạo database hoặc bài fallback staging có migrate nội bộ. Chỉ dùng cấu hình cô lập, unittest/SimpleTestCase và HTTPTransport mock. Có vector SQLite tạm riêng trong bài RAG như trước; không kết nối MySQL, không migrate, không đọc dữ liệu thật. Các chuỗi key trong mock đều giả, không yêu cầu/nhập/đọc key thật. Google/OpenAI/PayOS API thực tế: **0 request**.

Sau mock: chỉ khẳng định JSON request đã phù hợp hơn với chỉ dẫn migration và fallback không hỏng. Việc Gemini thật chấp nhận request hoặc nguyên nhân 400 tài khoản vẫn **CHƯA XÁC MINH**, cần người dùng phê duyệt riêng nếu muốn gọi lại generate-only tối đa một request. Dừng, không tự chạy live.
