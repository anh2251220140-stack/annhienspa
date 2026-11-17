# FR-21: numeric grounding — 16/11/2026

## Kết luận và phạm vi

Bằng chứng người dùng cung cấp xác định phản hồi HTTP 200 đã được parse thành object, sau đó bị từ chối tại numeric grounding. Bộ so sánh cũ dùng tập chuỗi số theo regex nên `200000` không khớp `200.000` hoặc `200,000`. Mock tái hiện và chứng minh cách định dạng tương đương được chấp nhận sau sửa.

Không đọc nội dung phản hồi Gemini thật trong lượt này. Vì vậy chưa kết luận phản hồi thực tế trước đó chỉ mắc lỗi định dạng; các số không có căn cứ vẫn bị từ chối. Nghiệm thu API thật còn chờ phê duyệt.

## File source/test thay đổi trong lượt này

- `ai_features/numeric_grounding.py`: mới; bộ tách và đối chiếu giá trị số.
- `ai_features/integration.py:43`: thay so sánh chuỗi số bằng `numeric_claims_supported`; giữ nguyên kiểm tra answer, source IDs và mã diagnostics.
- `tools/test_numeric_grounding.py`: mới; 15 bài kiểm thử số liệu và GroundedProvider.
- `tools/test_gemini_stages.py:140`: bổ sung ca pipeline generate-only với hai cách định dạng giá, mỗi lần chỉ một HTTP request mock.

Các thay đổi chưa commit từ trước được giữ nguyên. Báo cáo và log `numeric-grounding-*-20261116.txt` là bằng chứng bổ sung, không ghi đè báo cáo cũ.

## Quy tắc số liệu

- Dùng `Decimal` từ chuỗi, không làm tròn, không tính số mới, không quy đổi đơn vị.
- Nhóm hàng nghìn phải đúng cấu trúc: nhóm đầu 1–3 chữ số, các nhóm sau đúng 3 chữ số. Trong ngữ cảnh tiền, `200000`, `200.000`, `200,000` tương đương.
- Hỗ trợ dấu thập phân chấm/phẩy và dạng kết hợp như `200.000,50 VND` / `200,000.50 VND`; không bỏ toàn bộ dấu một cách máy móc.
- Ngữ cảnh phần trăm và đơn vị đo được giữ riêng; `12.500%` là 12,5%, không phải 12.500%. `1.234 kg` không biến thành 1234 kg.
- Ngày, giờ, khoảng số, số mũ và chuỗi đặc biệt được giữ nguyên dạng để đối chiếu. Không biến `09:00` thành 900 hay ngày tháng thành số tiền.
- Số âm vẫn phân biệt số dương. Giá trị dài hơn độ chính xác Decimal mặc định vẫn đối chiếu chính xác vì không dùng phép toán làm tròn.
- Nguồn trần `1.234` thiếu ngữ cảnh là mơ hồ: không tự khẳng định là 1234. Câu trả lời có nhóm hàng nghìn chỉ được neo vào số nguyên rõ ràng trong nguồn. Dữ liệu mơ hồ có thể tiếp tục fallback an toàn.
- Mọi số trong câu trả lời phải đối chiếu được với tập nguồn truy xuất; giữ cách chọn tập nguồn như trước, không nới kiểm tra source ID.

## Kiểm thử offline thực chạy

150 bài khác nhau PASS, 0 FAIL, 0 ERROR. Một số bài chạy lại sau khi bổ sung kiểm thử; tổng sau đây đã loại trùng theo ID bài test.

| Nhóm | PASS | Bằng chứng |
| --- | ---: | --- |
| Numeric grounding / GroundedProvider | 15 | `numeric-grounding-core-final-20261116.txt`; chạy lại đủ 15 sau chỉnh token cuối cùng, PASS |
| Diagnostics an toàn | 26 | `numeric-grounding-offline-20261116.txt` (ngoài các bài numeric trùng) |
| FR-21 pipeline và mã giai đoạn | 19 | `numeric-grounding-fr21-stages-20261116.txt` |
| Launcher FR-21/22/23 và fallback | 29 | `numeric-grounding-launcher-regression-20261116.txt` |
| Gemini adapter/deadline và OpenAI compatibility | 36 | `numeric-grounding-adapter-regression-20261116.txt` |
| Request compatibility | 8 | `numeric-grounding-compat-final-20261116.txt` (ngoài các bài numeric trùng) |
| Studio probe offline | 17 | `numeric-grounding-studio-regression-20261116.txt` |

Đã kiểm tra cú pháp Python cả 4 file source/test và `git diff --check`.

Các ca chính: 200000 → 200.000/200,000 PASS; 200000 → 250.000 FAIL theo mong đợi; 60 phút → 90 phút FAIL theo mong đợi; thay đổi số thập phân, thêm số không có nguồn, sai source ID, đổi ngày giờ/phần trăm đều bị từ chối. Các ca từ chối là test PASS khi hành vi từ chối đúng.

## Phần chưa nghiệm thu / bảo toàn

- BLOCKED theo yêu cầu: xác nhận lại phản hồi Gemini thật; không chạy live/generate-only thật.
- Chưa chạy lại kiểm thử tích hợp database FR-24/lịch sử, vì lượt này không khởi tạo database hoặc migration. Không coi các luồng database này là PASS mới. Hồi quy launcher/adapter và fallback FR-22/23 chạy bằng mock, không thay thế nghiệm thu database.
- Không thay model, SDK, API version, timeout, prompt, JSON mode, OpenAI adapter, nghiệp vụ FR-22/23, quyền/lịch sử FR-24 hoặc giao diện.
- Không nhập key thật, gọi Gemini/OpenAI/PayOS thật, kết nối MySQL, migration, sửa `.env`, commit hoặc push.

Dừng chờ duyệt nghiệm thu API thật.
