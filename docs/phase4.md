# Giai đoạn 4 — hóa đơn, thanh toán, đánh giá và báo cáo

> **Phạm vi công khai — cập nhật hồ sơ ngày 27/10/2026.** Kết luận hiện tại nằm trong
> [Biên bản nghiệm thu cuối Giai đoạn 4](phase4-acceptance.md): thanh toán thật đã
> được xác nhận, chỉ ghi nhận một lần; khuyến mãi dùng đúng một lượt; hồi quy gần
> nhất 134/134 đạt; code main tại 1552cca. Lượt này chỉ cập nhật tài liệu, không
> chạy lại tests hoặc gọi payOS.
>
> **Toàn bộ nội dung lịch sử bên dưới phản ánh thời điểm ghi trong từng mục**, không
> phải trạng thái hiện tại. Các câu “chưa thanh toán”, “chỉ mock”, “chưa push” hoặc
> “chưa có giới hạn lượt” chỉ có hiệu lực tại mốc đó. Không dùng hướng dẫn cũ để
> thao tác trên hóa đơn đã thanh toán. Hành vi hiện tại: QR nhúng, hạn tối đa 600
> giây (không vượt giờ hẹn), polling chỉ đọc MySQL, đối soát provider chủ động.
>
> Mã HD-A/HD-B/HD-C và LH-A/LH-B/LH-C/LH-D là bí danh trong tài liệu, không phải ID
> để truy vấn. HD-TEST/LH-TEST là fixture. Định danh người, số tiền và ngày/giờ hẹn
> đã được ẩn danh; diễn biến kỹ thuật và các mốc kiểm thử được giữ lại. JSON/log/ảnh
> được nhắc tới là chứng cứ cục bộ, không thuộc gói Markdown công khai.

## Hồ sơ lịch sử (giữ theo mốc triển khai)

Cập nhật ngày 23/10/2026. Tiếp tục source hiện có, không commit/push. Đọc SRS/HLD qua `docs/srs-extracted.txt`, models/ERD và prompt Giai đoạn 4. Bảng đối chiếu Figma/backend: `docs/phase4-inventory.md`.

## Phần đã triển khai

