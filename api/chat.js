/**
 * BAL Tech Command Center — Multi-Model AI Chat Endpoint (AI Model Switcher + Domain Fit Analysis)
 * Reads GEMINI_API_KEY / ANTHROPIC_API_KEY strictly from Vercel Environment Variables.
 */
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const DEFAULT_FLASH_MODEL = "gemini-2.5-flash-lite";

const ALLOWED_MODELS = {
  "gemini-2.5-flash-lite": {
    provider: "gemini",
    analysisMode: "quick_flash",
    label: "⚡ Phân tích nhanh — Gemini 2.5 Flash-Lite (Free Tier nhẹ nhất)",
    upstreamModel: "gemini-2.5-flash-lite"
  },
  "gemini-2.5-flash": {
    provider: "gemini",
    analysisMode: "quick_flash",
    label: "⚡ Phân tích nhanh — Gemini 2.5 Flash",
    upstreamModel: "gemini-2.5-flash"
  },
  "gemini-2.5-pro": {
    provider: "gemini",
    analysisMode: "deep_pro",
    label: "🧠 Phân tích kiến trúc sâu — Gemini 2.5 Pro",
    upstreamModel: "gemini-2.5-pro"
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

function loadRadarContext(selectedFullName) {
  try {
    const dataPath = path.join(process.cwd(), "data", "tech_radar_latest.json");
    const raw = JSON.parse(fs.readFileSync(dataPath, "utf-8"));
    const repos = Array.isArray(raw.repositories) ? raw.repositories : [];
    const selected = selectedFullName ? repos.find((r) => r.full_name === selectedFullName) : null;
    const topBrief = repos.slice(0, 12).map(
      (r) => `#${r.rank} ${r.full_name} (${r.language}, ${r.stars}★): ${r.summary_vi || r.description || ""}`
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
    const requestedModel = String(body.model || DEFAULT_FLASH_MODEL).trim();
    const modelCfg = ALLOWED_MODELS[requestedModel] || ALLOWED_MODELS[DEFAULT_FLASH_MODEL];

    if (!message) {
      return res.status(400).json({ error: "Vui lòng nhập nội dung câu hỏi cho AI Advisor." });
    }

    const geminiKey = String(process.env.GEMINI_API_KEY || "").trim();
    if (!geminiKey) {
      return res.status(500).json({
        error: "HTTP 500: Thiếu biến môi trường GEMINI_API_KEY trên máy chủ.",
        upstreamStatus: 500,
        model: modelCfg.upstreamModel
      });
    }

    const ctx = loadRadarContext(selectedRepo);
    const selectedMeta = ctx.selected
      ? [
          `Repo đang chọn: ${ctx.selected.full_name} (${ctx.selected.language}, ${ctx.selected.stars}★)`,
          ctx.selected.description ? `Description: ${ctx.selected.description}` : "",
          ctx.selected.summary_vi ? `Tóm tắt AI: ${ctx.selected.summary_vi}` : "",
          typeof ctx.selected.fit_score === "number" ? `BAL Fit: ${ctx.selected.fit_score}/100 (${ctx.selected.sector || ""})` : "",
          ctx.selected.suggestion ? `Khuyến nghị trước đó: ${ctx.selected.suggestion}` : ""
        ].filter(Boolean).join(" | ")
      : "";

    const systemPrompt = [
      `Bạn là Cố vấn Công nghệ Cấp cao đang chạy trên mô hình ${modelCfg.label} tại BAL Tech Command Center (Bảo Anh Lâm - MST 3401289271).`,
      "Trả lời bằng tiếng Việt thực chiến theo 3 trụ cột: (1) Tối ưu RAM 8GB / Cloud Serverless, (2) Ứng dụng cho F&B Hy Chay (POS V39, HTKK, Reels, SEO) hoặc Xe Du Lịch Đình Nhân (Carnival 300k, Booking, CSKH), (3) An toàn API Shield.",
      selectedMeta,
      ctx.topBrief ? `Danh sách Radar 24h:\n${ctx.topBrief}` : ""
    ].filter(Boolean).join("\n\n");

    const upstream = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(modelCfg.upstreamModel)}:generateContent`,
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

    const gData = await upstream.json().catch(() => ({}));
    const parts = gData?.candidates?.[0]?.content?.parts || [];
    const gText = parts.map((p) => p?.text || "").join("").trim();

    if (upstream.ok && gText) {
      return res.status(200).json({
        dryRun: false,
        geminiKeyConfigured: true,
        mode: "LIVE_GEMINI",
        analysisMode: modelCfg.analysisMode,
        model: modelCfg.upstreamModel,
        modelLabel: modelCfg.label,
        reply: gText
      });
    }

    const errCode = upstream.status || 502;
    const errMsg = gData?.error?.message || upstream.statusText || "Upstream Gemini API không trả về nội dung hợp lệ.";
    return res.status(errCode).json({
      dryRun: false,
      geminiKeyConfigured: true,
      mode: "API_ERROR",
      analysisMode: modelCfg.analysisMode,
      model: modelCfg.upstreamModel,
      modelLabel: modelCfg.label,
      upstreamStatus: errCode,
      googleStatus: gData?.error?.status || null,
      error: `Chưa có đánh giá AI (Lỗi mã HTTP ${errCode}): ${errMsg}`
    });
  } catch (err) {
    return res.status(500).json({ error: `HTTP 500: ${err.message}` });
  }
};
