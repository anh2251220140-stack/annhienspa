// Dữ liệu demo tĩnh. ID ổn định giữ nguyên liên kết từ Home; không có API.
// relations là nguồn duy nhất cho cả hai chiều, tương ứng bảng nối Service–CareProduct trong Django.
window.spaCatalog = {
  "services": [
    {
      "id": 0,
      "active": true,
      "name": "Massage đá nóng",
      "category": "Massage / thư giãn",
      "price": "590.000 VND",
      "priceValue": 590000,
      "duration": "90 phút",
      "minutes": 90,
      "image": "images/care-1.jpg",
      "description": "Hơi ấm từ đá tự nhiên kết hợp những động tác massage nhẹ nhàng, giúp thả lỏng cơ thể và xoa dịu những căng thẳng trong ngày.",
      "introduction": "Hơi ấm từ đá tự nhiên kết hợp những động tác massage nhẹ nhàng, giúp thả lỏng cơ thể và xoa dịu những căng thẳng trong ngày. Mỗi buổi chăm sóc bắt đầu bằng việc lắng nghe nhu cầu của bạn, để chuyên viên điều chỉnh thao tác và sản phẩm phù hợp. Đây là thời gian dành riêng cho sự thư thái, không vội vàng.",
      "benefits": [
        "Giúp cơ thể thả lỏng và giảm cảm giác căng cứng.",
        "Chăm sóc làn da mềm mại bằng thao tác nhẹ nhàng.",
        "Mang đến một khoảng nghỉ để tinh thần thư thái."
      ],
      "steps": [
        "Lắng nghe nhu cầu và kiểm tra tình trạng da.",
        "Làm sạch nhẹ nhàng trước liệu trình.",
        "Thực hiện chăm sóc và massage theo nhu cầu.",
        "Hoàn thiện dưỡng ẩm và gợi ý chăm sóc tại nhà."
      ],
      "suitable": "Người cần nghỉ ngơi sau những ngày bận rộn, muốn chăm sóc cơ thể và làn da nhẹ nhàng.",
      "note": "Vui lòng thông báo về dị ứng, vùng da tổn thương, thai kỳ hoặc tình trạng sức khỏe cần lưu ý trước khi thực hiện. Chuyên viên sẽ tư vấn mức độ phù hợp; liệu trình không thay thế chăm sóc y tế.",
      "gallery": "images/facial.jpg",
      "careGroup": "relax"
    },
    {
      "id": 1,
      "active": true,
      "name": "Chăm sóc da chuyên sâu",
      "category": "Chăm sóc da mặt",
      "price": "450.000 VND",
      "priceValue": 450000,
      "duration": "60 phút",
      "minutes": 60,
      "image": "images/care-2.jpg",
      "description": "Làm sạch, cấp ẩm và chăm sóc làn da với liệu trình được lựa chọn theo nhu cầu của bạn, để da tìm lại vẻ rạng rỡ tự nhiên.",
      "introduction": "Làm sạch, cấp ẩm và chăm sóc làn da với liệu trình được lựa chọn theo nhu cầu của bạn, để da tìm lại vẻ rạng rỡ tự nhiên. Mỗi buổi chăm sóc bắt đầu bằng việc lắng nghe nhu cầu của bạn, để chuyên viên điều chỉnh thao tác và sản phẩm phù hợp. Đây là thời gian dành riêng cho sự thư thái, không vội vàng.",
      "benefits": [
        "Hỗ trợ làm sạch và bổ sung độ ẩm cho da.",
        "Mang lại cảm giác mềm mại, dễ chịu sau chăm sóc.",
        "Dành thời gian nghỉ ngơi cho cơ thể và tâm trí."
      ],
      "steps": [
        "Lắng nghe nhu cầu và kiểm tra tình trạng da.",
        "Làm sạch nhẹ nhàng trước liệu trình.",
        "Thực hiện chăm sóc và massage theo nhu cầu.",
        "Hoàn thiện dưỡng ẩm và gợi ý chăm sóc tại nhà."
      ],
      "suitable": "Người muốn chăm sóc da, bổ sung độ ẩm và dành một khoảng thời gian thư giãn.",
      "note": "Vui lòng thông báo về dị ứng, vùng da tổn thương, thai kỳ hoặc tình trạng sức khỏe cần lưu ý trước khi thực hiện. Chuyên viên sẽ tư vấn mức độ phù hợp; liệu trình không thay thế chăm sóc y tế.",
      "gallery": "images/care-2.jpg",
      "careGroup": "face"
    },
    {
      "id": 2,
      "active": true,
      "name": "Dưỡng thể thư giãn",
      "category": "Chăm sóc cơ thể",
      "price": "420.000 VND",
      "priceValue": 420000,
      "duration": "90 phút",
      "minutes": 90,
      "image": "images/care-3.jpg",
      "description": "Một khoảng lặng với tinh dầu và kỹ thuật chăm sóc nhẹ nhàng, nuôi dưỡng làn da và mang lại cảm giác cân bằng.",
      "introduction": "Một khoảng lặng với tinh dầu và kỹ thuật chăm sóc nhẹ nhàng, nuôi dưỡng làn da và mang lại cảm giác cân bằng. Mỗi buổi chăm sóc bắt đầu bằng việc lắng nghe nhu cầu của bạn, để chuyên viên điều chỉnh thao tác và sản phẩm phù hợp. Đây là thời gian dành riêng cho sự thư thái, không vội vàng.",
      "benefits": [
        "Giúp cơ thể thả lỏng và giảm cảm giác căng cứng.",
        "Chăm sóc làn da mềm mại bằng thao tác nhẹ nhàng.",
        "Mang đến một khoảng nghỉ để tinh thần thư thái."
      ],
      "steps": [
        "Lắng nghe nhu cầu và kiểm tra tình trạng da.",
        "Làm sạch nhẹ nhàng trước liệu trình.",
        "Thực hiện chăm sóc và massage theo nhu cầu.",
        "Hoàn thiện dưỡng ẩm và gợi ý chăm sóc tại nhà."
      ],
      "suitable": "Người cần nghỉ ngơi sau những ngày bận rộn, muốn chăm sóc cơ thể và làn da nhẹ nhàng.",
      "note": "Vui lòng thông báo về dị ứng, vùng da tổn thương, thai kỳ hoặc tình trạng sức khỏe cần lưu ý trước khi thực hiện. Chuyên viên sẽ tư vấn mức độ phù hợp; liệu trình không thay thế chăm sóc y tế.",
      "gallery": "images/facial.jpg",
      "careGroup": "body"
    },
    {
      "id": 3,
      "active": true,
      "name": "Tẩy tế bào chết body",
      "category": "Chăm sóc cơ thể",
      "price": "350.000 VND",
      "priceValue": 350000,
      "duration": "50 phút",
      "minutes": 50,
      "image": "images/care-4.jpg",
      "description": "Nhẹ nhàng loại bỏ tế bào chết và dưỡng ẩm toàn thân, trả lại làn da mềm mại, mịn màng.",
      "introduction": "Nhẹ nhàng loại bỏ tế bào chết và dưỡng ẩm toàn thân, trả lại làn da mềm mại, mịn màng. Mỗi buổi chăm sóc bắt đầu bằng việc lắng nghe nhu cầu của bạn, để chuyên viên điều chỉnh thao tác và sản phẩm phù hợp. Đây là thời gian dành riêng cho sự thư thái, không vội vàng.",
      "benefits": [
        "Giúp cơ thể thả lỏng và giảm cảm giác căng cứng.",
        "Chăm sóc làn da mềm mại bằng thao tác nhẹ nhàng.",
        "Mang đến một khoảng nghỉ để tinh thần thư thái."
      ],
      "steps": [
        "Lắng nghe nhu cầu và kiểm tra tình trạng da.",
        "Làm sạch nhẹ nhàng trước liệu trình.",
        "Thực hiện chăm sóc và massage theo nhu cầu.",
        "Hoàn thiện dưỡng ẩm và gợi ý chăm sóc tại nhà."
      ],
      "suitable": "Người cần nghỉ ngơi sau những ngày bận rộn, muốn chăm sóc cơ thể và làn da nhẹ nhàng.",
      "note": "Vui lòng thông báo về dị ứng, vùng da tổn thương, thai kỳ hoặc tình trạng sức khỏe cần lưu ý trước khi thực hiện. Chuyên viên sẽ tư vấn mức độ phù hợp; liệu trình không thay thế chăm sóc y tế.",
      "gallery": "images/facial.jpg",
      "careGroup": "body"
    },
    {
      "id": 4,
      "active": true,
      "name": "Ủ dưỡng tóc phục hồi",
      "category": "Chăm sóc tóc / da đầu",
      "price": "320.000 VND",
      "priceValue": 320000,
      "duration": "60 phút",
      "minutes": 60,
      "image": "images/hair-care.jpg",
      "description": "Một nghi thức chăm sóc dịu dàng cho mái tóc khô xơ, kết hợp ủ dưỡng và massage da đầu để bạn tìm lại sự nhẹ nhõm.",
      "introduction": "Một nghi thức chăm sóc dịu dàng cho mái tóc khô xơ, kết hợp ủ dưỡng và massage da đầu để bạn tìm lại sự nhẹ nhõm. Mỗi buổi chăm sóc bắt đầu bằng việc lắng nghe nhu cầu của bạn, để chuyên viên điều chỉnh thao tác và sản phẩm phù hợp. Đây là thời gian dành riêng cho sự thư thái, không vội vàng.",
      "benefits": [
        "Hỗ trợ tóc mềm mại, dễ chải và vào nếp.",
        "Chăm sóc nhẹ nhàng cho da đầu và mái tóc.",
        "Giúp thư giãn vùng đầu, vai và gáy."
      ],
      "steps": [
        "Trao đổi về tình trạng tóc và da đầu.",
        "Làm sạch tóc bằng sản phẩm phù hợp.",
        "Ủ dưỡng kết hợp massage da đầu nhẹ nhàng.",
        "Làm sạch và hoàn thiện, hướng dẫn chăm sóc tại nhà."
      ],
      "suitable": "Người có mái tóc khô xơ, thiếu độ mềm mại hoặc muốn chăm sóc da đầu kết hợp thư giãn.",
      "note": "Vui lòng thông báo về dị ứng, vùng da tổn thương, thai kỳ hoặc tình trạng sức khỏe cần lưu ý trước khi thực hiện. Chuyên viên sẽ tư vấn mức độ phù hợp; liệu trình không thay thế chăm sóc y tế.",
      "gallery": "images/hair-care.jpg",
      "careGroup": "hair"
    },
    {
      "id": 5,
      "active": true,
      "name": "Ủ chăm sóc tóc và da đầu",
      "category": "Chăm sóc tóc / da đầu",
      "price": "390.000 VND",
      "priceValue": 390000,
      "duration": "75 phút",
      "minutes": 75,
      "image": "images/hair-care.jpg",
      "description": "Làm sạch nhẹ nhàng, chăm sóc da đầu và nuôi dưỡng tóc trong không gian ấm áp, riêng tư của An Nhiên.",
      "introduction": "Làm sạch nhẹ nhàng, chăm sóc da đầu và nuôi dưỡng tóc trong không gian ấm áp, riêng tư của An Nhiên. Mỗi buổi chăm sóc bắt đầu bằng việc lắng nghe nhu cầu của bạn, để chuyên viên điều chỉnh thao tác và sản phẩm phù hợp. Đây là thời gian dành riêng cho sự thư thái, không vội vàng.",
      "benefits": [
        "Hỗ trợ tóc mềm mại, dễ chải và vào nếp.",
        "Chăm sóc nhẹ nhàng cho da đầu và mái tóc.",
        "Giúp thư giãn vùng đầu, vai và gáy."
      ],
      "steps": [
        "Trao đổi về tình trạng tóc và da đầu.",
        "Làm sạch tóc bằng sản phẩm phù hợp.",
        "Ủ dưỡng kết hợp massage da đầu nhẹ nhàng.",
        "Làm sạch và hoàn thiện, hướng dẫn chăm sóc tại nhà."
      ],
      "suitable": "Người có mái tóc khô xơ, thiếu độ mềm mại hoặc muốn chăm sóc da đầu kết hợp thư giãn.",
      "note": "Vui lòng thông báo về dị ứng, vùng da tổn thương, thai kỳ hoặc tình trạng sức khỏe cần lưu ý trước khi thực hiện. Chuyên viên sẽ tư vấn mức độ phù hợp; liệu trình không thay thế chăm sóc y tế.",
      "gallery": "images/hair-care.jpg",
      "careGroup": "hair"
    },
    {
      "id": 6,
      "active": true,
      "name": "Massage da đầu thư giãn",
      "category": "Chăm sóc tóc / da đầu",
      "price": "290.000 VND",
      "priceValue": 290000,
      "duration": "45 phút",
      "minutes": 45,
      "image": "images/hair-care.jpg",
      "description": "Massage da đầu nhẹ nhàng kết hợp chăm sóc mái tóc, mang lại một khoảng nghỉ dịu êm và cảm giác nhẹ nhõm.",
      "introduction": "Massage da đầu nhẹ nhàng kết hợp chăm sóc mái tóc, mang lại một khoảng nghỉ dịu êm và cảm giác nhẹ nhõm. Mỗi buổi chăm sóc bắt đầu bằng việc lắng nghe nhu cầu của bạn, để chuyên viên điều chỉnh thao tác và sản phẩm phù hợp. Đây là thời gian dành riêng cho sự thư thái, không vội vàng.",
      "benefits": [
        "Hỗ trợ tóc mềm mại, dễ chải và vào nếp.",
        "Chăm sóc nhẹ nhàng cho da đầu và mái tóc.",
        "Giúp thư giãn vùng đầu, vai và gáy."
      ],
      "steps": [
        "Trao đổi về tình trạng tóc và da đầu.",
        "Làm sạch tóc bằng sản phẩm phù hợp.",
        "Ủ dưỡng kết hợp massage da đầu nhẹ nhàng.",
        "Làm sạch và hoàn thiện, hướng dẫn chăm sóc tại nhà."
      ],
      "suitable": "Người có mái tóc khô xơ, thiếu độ mềm mại hoặc muốn chăm sóc da đầu kết hợp thư giãn.",
      "note": "Vui lòng thông báo về dị ứng, vùng da tổn thương, thai kỳ hoặc tình trạng sức khỏe cần lưu ý trước khi thực hiện. Chuyên viên sẽ tư vấn mức độ phù hợp; liệu trình không thay thế chăm sóc y tế.",
      "gallery": "images/hair-care.jpg",
      "careGroup": "hair"
    }
  ],
  "products": [
    {
      "id": 0,
      "active": true,
      "name": "Tinh dầu thư giãn",
      "category": "Tinh dầu thiên nhiên",
      "image": "images/care-5.jpg",
      "description": "Hương thơm dịu nhẹ, đưa những khoảnh khắc thư thái vào không gian của bạn.",
      "skins": [
        "Không áp dụng"
      ],
      "audiences": [
        "Người cần thư giãn"
      ],
      "ingredients": "Hương oải hương, gỗ tuyết tùng và cam ngọt.",
      "usage": "Thêm lượng nhỏ vào máy khuếch tán theo hướng dẫn của thiết bị, sử dụng trong không gian thoáng.",
      "note": "Chỉ dùng khuếch tán. Không uống hoặc thoa trực tiếp lên da; tránh xa trẻ nhỏ và vật nuôi. Hỏi ý kiến chuyên môn nếu mang thai hoặc nhạy cảm với hương thơm.",
      "careGroup": "relax"
    },
    {
      "id": 1,
      "active": true,
      "name": "Serum dưỡng ẩm",
      "category": "Serum",
      "image": "images/care-6.jpg",
      "description": "Bổ sung độ ẩm, giúp làn da mềm mịn và tươi sáng mỗi ngày.",
      "skins": [
        "Da khô",
        "Da thường"
      ],
      "audiences": [
        "Da thiếu ẩm"
      ],
      "ingredients": "Hyaluronic acid, glycerin và panthenol.",
      "usage": "Sau khi làm sạch, thoa một lượng nhỏ lên da hơi ẩm, vỗ nhẹ rồi tiếp tục với kem dưỡng.",
      "note": "Thử trên một vùng da nhỏ trước khi dùng. Tránh tiếp xúc mắt; ngừng sử dụng nếu có dấu hiệu kích ứng.",
      "careGroup": "face"
    },
    {
      "id": 2,
      "active": true,
      "name": "Kem dưỡng phục hồi",
      "category": "Kem dưỡng",
      "image": "images/care-7.jpg",
      "description": "Chăm sóc nhẹ nhàng, hỗ trợ hàng rào bảo vệ và giữ ẩm cho làn da.",
      "skins": [
        "Da khô",
        "Da nhạy cảm"
      ],
      "audiences": [
        "Da cần chăm sóc dịu nhẹ"
      ],
      "ingredients": "Ceramide, squalane và chiết xuất yến mạch.",
      "usage": "Thoa một lớp mỏng ở bước cuối quy trình dưỡng da, massage nhẹ nhàng để kem thấm đều.",
      "note": "Da nhạy cảm cần thử sản phẩm trước khi dùng. Không thoa lên vùng da đang tổn thương hoặc viêm.",
      "careGroup": "face"
    },
    {
      "id": 3,
      "active": true,
      "name": "Dầu dưỡng tóc",
      "category": "Chăm sóc tóc",
      "image": "images/care-8.jpg",
      "description": "Nuôi dưỡng mái tóc mềm mại, bóng khỏe và dễ vào nếp.",
      "skins": [
        "Không áp dụng"
      ],
      "audiences": [
        "Tóc khô xơ"
      ],
      "ingredients": "Dầu argan, dầu jojoba và vitamin E.",
      "usage": "Lấy một lượng nhỏ, xoa đều giữa hai lòng bàn tay rồi thoa lên thân và ngọn tóc, tránh dùng quá nhiều.",
      "note": "Tránh thoa trực tiếp vào mắt và da đầu nhạy cảm. Điều chỉnh lượng dùng theo độ dày và tình trạng tóc.",
      "careGroup": "hair"
    },
    {
      "id": 4,
      "active": true,
      "name": "Sữa rửa mặt dịu nhẹ",
      "category": "Sữa rửa mặt",
      "careGroup": "face",
      "image": "images/care-7.jpg",
      "description": "Làm sạch nhẹ nhàng bụi bẩn và lớp dầu thừa, chuẩn bị làn da cho các bước chăm sóc tiếp theo.",
      "skins": [
        "Da thường",
        "Da khô",
        "Da nhạy cảm"
      ],
      "audiences": [
        "Da mặt cần làm sạch dịu nhẹ"
      ],
      "ingredients": "Glycerin, chiết xuất yến mạch và chất làm sạch dịu nhẹ.",
      "usage": "Làm ướt da, massage một lượng nhỏ trong khoảng 30 giây rồi rửa sạch với nước.",
      "note": "Tránh vùng mắt. Thử sản phẩm trên vùng da nhỏ trước khi dùng, ngừng sử dụng nếu kích ứng."
    },
    {
      "id": 5,
      "active": true,
      "name": "Mặt nạ dưỡng ẩm",
      "category": "Mặt nạ",
      "careGroup": "face",
      "image": "images/care-6.jpg",
      "description": "Bổ sung độ ẩm và mang đến một khoảng nghỉ dịu nhẹ cho làn da sau bước làm sạch.",
      "skins": [
        "Da khô",
        "Da thường"
      ],
      "audiences": [
        "Da thiếu ẩm"
      ],
      "ingredients": "Hyaluronic acid, panthenol và chiết xuất lô hội.",
      "usage": "Sử dụng sau bước làm sạch, giữ theo thời gian trên nhãn rồi tiếp tục với kem dưỡng.",
      "note": "Không để mặt nạ quá thời gian hướng dẫn. Tránh dùng trên vùng da tổn thương."
    },
    {
      "id": 6,
      "active": true,
      "name": "Dầu gội chăm sóc da đầu",
      "category": "Dầu gội",
      "careGroup": "hair",
      "image": "images/care-8.jpg",
      "description": "Làm sạch tóc và da đầu nhẹ nhàng, chuẩn bị cho bước dưỡng và ủ tóc.",
      "skins": [
        "Không áp dụng"
      ],
      "audiences": [
        "Tóc và da đầu cần làm sạch",
        "Tóc khô xơ"
      ],
      "ingredients": "Chất làm sạch dịu nhẹ, panthenol và chiết xuất trà xanh.",
      "usage": "Làm ướt tóc, tạo bọt nhẹ, massage da đầu bằng đầu ngón tay rồi xả sạch.",
      "note": "Tránh dùng móng tay cào da đầu và tránh tiếp xúc mắt. Ngừng dùng nếu kích ứng."
    },
    {
      "id": 7,
      "active": true,
      "name": "Dầu xả mềm mượt",
      "category": "Dầu xả",
      "careGroup": "hair",
      "image": "images/care-7.jpg",
      "description": "Giúp tóc dễ chải, mềm mại và giảm cảm giác khô rối sau khi gội.",
      "skins": [
        "Không áp dụng"
      ],
      "audiences": [
        "Tóc khô xơ",
        "Tóc dễ rối"
      ],
      "ingredients": "Panthenol, dầu jojoba và protein thực vật.",
      "usage": "Sau khi gội, thoa lên thân và ngọn tóc, giữ theo hướng dẫn trên nhãn rồi xả sạch.",
      "note": "Không thoa quá nhiều lên da đầu; điều chỉnh lượng dùng theo độ dày của tóc."
    },
    {
      "id": 8,
      "active": true,
      "name": "Kem ủ tóc phục hồi",
      "category": "Kem ủ tóc",
      "careGroup": "hair",
      "image": "images/care-7.jpg",
      "description": "Nuôi dưỡng thân tóc khô xơ, giúp mái tóc mềm mại hơn sau liệu trình chăm sóc.",
      "skins": [
        "Không áp dụng"
      ],
      "audiences": [
        "Tóc khô xơ",
        "Tóc cần ủ dưỡng"
      ],
      "ingredients": "Dầu argan, bơ hạt mỡ và panthenol.",
      "usage": "Thoa lên thân và ngọn tóc sạch, ủ theo thời gian trên nhãn rồi xả kỹ.",
      "note": "Không ủ quá thời gian khuyến nghị. Kiểm tra khả năng dị ứng trước khi dùng."
    },
    {
      "id": 9,
      "active": true,
      "name": "Sữa dưỡng thể",
      "category": "Sữa dưỡng thể",
      "careGroup": "body",
      "image": "images/care-7.jpg",
      "description": "Bổ sung độ ẩm cho da cơ thể, giữ cảm giác mềm mại sau bước làm sạch.",
      "skins": [
        "Da khô",
        "Da thường"
      ],
      "audiences": [
        "Da cơ thể thiếu ẩm"
      ],
      "ingredients": "Glycerin, bơ hạt mỡ và vitamin E.",
      "usage": "Thoa lên da cơ thể sạch, còn hơi ẩm, massage nhẹ nhàng đến khi thấm.",
      "note": "Chỉ dùng ngoài da; tránh vùng da trầy xước và ngừng dùng nếu có kích ứng."
    },
    {
      "id": 10,
      "active": true,
      "name": "Dầu massage thư giãn",
      "category": "Dầu massage",
      "careGroup": "body",
      "image": "images/care-5.jpg",
      "description": "Tạo độ trượt cho các thao tác massage cơ thể, mang lại cảm giác thư giãn nhẹ nhàng.",
      "skins": [
        "Da khô",
        "Da thường"
      ],
      "audiences": [
        "Người cần massage cơ thể"
      ],
      "ingredients": "Dầu hạnh nhân, dầu jojoba và vitamin E.",
      "usage": "Làm ấm lượng nhỏ giữa hai lòng bàn tay rồi massage nhẹ nhàng lên da cơ thể.",
      "note": "Không dùng nếu dị ứng với thành phần dầu. Tránh vùng mắt, vùng da tổn thương và thử trước khi dùng."
    },
    {
      "id": 11,
      "active": true,
      "name": "Kem dưỡng body",
      "category": "Kem dưỡng body",
      "careGroup": "body",
      "image": "images/care-7.jpg",
      "description": "Dưỡng ẩm da cơ thể sau massage hoặc tẩy tế bào chết, giúp da mềm mại.",
      "skins": [
        "Da khô",
        "Da thường"
      ],
      "audiences": [
        "Da cơ thể cần dưỡng ẩm"
      ],
      "ingredients": "Bơ hạt mỡ, glycerin và squalane.",
      "usage": "Thoa một lớp mỏng lên da cơ thể sau khi làm sạch hoặc sau liệu trình chăm sóc.",
      "note": "Không dùng thay sản phẩm dành riêng cho da mặt; ngừng dùng nếu có kích ứng."
    },
    {
      "id": 12,
      "active": true,
      "name": "Scrub body dịu nhẹ",
      "category": "Tẩy tế bào chết body",
      "careGroup": "body",
      "image": "images/care-7.jpg",
      "description": "Hỗ trợ làm sạch tế bào chết trên da cơ thể, chuẩn bị cho bước dưỡng ẩm.",
      "skins": [
        "Da thường"
      ],
      "audiences": [
        "Da cơ thể cần làm mới"
      ],
      "ingredients": "Hạt đường mịn, dầu jojoba và vitamin E.",
      "usage": "Massage nhẹ trên da cơ thể ẩm, rửa sạch và tiếp tục dưỡng ẩm theo hướng dẫn.",
      "note": "Không chà xát mạnh hoặc dùng trên vùng da viêm, trầy xước. Tần suất theo nhãn sản phẩm."
    },
    {
      "id": 13,
      "active": true,
      "name": "Dầu dưỡng cơ thể",
      "category": "Dầu dưỡng cơ thể",
      "careGroup": "body",
      "image": "images/care-5.jpg",
      "description": "Giúp giữ ẩm và nuôi dưỡng da cơ thể sau tắm hoặc sau liệu trình tẩy tế bào chết.",
      "skins": [
        "Da khô",
        "Da thường"
      ],
      "audiences": [
        "Da cơ thể thiếu ẩm"
      ],
      "ingredients": "Dầu jojoba, dầu hạt nho và vitamin E.",
      "usage": "Thoa một lượng nhỏ lên da cơ thể còn hơi ẩm, massage nhẹ cho dầu thấm đều.",
      "note": "Tránh vùng mắt và da tổn thương. Không dùng nếu dị ứng với thành phần dầu."
    }
  ],
  "staff": [
    {
      "id": 0,
      "active": true,
      "name": "Mai Anh",
      "image": "images/specialist-mai-anh.jpg",
      "specialty": "Chăm sóc cơ thể, massage thư giãn và kỹ thuật đá nóng.",
      "serviceIds": [
        0,
        2,
        3
      ]
    },
    {
      "id": 1,
      "active": true,
      "name": "Thu Hà",
      "image": "images/specialist-thu-ha.jpg",
      "specialty": "Chăm sóc da mặt, cấp ẩm và chăm sóc dịu nhẹ.",
      "serviceIds": [
        1,
        2,
        3
      ]
    },
    {
      "id": 2,
      "active": true,
      "name": "Ngọc Linh",
      "image": "images/specialist-mai-anh.jpg",
      "specialty": "Chăm sóc tóc, ủ dưỡng và massage da đầu.",
      "serviceIds": [
        4,
        5,
        6
      ]
    }
  ],
  "relations": [
    {
      "serviceId": 0,
      "productId": 0
    },
    {
      "serviceId": 0,
      "productId": 10
    },
    {
      "serviceId": 0,
      "productId": 11
    },
    {
      "serviceId": 1,
      "productId": 1
    },
    {
      "serviceId": 1,
      "productId": 2
    },
    {
      "serviceId": 1,
      "productId": 4
    },
    {
      "serviceId": 1,
      "productId": 5
    },
    {
      "serviceId": 2,
      "productId": 9
    },
    {
      "serviceId": 2,
      "productId": 10
    },
    {
      "serviceId": 2,
      "productId": 11
    },
    {
      "serviceId": 2,
      "productId": 13
    },
    {
      "serviceId": 3,
      "productId": 9
    },
    {
      "serviceId": 3,
      "productId": 11
    },
    {
      "serviceId": 3,
      "productId": 12
    },
    {
      "serviceId": 3,
      "productId": 13
    },
    {
      "serviceId": 4,
      "productId": 3
    },
    {
      "serviceId": 4,
      "productId": 6
    },
    {
      "serviceId": 4,
      "productId": 7
    },
    {
      "serviceId": 4,
      "productId": 8
    },
    {
      "serviceId": 5,
      "productId": 3
    },
    {
      "serviceId": 5,
      "productId": 6
    },
    {
      "serviceId": 5,
      "productId": 7
    },
    {
      "serviceId": 5,
      "productId": 8
    },
    {
      "serviceId": 6,
      "productId": 3
    },
    {
      "serviceId": 6,
      "productId": 6
    },
    {
      "serviceId": 6,
      "productId": 7
    },
    {
      "serviceId": 6,
      "productId": 8
    }
  ]
};