- Admin xác nhận lịch mới: tạo Invoice và InvoiceDetail trong cùng transaction; OneToOne và khóa lịch chống trùng. Lưu tên/giá dịch vụ lúc lập hóa đơn. Chỉ dịch vụ, không đưa sản phẩm giới thiệu vào hóa đơn. Tiền dùng Decimal.
- Hóa đơn User: danh sách, tìm kiếm, lọc trạng thái, phân trang, chi tiết theo quyền sở hữu, ưu đãi được kiểm tra ở backend; hiển thị lịch sử thanh toán. ID trong URL được kiểm tra quyền, không dùng sessionStorage làm dữ liệu nghiệp vụ.
- Hóa đơn/thanh toán Admin: bảng Figma, thống kê, tìm kiếm/ngày/trạng thái, phân trang và modal chi tiết. Admin ghi nhận tiền mặt đúng số tiền, lưu người thu/thời điểm/tham chiếu; transaction và khóa chống thu lặp. Admin không tự đánh dấu online thành công.
- payOS: adapter SDK chính thức 1.1.0; tạo giao dịch chờ với order code duy nhất; tái sử dụng phiên đang chờ; lưu mã trước gọi API để không mất dấu giao dịch khi timeout. Trả checkout URL thật từ SDK khi cấu hình sẵn sàng. Không còn QR/nút thanh toán thành công giả.
- Webhook: xác minh chữ ký bằng SDK, đối chiếu order code/số tiền/VND/payment link; xử lý lặp an toàn. Chỉ webhook hợp lệ ghi nhận online thành công; return/cancel query không đổi trạng thái thanh toán. Khoản đến muộn sau thu tiền mặt/hủy lịch được đánh dấu cần đối soát và không cộng trùng doanh thu.
- Trước khi thu trực tiếp/hủy lịch có phiên online chờ, phải đóng và xác minh phiên tại payOS; phiên đã nhận một phần tiền phải đối soát thủ công trước khi thu tiếp/hủy. Nếu API lỗi hoặc chưa xác nhận đóng, thao tác dừng và không ghi nhận tiền/hủy lịch.
- API cập nhật trạng thái nhà cung cấp hỗ trợ CANCELLED/EXPIRED/FAILED không có tiền đã nhận. PAID từ truy vấn trạng thái vẫn chờ webhook. Không tạo phiên online từ giờ bắt đầu lịch, lịch chờ xác nhận hoặc lịch hoàn thành.
- Đánh giá User: lịch của mình đã hoàn thành, 1–5 sao, nhận xét tùy chọn tối đa 2.000 ký tự; một đánh giá/lịch, sửa được, không xóa. Phản hồi phẳng của chủ đánh giá/Admin, không sửa/xóa phản hồi.
- Trang chi tiết dịch vụ đọc đánh giá thật có phân trang; form dùng cùng API với Đánh giá của tôi. Không đọc review demo/sessionStorage. Ảnh đánh giá chưa có trong SRS/model nên không gửi/lưu ảnh bằng dữ liệu phiên.
- Admin xem/lọc đánh giá, số sao, ngày, tìm kiếm, phân trang và phản hồi trong modal. AI chỉ giữ vị trí giao diện, ghi rõ giai đoạn sau và vô hiệu thao tác phân tích.
- Dashboard/báo cáo dùng ORM: khách hàng loại Admin/superuser, lịch hôm nay, trạng thái, dịch vụ hoạt động/top dịch vụ, lịch gần đây, doanh thu/đánh giá. Bộ lọc ngày/trạng thái, biểu đồ và bảng dùng dữ liệu thật, có trạng thái rỗng.
- Doanh thu theo ngày thanh toán, lịch hẹn theo ngày hẹn, đánh giá theo ngày gửi. Dùng khoảng thời gian có múi giờ và nhóm theo giờ Việt Nam trong Python, không phụ thuộc bảng timezone MySQL (máy này `CONVERT_TZ` theo tên trả NULL). Doanh thu chỉ gồm Payment thành công, hóa đơn paid, không cần đối soát.

## Đồng bộ lịch hẹn và hóa đơn

| Lịch hẹn | Hóa đơn / thao tác |
|---|---|
| Chờ xác nhận | Không tự lập hóa đơn, không thu tiền hoặc tạo payOS. Nút Xem hóa đơn chỉ dựa trên invoiceId thật từ ORM. |
| Đã xác nhận | Tạo một hóa đơn khi chuyển từ pending; yêu cầu lặp dùng hóa đơn đã có. Online chỉ trước giờ hẹn; tiền mặt được Admin ghi nhận. Thanh toán không tự hoàn thành lịch. |
| Đã hoàn thành | Giữ hóa đơn và lịch sử thanh toán, vẫn có Xem hóa đơn. Chưa trả thì thu tại Spa; được đánh giá theo quyền sở hữu. |

`appointments/views.py` trả invoiceId/trạng thái hóa đơn từ quan hệ thật. Trang lịch User và modal lịch Admin dùng cùng API; không suy hóa đơn từ nhãn trạng thái. Đã thêm phiên bản URL JavaScript liên quan để tải lại code mới khi trình duyệt có cache.

## Hai lỗi đã được đối chiếu trực tiếp

**LH-A**: ORM xác nhận ngày [ngày/giờ hẹn đã ẩn danh], Massage đá nóng thư giãn toàn thân, [chuyên viên ẩn danh], completed; chưa có Invoice. Đây là lịch từ giai đoạn chưa tạo hóa đơn khi xác nhận. Không có snapshot giá lịch sử trong lịch này, vì vậy chưa tự tạo hóa đơn bằng giá hiện tại. Trạng thái lịch và dữ liệu gốc giữ nguyên.

