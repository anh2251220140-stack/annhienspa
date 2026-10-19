(() => {
  "use strict";
  const main = document.querySelector("[data-admin-quality]");
  if (!main || !window.spaAuth?.isAuthenticated()) return;
  try { if (JSON.parse(sessionStorage.getItem("spa-auth"))?.role !== "Admin") return; } catch { return; }
  const $ = (selector) => document.querySelector(selector);
  const escape = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const normalize = (value) => String(value ?? "").toLocaleLowerCase("vi").normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/g, "d");
  const money = (value) => `${new Intl.NumberFormat("vi-VN").format(value)} VND`;
  const dateLabel = (value) => value.split("-").reverse().join(".");
  const day = (value) => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value || "")) return NaN;
    const d = new Date(`${value}T00:00:00Z`);
    return Number.isFinite(d.getTime()) && d.toISOString().slice(0, 10) === value ? d.getTime() / 86400000 : NaN;
  };
  const serviceName = (id) => window.spaCatalog.services.find((s) => s.id === id)?.name || "Dịch vụ chưa cập nhật";
  const average = (rows) => rows.length ? (rows.reduce((sum, r) => sum + r.rating, 0) / rows.length).toLocaleString("vi-VN", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) : "—";
  // Quality-only fictional cases, never customer records. The final two comments
  // reuse existing User demo wording; no User review or personal session is read.
  const reviewSeeds = [
    [0, 5, "Massage nhẹ nhàng, tôi rất hài lòng với liệu trình. Chuyên viên giải thích rõ từng bước, không gian yên tĩnh giúp tôi có một khoảng nghỉ dễ chịu sau ngày làm việc.", "2026-10-11"],
    [1, 4, "Chuyên viên tư vấn tận tâm, dịch vụ tốt.", "2026-10-12"],
    [2, 3, "Dịch vụ tốt nhưng xác nhận đặt lịch bị trễ.", "2026-10-12"],
    [3, 2, "Đặt lịch khó, phải chờ lâu khi đến spa.", "2026-10-13"],
    [4, 3, "Trải nghiệm ở mức bình thường, chưa có điểm nổi bật.", "2026-10-13"],
    [5, 1, "Không hài lòng vì không gian ồn.", "2026-10-13"],
    [6, 5, "Giá hợp lý và nhân viên tận tâm.", "2026-10-14"],
    [0, 4, "", "2026-10-14"],
    [1, 2, "Chi phí cao, giá chưa rõ trước liệu trình.", "2026-10-15"],
    [2, 5, "Không gian sạch, nhân viên nhẹ nhàng.", "2026-10-15"],
    [5, 5, "Rất hài lòng, nhân viên nhẹ nhàng và không gian thư giãn.", "2026-10-08"],
    [2, 4, "Dịch vụ tốt, không gian yên tĩnh và dễ chịu.", "2026-10-10"],
  ];
  const reviews = reviewSeeds.map(([serviceId, rating, message, date], index) => ({
    id: `DG-Q-${String(index + 1).padStart(3, "0")}`, customer: `Khách demo ${String(index + 1).padStart(2, "0")}`,
    serviceId, rating, message, date, images: [],
  }));
  const exactMatches = (message, phrases, tone) => phrases.flatMap((phrase) => {
    const pattern = new RegExp(phrase.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "giu");
    return [...message.matchAll(pattern)].map((match) => ({ quote: match[0], index: match.index, tone }));
  });
  // Topic-specific phrases avoid treating a contextual word ("trước liệu trình")
  // as a judgment about treatment quality. Quotes always come from the source text.
  const topicRules = [
    { key: "price", name: "Giá cả / Minh bạch chi phí", positive: ["Giá hợp lý"], negative: ["Chi phí cao", "giá chưa rõ"],
      positiveTitle: "Giá hợp lý được ghi nhận", negativeTitle: "Làm rõ chi phí trước liệu trình",
      positiveSummary: "Mức giá được khách ghi nhận là phù hợp; có thể duy trì cách trình bày chi phí đang tạo thiện cảm.",
      negativeSummary: "Phản hồi tập trung vào cảm nhận về mức phí và việc được thông tin trước dịch vụ. Không có lời chê trực tiếp về chất lượng liệu trình.",
      steps: ["Đối chiếu bảng giá công khai và nội dung tư vấn chi phí tại thời điểm trải nghiệm.", "Làm rõ với khách khoản phí nào được cho là cao hoặc chưa được giải thích trước.", "Rà soát bước giải thích chi phí trước liệu trình; thống nhất cách tư vấn sau khi xác minh, không tự sửa giá hay hoàn tiền.", "Theo dõi các phản hồi về cùng khoản phí để biết vấn đề có lặp lại."] },
    { key: "booking", name: "Trải nghiệm đặt lịch", positive: [], negative: ["Đặt lịch khó", "xác nhận đặt lịch bị trễ"],
      negativeTitle: "Rà soát khâu đặt lịch",
      negativeSummary: "Khách phản ánh vướng mắc ở bước đặt hoặc xác nhận lịch. Cần kiểm tra mốc xử lý trước khi kết luận nguyên nhân.",
      steps: ["Kiểm tra kênh đặt lịch, thời điểm gửi yêu cầu và mốc xác nhận trong hồ sơ liên quan.", "Làm rõ với khách bước nào gặp khó; nếu có chờ đợi, đối chiếu thêm giờ đến và giờ được tiếp nhận.", "Rà soát hướng dẫn đặt lịch, bước xác nhận và cách tiếp nhận khách; chỉ điều chỉnh sau khi xác minh.", "Theo dõi các phản hồi về đặt lịch và thời gian tiếp nhận ở các cuộc hẹn tiếp theo."] },
    { key: "waiting", name: "Thời gian chờ", positive: [], negative: ["chờ lâu"],
      negativeTitle: "Rà soát thời gian tiếp nhận",
      negativeSummary: "Thời gian đợi được nêu là điểm chưa hài lòng; chưa đủ thông tin để xác định khâu gây chậm.",
      steps: ["Đối chiếu giờ hẹn, giờ khách đến và thời điểm bắt đầu được phục vụ.", "Làm rõ khoảng chờ cụ thể và thông tin khách đã được hướng dẫn trong lúc đợi.", "Rà soát cách tiếp nhận và thông tin về thời gian chờ sau khi xác minh.", "Theo dõi phản hồi ở cùng khung giờ để kiểm tra tình trạng lặp lại."] },
    { key: "space", name: "Không gian", positive: ["không gian yên tĩnh", "không gian sạch", "không gian thư giãn"], negative: ["không gian ồn"],
      positiveTitle: "Không gian mang lại thư thái", negativeTitle: "Tiếng ồn cần được kiểm tra",
      positiveSummary: "Không gian là điểm được ghi nhận tích cực, góp phần vào cảm giác nghỉ ngơi trong trải nghiệm mẫu.",
      negativeSummary: "Tiếng ồn là điểm chưa hài lòng được nhắc trực tiếp. Không thể suy ra chất lượng kỹ thuật hay kết luận sự cố đã được xác minh.",
      steps: ["Kiểm tra khu vực phục vụ và khung giờ khách phản ánh về tiếng ồn.", "Nếu cần, làm rõ thời điểm và nguồn âm thanh khiến khách khó thư giãn.", "Sau khi xác minh, rà soát mức âm thanh hoặc cách bố trí hoạt động trong khu vực liên quan.", "Theo dõi phản hồi về không gian ở cùng khung giờ."] },
    { key: "staff", name: "Thái độ nhân viên", positive: ["nhân viên nhẹ nhàng", "nhân viên tận tâm", "Chuyên viên tư vấn tận tâm", "Chuyên viên giải thích rõ từng bước"], negative: [],
      positiveTitle: "Sự tận tâm được ghi nhận",
      positiveSummary: "Cách tư vấn hoặc thái độ chăm sóc là điểm tạo thiện cảm; nên ghi nhận hành vi cụ thể thay vì khái quát thành toàn bộ chất lượng dịch vụ." },
    { key: "treatment", name: "Chất lượng liệu trình", positive: ["Massage nhẹ nhàng", "hài lòng với liệu trình", "Dịch vụ tốt"], negative: [],
      positiveTitle: "Liệu trình tạo sự hài lòng",
      positiveSummary: "Khách ghi nhận cảm giác dễ chịu hoặc sự hài lòng với dịch vụ. Đây là cảm nhận trải nghiệm, không phải kết luận về hiệu quả y tế." },
  ];
  const analysisFor = (review) => {
    const bad = exactMatches(review.message, ["Không hài lòng", ...topicRules.flatMap((t) => t.negative)], "negative");
    const good = exactMatches(review.message, ["hài lòng", "tốt", "nhẹ nhàng", "yên tĩnh", "dễ chịu", "hợp lý", "tận tâm", "sạch"], "positive")
      .filter((match) => !bad.some((negative) => match.index < negative.index + negative.quote.length && match.index + match.quote.length > negative.index));
    const neutral = exactMatches(review.message, ["bình thường", "chưa có điểm nổi bật"], "neutral");
    const mixed = good.length > 0 && bad.length > 0;
    const sentiment = !review.message.trim() ? "unknown" : bad.length && !good.length ? "negative" : good.length && !bad.length ? "positive" : "neutral";
    const topics = topicRules.map((rule) => {
      const evidence = [...exactMatches(review.message, rule.negative, "negative"), ...exactMatches(review.message, rule.positive, "positive")].sort((a, b) => a.index - b.index);
      return { ...rule, evidence, tone: evidence.some((e) => e.tone === "negative") ? "negative" : "positive" };
    }).filter((t) => t.evidence.length).sort((a, b) => Number(b.tone === "negative") - Number(a.tone === "negative") || a.evidence[0].index - b.evidence[0].index);
    const primary = topics[0], secondary = topics.slice(1);
    const priority = sentiment === "negative" ? 3 : sentiment === "neutral" ? 2 : sentiment === "positive" ? 1 : 0;
    const title = sentiment === "unknown" ? "Chưa đủ dữ liệu văn bản" : mixed && primary?.key === "booking" ? "Dịch vụ tốt, xác nhận chậm" :
      primary ? primary[`${primary.tone}Title`] : "Trải nghiệm chưa có điểm nhấn";
    const focusExplanation = sentiment === "unknown" ? "Bản ghi chỉ có số sao, chưa có nhận xét để xác định điều khách hài lòng hay chưa hài lòng. Không gán cảm xúc hoặc chủ đề." :
      mixed ? `${primary?.negativeSummary || "Có cả tín hiệu khen và chê trong nội dung."} Phần được khen vẫn được ghi nhận riêng, không bị xóa bởi góp ý chưa hài lòng.` :
        primary ? primary[`${primary.tone}Summary`] : "Nhận xét mô tả trải nghiệm ở mức bình thường nhưng chưa nêu khía cạnh cụ thể. Cần làm rõ điều khách mong đợi trước khi đề xuất thay đổi.";
    const explanation = focusExplanation + (sentiment === "positive" && secondary.length ? ` Điểm tốt đi kèm được nhắc đến: ${secondary.map((t) => t.name.toLocaleLowerCase("vi")).join(", ")}.` : "");
    const reason = sentiment === "unknown" ? "Thiếu dữ liệu văn bản nên cần làm rõ, không xếp mức nghiêm trọng từ số sao." :
      sentiment === "negative" ? `Có phản ánh trực tiếp về ${primary?.name.toLocaleLowerCase("vi") || "trải nghiệm"}. Nên ưu tiên xác minh và lắng nghe; chưa có căn cứ kết luận sự cố đã xảy ra hay vi phạm nghiêm trọng.` :
        mixed ? "Nhận xét có cả khen và chê; nên theo dõi khâu chưa đáp ứng, đồng thời giữ lại điểm tốt. Không quy toàn bộ trải nghiệm thành tiêu cực." :
          sentiment === "neutral" ? "Nội dung chưa chỉ ra vấn đề cụ thể; nên hỏi thêm kỳ vọng thay vì coi điểm trung bình là sự cố." :
            "Nội dung ghi nhận điểm tốt, không có vấn đề trực tiếp cần xử lý khẩn. Ưu tiên duy trì và theo dõi, không suy thành chất lượng đã được kiểm chứng.";
    return { review, sentiment, mixed, topics, primary, secondary, evidence: [...good, ...bad, ...neutral].sort((a, b) => a.index - b.index), priority, title, explanation, reason };
  };
  const sentimentLabels = { positive: "Tích cực", neutral: "Trung lập", negative: "Tiêu cực", unknown: "Chưa đủ dữ liệu văn bản" };
  const tag = (text, tone = "neutral") => `<span class="admin-quality-chip is-${tone}">${escape(text)}</span>`;
  const stars = (rating) => `<span class="admin-quality-stars" role="img" aria-label="${rating} trên 5 sao">${[1, 2, 3, 4, 5].map((n) => `<span class="${n <= rating ? "is-filled" : ""}">${window.spaIcon("star")}</span>`).join("")}</span>`;
  const sparkles = '<svg class="line-icon" viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round" aria-hidden="true"><path d="m12 3 2.4 6.6L21 12l-6.6 2.4L12 21l-2.4-6.6L3 12l6.6-2.4L12 3Z"/><path d="m20 2 .6 1.4L22 4l-1.4.6L20 6l-.6-1.4L18 4l1.4-.6L20 2Z"/></svg>';
  const statsMarkup = (stats) => stats.map(([label, value, caption, icon], index) => `<article class="admin-finance-stat${index === 0 ? " is-featured" : ""}"><div class="admin-finance-stat-heading"><span>${label}</span>${window.spaIcon(icon)}</div><strong>${value}</strong><p>${caption}</p></article>`).join("");
  const priorityLabel = (analysis) => analysis.priority === 3 ? "Cao" : analysis.priority === 2 ? "Trung bình" : analysis.priority === 1 ? "Thấp" : "Cần làm rõ";
  const actionPlan = (analysis) => {
    if (analysis.primary?.tone === "negative") return analysis.primary.steps;
    if (analysis.sentiment === "unknown") return ["Kiểm tra bản ghi: hiện chỉ có số sao, chưa có lời nhận xét.", "Admin cân nhắc thu thập thêm nội dung qua quy trình chăm sóc phù hợp; không tự gửi yêu cầu.", "Giữ kết luận chưa đủ dữ liệu cho đến khi có thêm thông tin, không tự tạo nhận xét."];
    if (!analysis.primary) return ["Đọc lại nhận xét và bối cảnh cuộc hẹn, chưa gán nguyên nhân cho trải nghiệm ở mức bình thường.", "Nếu cần, làm rõ với khách khía cạnh chưa tạo điểm nhấn hoặc kỳ vọng chưa được đáp ứng.", "Chỉ xác định hướng cải thiện khi có thêm chi tiết; theo dõi phản hồi tương tự."];
    const plans = {
      price: ["Ghi nhận phản hồi tích cực về mức giá, đối chiếu cách thông tin chi phí tại thời điểm trải nghiệm.", "Duy trì việc giải thích giá trước liệu trình; không tự đổi giá hoặc thêm ưu đãi.", "Theo dõi những nhận xét khác về cùng mức phí để nhận biết kỳ vọng khác nhau."],
      staff: ["Xác định hành vi tư vấn hoặc chăm sóc được khách nhắc đến trong hồ sơ trải nghiệm.", "Ghi nhận điểm tích cực với nhóm chuyên viên sau khi Admin kiểm tra bối cảnh.", "Duy trì hướng dẫn tiếp đón và tư vấn; theo dõi nhận xét về sự tận tâm."],
      space: ["Ghi nhận điều kiện không gian được khách khen ở thời điểm trải nghiệm.", "Duy trì vệ sinh và sự yên tĩnh ở khu vực liên quan, không khái quát cho mọi khung giờ.", "Theo dõi thêm phản hồi về không gian để phát hiện thay đổi."],
      treatment: ["Ghi nhận bước chăm sóc hoặc thao tác nhẹ nhàng được nhắc đến; không suy ra hiệu quả y tế.", "Nếu cần, làm rõ phần liệu trình tạo cảm giác hài lòng để hiểu nhu cầu khách.", "Chia sẻ điểm tốt với nhóm dịch vụ và theo dõi khả năng duy trì trải nghiệm."],
    };
    return plans[analysis.primary.key].map((step, index, all) => index === all.length - 1 && analysis.secondary.length ? `${step} Điểm đi kèm cần theo dõi: ${analysis.secondary.map((t) => t.name.toLocaleLowerCase("vi")).join(", ")}.` : step);
  };

  if (main.dataset.adminQuality === "reviews") {
    const dialog = $("#quality-dialog");
    let page = 1, filtered = reviews.slice(), returnFocus;
    $("[data-quality-sparkle]").innerHTML = sparkles;
    const evidenceMarkup = (evidence) => {
      const unique = evidence.filter((item, index) => evidence.findIndex((other) => other.index === item.index && other.quote === item.quote) === index);
      return unique.length ? `<div class="admin-ai-quotes">${unique.map((e) => `<q class="is-${e.tone}">${escape(e.quote)}</q>`).join("")}</div>` : '<p class="admin-ai-muted">Chưa có dữ liệu văn bản để trích dẫn. Không suy diễn từ số sao.</p>';
    };
    const planMarkup = (steps, headings) => `<ol class="admin-ai-plan">${steps.map((text, index) => `<li><span class="admin-ai-step" aria-hidden="true">${String(index + 1).padStart(2, "0")}</span><div><h4>${escape(headings[index])}</h4><p>${escape(text)}</p></div></li>`).join("")}</ol>`;
    const spotlight = (title, explanation, tone, meta) => `<section class="admin-ai-spotlight is-${tone}" aria-label="AI Insight Spotlight"><div class="admin-ai-spotlight-heading"><span class="admin-eyebrow">${sparkles}AI INSIGHT SPOTLIGHT</span>${tag(meta, tone)}</div><h3>${escape(title)}</h3><p>${escape(explanation)}</p><span class="admin-ai-boundary">Diễn giải minh họa từ nội dung · Chưa xác minh sự việc · Không có điểm tin cậy giả</span></section>`;
    const singleAnalysis = (analysis) => {
      const plan = actionPlan(analysis);
      const headings = plan.length === 4 ? ["Kiểm tra thông tin", "Làm rõ với khách", "Cải thiện có căn cứ", "Theo dõi lặp lại"] :
        analysis.sentiment === "unknown" ? ["Kiểm tra bản ghi", "Bổ sung ngữ cảnh", "Giữ đúng giới hạn"] :
          !analysis.primary ? ["Đọc lại bối cảnh", "Làm rõ kỳ vọng", "Theo dõi thêm"] : ["Ghi nhận điểm tốt", "Duy trì trải nghiệm", "Theo dõi phản hồi"];
      return spotlight(analysis.title, analysis.explanation, analysis.sentiment, `Ưu tiên: ${priorityLabel(analysis)}`) +
        `<div class="admin-analysis-grid admin-ai-detail-grid">
          <article><h3>${window.spaIcon("heart")}Cảm xúc & bằng chứng</h3><div class="admin-topic-chips">${tag(sentimentLabels[analysis.sentiment], analysis.sentiment)}${analysis.mixed ? tag("Sắc thái hỗn hợp: có cả khen và chê") : ""}</div>
          <p>${analysis.mixed ? "Ghi nhận đồng thời phần được khen và phần chưa hài lòng. Nhãn trung lập ở đây không có nghĩa khách không có vấn đề." : analysis.sentiment === "unknown" ? "Không có nhận xét; chưa thể xác định khách hài lòng hoặc không hài lòng về điều gì." : "Các cụm từ dưới đây được trích nguyên văn, giữ cách viết của nhận xét gốc."}</p>${evidenceMarkup(analysis.evidence)}
          <details class="admin-ai-original"><summary>Đọc nhận xét gốc</summary><blockquote>${escape(analysis.review.message || "Chưa có nội dung nhận xét.")}</blockquote></details></article>
          <article><h3>${window.spaIcon("leaf")}Chủ đề chính & phụ</h3>${analysis.topics.length ? analysis.topics.map((topic, index) => `<div class="admin-ai-topic"><div>${tag(index === 0 ? "Chủ đề chính" : "Chủ đề phụ", topic.tone)}<strong>${topic.name}</strong></div>${evidenceMarkup(topic.evidence)}</div>`).join("") : `<p>${analysis.sentiment === "unknown" ? "Chưa có dữ liệu văn bản; không tự gán chủ đề." : "Nhận xét chưa nêu một khía cạnh cụ thể. Không tự gán chất lượng liệu trình hoặc vấn đề khác."}</p>`}
          <p class="admin-data-note">Góp ý trực tiếp được ưu tiên làm chủ đề chính; nếu cùng sắc thái, theo thứ tự xuất hiện. Nhắc bối cảnh “trước liệu trình” không đồng nghĩa chê chất lượng liệu trình.</p></article>
          <article class="admin-analysis-priority admin-ai-priority-wide is-${analysis.sentiment}"><h3>${window.spaIcon("clock")}Vì sao cần ưu tiên?</h3>${tag(priorityLabel(analysis), analysis.sentiment)}<p>${escape(analysis.reason)}</p><p class="admin-data-note">Không dùng số sao để kết luận mức độ nghiêm trọng hay xác nhận vi phạm.</p></article>
        </div><section class="admin-ai-action-section"><div class="admin-ai-section-heading"><h3>${window.spaIcon("note")}Lộ trình hành động đề xuất</h3><span>Admin xem xét và quyết định</span></div>${planMarkup(plan, headings)}<p class="admin-data-note">Đây là gợi ý, không phải thao tác đã thực hiện. Không gửi phản hồi, hoàn tiền, sửa giá hoặc đổi lịch.</p></section>`;
    };
    const aggregateAnalysis = (analyses) => {
      const counts = Object.fromEntries(Object.keys(sentimentLabels).map((s) => [s, analyses.filter((a) => a.sentiment === s).length]));
      const topics = topicRules.map((rule) => {
        const mentions = analyses.flatMap((analysis) => analysis.topics.filter((t) => t.key === rule.key).map((topic) => ({ analysis, topic })));
        return { ...rule, mentions, count: mentions.length };
      }).filter((t) => t.count).sort((a, b) => b.count - a.count || a.key.localeCompare(b.key));
      const positiveTopics = topics.filter((t) => t.mentions.some((m) => m.topic.tone === "positive")).slice(0, 3);
      const issueTopics = topics.filter((t) => t.mentions.some((m) => m.topic.tone === "negative"));
      const issueKeys = [...new Set(issueTopics.map((t) => t.key === "waiting" && issueTopics.some((t) => t.key === "booking") ? "booking" : t.key))];
      const priority = analyses.filter((a) => a.priority >= 2 || a.sentiment === "unknown").sort((a, b) => b.priority - a.priority || a.review.id.localeCompare(b.review.id)).slice(0, 3);
      const tone = counts.negative ? "negative" : analyses.some((a) => a.mixed) || counts.neutral ? "neutral" : counts.positive ? "positive" : "unknown";
      const shortNames = { price: "chi phí", booking: "đặt lịch & tiếp nhận", waiting: "thời gian chờ", space: "không gian" };
      const title = issueKeys.length ? `Cần rà soát: ${issueKeys.map((key) => shortNames[key]).join(", ")}` :
        counts.positive ? `${counts.positive} phản hồi tích cực đáng ghi nhận` : counts.neutral ? "Cần làm rõ kỳ vọng trải nghiệm" : "Chưa đủ dữ liệu văn bản để tổng hợp";
      const explanation = `${analyses.length} đánh giá trong toàn bộ kết quả lọc. ${counts.negative} tiêu cực, ${analyses.filter((a) => a.mixed).length} có cả khen và chê; ${counts.unknown} chưa có nội dung. ${issueKeys.length ? `Các góp ý có căn cứ tập trung ở ${issueKeys.length} nhóm vấn đề; cần xác minh trước khi quyết định xử lý.` : counts.positive ? "Các điểm tốt bên dưới đều có trích dẫn; không khái quát thành toàn bộ chất lượng spa." : "Chưa đủ chi tiết để kết luận nguyên nhân hoặc tự tạo vấn đề."}`;
      const aggregateSteps = issueKeys.map((key) => {
        const rule = topicRules.find((t) => t.key === key);
        const example = analyses.find((a) => a.topics.some((t) => t.key === key && t.tone === "negative"));
        return { heading: rule.name, text: `${rule.steps[0]} ${rule.steps[1]} Tham chiếu ${example.review.id}; Admin xác minh trước khi cải thiện.` };
      });
      if (positiveTopics.length && aggregateSteps.length < 5) aggregateSteps.push({
        heading: "Duy trì điểm được khách ghi nhận", text: `Ghi nhận các tín hiệu tốt về ${positiveTopics.map((t) => t.name.toLocaleLowerCase("vi")).join(", ")} cùng trích dẫn bên dưới; theo dõi khả năng duy trì thay vì kết luận chung cho mọi khách.`,
      });
      if (counts.unknown && aggregateSteps.length < 5) aggregateSteps.push({ heading: "Làm rõ phản hồi thiếu nội dung", text: `${counts.unknown} đánh giá chưa có văn bản. Chỉ cân nhắc bổ sung ngữ cảnh qua quy trình Admin lựa chọn; không tự liên hệ hoặc suy cảm xúc từ sao.` });
      if (aggregateSteps.length < 3) {
        const exemplar = analyses.find((a) => a.primary?.tone === "negative") || analyses[0];
        const extraSteps = issueKeys.length ? actionPlan(exemplar).slice(2) : actionPlan(exemplar);
        extraSteps.forEach((text, index) => {
          if (aggregateSteps.length < 3) aggregateSteps.push({ heading: `${index === 0 ? "Đối chiếu & cải thiện" : "Theo dõi"}${exemplar.primary ? ` · ${exemplar.primary.name}` : " · bổ sung ngữ cảnh"}`, text });
        });
      }
      if (aggregateSteps.length < 3) aggregateSteps.push({ heading: "Đối chiếu bối cảnh", text: "Đọc các phản hồi trong phạm vi cùng hồ sơ trải nghiệm liên quan; không coi số lượng từ khóa là số sự cố đã xác minh." });
      if (aggregateSteps.length < 3) aggregateSteps.push({ heading: "Theo dõi bằng chứng mới", text: "Theo dõi các nhận xét tiếp theo theo cùng bộ lọc. Chỉ điều chỉnh đề xuất khi có thêm nội dung cụ thể." });
      if (aggregateSteps.length < 3) aggregateSteps.push({ heading: "Làm rõ kỳ vọng", text: "Admin cân nhắc hỏi thêm điều khách kỳ vọng ở trải nghiệm này; chưa đề xuất thay đổi một khâu cụ thể khi chưa có căn cứ." });
      const topicExamples = (list, selectedTone) => list.length ? list.map((topic) => {
        const mentions = topic.mentions.filter((m) => m.topic.tone === selectedTone);
        const example = mentions[0];
        return `<div class="admin-ai-pattern"><div><strong>${topic.name}</strong>${tag(`${mentions.length} nhận xét`, selectedTone)}</div>${evidenceMarkup(example.topic.evidence)}<p class="admin-data-note">Ví dụ ${example.analysis.review.id} · ${example.analysis.review.customer}</p></div>`;
      }).join("") : `<p>${selectedTone === "positive" ? "Chưa có cụm từ ghi nhận điểm tốt trong phạm vi này." : "Chưa có góp ý tiêu cực theo các mẫu nội dung hiện có. Không tự gán vấn đề."}</p>`;
      return spotlight(title, explanation, tone, `${analyses.length} đánh giá trong phạm vi`) +
        `<div class="admin-ai-distribution"><div class="admin-ai-section-heading"><h3>${window.spaIcon("heart")}Bức tranh cảm xúc</h3><span>Không phải độ tin cậy mô hình</span></div><div class="admin-sentiment-track" role="img" aria-label="${escape(Object.entries(counts).map(([s, n]) => `${sentimentLabels[s]}: ${n}`).join(", "))}">${Object.entries(counts).filter(([, n]) => n).map(([s, n]) => `<span class="is-${s}" style="flex-grow:${n}"></span>`).join("")}</div><div class="admin-sentiment-legend">${Object.entries(counts).map(([s, n]) => `<span>${tag(sentimentLabels[s], s)}<strong>${n}</strong></span>`).join("")}</div></div>
        <section class="admin-ai-topic-overview"><h3>${window.spaIcon("leaf")}Chủ đề được nhắc đến</h3><div class="admin-topic-chips">${topics.length ? topics.map((t) => tag(`${t.name} · ${t.count}`)).join("") : "<p>Không có chủ đề có căn cứ từ văn bản.</p>"}</div><p class="admin-data-note">Một nhận xét có thể có nhiều chủ đề; mỗi chủ đề chỉ đếm một lần trong một nhận xét.</p></section>
        <div class="admin-analysis-grid"><article><h3>${window.spaIcon("leaf")}Điểm khách hàng hài lòng</h3>${topicExamples(positiveTopics, "positive")}</article><article><h3>${window.spaIcon("note")}Góp ý cần cải thiện</h3>${topicExamples(issueTopics, "negative")}</article></div>
        <section class="admin-ai-priority-list"><div class="admin-ai-section-heading"><h3>${window.spaIcon("clock")}Phản hồi cần xem trước</h3><span>Tối đa 3 · lý do từ nội dung</span></div>${priority.length ? priority.map((a) => `<article><div><strong>${a.review.id}</strong>${tag(priorityLabel(a), a.sentiment)}</div><h4>${escape(a.title)}</h4><p>${escape(a.reason)}</p>${evidenceMarkup(a.evidence)}<button class="admin-button" type="button" data-review-analyze="${a.review.id}">Phân tích riêng</button></article>`).join("") : "<p>Không có góp ý cần ưu tiên hoặc phản hồi thiếu nội dung trong phạm vi này. Tiếp tục ghi nhận và duy trì điểm tốt.</p>"}</section>
        <section class="admin-ai-action-section"><div class="admin-ai-section-heading"><h3>${window.spaIcon("note")}Hành động theo nhóm vấn đề</h3><span>3–5 gợi ý, không tự thực thi</span></div>${planMarkup(aggregateSteps.slice(0, 5).map((s) => s.text), aggregateSteps.slice(0, 5).map((s) => s.heading))}<p class="admin-data-note">Chỉ tham khảo. Không tự gửi phản hồi, hoàn tiền, sửa giá, hủy lịch hoặc thay đổi dữ liệu.</p></section>`;
    };
    const renderAnalysis = () => {
      const individual = $("#analysis-mode").value === "individual";
      $("#analysis-review-label").hidden = !individual;
      $("#analysis-review").disabled = !individual || !filtered.length;
      const scope = individual ? filtered.filter((r) => r.id === $("#analysis-review").value) : filtered;
      const target = $("#analysis-results");
      if (!scope.length) { target.innerHTML = '<div class="admin-empty-state"><h3>Chưa có dữ liệu để phân tích</h3><p>Điều chỉnh bộ lọc hoặc chọn một đánh giá khác.</p></div>'; return; }
      const analyses = scope.map(analysisFor);
      target.innerHTML = `<div class="admin-analysis-scope"><span>${individual ? `${escape(scope[0].id)} · ${escape(scope[0].customer)}` : `${scope.length} đánh giá · toàn bộ kết quả lọc, không chỉ trang hiện tại`}</span>${tag("Phân tích AI minh họa")}</div>${individual ? singleAnalysis(analyses[0]) : aggregateAnalysis(analyses)}`;
    };
    const render = () => {
      const from = $("#quality-from").value, to = $("#quality-to").value;
      const error = $("#quality-filter-error");
      if ((from && !Number.isFinite(day(from))) || (to && !Number.isFinite(day(to))) || (from && to && from > to)) {
        error.hidden = false; error.textContent = "Khoảng thời gian chưa hợp lệ. Kết quả vẫn giữ theo bộ lọc hợp lệ trước đó."; return;
      }
      error.hidden = true;
      const query = normalize($("#quality-search").value), rating = $("#quality-stars").value;
      filtered = reviews.filter((r) => normalize(`${r.customer} ${serviceName(r.serviceId)} ${r.message}`).includes(query) &&
        (!rating || r.rating === Number(rating)) && (!from || r.date >= from) && (!to || r.date <= to)).sort((a, b) => b.date.localeCompare(a.date) || a.id.localeCompare(b.id));
      page = Math.min(page, Math.max(1, Math.ceil(filtered.length / 5)));
      const visible = filtered.slice((page - 1) * 5, page * 5);
      $("#quality-rows").innerHTML = visible.map((r) => `<tr><td><strong>${r.id}</strong><span class="admin-table-time">${r.customer}</span></td><td class="admin-quality-service">${escape(serviceName(r.serviceId))}</td><td>${stars(r.rating)}</td><td><p class="admin-quality-comment">${escape(r.message || "Chưa có nội dung nhận xét.")}</p></td><td>${dateLabel(r.date)}</td><td><div class="admin-row-actions"><button class="admin-button" type="button" data-review-view="${r.id}">${window.spaIcon("eye")}Xem</button><button class="admin-button" type="button" data-review-analyze="${r.id}">${window.spaIcon("star")}Phân tích</button></div></td></tr>`).join("");
      $("#quality-empty").hidden = Boolean(filtered.length);
      const pages = Math.max(1, Math.ceil(filtered.length / 5));
      $("#quality-pagination").innerHTML = `<span>${visible.length} / ${filtered.length} đánh giá</span><div><button class="admin-button" data-quality-page="${page - 1}" type="button" ${page === 1 ? "disabled" : ""}>Trước</button><span>${page} / ${pages}</span><button class="admin-button" data-quality-page="${page + 1}" type="button" ${page >= pages ? "disabled" : ""}>Sau</button></div>`;
      const positiveCount = filtered.filter((r) => r.rating >= 4).length;
      $("#quality-stats").innerHTML = statsMarkup([
        ["Điểm trung bình", filtered.length ? `${average(filtered)} / 5` : "—", "Theo các đánh giá trong kết quả lọc", "star"],
        ["Tổng đánh giá", filtered.length, "Bộ Quality · khách hàng minh họa", "note"],
        ["Từ 4–5 sao", positiveCount, "Phân bố sao, không thay cho cảm xúc nội dung", "heart"],
        ["Cần quan tâm", filtered.filter((r) => analysisFor(r).priority >= 2).length, "Theo quy tắc nội dung và ngữ cảnh", "clock"],
      ]);
      const selection = $("#analysis-review").value;
      $("#analysis-review").replaceChildren(...filtered.map((r) => new Option(`${r.id} · ${r.customer}`, r.id)));
      if (filtered.some((r) => r.id === selection)) $("#analysis-review").value = selection;
      renderAnalysis();
    };
    const view = (id) => {
      const r = reviews.find((r) => r.id === id);
      if (!r) return;
      returnFocus = document.activeElement;
      const a = analysisFor(r);
      dialog.innerHTML = `<header class="admin-service-modal-heading"><span class="admin-service-modal-icon">${window.spaIcon("heart")}</span><div><span class="admin-eyebrow">AN NHIÊN / QUALITY DEMO</span><h2 id="quality-dialog-title">Chi tiết đánh giá</h2></div><button class="admin-icon-button" type="button" data-quality-close aria-label="Đóng">${window.spaIcon("close")}</button></header><div class="admin-service-modal-scroll"><div class="admin-quality-detail"><span class="admin-eyebrow">${r.id} · ${dateLabel(r.date)}</span><h3>${r.customer}</h3><p>${escape(serviceName(r.serviceId))}</p>${stars(r.rating)}<blockquote>${escape(r.message || "Chưa có nội dung nhận xét.")}</blockquote><div class="admin-topic-chips">${tag(sentimentLabels[a.sentiment], a.sentiment)}${tag(priorityLabel(a), a.sentiment)}</div><p class="admin-data-note">Phân tích AI minh họa theo từ khóa, không gọi API. Bộ mẫu này không có ảnh đánh giá; không chỉnh sửa nội dung hay số sao.</p></div></div><div class="admin-dialog-actions"><button class="admin-button" type="button" data-quality-close>Đóng</button><button class="admin-button admin-button-primary" type="button" data-review-analyze="${r.id}">Xem phân tích minh họa</button></div>`;
      dialog.showModal();
    };
    const analyzeOne = (id) => {
      if (!filtered.some((r) => r.id === id)) return;
      if (dialog.open) { returnFocus = $("#analysis-mode"); dialog.close(); }
      $("#analysis-mode").value = "individual"; $("#analysis-review").value = id;
      renderAnalysis(); $("#analysis-mode").focus({ preventScroll: true });
      $("#review-analysis").scrollIntoView({ block: "start" });
    };
    main.addEventListener("click", (event) => {
      const viewButton = event.target.closest("[data-review-view]");
      if (viewButton) view(viewButton.dataset.reviewView);
      const aiButton = event.target.closest("[data-review-analyze]");
      if (aiButton) analyzeOne(aiButton.dataset.reviewAnalyze);
      const pageButton = event.target.closest("[data-quality-page]");
      if (pageButton && !pageButton.disabled) { page = Number(pageButton.dataset.qualityPage); render(); }
    });
    dialog.addEventListener("click", (event) => {
      if (event.target.closest("[data-quality-close]")) dialog.close();
      const button = event.target.closest("[data-review-analyze]");
      if (button) analyzeOne(button.dataset.reviewAnalyze);
    });
    dialog.addEventListener("close", () => { if (returnFocus?.isConnected) returnFocus.focus({ preventScroll: true }); });
    ["#quality-search", "#quality-stars", "#quality-from", "#quality-to"].forEach((s) => $(s).addEventListener(s === "#quality-search" ? "input" : "change", () => { page = 1; render(); }));
    $("#quality-reset").addEventListener("click", () => { ["#quality-search", "#quality-stars", "#quality-from", "#quality-to"].forEach((s) => { $(s).value = ""; }); page = 1; render(); });
    ["#analysis-mode", "#analysis-review"].forEach((s) => $(s).addEventListener("change", renderAnalysis));
    $("#analysis-run").addEventListener("click", renderAnalysis);
    render();
    return;
  }

  // Read-only report projection of Finance V1's fixed snapshots, not Operations.
  // Revenue dates are the successful transaction dates in admin-finance.js.
  const financeRows = [
    [0, "2026-10-14", "pending", "unpaid", 590000, null],
    [1, "2026-10-14", "confirmed", "unpaid", 382500, null],
    [5, "2026-10-13", "completed", "paid", 351000, "2026-10-13"],
    [2, "2026-10-14", "confirmed", "paid", 420000, "2026-10-12"],
    [4, "2026-10-14", "cancelled", "unpaid", 320000, null],
    [3, "2026-10-13", "completed", "paid", 300000, "2026-10-13"],
    [6, "2026-10-15", "confirmed", "unpaid", 290000, null],
    [1, "2026-10-16", "confirmed", "paid", 450000, "2026-10-13"],
  ].map(([serviceId, date, status, invoiceStatus, total, paidAt], index) => ({ id: `LH-FIN-${String(index + 1).padStart(3, "0")}`, serviceId, date, status, invoiceStatus, total, paidAt }));
  const statusLabels = { pending: "Chờ xác nhận", confirmed: "Đã xác nhận", completed: "Đã hoàn thành", cancelled: "Đã hủy" };
  const tooltip = $("#analytics-tooltip");
  let tooltipTarget;
  const hideTip = () => { tooltip.hidden = true; tooltipTarget?.removeAttribute("aria-describedby"); tooltipTarget = null; };
  const showTip = (target) => {
    hideTip(); tooltipTarget = target; target.setAttribute("aria-describedby", tooltip.id);
    tooltip.textContent = target.dataset.analyticsTip; tooltip.hidden = false;
    const r = target.getBoundingClientRect(), t = tooltip.getBoundingClientRect();
    tooltip.style.left = `${Math.max(8, Math.min(innerWidth - t.width - 8, r.x + r.width / 2 - t.width / 2))}px`;
    tooltip.style.top = `${Math.max(8, Math.min(innerHeight - t.height - 8, r.top > t.height + 16 ? r.top - t.height - 12 : r.bottom + 12))}px`;
  };
  document.querySelectorAll(".admin-analytics-chart").forEach((card) => {
    card.addEventListener("pointerover", (e) => { const t = e.target.closest("[data-analytics-tip]"); if (t) showTip(t); });
    card.addEventListener("pointerout", hideTip);
    card.addEventListener("focusin", (e) => { const t = e.target.closest("[data-analytics-tip]"); if (t) showTip(t); });
    card.addEventListener("focusout", hideTip);
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") hideTip(); });
  window.addEventListener("scroll", hideTip, { passive: true });
  window.addEventListener("resize", hideTip);
  const bars = (rows, max) => rows.map(({ label, value, tone = "neutral" }) => `<div class="admin-analytics-bar is-${tone}" tabindex="0" data-analytics-tip="${escape(label)}: ${value}"><div><span>${escape(label)}</span><strong>${value}</strong></div><div class="admin-analytics-track"><span style="width:${max ? value / max * 100 : 0}%"></span></div></div>`).join("");
  const renderReport = () => {
    const from = $("#report-from").value, to = $("#report-to").value;
    const start = day(from), end = day(to);
    const error = $("#report-filter-error");
    if (!Number.isFinite(start) || !Number.isFinite(end) || start > end || end - start > 365) {
      error.textContent = "Chọn kỳ hợp lệ, ngày kết thúc từ ngày bắt đầu trở đi. Bản demo hỗ trợ tối đa 366 ngày mỗi kỳ; kết quả vẫn giữ theo kỳ hợp lệ trước đó.";
      error.hidden = false; return;
    }
    error.hidden = true; hideTip();
    const inRange = (d) => d && d >= from && d <= to;
    const appointments = financeRows.filter((a) => inRange(a.date));
    const paid = financeRows.filter((a) => a.invoiceStatus === "paid" && inRange(a.paidAt));
    const ratings = reviews.filter((r) => inRange(r.date));
    const bookings = appointments.filter((a) => a.status !== "cancelled");
    const revenue = paid.reduce((sum, a) => sum + a.total, 0);
    $("#report-period").textContent = `Kỳ: ${dateLabel(from)} — ${dateLabel(to)}`;
    $("#report-stats").innerHTML = statsMarkup([
      ["Doanh thu đã thanh toán", money(revenue), `${paid.length} hóa đơn Finance · theo ngày thanh toán`, "note"],
      ["Lịch hẹn", appointments.length, "Bốn trạng thái · snapshot LH-FIN", "calendar"],
      ["Lượt đặt không hủy", bookings.length, `${new Set(bookings.map((a) => a.serviceId)).size} dịch vụ khác nhau`, "leaf"],
      ["Điểm trải nghiệm", ratings.length ? `${average(ratings)} / 5` : "—", `${ratings.length} đánh giá · bộ Quality riêng`, "star"],
    ]);
    const empty = !appointments.length && !paid.length && !ratings.length;
    $("#report-empty").hidden = !empty;
    const noData = '<p class="admin-analytics-no-data">Chưa có dữ liệu phù hợp trong kỳ.</p>';
    const daily = Array.from({ length: end - start + 1 }, (_, index) => {
      const date = new Date((start + index) * 86400000).toISOString().slice(0, 10);
      return { date, value: paid.filter((a) => a.paidAt === date).reduce((sum, a) => sum + a.total, 0) };
    });
    if (!paid.length) $("#report-revenue").innerHTML = noData;
    else {
      // Display only dates with revenue; all amounts/dates remain the original daily totals.
      const revenueDays = daily.filter((d) => d.value > 0);
      const maximum = Math.max(...revenueDays.map((d) => d.value));
      $("#report-revenue").innerHTML = `<div class="admin-revenue-days">${revenueDays.map((d) => `<div class="admin-revenue-day" tabindex="0" data-analytics-tip="${dateLabel(d.date)}: ${money(d.value)} · ${paid.filter((a) => a.paidAt === d.date).length} hóa đơn đã thanh toán" aria-label="${dateLabel(d.date)}: ${money(d.value)}"><div class="admin-revenue-day-label"><span>${window.spaIcon("calendar")}${dateLabel(d.date)}</span><strong>${money(d.value)}</strong></div><div class="admin-analytics-track"><span style="width:${d.value / maximum * 100}%"></span></div></div>`).join("")}</div>`;
    }
    const stateRows = Object.entries(statusLabels).map(([key, label]) => ({ label, value: appointments.filter((a) => a.status === key).length, tone: key }));
    $("#report-status").innerHTML = appointments.length ? bars(stateRows, appointments.length) : noData;
    const serviceRows = [...new Set(bookings.map((a) => a.serviceId))].map((id) => ({ label: serviceName(id), value: bookings.filter((a) => a.serviceId === id).length, tone: "positive" })).sort((a, b) => b.value - a.value || a.label.localeCompare(b.label, "vi")).slice(0, 5);
    $("#report-services").innerHTML = serviceRows.length ? bars(serviceRows, Math.max(...serviceRows.map((r) => r.value))) : noData;
    $("#report-ratings").innerHTML = ratings.length ? bars([5, 4, 3, 2, 1].map((n) => ({ label: `${n} sao`, value: ratings.filter((r) => r.rating === n).length, tone: n >= 4 ? "positive" : n === 3 ? "neutral" : "negative" })), ratings.length) : noData;
    const ids = [...new Set([...appointments, ...paid, ...ratings].map((r) => r.serviceId))].sort((a, b) => a - b);
    $("#report-rows").innerHTML = ids.map((id) => {
      const a = appointments.filter((r) => r.serviceId === id), p = paid.filter((r) => r.serviceId === id), r = ratings.filter((r) => r.serviceId === id);
      return `<tr><td>${escape(serviceName(id))}</td><td>${a.length}</td><td>${a.filter((a) => a.status !== "cancelled").length}</td><td>${a.filter((a) => a.status === "completed").length}</td><td>${money(p.reduce((sum, r) => sum + r.total, 0))}</td><td>${r.length}</td><td>${average(r)}</td></tr>`;
    }).join("") || '<tr><td colspan="7">Không có dữ liệu trong kỳ đã chọn.</td></tr>';
    $("#report-total").innerHTML = `<tr><th scope="row">Tổng trong kỳ</th><td>${appointments.length}</td><td>${bookings.length}</td><td>${appointments.filter((a) => a.status === "completed").length}</td><td>${money(revenue)}</td><td>${ratings.length}</td><td>${average(ratings)}</td></tr>`;
    $("#report-insights").innerHTML = empty ? "<p>Chưa có dữ liệu để rút ra nhận định trong kỳ.</p>" :
      `<article>${window.spaIcon("note")}<p><strong>${paid.length} hóa đơn đã thanh toán</strong> đóng góp ${money(revenue)}.</p></article><article>${window.spaIcon("calendar")}<p><strong>${bookings.length} lượt đặt không hủy · ${appointments.filter((a) => a.status === "cancelled").length} lịch hủy.</strong>${serviceRows.length ? ` ${escape(serviceRows[0].label)} đứng đầu nhóm top: ${serviceRows[0].value} lượt${serviceRows.filter((r) => r.value === serviceRows[0].value).length > 1 ? " (đồng hạng)" : ""}.` : ""}</p></article><article>${window.spaIcon("star")}<p><strong>${ratings.filter((r) => r.rating >= 4).length} / ${ratings.length} đánh giá</strong> đạt 4–5 sao trong bộ Quality.</p></article>`;
  };
  $("#report-filters").addEventListener("submit", (e) => { e.preventDefault(); renderReport(); });
  ["#report-from", "#report-to"].forEach((s) => $(s).addEventListener("change", renderReport));
  $("#report-reset").addEventListener("click", () => { $("#report-from").value = "2026-10-01"; $("#report-to").value = "2026-10-31"; renderReport(); });
  renderReport();
})();
