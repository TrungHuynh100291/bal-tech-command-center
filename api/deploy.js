/**
 * BAL Tech Command Center — Deploy Approval Webhook Endpoint
 * Dispatches GitHub Actions event (repository_dispatch) using Vercel Env GITHUB_DISPATCH_TOKEN
 */
const crypto = require("crypto");

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

module.exports = async function handler(req, res) {
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Cache-Control", "no-store, max-age=0");

  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method Not Allowed" });
  }
  if (!isAuthorized(req)) {
    return res.status(401).json({ error: "Chưa xác thực Mã PIN Giám đốc." });
  }

  try {
    const body = typeof req.body === "string" ? JSON.parse(req.body || "{}") : (req.body || {});
    const fullName = String(body.full_name || "").trim();
    const repoUrl = String(body.url || "").trim();
    const language = String(body.language || "").trim();
    const targetCompanyRepo = String(
      body.target_repo || process.env.BAL_TARGET_GITHUB_REPO || "TrungHuynh100291/hy-chay"
    ).trim();

    if (!fullName || !/^[^/\s]+\/[^/\s]+$/.test(fullName)) {
      return res.status(400).json({ error: "Tên repository không hợp lệ." });
    }

    const ghToken = process.env.GITHUB_DISPATCH_TOKEN || process.env.GITHUB_TOKEN || "";
    const webhookUrl = `https://api.github.com/repos/${targetCompanyRepo}/dispatches`;
    const dispatchPayload = {
      event_type: "bal_approve_and_deploy",
      client_payload: {
        source_repo: fullName,
        source_url: repoUrl || `https://github.com/${fullName}`,
        language,
        target_company_repo: targetCompanyRepo,
        approved_by: "Giam_Doc_Bao_Anh_Lam",
        requested_at: new Date().toISOString()
      }
    };

    if (!ghToken) {
      return res.status(200).json({
        dispatched: false,
        mode: "DRY_RUN_WEBHOOK_PREVIEW",
        webhookUrl,
        payload: dispatchPayload,
        message:
          `Đã ghi nhận lệnh [Duyệt & Triển Khai] cho ${fullName} -> ${targetCompanyRepo}. ` +
          `Thêm GITHUB_DISPATCH_TOKEN vào Vercel Environment Variables để bắn Webhook trực tiếp sang GitHub Actions.`
      });
    }

    const ghResp = await fetch(webhookUrl, {
      method: "POST",
      headers: {
        "Accept": "application/vnd.github+json",
        "Authorization": `Bearer ${ghToken}`,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "BAL-Tech-Command-Center/2.0",
        "Content-Type": "application/json"
      },
      body: JSON.stringify(dispatchPayload)
    });

    if (ghResp.status === 204 || (ghResp.status >= 200 && ghResp.status < 300)) {
      return res.status(200).json({
        dispatched: true,
        mode: "LIVE_GITHUB_ACTIONS_DISPATCHED",
        webhookUrl,
        payload: dispatchPayload,
        message: `Đã kích hoạt Webhook GitHub Actions thành công cho ${fullName} (HTTP ${ghResp.status}).`
      });
    }

    const errText = await ghResp.text();
    return res.status(502).json({
      dispatched: false,
      error: `GitHub Webhook trả về HTTP ${ghResp.status}`,
      detail: errText.slice(0, 300)
    });
  } catch (err) {
    return res.status(500).json({ error: err.message });
  }
};
