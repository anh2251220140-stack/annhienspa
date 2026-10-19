// Step 2 static fixtures. Django will supply dates, scopes and eligibility later.
window.spaPromotions = {
  referenceDate: "2026-10-11",
  expiringWithinDays: 7,
  items: [
    {
      code: "WELCOME10", aliases: [], active: true,
      name: "Ưu đãi khách hàng mới", discount: "Giảm 10%",
      description: "Dành cho khách hàng lần đầu trải nghiệm dịch vụ tại An Nhiên Spa.",
      detail: "Một món quà chào đón cho lần đầu bạn dành thời gian chăm sóc bản thân tại An Nhiên. Chọn liệu trình phù hợp và để chúng tôi đồng hành cùng bạn.",
      conditions: ["Dành cho lần trải nghiệm đầu tiên.", "Áp dụng cho dịch vụ từ 300.000 VND. Giảm tối đa 100.000 VND."],
      startDate: "2026-10-01", endDate: "2026-12-31",
      badge: "Khách hàng mới", accent: "terracotta", serviceIds: [0, 1, 2, 3, 4, 5],
      note: "Spa xác nhận điều kiện khách hàng mới và mức giảm khi tiếp nhận lịch hẹn."
    },
    {
      code: "ANNHIEN20", aliases: ["ANHIEN20"], active: true,
      name: "Thư giãn cùng An Nhiên", discount: "Giảm 20%",
      description: "Ưu đãi cho một số liệu trình thư giãn và chăm sóc được lựa chọn.",
      detail: "Một khoảng nghỉ, nhiều yêu thương. Chương trình dành cho những liệu trình được An Nhiên lựa chọn theo điều kiện của chương trình.",
      conditions: ["Áp dụng cho liệu trình từ 600.000 VND.", "Giảm tối đa 200.000 VND."],
      startDate: "2026-10-01", endDate: "2026-12-31",
      badge: "Được yêu thích", accent: "champagne", serviceIds: [],
      scopeNote: "Danh sách liệu trình từ 600.000 VND đang được cập nhật. Vui lòng liên hệ spa để xác nhận liệu trình phù hợp; các dịch vụ demo hiện tại chưa đạt mốc này.",
      note: "Không tự áp dụng mức giảm trong giao diện. Spa xác nhận liệu trình và điều kiện trước cuộc hẹn."
    },
    {
      code: "RELAX50", aliases: [], active: true,
      name: "Món quà cho chính bạn", discount: "Giảm 50.000 VND",
      description: "Nhẹ nhàng hơn một chút cho những buổi chăm sóc bản thân.",
      detail: "Để mỗi cuộc hẹn thêm trọn vẹn. Một lời nhắc dịu dàng rằng bạn xứng đáng có một khoảng thời gian dành riêng cho mình.",
      conditions: ["Áp dụng cho dịch vụ từ 350.000 VND.", "Không áp dụng cùng ưu đãi khác."],
      startDate: "2026-10-01", endDate: "2026-12-31",
      badge: "Quà tặng", accent: "caramel", serviceIds: [0, 1, 2, 3, 5],
      note: "Mức giảm chỉ được xác nhận khi lịch hẹn đáp ứng điều kiện chương trình."
    },
    {
      code: "FACIAL15", aliases: [], active: true,
      name: "Nâng niu làn da", discount: "Giảm 15%",
      description: "Một lời hẹn dịu dàng cho làn da cần được chăm sóc.",
      detail: "Tiếp nối những thói quen chăm sóc nhẹ nhàng với liệu trình da mặt được lựa chọn tại An Nhiên.",
      conditions: ["Áp dụng cho chăm sóc da chuyên sâu.", "Dịch vụ từ 350.000 VND; giảm tối đa 100.000 VND."],
      startDate: "2026-10-01", endDate: "2026-11-30",
      badge: "Ưu đãi đặc biệt", accent: "terracotta", serviceIds: [1],
      note: "Không cộng dồn ưu đãi. Chuyên viên tư vấn mức độ phù hợp của liệu trình."
    },
    {
      code: "HAIR10", aliases: [], active: true,
      name: "Khoảng nghỉ cho mái tóc", discount: "Giảm 10%",
      description: "Chăm sóc tóc và da đầu, để bạn tìm lại cảm giác nhẹ nhõm.",
      detail: "Dành một khoảng nghỉ cho mái tóc khô xơ với hai liệu trình ủ dưỡng và chăm sóc tóc, da đầu.",
      conditions: ["Áp dụng cho các liệu trình tóc được liệt kê.", "Dịch vụ từ 300.000 VND; giảm tối đa 80.000 VND."],
      startDate: "2026-10-01", endDate: "2026-10-15",
      badge: "Một khoảng nghỉ", accent: "champagne", serviceIds: [4, 5],
      note: "Spa kiểm tra điều kiện và thời gian áp dụng khi tiếp nhận lịch hẹn."
    },
    {
      code: "BODY15", aliases: [], active: true,
      name: "Nâng niu cơ thể", discount: "Giảm 15%",
      description: "Chậm lại một chút với những nghi thức chăm sóc cơ thể.",
      detail: "Gợi ý dành cho những phút giây dưỡng thể hoặc làm mới làn da cơ thể trong không gian ấm áp của An Nhiên.",
      conditions: ["Áp dụng cho dưỡng thể và tẩy tế bào chết body.", "Dịch vụ từ 350.000 VND; giảm tối đa 100.000 VND."],
      startDate: "2026-10-01", endDate: "2026-11-30",
      badge: "Chăm sóc cơ thể", accent: "caramel", serviceIds: [2, 3],
      note: "Không cộng dồn ưu đãi. Giá dịch vụ hiển thị là giá gốc để tham khảo."
    },
    {
      code: "AUTUMN10", aliases: [], active: true,
      name: "Khoảng lặng mùa thu", discount: "Giảm 10%",
      description: "Chương trình mùa thu đã kết thúc.",
      detail: "Nội dung minh họa trạng thái hết hạn, không hiển thị trong danh sách chính.",
      conditions: ["Áp dụng cho massage đá nóng trong thời gian chương trình."],
      startDate: "2026-09-01", endDate: "2026-09-30",
      badge: "Đã kết thúc", accent: "terracotta", serviceIds: [0],
      note: "Chương trình đã hết hạn và không nhận lịch hẹn theo ưu đãi này."
    },
    {
      code: "PAUSED10", aliases: [], active: false,
      name: "Ưu đãi tạm ngưng", discount: "Giảm 10%",
      description: "Dữ liệu kiểm thử trạng thái không hoạt động.", detail: "",
      conditions: [], startDate: "2026-10-01", endDate: "2026-12-31",
      badge: "Tạm ngưng", accent: "caramel", serviceIds: [], note: ""
    }
  ]
};
