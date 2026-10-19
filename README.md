# An Nhiên Spa — giao diện tĩnh

Giao diện tiếng Việt sử dụng HTML semantic, CSS và JavaScript thuần. Không React,
TypeScript, Vite, Tailwind, framework frontend, API hoặc database.

## Cấu trúc

- `index.html`: Home công khai, Header dành cho khách chưa đăng nhập.
- `home.html`: Home User sau đăng nhập, giữ các section và bố cục đã chốt.
- `login.html`, `register.html`: đăng nhập/đăng ký giao diện mẫu.
- `services.html`, `service-detail.html?id=0`: danh sách và chi tiết dịch vụ.
- `products.html`, `product-detail.html?id=0`: sản phẩm giới thiệu, không mua hàng.
- `booking.html`, `appointments.html`, `invoice.html`, `profile.html`: giao diện khách hàng.
- `promotions.html`, `reviews.html`, `admin-dashboard.html`: ưu đãi, đánh giá và quản trị mẫu.
- `promotion-detail.html?code=WELCOME10`: chi tiết chương trình và dịch vụ áp dụng.
- `css/style.css`: typography, palette, bố cục, responsive và hiệu ứng.
- `js/app.js`: menu mobile và tương tác mẫu; `js/catalog.js`: dữ liệu giới thiệu.
- `js/auth.js`, `css/auth.css`: trạng thái phiên và giao diện đăng nhập.
- `js/ui.js`: icon line-art, password toggle và modal xác nhận đăng xuất dùng chung.
- `images/`: logo và ảnh của giao diện hiện tại.

Các trang chứa header/footer HTML đầy đủ và nhất quán, không cần JavaScript để
hiển thị giao diện Home hoặc điều hướng. Chi tiết dịch vụ/sản phẩm dùng chỉ số
`id=0` đến `id=6` cho dịch vụ và `id=0` đến `id=13` cho sản phẩm.
Các ID từ Home được giữ nguyên. Hai font Google Fonts của giao diện ban đầu
(Be Vietnam Pro và Playfair Display) được phục vụ cục bộ qua `css/fonts.css`
và `css/fonts/`, gồm mặt chữ thường/italic và các weight hiện có.
Không cần kết nối Google Fonts khi mở trang. Giấy phép OFL đi kèm tài nguyên font.

## Danh sách và chi tiết

`services.html`, `service-detail.html`, `products.html`, `product-detail.html`
nạp thêm `css/catalog.css` và `js/catalog-pages.js`; Home không nạp các file này.
Design system và các card của Home được giữ nguyên. Header chuyển trực tiếp
đến các trang; section sản phẩm có thêm nút “Xem tất cả sản phẩm”.

- Dịch vụ: tìm theo tên (hỗ trợ không dấu), lọc danh mục, sắp xếp theo giá
  hoặc thời lượng tăng dần.
- Sản phẩm: tìm theo tên, lọc theo loại và loại da/đối tượng, chỉ giới thiệu.
- Cả hai danh sách có nút “Xóa bộ lọc” cạnh toolbar và trong trạng thái không
  có kết quả; reset trả về toàn bộ dữ liệu hoạt động.
- `js/catalog.js`: 7 dịch vụ, 14 sản phẩm, hồ sơ nhân viên demo và danh sách
  quan hệ nhiều–nhiều `relations`. Chỉ nội dung có `active: true` được hiển thị.
- Nhân viên chỉ xuất hiện khi `serviceIds` chứa ID của dịch vụ đang xem.
- Danh sách quan hệ dùng chung cho cả hai chiều tham khảo. Người dùng không
  có thao tác thêm, sửa hoặc xóa quan hệ.
- `relations` gồm các cặp `{ serviceId, productId }` duy nhất, tương ứng
  bảng nối của quan hệ Django `Service`–`CareProduct`. `careGroup` mô tả nhóm
  công dụng: face, hair, body hoặc relax. Serum/kem dưỡng mặt chỉ liên kết
  chăm sóc da mặt; sản phẩm tóc chỉ liên kết liệu trình tóc/da đầu; sản phẩm
  body và dầu massage chỉ liên kết liệu trình cơ thể hoặc massage phù hợp.
- Hai section liên quan được render từ `relations`, không hard-code card
  liên quan trong HTML và không cắt bớt một chiều theo giới hạn số card.
- Nội dung mặc định của bốn trang nằm trong HTML. JavaScript cập nhật chi tiết
  theo query `id`, lọc dữ liệu và chuyển ID dịch vụ sang giao diện đặt lịch mẫu.
- Thông tin sản phẩm và chuyên viên là minh họa, không phải tư vấn y tế,
  công thức sản phẩm được xác minh hoặc hồ sơ nhân viên thật.
