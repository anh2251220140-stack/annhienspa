# Gói tài liệu nghiệm thu Giai đoạn 4 được đề xuất công bố

Ngày rà soát: 27/10/2026. Chỉ biên tập Markdown; không sửa code, dữ liệu hay
cấu hình đang chạy. Không thực hiện git add, commit hoặc push.

## Danh sách chính xác nên git add

1. `.env.example`
2. `docs/phase4-acceptance.md`
3. `docs/phase4-publication.md`
4. `docs/phase4.md`
5. `docs/phase4-inventory.md`
6. `docs/invoice-flow.md`
7. `docs/promotion-diagnostics.md`
8. `docs/promotion-usage.md`
9. `docs/payos-feedback.md`
10. `docs/payos-qr.md`
11. `tools/audit_git_secrets.py`

Đây là danh sách cho lần commit tài liệu này, không phải lệnh đã chạy. Không dùng
`git add .`, `git add docs/` hoặc `git add tools/`. Trước commit, kiểm tra lại
`git diff --cached` để chắc chắn index không chứa file ngoài danh sách.

Thông điệp đề xuất: **Hoàn tất hồ sơ nghiệm thu Giai đoạn 4 và ẩn danh tài liệu công khai**.

## Phân loại docs

| Nhóm | Xử lý |
|---|---|
| Chín Markdown trong danh sách trên | Nên commit; kết luận hiện tại tách khỏi lịch sử, ca thực tế đã ẩn danh. |
| `phase1-analysis.md`, `phase2.md`, `phase3.md`, `phase3-figma-inventory.md`, `password-reset.md` | Hồ sơ giai đoạn trước, chưa duyệt công bố trong lượt này; cần rà soát riêng trước khi thêm file chưa được theo dõi. |
| `invoice-flow-data-verification.json`, `payos-button-audit.json`, `promotion-diagnostics-data.json`, `promotion-usage-audit.json`, `phase4-final-data-verification.json`, `phase4-migration-verification.json` | Giữ cục bộ. Có dữ liệu đối chiếu nghiệp vụ, định danh, thời điểm hoặc dấu vân tay dữ liệu; chỉ xuất bản bản tổng hợp đã ẩn danh nếu cần. |
| `historical-invoice-plan.example.json` | Cần ẩn danh/tham số hóa trước khi công bố; tên example không bảo đảm các khóa bản ghi bên trong là giả. Không sửa JSON trong lượt này. |
| Các JSON còn lại trong docs | Chưa duyệt công bố; kiểm tra định danh, đường dẫn và dữ liệu trả về trước khi dùng làm minh chứng công khai. |
| Mọi ảnh PNG/JPG và thư mục `*-ui/` | Giữ cục bộ; phải xem từng ảnh và che thông tin liên hệ, tài khoản, QR/link, giao dịch trước khi xuất bản. Chưa xác nhận toàn bộ ảnh đã sạch. |
| Các log `*-tests.txt`, `*-results.txt` và log kiểm thử khác | Giữ cục bộ; chỉ trích kết quả tổng hợp vào Markdown. Muốn công bố phải lọc đường dẫn máy, thông tin tài khoản và payload trước. |
| `srs-extracted.txt` | Tài liệu nguồn cục bộ; cần kiểm tra thông tin cá nhân và quyền công bố riêng. |

Các đường dẫn log/JSON/ảnh được nhắc trong hồ sơ lịch sử là chứng cứ cục bộ,
không phải yêu cầu đưa chúng vào Git. Việc loại khỏi danh sách không tự làm file
được ignore hoặc xóa file đã tracked. Không chỉnh .gitignore trong phạm vi lượt này.

## Phân loại tools