Đã bổ sung lệnh `reconcile_invoices`: mặc định chỉ rà soát; plan cần giá/giảm/tên dịch vụ theo chứng từ và căn cứ. Chế độ apply yêu cầu Admin đang hoạt động và cờ xác nhận rõ. Transaction toàn bộ plan, khóa lịch và OneToOne chống trùng; chạy lại bỏ qua hóa đơn đã có; chỉ tạo unpaid, không tạo Payment, không đổi lịch. Căn cứ và Admin được ghi vào `Invoice.historical_basis`. Xác nhận lại một lịch confirmed cũ thiếu hóa đơn sẽ yêu cầu đối soát thay vì tự đoán giá.

**Lịch ngày [ngày/giờ hẹn đã ẩn danh], [chuyên viên ẩn danh]**: truy vấn database `annhien_spa` lúc kiểm tra không có lịch ngày này, nên không tìm thấy hóa đơn thật tương ứng. Chưa đủ căn cứ xác định trang cũ/cache hay nguồn màn hình đã dùng. Source Django hiện tại đã kiểm tra bằng trình duyệt và tests: pending không có invoiceId thì không có nút; confirmed/completed có invoiceId vẫn có nút. Frontend gốc mở bằng file/static vẫn là bản mẫu độc lập; nghiệm thu dùng URL Django `http://127.0.0.1:8000/appointments.html` và Ctrl+F5.

## Bổ sung hóa đơn cũ sau khi Admin kiểm tra giá

Không có lệnh apply nào được chạy trên database nghiệp vụ trong lượt này.

1. Chạy rà soát: `.\.venv\Scripts\python.exe manage.py reconcile_invoices`.
2. Sao chép `docs/historical-invoice-plan.example.json` sang `backups/historical-approved.json`. Điền subtotal/discount chính xác theo chứng từ, mã ưu đãi nếu có, tên dịch vụ lịch sử và evidence. Giá null trong mẫu cố ý không hợp lệ; không lấy giá catalog hiện tại nếu chưa có căn cứ.
3. Chạy thử: `.\.venv\Scripts\python.exe manage.py reconcile_invoices --plan backups/historical-approved.json`.
4. Sau khi người dùng/Admin duyệt giá và tổng tiền, sao lưu rồi tự chạy với ID Admin thật: `.\.venv\Scripts\python.exe manage.py reconcile_invoices --plan backups/historical-approved.json --apply --admin-id ID_ADMIN --acknowledge-historical-prices`.
5. Kiểm tra LH-A vẫn completed, có đúng một hóa đơn unpaid, không có giao dịch. F5 User/Admin phải cùng xem được hóa đơn.

## Migrations và bảo toàn dữ liệu

- `billing/0002_invoice_promotion_code_snapshot_payment_checkout_url_and_more.py`: snapshot mã ưu đãi, order code/link/QR/URL/trạng thái nhà cung cấp/hạn phiên/người thu/cờ đối soát. Đã áp dụng ở lượt triển khai trước, sau backup `backups/phase4-20261021-151950`.
- `billing/0003_invoice_historical_basis.py`: thêm trường căn cứ bổ sung hóa đơn lịch sử. Đã áp dụng sau backup xác minh `backups/phase4-20261023-134148`.
- Không thêm bảng nghiệp vụ trùng. Không reset migration hoặc database. `tools/verify_phase4_backup.py` so sánh 26 bảng trên cột cũ với dump trước 0003: tất cả giữ nguyên. Bằng chứng: `docs/phase4-final-data-verification.json`; kiểm tra 0002: `docs/phase4-migration-verification.json`.
- `.env`, khóa Django/MySQL/Gmail/payOS không sửa hoặc xuất ra báo cáo. Backup/dump nằm ngoài Git theo `.gitignore`.

## File chính tạo/sửa