- Hai trang chi tiết dùng info card, khối lợi ích, timeline và card hướng dẫn.
  Các nội dung vẫn lấy từ `catalog.js`; timeline sản phẩm tách hướng dẫn thực tế
  theo từng sản phẩm, không áp dụng quy trình thoa da cho tinh dầu khuếch tán.
- Typography Home public/User dùng chung hai font hiện có; các `</br>` không
  hợp lệ đã được bỏ, Hero giữ hai dòng chủ đích và wrap tự nhiên trên mobile.

Ảnh bổ sung từ Unsplash: chăm sóc tóc — Lindsay Cash; chân dung minh họa —
Štefan Štefančík và Daniil Lobachev. Hình ảnh được lưu trong `images/`.

## Trạng thái khách và User

- `index.html` sử dụng chính nội dung Home hiện có; không thêm lại các section
  đã được loại bỏ trước đó. Header public chỉ có logo, Dịch vụ, Khuyến mãi,
  Đặt lịch và Đăng nhập. Các CTA cần tài khoản dẫn đến `login.html`.
- `home.html` giữ nguyên nội dung Home User. Sau đăng nhập, Header đầy đủ và
  logo dẫn về Home User; các trang dùng chung đổi Header theo phiên.
- Khách được xem dịch vụ, chi tiết dịch vụ và khuyến mãi. Home User, sản phẩm/
  chi tiết sản phẩm, đặt lịch, lịch hẹn, hóa đơn, tài khoản, đánh giá và quản trị
  mẫu cần phiên giao diện. Truy cập trực tiếp khi chưa đăng nhập chuyển đến login.
- Đăng nhập chỉ chấp nhận hai tài khoản demo bên dưới bằng email hoặc username.
  Sai định danh/mật khẩu hiển thị “Thông tin đăng nhập không chính xác.”
  Không gửi request đăng nhập, không lưu mật khẩu vào sessionStorage/localStorage.
- Phiên `spa-auth` lưu trạng thái, username, email và vai trò; phiên mẫu cũ
  không có vai trò hợp lệ phải đăng nhập lại. User vào dashboard Admin được
  chuyển về `home.html`; Admin được vào dashboard.
- Đăng ký chỉ minh họa validation và chuyển sang login; không tạo tài khoản thật.
- Đăng xuất chỉ xóa các key `spa-auth`, `spa-profile`, `spa-appointments`,
  `spa-reviews` trong tab hiện tại sau khi xác nhận “Có, đăng xuất”, rồi trở về
  Home public. “Không”, Escape hoặc bấm ngoài modal không thay đổi phiên.
- Mọi password field hiện có trong login/register có nút mắt bằng JavaScript,
  hỗ trợ bàn phím, aria-label, giữ focus/caret và không thay đổi chiều cao input.
- Form đăng nhập/đăng ký vô hiệu hóa khi JavaScript chưa chạy để tránh gửi
  thông tin qua cơ chế submit mặc định của HTML.

## Khuyến mãi — dữ liệu demo

- Hai Home giữ nguyên ba card ưu đãi và thêm nút “Xem tất cả khuyến mãi”.
- Danh sách/chi tiết công khai; đặt lịch vẫn qua kiểm tra phiên mẫu.
- `js/promotions-data.js` là nguồn dùng chung: mã, mô tả, điều kiện, khoảng
  hiệu lực, trạng thái hoạt động và `serviceIds`.
- Ngày tham chiếu demo cố định **11.10.2026** chỉ dùng trong JavaScript,
  không hiển thị thông tin kỹ thuật này trên giao diện công khai.
  “Sắp hết hạn” là chương trình còn tối đa 7 ngày, tính theo ngày UTC.
- Danh sách mặc định gồm 6 chương trình hoạt động/còn hiệu lực. Hết hạn,
  chưa bắt đầu, tạm ngưng hoặc khoảng ngày không hợp lệ đều bị loại.
- Filter “Tất cả” gồm hai trạng thái còn hiệu lực; filter từng trạng thái
  chọn “Đang hiệu lực” hoặc “Sắp hết hạn”. Reset trả về danh sách hợp lệ.
- Card danh sách chỉ có mô tả ngắn tối đa hai dòng, trạng thái nhẹ cạnh thời gian
  và liên kết chi tiết; toàn bộ điều kiện/mức giảm tối đa/ghi chú nằm ở trang chi tiết.
- Mã `ANNHIEN20` trên Home được giữ nguyên; `ANHIEN20` là bí danh cho tìm
  kiếm/chi tiết. Các URL cũ `promotions.html#CODE` chuyển đến chi tiết tương ứng.