| File | Kết luận |
|---|---|
| `audit_git_secrets.py` | Nên commit. Đọc bí mật từ môi trường để so khớp, chỉ in tên biến và vị trí phát hiện; không chứa khóa thật, không gọi Django/MySQL/payOS. Chỉ phát hiện các giá trị hiện tại dài từ 8 ký tự; không thay thế kiểm toán mọi bí mật lịch sử. |
| `audit_payos_button.py` | Giữ cục bộ hiện tại. Gắn cố định một hóa đơn thật và ghi báo cáo trạng thái/số tiền vào docs; cần tham số hóa và giới hạn đầu ra trước khi công bố. |
| `audit_promotion_usage.py` | Giữ cục bộ hiện tại. Gắn cố định hóa đơn/mã kiểm tra; xuất dữ liệu nghiệp vụ và fingerprint. Cần làm sạch trước khi công bố. |
| `backup_phase4.py` | Chưa đưa vào commit này. Không chứa mật khẩu thật nhưng phụ thuộc đường dẫn MySQL Windows; ZIP/dump tạo ra có thể chứa dữ liệu cá nhân. Cần quy định lưu trữ và quyền truy cập backup trước khi chia sẻ công cụ. |
| `verify_phase4_backup.py` | Chưa đưa vào commit này. Phụ thuộc database/backup cục bộ, ghi metadata đối chiếu vào docs; cần rà soát khả năng tái sử dụng và đầu ra trước khi công bố. |
| `check_mysql.py` | Công cụ chẩn đoán nguồn không chứa khóa thật; không đề xuất thay đổi hoặc thêm lại trong commit tài liệu này. |
| `setup_mysql.py` | Công cụ khởi tạo nguồn không chứa khóa thật; có thao tác DDL và ghi .env khi khởi tạo. Không chạy khi nghiệm thu, không đề xuất thay đổi hoặc thêm lại trong commit này. |

Mã nguồn công cụ và sản phẩm đầu ra là hai phạm vi khác nhau: `.env`, SQL dump,
ZIP backup, chứng từ, QR/payload và log giao dịch thật phải giữ cục bộ dù công cụ
tạo ra chúng có thể được công bố sau rà soát.

## Cấu hình mẫu và bằng chứng

`.env.example` chỉ có tên biến, giá trị mặc định cục bộ và placeholder SMTP ở
example.com; các khóa payOS, mật khẩu MySQL/SMTP và Django secret để trống.
DEBUG=true và URL localhost trong file mẫu phục vụ phát triển, không mô tả cấu
hình nghiệm thu hiện tại hay cấu hình production. Không sao chép .env thật vào Git.

Bảy vị trí override_settings đã được xác nhận là khóa mock trong lần rà soát:
`billing/test_phase4.py:21`, `billing/test_invoice_flow.py:61,190`,
`billing/test_promotion_usage.py:35,178`, `billing/test_payos_feedback.py:11`,
`billing/test_qr.py:19`. Không đề xuất thêm các file test vào commit tài liệu này.

Kết quả 134/134 và đối chiếu main 1552cca thuộc lần rà soát gần nhất; lượt này
không chạy lại Django tests, không truy vấn dữ liệu nghiệp vụ hoặc gọi payOS.
Xem [biên bản nghiệm thu](phase4-acceptance.md) để biết giới hạn còn tồn tại.

Kiểm tra tài liệu ngày 27/10/2026: 11 file đề xuất không khớp các giá trị bí mật
hiện tại, không có email ngoài miền mẫu hoặc chuỗi số điện thoại theo mẫu kiểm
tra; liên kết Markdown nội bộ hợp lệ. `git diff --check` đạt, index trống.
Đã chạy lại `audit_git_secrets.py`: .env được ignore, không có trong index/lịch
sử; không phát hiện giá trị hiện tại của sáu biến bí mật được kiểm tra trong
working tree không bị ignore, index hoặc các blob lịch sử Git. Không in giá trị
bí mật. Phép quét này không bao phủ bí mật cũ đã thay đổi hoặc chữ nằm trong ảnh;
ảnh và chứng từ thô không nằm trong danh sách công bố.