- Backend: `billing/models.py`, `services.py`, `gateway.py`, `dates.py`, `views.py`, `urls.py`, management command `reconcile_invoices`, migrations 0002/0003; `reviews/views.py`, `reviews/urls.py`; `dashboard/views.py`; `appointments/services.py`, `appointments/views.py`; `config/settings.py`, `config/urls.py`, `requirements.txt`, `.env.example`.
- Frontend: templates invoice, reviews, service-detail, admin-invoices/payments/reviews/reports/dashboard và cache URL booking/appointments/admin-appointments; static JS `phase4-api`, `live-invoice`, `live-reviews`, `live-service-reviews`, `live-reports`, `admin-finance`, `admin`, `app`, `live-booking`, `live-admin`; CSS bổ sung `phase4.css`.
- Kiểm thử/tài liệu: `billing/test_phase4.py`, điều chỉnh hai fixture cũ trong `core/test_phase3.py` cho hóa đơn tự lập; `tools/backup_phase4.py`, `tools/verify_phase4_backup.py`; các tài liệu và ảnh trong `docs/phase4*`.
- 27 HTML gốc ở root và CSS/font/ảnh gốc được giữ nguyên; test checksum nguồn frontend vẫn nằm trong bộ kiểm thử toàn hệ thống.

## Kiểm thử và giao diện

Kết quả cuối: **84/84 tests đạt**, chạy thực tế trong 131,790 giây trên `test_annhien_spa`. Log: `docs/phase4-tests.txt`. Bao gồm 64 tests trước Giai đoạn 4 và 20 tests Giai đoạn 4; không dùng kết quả 78/78 cũ làm kết luận sau sửa code. System check, py_compile dashboard và kiểm tra migrations đã thực thi. File dashboard đầy đủ, không có escape bất thường `\.`/`\~`.

Các nhóm mới bao gồm snapshot/khuyến mãi, quyền/CSRF, tiền mặt đúng số tiền/chống lặp, cutoff online, timeout giữ order, webhook chữ ký sai/số tiền sai/lặp/đến muộn, hết hạn/PAID từ status không tự trả tiền, tiền mặt đồng thời và tiền mặt đua với webhook, doanh thu qua 00:00 Việt Nam, review quyền/sửa/phản hồi, review công khai không lộ ID lịch/email, ba trạng thái lịch, đối soát lịch cũ không đoán giá và chạy lại không trùng.

Kiểm tra trình duyệt trên preview `127.0.0.1:8001`, chỉ ghi fixture vào database test và tắt khóa payOS trong tiến trình preview:

- User: hóa đơn desktop/mobile, lỗi chưa cấu hình payOS, review/phản hồi sau F5; ba lịch pending/confirmed/completed lần lượt có 0/1/1 nút hóa đơn; mở hóa đơn completed còn unpaid chỉ có phương thức tại Spa.
- Trang chi tiết dịch vụ: viết đánh giá thật qua form, F5 còn đánh giá; desktop 1440 và mobile 390, không tràn ngang; không có lỗi JS trong log kiểm tra.
- Admin: modal hóa đơn, thu 1 VND bị từ chối, thu đúng [số tiền ẩn danh] VND lưu và còn sau F5; báo cáo ghi đúng doanh thu tương ứng trong lần kiểm tra đó. Review Admin gửi phản hồi đúng danh tính; dashboard biểu đồ thật.
- Báo cáo mobile: bộ lọc ngày, số 0 khi không có doanh thu, trạng thái rỗng với kỳ năm 2000, không tràn ngang hoặc lỗi JS.
- Ảnh bằng chứng: `docs/phase4-ui/`. Đối chiếu bố cục với các templates/CSS Figma gốc và ảnh dự án trước; chưa có phiên Figma cloud để xác nhận pixel từng thành phần. Test 27 trang kiểm tra render/quyền/tài nguyên; không tuyên bố đã click mọi tương tác của cả 27 trang trong trình duyệt.

## Cấu hình và phạm vi payOS đã kiểm chứng

