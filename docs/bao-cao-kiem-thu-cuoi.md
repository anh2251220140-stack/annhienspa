# An Nhiên Spa Home — Báo cáo kiểm thử tổng hợp Bước 3

Ngày tổng hợp **25/11/2026**. Mốc đối chiếu mã nguồn trên nhánh `main` là `f465acb`. Các số liệu lấy từ những đợt kiểm thử đã lưu. Một số bộ kiểm thử chạy lại cùng ca ở các thời điểm khác nhau, vì vậy mỗi dòng có số liệu riêng.

## Kết quả hệ thống và thanh toán

| Phạm vi | Kết quả đã lưu | Bằng chứng và giới hạn |
|---|---|---|
| Nghiệp vụ Django trên MySQL kiểm thử | **205/205 đạt** ở mốc hồi quy đã nghiệm thu | Accounts 17, core 101, billing 70 và FR-14 17. Đây là mốc lịch sử được ghi trong [README](../README.md#kiểm-thử-và-xác-minh). |
| Hóa đơn, giao dịch và webhook payOS | **99/99 đạt** ở đợt hồi quy hóa đơn | [Log Django](invoice-flow-full-tests.txt) và [tài liệu luồng hóa đơn](invoice-flow.md). |
| QR hết hạn và thông báo hóa đơn | **24 ca backend**, **18 ca JavaScript** và **146 phép kiểm tra Chrome cô lập** đạt ở đợt sửa `f465acb` | Số liệu của đợt sửa đã báo cáo. Đối chiếu phạm vi qua [test QR](../billing/test_qr.py), [test hóa đơn](../billing/test_invoice_flow.py), [test thông báo JS](../tools/test_invoice_feedback.cjs) và [kiểm tra UI](../tools/check_user_invoice_ui.py). Chưa có log của đợt này trong `HEAD` để xác minh độc lập các số đếm. |
| Media và avatar sau tích hợp Vercel Blob | **50/50** ca storage và HTTP Django đạt. **21/21** ca local/Docker đã chạy đạt, **2 ca symlink bỏ qua** trên Windows. **29/29** ca frontend đạt. | [Báo cáo media](vercel-private-blob-20261123.txt). Báo cáo ghi rõ các ca bảo vệ ảnh và các bước nghiệm thu Production. |
| Cấu hình Production | Chủ dự án xác nhận đã đặt `AI_RAG_DIRECTORY=/tmp/annhien-rag` và deploy thành công. | Chưa có bằng chứng xác minh việc tạo hoặc cập nhật SQLite, truy xuất vector và hành vi qua nhiều lần khởi tạo Vercel ở cấu hình này. |

## Đánh giá AI theo SRS mục 7.1

| Chức năng | Kết quả đã lưu | Cách đọc kết quả |
|---|---|---|
| FR-21 — Chatbot | **30/30** câu đạt theo kết quả đã ghi, gồm **15 Gemini** và **15 dự phòng** | Đạt ngưỡng **≥80%** trên bộ câu hỏi đã chấm theo cả hai chế độ. [Bảng 30 câu](fr21-acceptance-30-20261118.csv). |
| FR-22 — Gợi ý liệu trình | **40/40** ca offline đạt ở mốc kiểm thử ứng dụng. Đợt hồi quy sau đó chạy **232 ca**, **231 đạt**, **1 bỏ qua** do SQLite thiếu `select_for_update`. | [Nghiệm thu tích hợp FR-22](fr22-application-acceptance-20261117.md). Log hồi quy 22/11 hiện lưu cục bộ trong `docs/fr22-numeric-acceptance-final-20261122.txt`. Kết quả offline kiểm tra lọc theo nhu cầu, ngân sách, dữ liệu nguồn và phương án dự phòng. Nghiệm thu Gemini thật trên Production hiện tại chưa được xác minh trong đợt tổng hợp. |
| FR-23 — Phân tích cảm xúc đánh giá | **49/50 đúng (98%)**, đủ 50 phản hồi Gemini. Ngưỡng SRS **≥75%**. Mẫu `R36` có nhãn `negative` và dự đoán `neutral`. | Cột `label_status` ghi `HUMAN_APPROVED` cho cả 50 mẫu. Tệp hiện có chưa xác nhận danh tính người phê duyệt nhãn. [Bảng 50 đánh giá](fr23-label-review-50-20261118.csv). |
| FR-21–24 — Hồi quy backend AI | **57/57 đạt** trên MySQL kiểm thử cổng 3311, dùng dịch vụ AI mô phỏng | Bao phủ truy xuất RAG, ràng buộc dữ liệu, gợi ý, phân tích và quyền truy cập lịch sử. [Kết quả theo từng ca](ai-mysql-acceptance-20261115-132841/results.json) · [Báo cáo triển khai AI](ai-implementation-20261115.md). |

## Bàn giao Bước 3

- Nộp báo cáo Word cùng [repo GitHub chính thức](https://github.com/anh2251220140-stack/annhienspa) và [link deploy](https://annhienspa-sepia.vercel.app/). Gửi mật khẩu demo riêng cho giảng viên.
- Nếu cần nộp mã dạng ZIP, rà soát `git ls-tree -r --name-only HEAD`, rồi dùng `git archive --format=zip --output=AnNhienSpa-source.zip HEAD` sau khi các tài liệu cần nộp đã được commit. Kiểm tra lại danh sách tệp và mở thử ảnh/font trong ZIP vì repo có tài nguyên Git LFS. [GitHub Docs về Git LFS trong gói mã nguồn](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/managing-git-lfs-objects-in-archives-of-your-repository).
- Chỉ dùng `.env.example` và `.env.docker.example` cho tài liệu cấu hình. Giữ khóa, dữ liệu vận hành, bản dump, phiên đăng nhập và bản sao CSDL chat ngoài hồ sơ nộp.

## Ba luồng cần giải thích khi bảo vệ

### Đặt lịch chống trùng

Khi khách bấm đặt, Django mở transaction và dùng `select_for_update()` để khóa bản ghi dịch vụ, nhân viên và khách hàng trong MySQL. Trong transaction, hệ thống kiểm tra nhân viên có phụ trách dịch vụ, ca làm và ca nghỉ, rồi kiểm tra khoảng giờ có giao với lịch chưa hủy của nhân viên hoặc khách. Nếu hai yêu cầu cùng tranh một khung giờ, yêu cầu sau phải đợi khóa và kiểm tra lại sau khi yêu cầu trước ghi xong. Việc khóa bản ghi cha xử lý được cả trường hợp khung giờ chưa có lịch nào. [Luồng đặt lịch](../appointments/services.py) · [Kiểm tra lưu lịch hẹn](../appointments/models.py).

### Webhook payOS

Đường dẫn đưa khách quay về website phục vụ giao diện. Khi payOS gửi webhook, Django xác minh chữ ký bằng SDK, tìm phiên theo `orderCode` và đối chiếu số tiền, VND cùng mã liên kết thanh toán nếu phiên có lưu mã. Giao dịch hợp lệ cập nhật trạng thái hóa đơn trong transaction. Thông báo lặp được nhận diện qua trạng thái đã xử lý. Trường hợp tiền về phiên đã đóng hoặc có xung đột được đưa vào đối soát. Lịch hẹn vẫn được hoàn thành theo luồng nghiệp vụ riêng. [Điểm nhận webhook](../billing/views.py) · [Xử lý giao dịch](../billing/services.py).

### RAG và câu trả lời dự phòng

Chatbot lấy nguồn công khai của spa, như dịch vụ đang hoạt động, sản phẩm và ưu đãi hiện hành. Câu có ý định hoặc tên/mã khớp dùng dữ liệu danh mục trực tiếp. Khi cần tìm theo ngữ nghĩa, hệ thống tạo vector câu hỏi, tìm đoạn liên quan trong chỉ mục SQLite bằng độ tương đồng cosine rồi gửi nguồn phù hợp cho Gemini. Sau khi Gemini trả lời, hệ thống kiểm tra nguồn còn hiện hành. Khi thiếu nguồn, câu trả lời trống, hết thời gian hoặc nhà cung cấp lỗi, chatbot trả thông báo dự phòng. Đường dẫn chỉ mục đã cấu hình là `/tmp/annhien-rag`, nằm trong vùng lưu trữ tạm có quyền ghi của Vercel. [Truy xuất RAG](../ai_features/rag.py) · [Luồng hội thoại](../ai_features/chat.py) · [Vercel Functions](https://vercel.com/docs/functions/runtimes#file-system-support).
