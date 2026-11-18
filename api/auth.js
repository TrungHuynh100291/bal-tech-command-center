/**
 * BAL Tech Command Center — Internal PIN Security Gate
 * Validates Director PIN against process.env.BAL_COMMAND_PIN (default MST prefix: 340128)
 */
const crypto = require("crypto");

function sha256(val) {
  return crypto.createHash("sha256").update(String(val || "")).digest();
}

function getExpectedPin() {
  return String(process.env.BAL_COMMAND_PIN || "340128").trim();
}

function signSessionToken(secret) {
  const issuedAt = Date.now().toString();
  const sig = crypto.createHmac("sha256", secret).update(issuedAt).digest("hex");
  return `${issuedAt}.${sig}`;
}

function verifySessionCookie(cookieHeader, secret) {
  if (!cookieHeader) return false;
  const match = cookieHeader.match(/(?:^|;\s*)bal_cmd_session=([^;]+)/);
  if (!match) return false;
  const parts = decodeURIComponent(match[1]).split(".");
  if (parts.length !== 2) return false;
  const [issuedAt, sig] = parts;
  if (!/^\d+$/.test(issuedAt)) return false;
  if (Date.now() - Number(issuedAt) > 12 * 60 * 60 * 1000) return false;
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

  const expectedPin = getExpectedPin();
  const secret = process.env.BAL_SESSION_SECRET || crypto.createHash("sha256").update("BAL_V6_" + expectedPin).digest("hex");

  if (req.method === "GET") {
    const authenticated = verifySessionCookie(req.headers.cookie || "", secret);
    return res.status(200).json({ authenticated });
  }

  if (req.method === "DELETE") {
    res.setHeader("Set-Cookie", "bal_cmd_session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0");
    return res.status(200).json({ authenticated: false, locked: true });
  }

  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method Not Allowed" });
  }

  try {
    const body = typeof req.body === "string" ? JSON.parse(req.body || "{}") : (req.body || {});
    const submittedPin = String(body.pin || "").trim();

    if (!submittedPin) {
      return res.status(400).json({ authenticated: false, error: "Vui lòng nhập mã PIN nội bộ." });
    }

    const match = crypto.timingSafeEqual(sha256(submittedPin), sha256(expectedPin));
    if (!match) {
      return res.status(401).json({
        authenticated: false,
        error: "Mã PIN không chính xác. Truy cập vào Trạm Chỉ Huy bị từ chối."
      });
    }

    const token = signSessionToken(secret);
    const secureFlag = process.env.VERCEL ? "; Secure" : "";
    res.setHeader(
      "Set-Cookie",
      `bal_cmd_session=${encodeURIComponent(token)}; Path=/; HttpOnly; SameSite=Strict; Max-Age=43200${secureFlag}`
    );
    return res.status(200).json({
      authenticated: true,
      operator: "Giám đốc Bảo Anh Lâm (MST: 3401289271)"
    });
  } catch (err) {
    return res.status(500).json({ authenticated: false, error: err.message });
  }
};
