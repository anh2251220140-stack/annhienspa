;(() => {
  "use strict"
  if (window.spaAuth?.allowed === false) return
  // Demo data stays in this browser tab; no requests are sent to a backend.
  // Names and telephone numbers are deliberately not persisted.
  const read = (key, fallback) => {
    try {
      return (
        JSON.parse(sessionStorage.getItem(key)) ??
        fallback
      )
    } catch {
      return fallback
    }
  }
  const write = (key, value) => {
    try {
      sessionStorage.setItem(key, JSON.stringify(value))
      return true
    } catch {
      notify("Trình duyệt không cho phép lưu dữ liệu mẫu trong phiên này.")
      return false
    }
  }
  let toastTimer
  function notify(message) {
    const toast = document.querySelector(".toast")
    toast.textContent = message
    toast.hidden = false
    clearTimeout(toastTimer)
    toastTimer = setTimeout(() => {
      toast.hidden = true
    }, 5000)
  }
  const menu = document.querySelector(".menu-toggle")
  const navigation = document.querySelector(".navigation")
  function closeMenu() {
    navigation.classList.remove("open")
    menu.setAttribute("aria-expanded", "false")
  }
  menu.setAttribute("aria-controls", "main-navigation")
  navigation.id = "main-navigation"
  menu.addEventListener("click", () => {
    const open = navigation.classList.toggle("open")
    menu.setAttribute("aria-expanded", String(open))
  })
  navigation.addEventListener("click", (event) => {
    if (event.target.closest("a")) closeMenu()
  })
  document.addEventListener("keydown", (event) => {
    if (
      event.key ===
      "Escape"
    )
      closeMenu()
  })
  document.querySelector(".header-logout")?.addEventListener("click", () => {
    window.spaAuth.logout()
  })
  const params = new URLSearchParams(location.search)
  const detail = document.querySelector("[data-detail]")
  if (detail) {
    const list =
      detail.dataset.detail ===
      "service"
        ? window.spaCatalog.services
        : window.spaCatalog.products
    const id = Number(
      params.get("id") ||
        0,
    )
    const item = Number.isInteger(id) ? list[id] : null
    if (item) {
      document.title = `${item.name} | An Nhiên Spa`
      document.querySelector(".page-panel > h1").textContent = item.name
      document.querySelector(".page-panel > .eyebrow").textContent =
        item.category
      const image = detail.querySelector("img")
      image.src = item.image
      image.alt = item.name
      detail.querySelector("[data-description]").textContent = item.description
      if (item.price) {
        detail.querySelector("[data-price]").textContent =
          `${item.price} · ${item.duration}`
        detail.querySelector("[data-book]").href = `booking.html?service=${id}`
      }
    } else {
      document.querySelector(".page-panel > h1").textContent =
        "Không tìm thấy nội dung"
      detail.hidden = true
    }
  }
  const reviewRecords = () => {
    const items = read("spa-reviews", [])
    return Array.isArray(items) ? items : []
  }
  const reviewFor = (appointmentId) => reviewRecords().find((item) => item?.appointmentId === appointmentId)
  const journeyPage = document.querySelector(".journey-page")
  if (journeyPage) {
    const owner = read("spa-auth", {}).username
    const statuses = { pending: "Chờ xác nhận", confirmed: "Đã xác nhận", completed: "Đã hoàn thành", cancelled: "Đã hủy" }
    const escape = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[char])
    const numberFormatter = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 })
    const formatCurrency = (value) => `${numberFormatter.format(Number.isFinite(Number(value)) ? Number(value) : 0)} VND`
    const allAppointments = () => {
      const items = read("spa-appointments", [])
      return Array.isArray(items) ? items : []
    }
    // Legacy records belong to the single User demo session; no backend access control is implied.
    const mine = (item) => !item.owner || item.owner === owner
    const state = (item) => item.status || "pending"
    const starts = (item) => new Date(`${item.date}T${item.time}:00`).getTime()
    const ends = (item) => starts(item) + (Number(item.minutes) || 90) * 60000
    const clock = (minutes) => `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`
    const dayLabel = (date) => String(date).split("-").reverse().join(".")
    const shortCode = (prefix, id) => `${prefix}-${String(id ?? "").replace(/^(?:LH|HD)-/i, "").replace(/[^a-z0-9]/gi, "").slice(0, 8).toUpperCase()}`
    const paidOnline = (item) => item.invoice?.status === "paid" && item.invoice.method !== "spa"
    const cancellable = (item) => ["pending", "confirmed"].includes(state(item)) && Date.now() < starts(item) && !paidOnline(item)
    const cancelReason = (item) => paidOnline(item)
      ? "Lịch đã thanh toán online. Vui lòng liên hệ Spa/Admin để được hỗ trợ; không có hoàn tiền tự động."
      : "Chỉ có thể tự hủy lịch chờ xác nhận hoặc đã xác nhận, trước giờ bắt đầu."
    const booking = document.querySelector("#booking-form")
    if (booking) {
      const profile = window.spaAuth.getProfile()
      booking.elements.name.value = profile.name || ""
      booking.elements.phone.value = profile.phone || ""
      const catalog = window.spaCatalog
      const service = () => catalog.services.find((item) => item.active === true && String(item.id) === booking.elements.service.value)
      const employee = () => catalog.staff.find((item) => item.active === true && String(item.id) === booking.elements.employee.value)
      // Explicit UI fixtures, not official employee schedules. No network or staff data is changed.
      const shifts = { 0: [9 * 60, 21 * 60], 1: [10 * 60, 18 * 60], 2: [9 * 60, 19 * 60] }
      const localDay = () => {
        const now = new Date()
        return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`
      }
      booking.elements.date.min = localDay()
      booking.elements.service.replaceChildren(new Option("Chọn liệu trình của bạn", ""),
        ...catalog.services.filter((item) => item.active === true).map((item) => new Option(item.name, String(item.id))))
      const available = () => {
        const treatment = service(), person = employee(), date = booking.elements.date.value
        if (!treatment || !person || !person.serviceIds.includes(treatment.id) || !date || date < localDay() || !shifts[person.id]) return []
        const [open, close] = shifts[person.id]
        const appointments = allAppointments()
        const slots = []
        for (let time = open; time + treatment.minutes <= close; time += 30) {
          const start = new Date(`${date}T${clock(time)}:00`).getTime()
          const end = start + treatment.minutes * 60000
          if (start <= Date.now()) continue
          const collision = appointments.some((item) => state(item) !== "cancelled" &&
            (String(item.employeeId) === String(person.id) || mine(item)) &&
            start < ends(item) && end > starts(item))
          if (!collision) slots.push(clock(time))
        }
        return slots
      }
      const updateSlots = () => {
        booking.elements.date.min = localDay()
        const previous = booking.elements.time.value
        const slots = available()
        booking.elements.time.replaceChildren(new Option(slots.length ? "Chọn giờ bắt đầu" : "Chưa có khung giờ phù hợp", ""),
          ...slots.map((time) => new Option(time, time)))
        if (slots.includes(previous)) booking.elements.time.value = previous
        booking.elements.time.disabled = !slots.length
        document.querySelector("[data-slot-status]").textContent = slots.length
          ? `${slots.length} khung giờ phù hợp · ${service().duration}. Đã loại lịch trùng của bạn và chuyên viên trong phiên mẫu.`
          : "Chọn đủ chuyên viên và ngày hẹn. Nếu không còn giờ trống, hãy thử ngày khác."
        booking.querySelector('[type="submit"]').disabled = !booking.elements.time.value
      }
      const updateEmployees = () => {
        const treatment = service()
        const people = catalog.staff.filter((person) => person.active === true && treatment && person.serviceIds.includes(treatment.id))
        booking.elements.employee.replaceChildren(new Option(people.length ? "Chọn chuyên viên" : "Chưa có chuyên viên phù hợp", ""),
          ...people.map((person) => new Option(person.name, String(person.id))))
        booking.elements.employee.disabled = !people.length
        updateSlots()
      }
      booking.elements.service.addEventListener("change", updateEmployees)
      booking.elements.employee.addEventListener("change", updateSlots)
      booking.elements.date.addEventListener("change", updateSlots)
      booking.elements.time.addEventListener("change", () => { booking.querySelector('[type="submit"]').disabled = !booking.elements.time.value })
      if (params.has("service")) booking.elements.service.value = params.get("service")
      updateEmployees()
      booking.addEventListener("submit", (event) => {
        event.preventDefault()
        if (!booking.reportValidity()) return
        if (!available().includes(booking.elements.time.value)) {
          updateSlots()
          notify("Khung giờ không còn phù hợp. Vui lòng chọn lại.")
          return
        }
        const treatment = service(), person = employee(), id = crypto.randomUUID()
        const appointments = allAppointments()
        appointments.push({
          id, owner, serviceId: treatment.id, service: treatment.name, employeeId: person.id, employee: person.name,
          date: booking.elements.date.value, time: booking.elements.time.value, minutes: treatment.minutes,
          note: booking.elements.note.value.trim(), status: "pending",
          invoice: { id: `HD-${id}`, priceSnapshot: treatment.priceValue, subtotal: treatment.priceValue,
            discount: 0, total: treatment.priceValue, promotion: "", status: "unpaid", paymentState: "unpaid" },
        })
        if (!write("spa-appointments", appointments)) return
        booking.hidden = true
        const result = document.querySelector("#booking-result")
        result.querySelector("[data-booking-service]").textContent = treatment.name
        result.querySelector("[data-booking-employee]").textContent = person.name
        result.querySelector("[data-booking-date]").textContent = dayLabel(booking.elements.date.value)
        result.querySelector("[data-booking-time]").textContent = booking.elements.time.value
        result.hidden = false
        result.setAttribute("tabindex", "-1")
        result.focus()
      })
      window.addEventListener("focus", () => { if (!booking.hidden) updateSlots() })
    }

    const list = document.querySelector("#appointment-list")
    if (list) {
      // Stable review-test fixtures; never overwrite existing visits or customer edits.
      if (owner === "user" && read("spa-auth", {}).role === "User") {
        const appointments = allAppointments()
        const reviews = reviewRecords()
        const appointmentCount = appointments.length, reviewCount = reviews.length
        const fixtures = [
          ["01", 0, "Massage đá nóng", 0, "Mai Anh", "2026-10-01", "09:00", 90],
          ["02", 1, "Chăm sóc da chuyên sâu", 1, "Thu Hà", "2026-10-05", "14:00", 60],
          ["03", 5, "Ủ chăm sóc tóc và da đầu", 2, "Ngọc Linh", "2026-10-08", "10:00", 75, 5, "Rất hài lòng, nhân viên nhẹ nhàng và không gian thư giãn."],
          ["04", 2, "Dưỡng thể thư giãn", 0, "Mai Anh", "2026-10-10", "16:00", 90, 4, "Dịch vụ tốt, không gian yên tĩnh và dễ chịu."],
          ["05", 1, "Chăm sóc da chuyên sâu", 1, "Thu Hà", "2026-10-12", "08:30", 60],
        ]
        fixtures.forEach(([suffix, serviceId, service, employeeId, employee, date, time, minutes, rating, message]) => {
          const id = `demo-review-completed-${suffix}`
          const appointment = { id, owner: "user", serviceId, service, employeeId, employee, date, time, minutes,
            status: "completed", note: "Lịch hẹn minh họa để thử tính năng đánh giá." }
          if (!appointments.some((item) => item?.id === id)) appointments.push(appointment)
          if (rating && !reviews.some((item) => item?.appointmentId === id)) {
            const createdAt = new Date(ends(appointment)).toISOString()
            reviews.push({ id: `demo-review-${suffix}`, appointmentId: id, serviceId, owner: "user",
              name: window.spaAuth.getProfile().name || "Lan Anh", rating, message, createdAt, updatedAt: createdAt, images: [] })
          }
        })
        if (appointments.length === appointmentCount || write("spa-appointments", appointments)) {
          if (reviews.length !== reviewCount) write("spa-reviews", reviews)
        }
      }
      const filter = document.querySelector("[data-appointment-filter]")
      if (statuses[params.get("status")]) filter.value = params.get("status")
      const render = () => {
        const items = allAppointments().filter((item) => mine(item) && (!filter.value || state(item) === filter.value))
        list.innerHTML = items.length ? items.map((item) => {
          const finish = new Date(ends(item)).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" })
          const [year, month, day] = String(item.date).split("-")
          return `<article class="journey-card appointment-card">
            <div class="appointment-heading">
              <time class="appointment-date" datetime="${escape(item.date)}T${escape(item.time)}">
                <strong>${escape(day)}</strong><span>THÁNG ${escape(month)} · ${escape(year)}</span><span>${escape(item.time)}–${escape(finish)}</span>
              </time>
              <div><span class="eyebrow">AN NHIÊN / CUỘC HẸN</span><h2>${escape(item.service)}</h2><p>${escape(item.employee || "Chuyên viên chưa được phân công")}</p></div>
              <span class="journey-status">${escape(statuses[state(item)] || "Chờ Spa kiểm tra")}</span></div>
            <details><summary class="button small">Xem chi tiết</summary><dl class="journey-facts">
              <div><dt>Mã lịch hẹn</dt><dd>${escape(shortCode("LH", item.id))}</dd></div>
              <div><dt>Ghi chú</dt><dd>${escape(item.note || "Không có ghi chú")}</dd></div>
              <div><dt>Hóa đơn</dt><dd>${item.invoice ? escape(item.invoice.status === "paid" ? "Đã thanh toán" : "Chưa thanh toán") : "Chưa có hóa đơn"}</dd></div>
            </dl></details>
            <div class="journey-actions">
              ${item.invoice ? `<a class="button filled" href="invoice.html?id=${encodeURIComponent(item.id)}">Xem hóa đơn</a>` : ""}
              ${cancellable(item) ? `<button class="button" type="button" data-cancel-appointment="${escape(item.id)}">Hủy lịch hẹn</button>` : ""}
              ${state(item) === "completed" && Number.isInteger(item.serviceId) ? `<a class="button small" href="service-detail.html?id=${item.serviceId}&appointment=${encodeURIComponent(item.id)}#reviews">${reviewFor(item.id) ? "Chỉnh sửa đánh giá" : "Viết đánh giá"}</a>` : ""}
            </div>
            ${state(item) !== "cancelled" && !cancellable(item) ? `<p class="form-note">${escape(cancelReason(item))}</p>` : ""}
          </article>`
        }).join("") : '<p class="journey-empty">Chưa có lịch hẹn phù hợp. Một cuộc hẹn với sự an yên đang chờ bạn.</p>'
      }
      let cancellation
      list.addEventListener("click", (event) => {
        const button = event.target.closest("[data-cancel-appointment]")
        if (!button) return
        const id = button.dataset.cancelAppointment
        const item = allAppointments().find((item) => item.id === id && mine(item))
        if (!item || !cancellable(item)) { render(); notify("Lịch hẹn không còn đủ điều kiện tự hủy."); return }
        if (!cancellation) {
          cancellation = document.createElement("dialog")
          cancellation.className = "logout-dialog"
          cancellation.setAttribute("aria-labelledby", "cancel-appointment-title")
          cancellation.innerHTML = '<span class="eyebrow">AN NHIÊN / LỊCH HẸN</span><h2 id="cancel-appointment-title">Hủy cuộc hẹn này?</h2><p>Lịch hẹn sẽ chuyển thành Đã hủy và khung giờ được giải phóng trong phiên mẫu. Không xử lý hoàn tiền tự động.</p><div class="logout-actions"><button class="button" type="button" data-cancel-no autofocus>Giữ lịch hẹn</button><button class="button filled" type="button" data-cancel-yes>Xác nhận hủy</button></div>'
          document.body.append(cancellation)
          cancellation.querySelector("[data-cancel-no]").addEventListener("click", () => cancellation.close())
          cancellation.querySelector("[data-cancel-yes]").addEventListener("click", () => {
            const items = allAppointments()
            const current = items.find((item) => item.id === cancellation.dataset.id && mine(item))
            if (!current || !cancellable(current)) {
              cancellation.close(); render(); notify("Không thể tự hủy lịch này. Vui lòng liên hệ Spa."); return
            }
            current.status = "cancelled"
            if (current.invoice?.paymentState === "pending") current.invoice.paymentState = "unpaid"
            if (write("spa-appointments", items)) { cancellation.close(); render(); notify("Đã hủy lịch hẹn mẫu.") }
          })
          cancellation.addEventListener("close", () => {
            const target = [...list.querySelectorAll("[data-cancel-appointment]")].find((node) => node.dataset.cancelAppointment === cancellation.dataset.id)
            if (target) target.focus()
            else { list.setAttribute("tabindex", "-1"); list.focus() }
          })
        }
        cancellation.dataset.id = id
        cancellation.showModal()
      })
      filter.addEventListener("change", render)
      window.addEventListener("focus", render)
      render()
    }

    const invoiceContent = document.querySelector("[data-invoice-content]")
    if (invoiceContent) {
      const select = document.querySelector("[data-invoice-select]")
      const items = allAppointments().filter((item) => mine(item) && item.invoice)
      const invoiceId = params.get("id")
      const currentId = invoiceId || items[0]?.id
      select.replaceChildren(...items.map((item) => new Option(`${dayLabel(item.date)} · ${item.service}`, item.id)))
      select.value = currentId || ""
      document.querySelector("[data-invoice-picker]").hidden = items.length < 2
      select.addEventListener("change", () => { location.href = `invoice.html?id=${encodeURIComponent(select.value)}` })
      const find = () => allAppointments().find((item) => mine(item) && item.id === currentId && item.invoice)
      const text = (key, value) => { document.querySelector(`[data-${key}]`).textContent = value }
      const canOnline = (item) => state(item) !== "cancelled" && item.invoice.status !== "paid" && Number.isFinite(starts(item)) && Date.now() < starts(item)
      const promoForm = document.querySelector("[data-invoice-promo]")
      const promoStatus = document.querySelector("#invoice-promo-status")
      const checkPromotion = (promotion, item, appointments) => {
        const data = window.spaPromotions
        if (!promotion || promotion.active !== true || data.referenceDate < promotion.startDate || data.referenceDate > promotion.endDate) {
          return { error: "Khuyến mãi chưa khả dụng hoặc không còn hiệu lực theo ngày demo." }
        }
        if (!promotion.serviceIds.includes(item.serviceId)) return { error: "Ưu đãi này không áp dụng cho dịch vụ của cuộc hẹn." }
        const subtotal = Number(item.invoice.subtotal)
        if (!Number.isFinite(subtotal) || subtotal < 0) return { error: "Chưa đủ thông tin hóa đơn để tính ưu đãi." }
        // Use the same existing fixture rules for both dropdown eligibility and application.
        const conditions = promotion.conditions.join(" ")
        if (/lần trải nghiệm đầu tiên/i.test(conditions) && appointments.some((other) => mine(other) && other.id !== item.id && state(other) === "completed")) {
          return { error: "Ưu đãi dành cho lần trải nghiệm đầu tiên. Spa có thể hỗ trợ chọn chương trình khác." }
        }
        const amount = (value) => Number(value.replace(/[.,]/g, ""))
        const minMatch = conditions.match(/từ\s+([\d.,]+)\s+VND/i)
        const maxMatch = conditions.match(/giảm tối đa\s+([\d.,]+)\s+VND/i)
        const minimum = promotion.min_amount ?? (minMatch ? amount(minMatch[1]) : 0)
        const maximum = promotion.max_discount ?? (maxMatch ? amount(maxMatch[1]) : Infinity)
        if (subtotal < minimum) return { error: `Ưu đãi dành cho dịch vụ từ ${formatCurrency(minimum)}.` }
        const percent = promotion.discount.match(/([\d.]+)\s*%/)
        const fixed = promotion.discount.match(/([\d.,]+)\s+VND/i)
        if (!percent && !fixed) return { error: "Spa sẽ hỗ trợ xác nhận mức giảm của chương trình này." }
        const discount = Math.min(subtotal, maximum, Math.round(percent ? subtotal * Number(percent[1]) / 100 : amount(fixed[1])))
        if (!Number.isFinite(discount) || discount < 0) return { error: "Chưa thể áp dụng mức giảm này." }
        return { discount }
      }
      const render = () => {
        const item = find()
        invoiceContent.hidden = !item
        document.querySelector("[data-invoice-empty]").hidden = Boolean(item)
        if (!item) return
        const invoice = item.invoice, paid = invoice.status === "paid", cancelled = state(item) === "cancelled"
        const online = canOnline(item), pending = online && invoice.paymentState === "pending"
        text("invoice-service", item.service)
        text("invoice-code", `Mã hóa đơn: ${shortCode("HD", invoice.id)}`)
        text("invoice-status", paid ? "Đã thanh toán" : cancelled ? "Lịch hẹn đã hủy" : pending ? "Đang chờ thanh toán online" : "Chưa thanh toán")
        text("invoice-appointment", `${dayLabel(item.date)} · ${item.time}`)
        text("invoice-employee", item.employee || "Chờ Spa phân công")
        text("invoice-price", formatCurrency(invoice.priceSnapshot))
        text("invoice-subtotal", formatCurrency(invoice.subtotal))
        text("invoice-promotion", invoice.promotion ? `${invoice.promotion}${invoice.promotionName ? ` · ${invoice.promotionName}` : ""}` : "Không áp dụng")
        text("invoice-discount", formatCurrency(invoice.discount))
        text("invoice-total", formatCurrency(invoice.total))
        text("payment-amount", formatCurrency(invoice.total))
        document.querySelector("[data-payment-options]").hidden = paid || cancelled
        document.querySelector("[data-payment-online]").hidden = !online
        document.querySelector("[data-payment-qr]").hidden = !pending
        document.querySelector("[data-payment-receipt]").hidden = !paid
        promoForm.hidden = paid || cancelled
        const eligible = (window.spaPromotions?.items || []).filter((promotion) => !checkPromotion(promotion, item, allAppointments()).error)
        const selection = promoForm.elements.promotion.value || invoice.promotion || ""
        promoForm.elements.promotion.replaceChildren(new Option(eligible.length ? "Chọn khuyến mãi phù hợp" : "Không có khuyến mãi phù hợp", ""),
          ...eligible.map((promotion) => new Option(`${promotion.code} · ${promotion.name}`, promotion.code)))
        if (eligible.some((promotion) => promotion.code === selection)) promoForm.elements.promotion.value = selection
        promoForm.querySelectorAll('select, button[type="submit"]').forEach((node) => { node.disabled = invoice.paymentState === "pending" || !eligible.length })
        document.querySelector("[data-promo-remove]").hidden = paid || cancelled || !invoice.promotion || invoice.paymentState === "pending"
        document.querySelector("[data-promo-remove]").disabled = invoice.paymentState === "pending"
        document.querySelector("[data-payment-edit]").hidden = paid || cancelled || invoice.paymentState !== "pending"
        if (invoice.paymentState === "pending") promoStatus.textContent = "Mã khuyến mãi đã được khóa cho phiên thanh toán này."
        else if (invoice.promotion) promoStatus.textContent = `Đã áp dụng ${invoice.promotion} · Giảm ${formatCurrency(invoice.discount)}. Spa xác nhận điều kiện thực tế.`
        else promoStatus.textContent = "Không áp dụng. Ưu đãi được tính thử; Spa xác nhận điều kiện thực tế."
        if (paid) {
          text("payment-method", invoice.method === "spa" ? "Trực tiếp tại Spa" : "payOS (minh họa)")
          text("payment-date", invoice.paidAt ? new Date(invoice.paidAt).toLocaleString("vi-VN") : "Chưa có thông tin")
          text("payment-reference", invoice.transaction || "Không có")
        }
        text("payment-message", paid ? "Hóa đơn đã được ghi nhận thanh toán trong dữ liệu mẫu. Không có giao dịch ngân hàng thật."
          : cancelled ? "Cuộc hẹn đã hủy. Không còn yêu cầu thanh toán; vui lòng liên hệ Spa nếu cần hỗ trợ."
          : !online ? "Đã đến giờ hẹn. Thanh toán online đã đóng; chỉ thanh toán trực tiếp tại Spa."
          : invoice.preference === "spa" ? "Bạn đã chọn thanh toán trực tiếp tại Spa. Hóa đơn vẫn chưa thanh toán."
          : pending ? "Đang chờ thanh toán — chỉ mô phỏng giao diện payOS."
          : "Trước giờ hẹn, bạn có thể chọn payOS demo hoặc thanh toán trực tiếp tại Spa.")
      }
      promoForm.addEventListener("submit", (event) => {
        event.preventDefault()
        const appointments = allAppointments()
        const item = appointments.find((item) => mine(item) && item.id === currentId && item.invoice)
        if (!item || item.invoice.status === "paid" || state(item) === "cancelled" || item.invoice.paymentState === "pending") {
          render()
          return
        }
        const code = promoForm.elements.promotion.value.trim().toUpperCase()
        const data = window.spaPromotions
        const promotion = data?.items.find((entry) => [entry.code, ...entry.aliases].includes(code))
        if (!code) { promoStatus.textContent = "Chọn một khuyến mãi phù hợp trước khi áp dụng."; return }
        const result = checkPromotion(promotion, item, appointments)
        if (result.error) { promoStatus.textContent = result.error; return }
        item.invoice.promotion = promotion.code
        item.invoice.promotionName = promotion.name
        item.invoice.discount = result.discount
        item.invoice.total = Number(item.invoice.subtotal) - result.discount
        if (write("spa-appointments", appointments)) {
          promoForm.elements.promotion.value = promotion.code
          render()
        }
      })
      document.querySelector("[data-promo-remove]").addEventListener("click", () => {
        const appointments = allAppointments()
        const item = appointments.find((item) => mine(item) && item.id === currentId && item.invoice)
        if (!item || item.invoice.status === "paid" || state(item) === "cancelled" || item.invoice.paymentState === "pending") { render(); return }
        const subtotal = Number(item.invoice.subtotal)
        if (!Number.isFinite(subtotal) || subtotal < 0) { promoStatus.textContent = "Chưa đủ thông tin để khôi phục tổng tiền."; return }
        item.invoice.promotion = ""
        item.invoice.promotionName = ""
        item.invoice.discount = 0
        item.invoice.total = subtotal
        if (write("spa-appointments", appointments)) {
          promoForm.elements.promotion.value = ""
          render()
        }
      })
      const updatePayment = (action) => {
        const appointments = allAppointments()
        const item = appointments.find((item) => mine(item) && item.id === currentId && item.invoice)
        if (!item || item.invoice.status === "paid" || state(item) === "cancelled") { render(); return }
        if (["online", "demo"].includes(action) && !canOnline(item)) { render(); notify("Thanh toán online đã đóng. Vui lòng thanh toán tại Spa."); return }
        if (action === "demo" && item.invoice.paymentState !== "pending") return
        if (action === "edit" && item.invoice.paymentState !== "pending") { render(); return }
        if (action === "online") {
          item.invoice.paymentState = "pending"; item.invoice.preference = "online"
        } else if (action === "spa") {
          item.invoice.paymentState = "unpaid"; item.invoice.preference = "spa"
        } else if (action === "edit") {
          item.invoice.status = "unpaid"; item.invoice.paymentState = "unpaid"
          delete item.invoice.preference
        } else {
          item.invoice.status = "paid"; item.invoice.paymentState = "paid"; item.invoice.method = "online"
          item.invoice.paidAt = new Date().toISOString(); item.invoice.transaction = `DEMO-${item.id}`
        }
        if (write("spa-appointments", appointments)) {
          render()
          if (action === "edit") {
            promoForm.elements.promotion.focus({ preventScroll: true })
            promoForm.scrollIntoView({ block: "nearest" })
          }
        }
      }
      document.querySelector("[data-payment-online]").addEventListener("click", () => updatePayment("online"))
      document.querySelector("[data-payment-spa]").addEventListener("click", () => updatePayment("spa"))
      document.querySelector("[data-payment-demo]").addEventListener("click", () => updatePayment("demo"))
      document.querySelector("[data-payment-edit]").addEventListener("click", () => updatePayment("edit"))
      window.addEventListener("focus", render)
      document.addEventListener("visibilitychange", render)
      // Re-evaluate at the appointment boundary even while the invoice stays open.
      const item = find()
      if (item && starts(item) > Date.now()) {
        const delay = starts(item) - Date.now()
        const boundary = () => { if (starts(item) <= Date.now()) { render(); clearInterval(timer) } }
        const timer = setInterval(boundary, Math.min(1000, delay))
      }
      render()
    }
  }
  function renderAppointments() {
    if (journeyPage) return
    const list = document.querySelector("#appointment-list")
    if (!list) return
    list.replaceChildren()
    const appointments = read("spa-appointments", [])
    const count = document.querySelector("#booking-count")
    if (count) count.textContent = String(appointments.length)
    if (!appointments.length) {
      const empty = document.createElement("p")
      empty.textContent =
        "Bạn chưa có lịch hẹn. Dành một khoảng thời gian cho chính mình nhé."
      list.append(empty)
    }
    appointments.forEach((item) => {
      const row = document.createElement("article")
      row.className = "appointment"
      const text = document.createElement("p")
      text.textContent = `${item.service} · ${item.date} · ${item.time}`
      const cancel = document.createElement("button")
      cancel.type = "button"
      cancel.textContent = "Hủy"
      cancel.setAttribute(
        "aria-label",
        `Hủy lịch hẹn ${item.service} ${item.date} ${item.time}`,
      )
      cancel.addEventListener("click", () => {
        if (!confirm("Hủy lịch hẹn mẫu này?")) return
        if (
          write(
            "spa-appointments",
            appointments.filter((a) => a.id !== item.id),
          )
        ) {
          renderAppointments()
          notify("Đã hủy lịch hẹn mẫu.")
        }
      })
      row.append(text, cancel)
      list.append(row)
    })
  }
  renderAppointments()
  const profile = document.querySelector("#profile-form")
  if (profile) {
    let saved = window.spaAuth.getProfile()
    let avatar = saved.avatar
    let avatarPending = false
    const edit = document.querySelector("[data-profile-edit]")
    const picker = document.querySelector("#profile-avatar")
    const facts = document.querySelector("[data-profile-facts]")
    const portrait = document.querySelector("[data-profile-avatar]")
    const personalEditor = document.querySelector("#profile-personal-editor")
    const profileStatus = document.querySelector("[data-profile-status]")
    const fields = ["name", "username", "email", "phone"]
    const careKeys = ["skin", "needs", "interests"]
    const changedCare = new Set()
    const careInputs = (key) => [...profile.querySelectorAll(`input[name="${key}"]`)]
    const careLabel = (value) => String(value ?? "").trim().replace(/[.]$/, "")
    const noPreference = "Không có sở thích đặc biệt"
    const showProfileStatus = (text, state = "error") => {
      profileStatus.textContent = text
      profileStatus.dataset.state = state
      profileStatus.hidden = !text
    }
    const budgetValue = () => {
      const value = profile.elements.budget.value.trim()
      if (!value) return null
      if (!/^(?:\d+|\d{1,3}(?:\.\d{3})+)$/.test(value)) return NaN
      const amount = Number(value.replace(/\./g, ""))
      return Number.isSafeInteger(amount) && amount >= 0 ? amount : NaN
    }
    const formatBudget = (value) => new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 }).format(value)
    document.querySelectorAll("[data-profile-icon]").forEach((node) => { node.innerHTML = window.spaIcon(node.dataset.profileIcon) })
    const renderAvatar = () => {
      portrait.textContent = String(saved.name || "Lan Anh").trim().split(/\s+/).slice(-2).map((part) => part[0]).join("").toUpperCase()
      if (/^data:image\/(?:png|jpeg|webp);base64,/.test(avatar)) {
        const image = document.createElement("img")
        image.src = avatar
        image.alt = "Ảnh đại diện xem trước"
        portrait.replaceChildren(image)
      }
    }
    const renderProfile = () => {
      fields.forEach((key) => {
        profile.elements[key].value = saved[key] ?? ""
        document.querySelectorAll(`[data-profile-value="${key}"]`).forEach((node) => {
          node.textContent = saved[key] || "Chưa cập nhật"
        })
      })
      careKeys.forEach((key) => {
        const raw = saved[key]
        const values = (Array.isArray(raw) ? raw : raw ? [raw] : []).map(careLabel)
        const controls = careInputs(key)
        controls.forEach((input) => { input.checked = values.includes(input.value) })
        if (key === "skin" && !controls.some((input) => input.checked)) profile.elements.skin.value = "Chưa xác định"
        const conflicting = key === "interests" && values.includes(noPreference) && values.some((value) => value !== noPreference)
        if (conflicting) controls.forEach((input) => { input.checked = false })
        const legacy = document.querySelector(`[data-care-legacy="${key}"]`)
        legacy.hidden = !conflicting && !values.some((value) => !controls.some((input) => input.value === value))
        legacy.textContent = legacy.hidden ? "" : `Đã lưu trước: ${Array.isArray(raw) ? raw.join("; ") : raw}. Chọn lại từ danh sách nếu muốn cập nhật; chưa chọn lại thì giữ nguyên dữ liệu cũ.`
      })
      const budget = saved.budget === null || saved.budget === undefined || saved.budget === "" ? null : Number(saved.budget)
      profile.elements.budget.value = budget === null ? "" : Number.isSafeInteger(budget) && budget >= 0 ? formatBudget(budget) : String(saved.budget)
      profile.elements.budget.setCustomValidity("")
      profile.elements.budget.removeAttribute("aria-invalid")
      changedCare.clear()
      renderAvatar()
    }
    const setEditing = (open) => {
      personalEditor.hidden = !open
      facts.hidden = open
      edit.setAttribute("aria-expanded", String(open))
      if (open) profile.elements.name.focus()
    }
    renderProfile()
    edit.addEventListener("click", () => setEditing(personalEditor.hidden))
    profile.addEventListener("change", (event) => {
      const input = event.target
      if (!careKeys.includes(input.name)) return
      changedCare.add(input.name)
      if (input.name === "interests" && input.checked) {
        careInputs("interests").forEach((other) => {
          if (other !== input && (input.value === noPreference || other.value === noPreference)) other.checked = false
        })
      }
      const legacy = document.querySelector(`[data-care-legacy="${input.name}"]`)
      if (legacy) legacy.hidden = true
      showProfileStatus("")
    })
    profile.addEventListener("input", (event) => { if (event.target.name !== "budget") showProfileStatus("") })
    profile.elements.budget.addEventListener("input", () => {
      const invalid = Number.isNaN(budgetValue())
      profile.elements.budget.setCustomValidity(invalid ? "Nhập số tiền VND nguyên không âm, ví dụ 500.000; hoặc để trống." : "")
      profile.elements.budget.setAttribute("aria-invalid", String(invalid))
      if (invalid) showProfileStatus("Ngân sách chỉ nhận số tiền VND nguyên không âm; bạn có thể để trống.")
      else showProfileStatus("")
    })
    profile.elements.budget.addEventListener("blur", () => {
      const value = budgetValue()
      if (value !== null && Number.isFinite(value)) profile.elements.budget.value = formatBudget(value)
    })
    document.querySelector("[data-profile-cancel]").addEventListener("click", () => {
      avatar = saved.avatar
      picker.value = ""
      renderProfile()
      setEditing(false)
      showProfileStatus("")
    })
    document.querySelector("[data-avatar-change]").addEventListener("click", () => picker.click())
    picker.addEventListener("change", () => {
      const file = picker.files[0]
      if (!file) return
      if (!["image/png", "image/jpeg", "image/webp"].includes(file.type) || file.size > 1024 * 1024) {
        notify("Chọn ảnh PNG, JPG hoặc WebP không quá 1 MB.")
        picker.value = ""
        return
      }
      const reader = new FileReader()
      avatarPending = true
      reader.onload = () => {
        avatarPending = false
        avatar = reader.result
        renderAvatar()
        setEditing(true)
        notify("Ảnh đang được xem trước. Chọn Lưu thay đổi để lưu trong phiên này.")
      }
      reader.onerror = () => { avatarPending = false; notify("Không thể đọc ảnh. Vui lòng chọn lại.") }
      reader.readAsDataURL(file)
    })
    profile.addEventListener("submit", (event) => {
      event.preventDefault()
      if (avatarPending) { notify("Vui lòng đợi ảnh tải xong."); return }
      const next = Object.fromEntries(fields.map((key) => [key, profile.elements[key].value.trim()]))
      const budget = budgetValue()
      if (Number.isNaN(budget)) {
        showProfileStatus("Ngân sách không hợp lệ. Nhập số tiền VND nguyên không âm hoặc để trống.")
        profile.elements.budget.setAttribute("aria-invalid", "true")
        profile.elements.budget.focus()
        return
      }
      profile.elements.budget.setCustomValidity("")
      if (!next.name || !next.username || !next.email) {
        setEditing(true)
        showProfileStatus("Vui lòng điền họ tên, username và email trước khi lưu.")
        return
      }
      if (!profile.checkValidity()) {
        const invalid = [...profile.elements].find((input) => input.willValidate && !input.validity.valid)
        if (personalEditor.contains(invalid)) setEditing(true)
        showProfileStatus("Vui lòng kiểm tra thông tin chưa hợp lệ trước khi lưu.")
        profile.reportValidity()
        return
      }
      careKeys.forEach((key) => {
        // Preserve unmatched legacy free text until this group is explicitly changed.
        next[key] = !changedCare.has(key) && saved[key] && !document.querySelector(`[data-care-legacy="${key}"]`).hidden
          ? saved[key] : key === "skin" ? profile.elements.skin.value || "Chưa xác định" : careInputs(key).filter((input) => input.checked).map((input) => input.value)
      })
      next.budget = budget
      if (write("spa-profile", { ...saved, ...next, avatar })) {
        saved = { ...saved, ...next, avatar }
        renderProfile()
        setEditing(false)
        document.dispatchEvent(new Event("spa-profile-updated"))
        showProfileStatus("Đã lưu hồ sơ chăm sóc và thông tin cá nhân trong phiên demo.", "success")
        notify("Đã lưu hồ sơ mẫu trong phiên này.")
      } else showProfileStatus("Chưa lưu được hồ sơ. Vui lòng kiểm tra quyền lưu trữ phiên của trình duyệt.")
    })
    const password = document.querySelector("#profile-password")
    const passwordOpen = document.querySelector("[data-password-open]")
    const passwordStatus = document.querySelector("[data-password-status]")
    const closePassword = () => {
      password.reset()
      password.hidden = true
      passwordOpen.setAttribute("aria-expanded", "false")
      passwordOpen.focus()
    }
    passwordOpen.addEventListener("click", () => {
      if (!password.hidden) { closePassword(); return }
      passwordStatus.textContent = ""
      password.hidden = false
      passwordOpen.setAttribute("aria-expanded", "true")
      password.elements.currentPassword.focus()
    })
    document.querySelector("[data-password-cancel]").addEventListener("click", closePassword)
    password.addEventListener("input", () => password.elements.confirmPassword.setCustomValidity(""))
    password.addEventListener("reset", () => password.elements.confirmPassword.setCustomValidity(""))
    password.addEventListener("submit", (event) => {
      event.preventDefault()
      const confirmation = password.elements.confirmPassword
      confirmation.setCustomValidity(confirmation.value !== password.elements.newPassword.value ? "Xác nhận mật khẩu không khớp." : "")
      if (!password.reportValidity()) return
      closePassword()
      passwordStatus.textContent = "Form mẫu hợp lệ. Mật khẩu chưa được thay đổi; thông tin đăng nhập demo giữ nguyên."
    })
  }
  const reviewSection = document.querySelector("[data-service-reviews]")
  const myReviews = document.querySelector(".reviews-page")
  const adminReviews = document.querySelector("[data-admin-review-analysis]")
  if (reviewSection || myReviews || adminReviews) {
    const session = read("spa-auth", {})
    const isUser = window.spaAuth.isAuthenticated() && session.role === "User"
    const owner = isUser ? session.username : null
    const isAdmin = window.spaAuth.isAuthenticated() && session.role === "Admin"
    if (adminReviews) adminReviews.hidden = !isAdmin
    const escape = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[char])
    const serviceId = Number(params.get("id") ?? "0")
    const service = window.spaCatalog.services.find((item) => item.active === true && item.id === serviceId)
    const appointments = () => {
      const items = read("spa-appointments", [])
      return Array.isArray(items) ? items : []
    }
    const candidates = () => !isUser || !service || service.active !== true ? [] : appointments().filter((item) => {
      const existing = reviewFor(item.id)
      return item.owner === owner && item.status === "completed" && item.serviceId === serviceId &&
        (!existing || (existing.owner === owner && existing.serviceId === serviceId))
    })
    const reviewUrl = (review) => `service-detail.html?id=${review.serviceId}&appointment=${encodeURIComponent(review.appointmentId)}#reviews`
    const dateLabel = (value) => {
      const date = new Date(value)
      return value && Number.isFinite(date.getTime()) ? date.toLocaleDateString("vi-VN") : "Ngày chưa cập nhật"
    }
    const stars = (rating) => `<span class="review-stars" role="img" aria-label="${rating} trên 5 sao">${[1, 2, 3, 4, 5].map((number) =>
      `<span data-selected="${number <= rating}">${window.spaIcon("star")}</span>`).join("")}</span>`
    const validReview = (review) => review && typeof review.owner === "string" && typeof review.appointmentId === "string" && Number.isInteger(review.serviceId) &&
      Number.isInteger(Number(review.rating)) && Number(review.rating) >= 1 && Number(review.rating) <= 5 && typeof review.message === "string"
    const reviewImages = (review) => (Array.isArray(review?.images) ? review.images : []).filter((src) =>
      typeof src === "string" && (/^data:image\/(?:jpeg|png|webp);base64,/.test(src) || /^images\/[a-zA-Z0-9_/-]+\.(?:jpe?g|png|webp)$/.test(src))).slice(0, 3)
    const gallery = (images, editable = false) => images.map((src, index) => `<figure><img src="${escape(src)}" alt="Ảnh trải nghiệm ${index + 1}" loading="lazy">
      ${editable ? `<button type="button" data-remove-review-image="${index}" aria-label="Xóa ảnh trải nghiệm ${index + 1}">${window.spaIcon("close")}</button>` : ""}</figure>`).join("")
    function renderReviews() {
      const list = document.querySelector(adminReviews ? "#admin-review-list" : "#review-list")
      const items = reviewRecords().filter((review) => validReview(review) && (adminReviews
        ? window.spaAuth.isAuthenticated() && session.role === "Admin" : myReviews ? review.owner === owner : review.serviceId === serviceId))
      list.innerHTML = items.length ? items.map((review) => {
        const treatment = window.spaCatalog.services.find((item) => item.id === review.serviceId)
        const name = review.name || "Khách An Nhiên"
        const initials = String(name).trim().split(/\s+/).slice(-2).map((part) => part[0]).join("").toUpperCase()
        const reply = typeof review.reply === "string" ? review.reply : review.reply?.message
        const rating = Number(review.rating)
        const sentiment = rating >= 4 ? "Tích cực" : rating === 3 ? "Trung lập" : "Tiêu cực"
        const summary = rating >= 4 ? "Khách hàng thể hiện mức độ hài lòng cao với trải nghiệm."
          : rating === 3 ? "Trải nghiệm được đánh giá ở mức trung bình, còn dư địa để chăm sóc tốt hơn."
          : "Khách hàng chưa hài lòng; Spa cần lắng nghe thêm những điều cần cải thiện."
        return `<article class="review-item">
          ${myReviews || adminReviews ? `<span class="eyebrow">${adminReviews ? "ĐÁNH GIÁ KHÁCH HÀNG" : "TRẢI NGHIỆM CỦA BẠN"}</span><h2>${escape(treatment?.name || "Dịch vụ đã trải nghiệm")}</h2>` : ""}
          <div class="review-byline"><span class="account-avatar" aria-hidden="true">${escape(initials)}</span>
            <div><strong>${escape(name)}</strong>${stars(rating)}</div><time datetime="${escape(review.createdAt || "")}">${escape(dateLabel(review.createdAt))}</time></div>
          <p class="review-comment">${escape(review.message)}</p>
          ${reviewImages(review).length ? `<div class="review-gallery">${gallery(reviewImages(review))}</div>` : ""}
          ${reply ? `<div class="review-reply"><span class="eyebrow">PHẢN HỒI TỪ AN NHIÊN SPA</span><p>${escape(reply)}</p></div>` : ""}
          ${adminReviews ? `<div class="review-analysis"><span>Cảm xúc: ${sentiment}</span><p>Tóm tắt AI demo: ${summary}</p></div>` : ""}
          ${myReviews ? `<div class="review-actions"><a class="button small" href="${reviewUrl(review)}">Chỉnh sửa</a><a class="button small" href="service-detail.html?id=${review.serviceId}#reviews">Xem dịch vụ</a></div>` : ""}
        </article>`
      }).join("") : `<div class="review-empty"><p>${adminReviews ? "Chưa có đánh giá trong phiên để phân tích." : myReviews ? "Bạn chưa có đánh giá nào." : "Chưa có đánh giá cho liệu trình này."}</p>
        ${myReviews ? '<a class="button" href="appointments.html?status=completed">Xem lịch hẹn đã hoàn thành</a>' : ""}</div>`
      if (reviewSection) {
        reviewSection.querySelector("[data-review-average]").textContent = items.length
          ? `${(items.reduce((sum, review) => sum + Number(review.rating), 0) / items.length).toFixed(1)} / 5` : "— / 5"
        reviewSection.querySelector("[data-review-count]").textContent = `${items.length} đánh giá`
      }
    }
    renderReviews()
    if (reviewSection && service) {
      const reviews = document.querySelector("#review-form")
      const open = document.querySelector("[data-review-open]")
      const status = document.querySelector("[data-review-status]")
      const preview = document.querySelector("[data-review-photo-preview]")
      let images = [], photosLoading = false, photoVersion = 0
      const available = candidates()
      reviews.elements.appointment.replaceChildren(...available.map((item) => new Option(
        `${String(item.date).split("-").reverse().join(".")} · ${item.time}`, item.id)))
      if (available.some((item) => item.id === params.get("appointment"))) reviews.elements.appointment.value = params.get("appointment")
      const pinned = available.find((item) => item.id === params.get("appointment")) || (available.length === 1 ? available[0] : null)
      if (pinned) {
        reviews.elements.appointment.disabled = true
        document.querySelector("[data-review-appointment]").hidden = true
        const summary = document.querySelector("[data-review-appointment-summary]")
        summary.hidden = false
        summary.textContent = `Cuộc hẹn · ${String(pinned.date).split("-").reverse().join(".")} · ${pinned.time}`
      }
      open.hidden = !available.length
      document.querySelector("[data-review-eligibility]").textContent = available.length
        ? "Cảm nhận từ cuộc hẹn đã hoàn thành của bạn. Mỗi cuộc hẹn có một đánh giá và bạn có thể chỉnh sửa."
        : "Chỉ khách có cuộc hẹn của mình đã hoàn thành mới có thể viết đánh giá cho dịch vụ này."
      const updateStars = () => reviews.querySelectorAll(".review-rating label").forEach((label) => {
        label.dataset.selected = String(Number(label.querySelector("input").value) <= Number(reviews.elements.rating.value))
      })
      const renderPhotos = () => { preview.innerHTML = gallery(images, true) }
      const resetEditor = () => {
        const appointment = reviews.elements.appointment.value
        reviews.reset()
        reviews.elements.appointment.value = appointment
        images = []; photosLoading = false; photoVersion++
        reviews.querySelector('[type="submit"]').disabled = false
        reviews.querySelector('[type="submit"]').textContent = "Gửi đánh giá"
        renderPhotos()
        updateStars()
      }
      const loadReview = () => {
        photoVersion++; photosLoading = false
        reviews.elements.photos.value = ""
        reviews.querySelector('[type="submit"]').disabled = false
        const existing = reviewFor(reviews.elements.appointment.value)
        const appointment = available.find((item) => item.id === reviews.elements.appointment.value)
        reviews.querySelector("[data-review-appointment-summary]").textContent = appointment
          ? `Cuộc hẹn · ${String(appointment.date).split("-").reverse().join(".")} · ${appointment.time}` : ""
        reviews.querySelectorAll('input[name="rating"]').forEach((input) => { input.checked = Boolean(existing && Number(input.value) === Number(existing.rating)) })
        reviews.elements.message.value = existing?.message || ""
        reviews.querySelector('[type="submit"]').textContent = existing ? "Lưu thay đổi" : "Gửi đánh giá"
        reviews.querySelector('[type="submit"]').disabled = false
        open.textContent = existing ? "Chỉnh sửa đánh giá" : "Viết đánh giá"
        images = reviewImages(existing)
        renderPhotos()
        updateStars()
      }
      const setOpen = (shown) => {
        reviews.hidden = !shown
        open.setAttribute("aria-expanded", String(shown))
        if (shown) reviews.elements.message.focus({ preventScroll: true })
        else open.focus({ preventScroll: true })
      }
      reviews.querySelectorAll("[data-rating-icon]").forEach((node) => { node.innerHTML = window.spaIcon("star") })
      reviews.elements.appointment.addEventListener("change", loadReview)
      reviews.querySelectorAll('input[name="rating"]').forEach((input) => input.addEventListener("change", updateStars))
      open.addEventListener("click", () => { loadReview(); setOpen(reviews.hidden) })
      document.querySelector("[data-review-cancel]").addEventListener("click", () => { resetEditor(); setOpen(false) })
      preview.addEventListener("click", (event) => {
        const button = event.target.closest("[data-remove-review-image]")
        if (!button || photosLoading) return
        const index = Number(button.dataset.removeReviewImage)
        if (Number.isInteger(index) && index >= 0 && index < images.length) { images.splice(index, 1); renderPhotos() }
      })
      reviews.elements.photos.addEventListener("change", async () => {
        const files = [...reviews.elements.photos.files]
        reviews.elements.photos.value = ""
        if (!files.length) return
        if (photosLoading || images.length + files.length > 3) { status.textContent = "Bạn có thể đính kèm tối đa 3 ảnh."; return }
        if (files.some((file) => !["image/jpeg", "image/png", "image/webp"].includes(file.type) || file.size > 1024 * 1024)) {
          status.textContent = "Chọn ảnh JPG, PNG hoặc WebP, tối đa 1 MB/ảnh."; return
        }
        const version = photoVersion
        photosLoading = true
        reviews.querySelector('[type="submit"]').disabled = true
        try {
          const added = await Promise.all(files.map((file) => new Promise((resolve, reject) => {
            const reader = new FileReader()
            reader.onload = () => resolve(reader.result)
            reader.onerror = reject
            reader.readAsDataURL(file)
          })))
          if (version === photoVersion) { images.push(...added); renderPhotos(); status.textContent = "Ảnh đang được xem trước; chỉ lưu khi bạn gửi đánh giá." }
        } catch {
          if (version === photoVersion) status.textContent = "Không đọc được ảnh. Vui lòng chọn lại."
        } finally {
          if (version === photoVersion) { photosLoading = false; reviews.querySelector('[type="submit"]').disabled = false }
        }
      })
      reviews.addEventListener("submit", (event) => {
        event.preventDefault()
        const appointment = candidates().find((item) => item.id === reviews.elements.appointment.value)
        const rating = Number(reviews.elements.rating.value), message = reviews.elements.message.value.trim()
        const currentSession = read("spa-auth", {})
        if (photosLoading) { status.textContent = "Vui lòng đợi ảnh tải xong."; return }
        if (!appointment || !window.spaAuth.isAuthenticated() || currentSession.role !== "User" || currentSession.username !== owner) {
          status.textContent = "Cuộc hẹn chưa đủ điều kiện để đánh giá."; return
        }
        if (!Number.isInteger(rating) || rating < 1 || rating > 5 || !message || message.length > 2000) {
          status.textContent = "Chọn 1–5 sao và nhập cảm nhận từ 1 đến 2000 ký tự."; return
        }
        const items = reviewRecords(), index = items.findIndex((item) => item?.appointmentId === appointment.id)
        const existing = index >= 0 ? items[index] : null
        const now = new Date().toISOString()
        const review = { ...existing, id: existing?.id || crypto.randomUUID(), appointmentId: appointment.id, serviceId,
          owner, name: window.spaAuth.getProfile().name || "Khách An Nhiên", rating, message,
          createdAt: existing?.createdAt || now, updatedAt: now, images: [...images] }
        if (index >= 0) items[index] = review
        else items.push(review)
        if (write("spa-reviews", items)) {
          renderReviews()
          resetEditor()
          open.textContent = "Chỉnh sửa đánh giá"
          setOpen(false)
          status.textContent = existing ? "Đánh giá của bạn đã được cập nhật." : "Cảm ơn bạn đã chia sẻ trải nghiệm cùng An Nhiên Spa."
          notify(status.textContent)
        }
      })
      loadReview()
      if (location.hash === "#reviews") {
        const requested = params.get("appointment")
        if (available.length && (!requested || available.some((item) => item.id === requested))) setOpen(true)
        else if (requested) status.textContent = "Cuộc hẹn này chưa đủ điều kiện để viết hoặc sửa đánh giá."
        const scroll = () => { if (reviewSection.isConnected) reviewSection.scrollIntoView({ block: "start" }) }
        if (document.readyState === "complete") scroll()
        else window.addEventListener("load", scroll, { once: true })
      }
    }
  }

  const recommendation = document.querySelector("[data-recommendation]")
  if (recommendation && window.spaAuth.isAuthenticated() && read("spa-auth", {}).role === "User") {
    recommendation.hidden = false
    const form = recommendation.querySelector("form"), catalog = window.spaCatalog
    const profile = window.spaAuth.getProfile()
    const normalize = (value) => String(value || "").toLocaleLowerCase("vi").normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/g, "d")
    const escape = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[char])
    const products = catalog.products.filter((item) => item.active === true)
    const skins = [...new Set(products.flatMap((item) => item.skins).filter((skin) => skin !== "Không áp dụng"))]
    form.elements.skin.replaceChildren(new Option("Chưa xác định", ""), ...skins.map((skin) => new Option(skin, skin)))
    const savedSkin = skins.find((skin) => normalize(skin) === normalize(profile.skin_type || profile.skin))
    if (savedSkin) form.elements.skin.value = savedSkin
    const savedBudget = profile.budget === null || profile.budget === "" ? NaN : Number(profile.budget)
    form.elements.budget.value = Number.isFinite(savedBudget) && savedBudget >= 0 ? savedBudget : ""
    const preferences = profile.preferences ?? profile.interests
    form.elements.interests.value = Array.isArray(preferences) ? preferences.join(", ") : preferences || ""
    const needsLabels = { face: "Chăm sóc da mặt", relax: "Thư giãn", body: "Chăm sóc cơ thể", hair: "Chăm sóc tóc" }
    const savedNeed = normalize(profile.care_needs || profile.needs)
    const needPatterns = { face: /face|da mat/, relax: /relax|thu gian|massage/, body: /body|co the/, hair: /hair|toc|da dau/ }
    const savedGroup = Object.keys(needsLabels).find((group) => savedNeed && needPatterns[group].test(savedNeed))
    if (savedGroup) form.elements.needs.value = savedGroup
    form.addEventListener("submit", (event) => {
      event.preventDefault()
      if (!form.reportValidity() || !window.spaAuth.isAuthenticated() || read("spa-auth", {}).role !== "User") return
      const skin = form.elements.skin.value, needs = form.elements.needs.value
      const budget = form.elements.budget.value === "" ? Infinity : form.elements.budget.valueAsNumber
      if (Number.isNaN(budget) || budget < 0) return
      const interests = form.elements.interests.value.trim(), duration = form.elements.duration.value
      const durationLabels = { short: "Dưới 60 phút", medium: "60–90 phút", long: "Trên 90 phút" }
      const money = (value) => `${value.toLocaleString("vi-VN")} VND`
      const durationMatch = (item) => !duration || (duration === "short" ? item.minutes < 60 : duration === "medium" ? item.minutes >= 60 && item.minutes <= 90 : item.minutes > 90)
      const needMatch = (item) => !needs || item.careGroup === needs ? 1
        : needs === "relax" && /massage|thu gian/.test(normalize(item.name)) ? .85 : 0
      const preferenceTerms = ["thư giãn", "nhẹ nhàng", "dịu nhẹ", "cấp ẩm", "đá nóng", "tinh dầu", "tóc", "da đầu", "phục hồi"]
        .filter((term) => normalize(interests).includes(normalize(term)))
      // Negative/medical preferences need a specialist; do not claim language understanding.
      const needsAdvice = /khong|tranh|di ung/.test(normalize(interests))
      const skinProducts = new Set(products.filter((item) => [...item.skins, ...item.audiences].includes(skin)).map((item) => item.id))
      const skinServices = new Set(catalog.relations.filter((relation) => skinProducts.has(relation.productId)).map((relation) => relation.serviceId))
      const preferenceHits = (item) => needsAdvice ? [] : preferenceTerms.filter((term) => normalize(`${item.name} ${item.category} ${item.description}`).includes(normalize(term)))
      const relevant = catalog.services.filter((item) => item.active === true && needMatch(item) > 0)
      const minimumPrice = Math.min(...relevant.map((item) => item.priceValue))
      const ranked = relevant.filter((item) => item.priceValue <= budget).map((item) => {
        const hits = preferenceHits(item)
        // 35 needs + 25 linked skin-care evidence + 20 budget + 10 preferences + 10 duration.
        // Unspecified criteria receive half weight, not an invented perfect match.
        const score = Math.round((needs ? 35 * needMatch(item) : 17.5) + (skin ? skinServices.has(item.id) ? 25 : 0 : 12.5)
          + (Number.isFinite(budget) ? 20 : 10) + (preferenceTerms.length && !needsAdvice ? 10 * hits.length / preferenceTerms.length : 5)
          + (duration ? durationMatch(item) ? 10 : 0 : 5))
        return { item, hits, score }
      }).sort((a, b) => b.score - a.score || a.item.priceValue - b.item.priceValue || a.item.id - b.item.id)
      const services = ranked.slice(0, 3), best = services[0]?.item
      const relatedProducts = new Set(catalog.relations.filter((relation) => relation.serviceId === best?.id).map((relation) => relation.productId))
      const care = products.filter((item) => relatedProducts.has(item.id) &&
        (!skin || item.skins.includes("Không áp dụng") || [...item.skins, ...item.audiences].includes(skin)))
        .sort((a, b) => Number([...b.skins, ...b.audiences].includes(skin)) - Number([...a.skins, ...a.audiences].includes(skin)) ||
          preferenceHits(b).length - preferenceHits(a).length || a.id - b.id).slice(0, 3)
      const chips = [skin || "Chưa xác định loại da", needsLabels[needs] || "Khám phá liệu trình",
        Number.isFinite(budget) ? `≤ ${money(budget)}` : "Ngân sách linh hoạt", durationLabels[duration] || "Thời lượng không quan trọng"]
      if (interests) chips.push(interests)
      const alternatives = [], used = new Set(best ? [best.id] : [])
      const addAlternative = (label, choice) => {
        if (choice && !used.has(choice.id)) { used.add(choice.id); alternatives.push({ label, item: choice }) }
      }
      if (best) {
        addAlternative("Nếu muốn tiết kiệm hơn", ranked.find(({ item }) => item.id !== best.id && item.priceValue < best.priceValue)?.item)
        if (!/massage|thu gian/.test(normalize(best.name))) {
          addAlternative("Nếu ưu tiên thư giãn hơn", ranked.find(({ item }) => !used.has(item.id) && /massage|thu gian/.test(normalize(item.name)))?.item)
        }
        addAlternative("Nếu có thêm thời gian", ranked.find(({ item }) => !used.has(item.id) && item.minutes > best.minutes)?.item)
      }
      let priority = [needs ? `đúng nhu cầu ${needsLabels[needs].toLocaleLowerCase("vi")}` : "khám phá liệu trình",
        Number.isFinite(budget) ? `trong ngân sách ${money(budget)}` : "đối chiếu các tiêu chí bạn đã cung cấp"].join(" và ")
      if (services.length > 1) {
        const runner = services[1]
        const drivers = [
          [needs ? 35 * (needMatch(best) - needMatch(runner.item)) : 0, "nhu cầu chăm sóc khớp hơn"],
          [skin ? 25 * (Number(skinServices.has(best.id)) - Number(skinServices.has(runner.item.id))) : 0, `dữ liệu chăm sóc liên quan cho ${skin}`],
          [preferenceTerms.length && !needsAdvice ? 10 * (services[0].hits.length - runner.hits.length) / preferenceTerms.length : 0, "từ khóa sở thích đối chiếu được"],
          [duration ? 10 * (Number(durationMatch(best)) - Number(durationMatch(runner.item))) : 0, `thời lượng ${durationLabels[duration].toLocaleLowerCase("vi")}`],
        ].filter(([difference]) => difference > 0).sort((a, b) => b[0] - a[0])
        priority = services[0].score === runner.score
          ? best.priceValue < runner.item.priceValue ? "mức giá thấp hơn khi các lựa chọn có điểm tương đương" : "thứ tự catalog ổn định khi điểm và giá tương đương, không khẳng định một lựa chọn vượt trội"
          : drivers.length ? drivers.slice(0, 2).map(([, label]) => label).join(" và ") : priority
      }
      priority = `Hệ thống ưu tiên ${priority}.${best && duration && !durationMatch(best) ? " Thời lượng được xem là tiêu chí phụ trong trường hợp này." : ""}`
      recommendation.querySelector("[data-recommendation-results]").innerHTML = `<section class="review-surface" data-recommendation-summary><h2>An Nhiên hiểu nhu cầu của bạn</h2>
        <p>Bạn chọn ${escape(skin || "chưa xác định loại da")}, ưu tiên ${escape((needsLabels[needs] || "khám phá liệu trình").toLocaleLowerCase("vi"))},
          ${Number.isFinite(budget) ? `ngân sách tối đa ${money(budget)}` : "chưa đặt giới hạn ngân sách"} và ${escape(durationLabels[duration] || "không giới hạn thời lượng")}.</p>
        <ul class="recommendation-chips">${chips.map((chip) => `<li title="${escape(chip)}">${escape(chip)}</li>`).join("")}</ul></section>
        <section><h2>Liệu trình gợi ý</h2>${best ? `<p class="review-note"><strong>Ưu tiên của hệ thống:</strong> ${escape(priority)}</p>` : ""}<div class="catalog-grid">${services.map(({ item, hits, score }, index) => {
          const reasons = [
            needs ? needMatch(item) === 1 ? `Đúng nhóm nhu cầu ${needsLabels[needs].toLocaleLowerCase("vi")}.` : "Tên liệu trình có massage/thư giãn, cùng định hướng bạn chọn." : `Thuộc nhóm ${item.category.toLocaleLowerCase("vi")} để bạn khám phá.`,
            Number.isFinite(budget) ? `Giá ${item.price} nằm trong ngân sách ${money(budget)}.` : `Giá gốc ${item.price} để bạn đối chiếu trước khi đặt lịch.`,
          ]
          if (skin && skinServices.has(item.id)) reasons.push(`Có sản phẩm chăm sóc liên kết dành cho ${skin.toLocaleLowerCase("vi")}.`)
          if (duration && durationMatch(item)) reasons.push(`Thời lượng ${item.duration} khớp mong muốn ${durationLabels[duration].toLocaleLowerCase("vi")}.`)
          if (hits.length) reasons.push(`Mô tả có ${hits.join(", ")}, khớp sở thích bạn nêu.`)
          const tradeoffs = []
          if (duration && !durationMatch(item)) tradeoffs.push(`thời lượng ${item.duration} chưa đúng mong muốn ${durationLabels[duration].toLocaleLowerCase("vi")}`)
          if (needs && needMatch(item) < 1) tradeoffs.push("nhu cầu chỉ khớp theo định hướng thư giãn, chưa thuộc đúng nhóm chính")
          if (hits.length && hits.length < preferenceTerms.length) tradeoffs.push("mới đối chiếu được một phần từ khóa sở thích")
          return `<article class="review-surface" data-recommended-service="${item.id}"><span class="eyebrow">#${index + 1} ${["Phù hợp nhất", "Lựa chọn thay thế", "Có thể cân nhắc"][index]}</span><h3>${escape(item.name)}</h3>
          <p class="recommendation-meta">${escape(item.price)} · ${escape(item.duration)}</p><p>${escape(item.description)}</p>
          <p class="recommendation-meta">Mức phù hợp: ${score >= 85 ? "Rất cao" : score >= 65 ? "Cao" : "Có thể cân nhắc"} <span class="review-note">(ước tính ${score}/100)</span>${tradeoffs.length ? `<br><span class="review-note">Chưa đạt mức phù hợp tối đa vì ${escape(tradeoffs.join("; "))}.</span>` : ""}</p>
          <p>Vì sao phù hợp với bạn</p><ul class="recommendation-reasons">${reasons.slice(0, 4).map((reason) => `<li>${escape(reason)}</li>`).join("")}</ul>
          <p>Điểm khớp</p><dl class="recommendation-matches"><dt>Nhu cầu</dt><dd>${needs ? needMatch(item) === 1 ? "Đúng nhóm đã chọn" : "Cùng định hướng thư giãn" : "Chưa chọn cụ thể"}</dd>
            <dt>Loại da</dt><dd>${skin ? skinServices.has(item.id) ? "Có chăm sóc liên quan phù hợp" : "Chưa có dữ liệu đối chiếu" : "Chưa xác định"}</dd>
            <dt>Ngân sách</dt><dd>${escape(item.price)}${Number.isFinite(budget) ? ` / ${money(budget)}` : " · Chưa giới hạn"}</dd>
            <dt>Thời lượng</dt><dd>${escape(item.duration)}${duration ? durationMatch(item) ? " · Khớp mong muốn" : " · Khác mong muốn" : ""}</dd>
            <dt>Sở thích</dt><dd>${needsAdvice ? "Cần trao đổi với chuyên viên" : hits.length ? escape(hits.join(", ")) : interests ? "Chưa đủ dữ liệu đối chiếu" : "Chưa cung cấp"}${interests && !needsAdvice && !hits.length ? `<br>Chưa có đủ dữ liệu để đánh giá mức độ phù hợp với sở thích «${escape(interests)}».` : ""}</dd></dl>
          <div class="review-actions"><a class="button small" href="service-detail.html?id=${item.id}">Xem chi tiết</a><a class="button filled small" href="booking.html?service=${item.id}">Đặt lịch</a></div></article>`
        }).join("")}</div>
        ${services.length ? "" : `<p>Chưa có liệu trình cùng nhu cầu trong ngân sách này.${Number.isFinite(minimumPrice) && Number.isFinite(budget) ? ` Giá thấp nhất cùng nhu cầu là ${money(minimumPrice)}, cao hơn ngân sách ${money(budget)}.` : ""} Bạn có thể điều chỉnh lựa chọn hoặc liên hệ Spa; hệ thống không tự thêm dịch vụ vượt ngân sách.</p>`}</section>
        <section><h2>Bạn cũng có thể cân nhắc</h2>${alternatives.length ? `<ul class="recommendation-alternatives">${alternatives.map(({ label, item }) =>
          `<li><span>${escape(label)}</span><a href="service-detail.html?id=${item.id}">${escape(item.name)}</a> · ${escape(item.price)} · ${escape(item.duration)}</li>`).join("")}</ul>`
          : "<p>Hiện chưa có phương án khác cùng nhu cầu và ngân sách trong catalog.</p>"}</section>
        <section><h2>Chăm sóc sau liệu trình</h2><div class="catalog-grid">${care.map((item) => `<article class="review-surface" data-recommended-product="${item.id}"><span class="eyebrow">${escape(item.category)}</span><h3>${escape(item.name)}</h3>
          <p>${escape(item.description)}</p><p class="review-note">${escape((item.skins.includes("Không áp dụng") ? item.audiences : item.skins).join(" · "))}</p>
          <p class="review-note">Vai trò trong chăm sóc tại nhà: ${escape(Array.isArray(item.benefits) ? item.benefits.join(" ") : item.benefits || item.usage || item.description)} Được liên kết với liệu trình ${escape(best?.name)}${skin && [...item.skins, ...item.audiences].includes(skin) ? ` và có đối tượng chăm sóc ${escape(skin.toLocaleLowerCase("vi"))}` : ""}${preferenceHits(item).length ? `; mô tả khớp sở thích ${escape(preferenceHits(item).join(", "))}` : ""}.</p>
          <div class="review-actions"><a class="button small" href="product-detail.html?id=${item.id}">Xem chi tiết</a></div></article>`).join("")}</div>
        ${care.length ? "" : `<p>${best ? "Chưa có sản phẩm liên kết phù hợp với loại da đã chọn." : "Chọn được liệu trình trước để xem chăm sóc liên quan; không gợi ý sản phẩm ngẫu nhiên."}</p>`}</section>
        <section data-recommendation-basis><h2>Cơ sở đề xuất</h2><p>Gợi ý được tạo từ loại da, nhu cầu chăm sóc, ngân sách, sở thích, thời lượng mong muốn và dữ liệu dịch vụ/sản phẩm của An Nhiên.</p>
          <p>Mức phù hợp được ước tính từ năm tiêu chí trên; loại da được đối chiếu qua sản phẩm liên kết, không phải chẩn đoán hoặc xác nhận phù hợp y khoa.</p>
          <p>Ở phiên bản hệ thống hoàn chỉnh, kết quả có thể được cá nhân hóa thêm dựa trên hồ sơ và lịch sử sử dụng dịch vụ của khách hàng.</p>
          <p>Gợi ý minh họa từ dữ liệu hiện có, chưa gọi AI thật. Thông tin trả lời không được lưu.</p></section>`
      recommendation.querySelector("[data-recommendation-status]").textContent = `${services.length} liệu trình được xếp hạng và ${care.length} gợi ý chăm sóc liên kết.${duration && services.length && !services.some(({ item }) => durationMatch(item)) ? " Chưa có thời lượng đúng mong muốn; xem điểm khớp để cân nhắc." : ""}`
    })
  }

  const chatPages = new Set(["home.html", "services.html", "service-detail.html", "products.html", "product-detail.html",
    "promotions.html", "promotion-detail.html", "booking.html", "appointments.html", "invoice.html", "reviews.html", "profile.html"])
  const pageName = location.pathname.split("/").pop()
  if (chatPages.has(pageName) && window.spaAuth.isAuthenticated() && read("spa-auth", {}).role === "User") {
    const concierge = document.createElement("aside")
    concierge.className = "concierge"
    concierge.innerHTML = `<button class="concierge-bubble" type="button" aria-label="Mở Trợ lý An Nhiên" aria-controls="concierge-panel" aria-expanded="false">${window.spaIcon("chat")}</button>
      <section class="concierge-panel" id="concierge-panel" role="dialog" aria-modal="false" aria-labelledby="concierge-title" hidden>
        <div class="concierge-heading"><div><span class="eyebrow">AN NHIÊN / CONCIERGE</span><h2 id="concierge-title">Trợ lý An Nhiên</h2><p>Tư vấn dịch vụ và chăm sóc tại Spa</p></div>
          <button type="button" data-chat-close aria-label="Đóng trò chuyện">${window.spaIcon("close")}</button></div>
        <div class="concierge-messages" role="log" aria-live="polite" aria-relevant="additions" aria-label="Cuộc trò chuyện minh họa">
          <p>Xin chào, mình là trợ lý An Nhiên. Mình có thể giúp bạn tìm dịch vụ phù hợp, khuyến mãi và thông tin chăm sóc.</p></div>
        <div class="concierge-suggestions"><button type="button">Tư vấn dịch vụ</button><button type="button">Khuyến mãi hiện có</button><button type="button">Chăm sóc da</button></div>
        <form class="concierge-form"><input id="concierge-message" name="message" required maxlength="500" autocomplete="off" aria-label="Tin nhắn của bạn" placeholder="Mình có thể giúp gì cho bạn?"><button class="button filled small" type="submit">Gửi</button></form>
        <p class="concierge-note">Phản hồi minh họa, chưa gọi AI thật. Không nhập thông tin nhạy cảm.</p>
      </section>`
    document.body.append(concierge)
    const bubble = concierge.querySelector(".concierge-bubble"), panel = concierge.querySelector(".concierge-panel")
    const messages = concierge.querySelector(".concierge-messages"), chatForm = concierge.querySelector("form")
    const footer = document.querySelector("footer")
    const adjustDock = () => {
      const top = footer?.getBoundingClientRect().top ?? innerHeight
      const lift = panel.hidden ? Math.max(0, innerHeight - top) : 0
      concierge.style.setProperty("--footer-lift", `${Math.min(lift, Math.max(0, innerHeight - 112))}px`)
      bubble.hidden = panel.hidden && top < 100
    }
    const setOpen = (shown) => {
      panel.hidden = !shown
      bubble.setAttribute("aria-expanded", String(shown))
      adjustDock()
      if (shown) chatForm.elements.message.focus({ preventScroll: true })
      else if (!bubble.hidden) bubble.focus({ preventScroll: true })
    }
    const respond = (question) => {
      const message = question.trim().slice(0, 500)
      if (!message) return
      const user = document.createElement("p")
      user.className = "concierge-question"
      user.textContent = message
      messages.append(user)
      const query = message.toLocaleLowerCase("vi").normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/g, "d")
      let reply = "An Nhiên có các liệu trình thư giãn, chăm sóc da, cơ thể và tóc. Chuyên viên sẽ tư vấn sự phù hợp trước cuộc hẹn.", href = "services.html", label = "Xem dịch vụ phù hợp"
      if (window.spaAuth.isAuthenticated() && read("spa-auth", {}).role === "User") href = "services.html#recommendations"
      if (/khuyen mai|uu dai/.test(query)) {
        reply = "Mời bạn xem chương trình, thời gian và điều kiện tại trang Khuyến mãi. Mức giảm thực tế được Spa xác nhận."; href = "promotions.html"; label = "Xem khuyến mãi"
      } else if (/cham soc da|da kho|da nhay cam|da mat/.test(query)) {
        reply = "Bạn có thể tham khảo chăm sóc da mặt và cấp ẩm. Hãy trao đổi tình trạng da, dị ứng với chuyên viên; đây không phải tư vấn y khoa."
      } else if (/gio mo|dia chi|lien he/.test(query)) {
        reply = "Spa mở cửa 09:00–21:00, Thứ Hai–Chủ Nhật, tại 12 Dương Thưởng, Hòa Cường, Đà Nẵng. Bạn có thể gọi 090 123 4567."; href = "tel:0901234567"; label = "Liên hệ An Nhiên"
      } else if (/dat lich|lich hen/.test(query)) {
        reply = "Bạn có thể chọn dịch vụ, chuyên viên và giờ trống trên trang đặt lịch. Trợ lý mẫu không tự tạo hoặc xác nhận lịch hẹn."; href = window.spaAuth.urlFor("booking.html"); label = "Đến trang đặt lịch"
      }
      const answer = document.createElement("p"), link = document.createElement("a")
      answer.textContent = reply
      link.href = href
      link.textContent = `${label} →`
      answer.append(document.createElement("br"), link)
      messages.append(answer)
      while (messages.children.length > 31) messages.firstElementChild.remove()
      messages.scrollTop = messages.scrollHeight
    }
    bubble.addEventListener("click", () => setOpen(panel.hidden))
    concierge.querySelector("[data-chat-close]").addEventListener("click", () => setOpen(false))
    concierge.addEventListener("keydown", (event) => {
      if (event.key === "Escape") { event.stopPropagation(); setOpen(false) }
    })
    document.addEventListener("click", (event) => { if (!panel.hidden && !concierge.contains(event.target)) setOpen(false) })
    concierge.querySelectorAll(".concierge-suggestions button").forEach((button) => button.addEventListener("click", () => respond(button.textContent)))
    chatForm.addEventListener("submit", (event) => { event.preventDefault(); respond(chatForm.elements.message.value); chatForm.reset() })
    window.addEventListener("scroll", adjustDock, { passive: true })
    window.addEventListener("resize", adjustDock)
    adjustDock()
  }
})()