- Giá dịch vụ áp dụng luôn là giá gốc; frontend không tính giá sau giảm hay
  tự áp dụng ưu đãi. Điều kiện thật được kiểm tra tại spa/Django ở bước sau.
- `ANNHIEN20` có mốc 600.000 đ nhưng catalog hiện tại không có dịch vụ đạt
  mốc này. UI hiển thị “Hiện chưa có dịch vụ phù hợp với điều kiện của chương trình.”
  và ẩn CTA đặt lịch khi không có dịch vụ hoạt động phù hợp; không gắn sai dịch vụ.
- Khi tích hợp Django, thay cả fixtures lẫn ngày tham chiếu bằng dữ liệu và
  thời gian phía server; ánh xạ phạm vi dịch vụ và kiểm tra điều kiện ở backend.

**Giới hạn bảo mật:** đây chỉ là trạng thái UI trong `sessionStorage`.
Người dùng vẫn có thể đọc file HTML hoặc tự thay đổi dữ liệu phiên; không dùng
guard này để bảo vệ thông tin thật. Django phải kiểm tra xác thực và quyền trên
mọi request, bao gồm quyền quản trị; không dựa vào trạng thái JavaScript.

### Tài khoản demo — Bước 2

| Vai trò | Email | Username | Mật khẩu mẫu | Sau đăng nhập |
| --- | --- | --- | --- | --- |
| User | user@annhienspa.vn | user | User@123 | home.html |
| Admin | admin@annhienspa.vn | admin | Admin@123 | admin-dashboard.html |

Đây là thông tin hư cấu công khai để kiểm thử, được hard-code trong `js/auth.js`.
Không dùng tài khoản/mật khẩu thật. Đăng ký mẫu không thêm tài khoản vào danh sách này.
Ở Bước 3 phải bỏ toàn bộ bảng tài khoản và kiểm tra phiên/vai trò phía frontend,
thay bằng Django Authentication + Session và kiểm tra quyền tại backend.

## Xem giao diện

Mở trực tiếp `index.html` hoặc bất kỳ trang `.html` nào bằng trình duyệt.
Các trang có HTML đầy đủ, CSS/JavaScript qua đường dẫn tương đối, không cần
Node.js, npm, pnpm, cài package hoặc biên dịch. Liên kết hoạt động cả khi
mở file trực tiếp và khi phục vụ bằng máy chủ tĩnh.

Nếu cần máy chủ tĩnh ngoài Figma Make, có thể dùng Python:

```sh
python3 -m http.server 8443
```

Trong Figma Make, máy chủ tĩnh được môi trường tự quản lý; không chạy thêm.
Tải lại preview để xem thay đổi (không có HMR).

## Công cụ môi trường

Không có `package.json`, lockfile, `node_modules/`, cấu hình framework,
toolchain Node hoặc thư mục React `src/`.

Các script trong `.figma/make/` chỉ phục vụ môi trường Figma Make:

- `install`: không cài dependency; chỉ kiểm tra Python phục vụ preview.
- `dev`: máy chủ tĩnh Python trên `$PORT`.
- `build`: sao chép các trang HTML và `css/`, `js/`, `images/` vào `dist/`,
  không biên dịch hay thay đổi nội dung.
- `deploy`, `deploy-preview`: đóng gói bằng script trên rồi chuyển gói tĩnh
  cho Figma Make. Không dùng npm hay framework.

`dist/` là bản đóng gói được sinh tự động, không phải nguồn chỉnh sửa.
Không cần `.figma/` hay `dist/` khi đưa giao diện vào Django.

## Giới hạn tương tác mẫu

Đặt lịch, hủy lịch, lưu tên và đánh giá chỉ dùng `sessionStorage` trong tab hiện
tại. Không gửi đến spa; thông tin họ tên/số điện thoại trong form đặt lịch không
được lưu. Trang hóa đơn không tạo hóa đơn thật; trang quản trị chỉ có kiểm tra
vai trò mock phía frontend, không phải phân quyền bảo mật thật.
Không dùng các trang mẫu này làm cơ chế bảo mật.

## Tích hợp Django sau này

1. Tách header, navigation và footer thành `base.html` cùng các template include.
2. Đưa `css/`, `js/`, `images/` vào static và dùng `{% static %}`.
3. Thay liên kết `.html` bằng `{% url %}`.
4. Render catalog và chi tiết bằng Django context; bỏ dữ liệu JS mẫu tương ứng.
5. Thay form mẫu bằng Django forms, CSRF và xử lý backend ở giai đoạn sau.
6. Thay `spa-auth` và guard frontend bằng Django Authentication + Session,
   kiểm tra quyền ở views; tách Header guest/User bằng context.

Không thay đổi palette, font, lớp CSS hoặc cấu trúc Home khi tách template.