SDK tham chiếu: [Python SDK chính thức](https://payos.vn/docs/sdks/back-end/python/), [mã nguồn SDK](https://github.com/payOSHQ/payos-lib-python), [API chính thức](https://payos.vn/docs/api/).

Người dùng tự thêm/sửa các dòng sau trong `.env` bằng ba khóa của đúng kênh **An Nhiên Spa**; không gửi khóa vào chat và không ghi đè cấu hình MySQL/Gmail:

```dotenv
PAYOS_CLIENT_ID=<nhap-tren-may>
PAYOS_API_KEY=<nhap-tren-may>
PAYOS_CHECKSUM_KEY=<nhap-tren-may>
PAYOS_RETURN_URL=http://127.0.0.1:8000/invoice.html
PAYOS_CANCEL_URL=http://127.0.0.1:8000/invoice.html
```

Khởi động lại Django để nạp cấu hình. Webhook: `/api/billing/webhook/payos/`. Tests dùng khóa giả và chữ ký hợp lệ tạo bằng SDK; mọi create/get/cancel có network đều được mock. Không gọi kết nối thật, không mở ngrok, không thay webhook kênh, không chuyển tiền.

Khi được phép kiểm thử webhook thật: kiểm tra cấu hình host/HTTPS/cookie/DEBUG phù hợp trước khi công khai; người dùng chạy `ngrok http 8000`, dùng URL HTTPS mới cho đúng kênh An Nhiên Spa và endpoint nêu trên, không dùng URL đồ án cũ; đăng ký/kiểm tra webhook rồi tắt ngrok sau nghiệm thu. Tìm thấy ngrok WindowsApps nhưng chưa chạy để kiểm tra tài khoản/cấu hình. Chưa có xác minh payOS kết nối/webhook Internet/thanh toán tiền thật.

## Giới hạn và nghiệm thu còn cần người dùng

- LH-A chưa được lập hóa đơn vì thiếu giá lịch sử đã được duyệt. Công cụ đối soát sẵn sàng; người dùng cần kiểm tra căn cứ trước khi apply.
- Cần kiểm tra lại URL nguồn của lịch được phản ánh không tồn tại trong database hiện tại; không xóa hoặc biến đổi dữ liệu để khớp màn hình mẫu.
- Nếu payOS tạo link nhưng phản hồi timeout, hệ thống giữ order và không sinh order khác tùy tiện. Khi thử lại vẫn lỗi hoặc provider báo đã nhận tiền mà webhook chưa tới, cần đối soát với payOS; không tự chuyển sang trả tiền mặt cho đến khi xác minh đóng phiên. Chưa có trang tác nghiệp xử lý khoản `requires_review`/hoàn tiền; Admin xử lý thủ công.
- Admin finance/reviews lấy danh sách theo quyền rồi lọc/phân trang trên giao diện Figma; với quy mô dữ liệu lớn cần chuyển sang phân trang server. User hóa đơn và review công khai đã phân trang server.
- Chưa triển khai AI, ảnh đánh giá, hoàn tiền tự động. Không tự sửa trạng thái lịch terminal hoặc hóa đơn paid.

Nghiệm thu trên Django 8000: User đặt lịch mới → kiểm tra pending chưa có hóa đơn → Admin xác nhận → User/Admin cùng thấy một hóa đơn → thử thu sai tiền bị chặn → thu đúng tại Spa → F5 vẫn paid và không thu lại → Admin hoàn thành sau giờ kết thúc → User vẫn mở hóa đơn và đánh giá → Admin phản hồi → F5 hai phía còn nội dung → báo cáo theo ngày thanh toán chỉ cộng một lần. Nhánh online hiện chỉ nghiệm thu mock; cấu hình khóa và webhook thật là bước riêng sau khi người dùng cho phép.

Xác minh cuối: Django localhost 8000 đã khởi động lại với code cuối, GET /login.html trả HTTP 200. `check`, `migrate --check`, `makemigrations --check --dry-run`, py_compile và `git diff --check` đều qua. Quét các file source/tài liệu thay đổi không tìm thấy giá trị khóa bí mật từ `.env`. Không commit/push.

## Bổ sung giao diện sau nghiệm thu

Đã hoàn thiện luồng dropdown/Xóa/Đổi khuyến mãi và chuyển phương thức an toàn; migration 0004/0005; 99/99 tests đạt. Chi tiết, ảnh và nghiệm thu: [invoice-flow.md](invoice-flow.md). Kết quả mới dùng backup phase4-20261023-144610; hồ sơ giai đoạn trước được giữ lại.

## Chẩn đoán TESTSPA10 trên HD-B

23/10/2026: nguyên nhân là trường điều kiện văn bản yêu cầu kiểm tra thủ công; trạng thái/ngày/phạm vi/giá tối thiểu đều phù hợp. Đã sửa API/JS hiển thị lý do bị loại, giữ nguyên dữ liệu và quy tắc xét mã. Toàn bộ **105/105 tests** đạt, có kiểm tra desktop/mobile và áp/xóa/F5 trên database test riêng. Không có migrations mới. Báo cáo, cách Admin kiểm tra cấu hình và giới hạn mỗi khách một lần chưa được thực thi: [promotion-diagnostics.md](promotion-diagnostics.md).

## Giới hạn lượt TESTSPA10 — hoàn thiện 24/10/2026

Đã bổ sung giới hạn theo khách, giữ lượt unpaid và chỉ dùng lượt khi paid, khóa MySQL chống chiếm lượt đồng thời, kiểm tra lại trong cash/online/webhook. Ba câu điều kiện đã được hỗ trợ tự động; văn bản khác vẫn bị chặn để xem xét. Migration promotions 0003 đã áp dụng, không sửa nội dung TESTSPA10 hay áp mã vào HD-B thật. API đọc HD-B trả mã hợp lệ, giảm dự kiến [số tiền ẩn danh]/tổng [số tiền ẩn danh]. **123/123 tests đạt** khi chạy lại toàn hệ thống; kiểm tra trình duyệt trên hai hóa đơn test xác nhận áp/F5/chặn hóa đơn thứ hai/xóa mã trả lượt. Chi tiết quy tắc, phần còn cần xử lý thủ công, files và bằng chứng: [promotion-usage.md](promotion-usage.md).

## Nút payOS — nghiệm thu mock 24/10/2026

Django đã nạp đủ ba khóa do người dùng tự cấu hình; chỉ kiểm tra có/thiếu. Hoàn
thiện loading, chống nhấn lặp, lỗi rõ ràng và bước mở checkout. **128/128 tests
đạt** sau khi cập nhật môi trường; Django/migrations checks qua, không migration
mới. Kiểm tra trình duyệt desktop/mobile trên database test: thiếu cấu hình,
lỗi API, thành công mock và F5 đều có phản hồi đúng. HD-C vẫn [số tiền ẩn danh] VND/unpaid,
không Payment và không đổi dữ liệu. .env bị ignore, không tìm thấy các giá trị
bí mật hiện tại trong source/index/lịch sử Git. Không gọi payOS thật, ngrok,
commit/push. Chi tiết và giới hạn nghiệm thu: [payos-feedback.md](payos-feedback.md).

## QR trực tiếp và 10 phút — 24/10/2026

Render PNG cục bộ từ qrCode đã lưu; không tạo dữ liệu chuyển khoản. Phiên mới
tối đa 600 giây, không vượt giờ hẹn; phiên cũ giữ nguyên. Đồng hồ theo backend,
F5 không reset, hết hạn ẩn QR và yêu cầu đối soát chủ động. Polling chỉ GET MySQL.
**134/134 tests đạt**, Django/migrations checks qua, desktop/mobile và F5/hết hạn/
thiếu QR đã kiểm tra bằng mock. Không migration mới. HD-C hiện có phiên đã hủy từ
trước lượt triển khai; không khôi phục hay sửa dữ liệu. Chi tiết: [payos-qr.md](payos-qr.md).
