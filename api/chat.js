/**
 * BAL Tech Command Center — Multi-Model AI Chat Endpoint (AI Model Switcher + Domain Fit Analysis)
 * Reads GEMINI_API_KEY / ANTHROPIC_API_KEY strictly from Vercel Environment Variables.
 */
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const ALLOWED_MODELS = {
  "gemini-4-argon": {
    provider: "gemini",
    label: "Gemini 4 Argon (Kiến trúc & POS)",
    upstreamModel: "gemini-4-argon"
  },
  "gemini-3.8-flash": {
    provider: "gemini",
    label: "Gemini 3.8 Flash (Tốc độ cao)",
    upstreamModel: "gemini-3.8-flash"
  },
  "gemini-3.5-flash-lite": {
    provider: "gemini",
    label: "Gemini 3.5 Flash-Lite (Tiết kiệm 80% Token)",
    upstreamModel: "gemini-3.5-flash-lite"
  },
  "claude-3-5-sonnet": {
    provider: "anthropic",
    label: "Claude 3.5 Sonnet (Fallback Code/UI)",
    upstreamModel: "claude-3-5-sonnet-20241022"
  }
};

function isAuthorized(req) {
  const expectedPin = String(process.env.BAL_COMMAND_PIN || "340128").trim();
  const secret = process.env.BAL_SESSION_SECRET || crypto.createHash("sha256").update("BAL_V6_" + expectedPin).digest("hex");
  const cookieHeader = req.headers.cookie || "";
  const match = cookieHeader.match(/(?:^|;\s*)bal_cmd_session=([^;]+)/);
  if (!match) return false;
  const parts = decodeURIComponent(match[1]).split(".");
  if (parts.length !== 2) return false;
  const [issuedAt, sig] = parts;
  if (!/^\d+$/.test(issuedAt) || Date.now() - Number(issuedAt) > 12 * 60 * 60 * 1000) return false;
  const expected = crypto.createHmac("sha256", secret).update(issuedAt).digest("hex");
  try {
    return crypto.timingSafeEqual(Buffer.from(sig), Buffer.from(expected));
  } catch {
    return false;
  }
}

function evaluateRepoForBal(repo) {
  const blob = `${repo.full_name || ""} ${repo.description || ""} ${repo.summary_vi || ""}`.toLowerCase();
  let score = 58;
  let sector = "⚡ Hạ tầng AI & Automation Chung";
  let ram = "🟡 Trung bình (Chạy Node/Python Worker)";
  let suggestion = "Tham khảo kiến trúc hoặc API nội bộ qua GitHub Actions.";

  if (/(appoint|booking|calendar|schedule|crm|chat|telegram|notify|radar)/.test(blob)) {
    score = 92;
    sector = "🚘 Xe Dịch Vụ Đình Nhân & 🍃 Đặt bàn F&B";
    ram = "🟢 Siêu nhẹ (Cloud / Serverless Ready)";
    suggestion = "Tích hợp đặt lịch Chuyên cơ Carnival 300k, nhắc chuyến 8h/15h và điều phối CSKH.";
  } else if (/(marketing|seo|copy|email|ads|social|content)/.test(blob)) {
    score = 94;
    sector = "🍃 F&B Hy Chay & 🚘 Đình Nhân Car";
    ram = "🟢 Siêu nhẹ (Markdown Skill / 0MB RAM)";
    suggestion = "Nạp ngay vào pipeline viết bài Fanpage Hy Chay chuẩn SEO & seeding khách đoàn.";
  } else if (/(tts|voice|speech|audio|voca)/.test(blob)) {
    score = 90;
    sector = "🍃 POS V39 Hy Chay & 🚘 Điều hành Xe";
    ram = "🟢 Siêu nhẹ (Chạy CPU 8GB / Browser)";
    suggestion = "Thay thế bộ đọc thông báo đơn mới cho bếp 280 Trần Hưng Đạo & báo chuyến tài xế.";
  } else if (/(video|clip|edit|drama|shot|canvas|typeface|font|ui)/.test(blob)) {
    score = 88;
    sector = "🍃 Media Reels Hy Chay & 🚘 TVC Carnival";
    ram = "🟡 Vừa (Ưu tiên chạy render trên Colab/Cloud)";
    suggestion = "Tăng tốc dựng Reels 9:16 món Chả Mít Non, Ruốc Nấm và UI Luxury cho Website.";
  } else if (/(payment|invoice|tax|nfse|checkout|qr)/.test(blob)) {
    score = 86;
    sector = "🍃 Kế toán Thuế HTKK & 🚘 Thanh toán Cọc";
    ram = "🟢 Siêu nhẹ (API Webhook)";
    suggestion = "Tham khảo luồng xuất hóa đơn tự động và đối soát VietQR cọc 30% đặt xe.";
  } else if (/(orchestra|agent|edge|cloudflare|serverless|worker)/.test(blob)) {
    score = 84;
    sector = "⚡ Hạ tầng Agent Bảo Anh Lâm V6";
    ram = "🟢 Siêu nhẹ (Cloud Edge / Zero RAM Local)";
    suggestion = "Chuyển tác vụ nền sang Edge Worker để máy 8GB RAM luôn trống > 50%.";
  } else if (/(trading|miner|dma|game|pokemon|crypto)/.test(blob)) {
    score = 22;
    sector = "⚠️ Ngoài lĩnh vực F&B / Xe Dịch Vụ";
    ram = "🔴 Không khuyến nghị tích hợp";
    suggestion = "Chỉ theo dõi xu hướng công nghệ, không đưa vào POS hay hệ thống vận hành công ty.";
  }

  return { score, sector, ram, suggestion };
}

function loadRadarContext(selectedFullName) {
  try {
    const dataPath = path.join(process.cwd(), "data", "tech_radar_latest.json");
    const raw = JSON.parse(fs.readFileSync(dataPath, "utf-8"));
    const repos = Array.isArray(raw.repositories) ? raw.repositories : [];
    const selected = selectedFullName ? repos.find((r) => r.full_name === selectedFullName) : null;
    const topBrief = repos.slice(0, 12).map(
      (r) => `#${r.rank} ${r.full_name} (${r.language}, ${r.stars}★): ${r.description}`
    ).join("\n");
    return { total: repos.length, selected, topBrief };
  } catch {
    return { total: 0, selected: null, topBrief: "" };
  }
}

module.exports = async function handler(req, res) {
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Cache-Control", "no-store, max-age=0");

  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method Not Allowed" });
  }
  if (!isAuthorized(req)) {
    return res.status(401).json({ error: "Phiên chưa được mở khóa bằng Mã PIN Giám đốc." });
  }

  try {
    const body = typeof req.body === "string" ? JSON.parse(req.body || "{}") : (req.body || {});
    const message = String(body.message || "").trim();
    const selectedRepo = String(body.selectedRepo || "").trim();
    const requestedModel = String(body.model || "gemini-4-argon").trim();
    const modelCfg = ALLOWED_MODELS[requestedModel] || ALLOWED_MODELS["gemini-4-argon"];

    if (!message) {
      return res.status(400).json({ error: "Vui lòng nhập nội dung câu hỏi cho AI Advisor." });
    }

    const ctx = loadRadarContext(selectedRepo);
    const evalFit = ctx.selected ? evaluateRepoForBal(ctx.selected) : null;

    const systemPrompt = [
      `Bạn là Cố vấn Công nghệ Cấp cao đang chạy trên mô hình ${modelCfg.label} tại BAL Tech Command Center (Bảo Anh Lâm - MST 3401289271).`,
      "Đánh giá mọi thư viện theo 3 trụ cột thực chiến: (1) Tối ưu RAM 8GB / Cloud Serverless, (2) Ứng dụng cho F&B Hy Chay (POS V39, HTKK, Reels, SEO) hoặc Xe Du Lịch Đình Nhân (Carnival 300k, Booking, CSKH), (3) An toàn API Shield.",
      ctx.selected && evalFit
        ? `Repo Giám đốc đang chọn: ${ctx.selected.full_name} (${ctx.selected.language}, ${ctx.selected.stars}★) | Điểm BAL Fit: ${evalFit.score}/100 | Ngành: ${evalFit.sector} | RAM: ${evalFit.ram} | Mô tả: ${ctx.selected.description}`
        : "",
      ctx.topBrief ? `Danh sách Radar 24h:\n${ctx.topBrief}` : ""
    ].filter(Boolean).join("\n\n");

    const geminiKey = process.env.GEMINI_API_KEY || "";
    const anthropicKey = process.env.ANTHROPIC_API_KEY || "";
    let upstreamStatus = null;
    let upstreamNote = "";

    if (modelCfg.provider === "anthropic" && anthropicKey) {
      const claudeResp = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-api-key": anthropicKey,
          "anthropic-version": "2023-06-01"
        },
        body: JSON.stringify({
          model: modelCfg.upstreamModel,
          max_tokens: 900,
          system: systemPrompt,
          messages: [{ role: "user", content: message }]
        })
      });
      const cData = await claudeResp.json();
      const cText = cData?.content?.[0]?.text;
      if (claudeResp.ok && cText) {
        return res.status(200).json({
          dryRun: false,
          geminiKeyConfigured: Boolean(geminiKey),
          mode: "PRODUCTION_LIVE",
          model: modelCfg.label,
          reply: cText,
          evaluation: evalFit
        });
      }
      upstreamStatus = claudeResp.status;
      upstreamNote = cData?.error?.message || claudeResp.statusText;
    }

    if (geminiKey) {
      const targetGemini = modelCfg.provider === "gemini" ? modelCfg.upstreamModel : "gemini-3.8-flash";
      const upstream = await fetch(
        `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(targetGemini)}:generateContent`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "x-goog-api-key": geminiKey
          },
          body: JSON.stringify({
            systemInstruction: { parts: [{ text: systemPrompt }] },
            contents: [{ role: "user", parts: [{ text: message }] }],
            generationConfig: { temperature: 0.35, maxOutputTokens: 900 }
          })
        }
      );
      const gData = await upstream.json();
      const gText = gData?.candidates?.[0]?.content?.parts?.[0]?.text;
      if (upstream.ok && gText) {
        return res.status(200).json({
          dryRun: false,
          geminiKeyConfigured: true,
          mode: "PRODUCTION_LIVE",
          model: modelCfg.label,
          reply: gText,
          evaluation: evalFit
        });
      }
      upstreamStatus = upstream.status;
      upstreamNote = gData?.error?.message || upstream.statusText;
    }

    // Chế độ tổng hợp Production dự phòng thông minh (khi biến GEMINI_API_KEY hết hạn mức 402 hoặc chưa nạp Anthropic)
    const summaryHeader = ctx.selected && evalFit
      ? `📌 Đánh giá Production [${ctx.selected.full_name}] (${modelCfg.label}):\n• Điểm tương thích BAL Fit: ${evalFit.score}/100\n• Ngành ứng dụng: ${evalFit.sector}\n• Mức tiêu thụ RAM 8GB: ${evalFit.ram}\n• Hướng triển khai: ${evalFit.suggestion}\n\n`
      : "";

    const quotaNotice = upstreamStatus
      ? `⚠️ Gemini Upstream HTTP ${upstreamStatus} (${upstreamNote}). Đã tự động chuyển sang bộ tổng hợp tình báo Production (${ctx.total} repo Radar).`
      : `⚠️ Thiếu biến GEMINI_API_KEY trên môi trường máy chủ.`;

    return res.status(200).json({
      dryRun: false,
      geminiKeyConfigured: Boolean(geminiKey),
      mode: "PRODUCTION_CONTEXT_SYNTHESIS",
      upstreamStatus,
      model: modelCfg.label,
      evaluation: evalFit,
      reply:
        `${summaryHeader}💬 Yêu cầu của Giám đốc: "${message}"\n${quotaNotice}\nNếu cần bật sinh văn bản trực tiếp từ Google AI Studio, Giám đốc kiểm tra hạn mức thanh toán (billing credits) của GEMINI_API_KEY trên AI Studio.`
    });
  } catch (err) {
    return res.status(500).json({ error: err.message });
  }
};
