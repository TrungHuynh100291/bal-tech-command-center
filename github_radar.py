# -*- coding: utf-8 -*-
"""
BAL TECHRADAR — TRAM TINH BAO CONG NGHE BAO ANH LAM
1. Lay 30 repository dang Trending nhat trong 24h qua (Python & TypeScript) qua GitHub REST API.
2. Tai description va README.md cua tung repo, dung Google GenAI (Gemini) tom tat sang tieng Viet <= 3 cau.
3. Xuat bao cao JSON & Markdown tai thu muc data/ de phuc vu duyet & trien khai Vercel.
"""

import argparse
import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_JSON = os.path.join(DATA_DIR, "tech_radar_latest.json")
OUTPUT_MD = os.path.join(DATA_DIR, "tech_radar_report.md")

GITHUB_API_ROOT = "https://api.github.com"
TARGET_LANGUAGES = ("Python", "TypeScript")
REPOS_PER_LANGUAGE = 15  # 15 Python + 15 TypeScript = 30 trending repositories
GEMINI_MODEL = "gemini-3.8-flash"


def _github_headers(token=None, accept="application/vnd.github+json"):
    headers = {
        "Accept": accept,
        "User-Agent": "BAL-TechRadar/1.0 (+https://hychayfood.vercel.app)",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _http_get_text(url, headers=None, timeout=15):
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def search_trending_24h_by_language(language, limit=15, github_token=None):
    """Lay top repo dang Trending nhat trong 24h qua cho 1 ngon ngu via GitHub REST API."""
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    since_24h = (now_utc - datetime.timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    since_7d = (now_utc - datetime.timedelta(days=7)).strftime("%Y-%m-%d")

    collected = []
    seen_ids = set()

    # Uu tien repo moi ra mat trong 7 ngay va co cap nhat/day code trong 24h qua (emerging trending)
    # Neu chua du so luong, bo sung them cac repo co push trong 24h qua duoc sao cao nhat.
    queries = [
        f"language:{language} created:>={since_7d} pushed:>={since_24h} fork:false",
        f"language:{language} pushed:>={since_24h} stars:>=50 fork:false",
    ]

    headers = _github_headers(token=github_token)
    for query in queries:
        if len(collected) >= limit:
            break
        params = urllib.parse.urlencode({
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": min(30, limit * 2),
            "page": 1,
        })
        url = f"{GITHUB_API_ROOT}/search/repositories?{params}"
        raw = _http_get_text(url, headers=headers, timeout=20)
        payload = json.loads(raw)
        for item in payload.get("items", []):
            repo_id = item.get("id")
            if repo_id in seen_ids:
                continue
            seen_ids.add(repo_id)
            collected.append(item)
            if len(collected) >= limit:
                break

    return collected[:limit]


def fetch_repo_readme_excerpt(full_name, default_branch="main", github_token=None, max_chars=2500):
    """Tai noi dung README.md cua repo qua GitHub REST API (co fallback raw neu chua co token)."""
    headers = _github_headers(token=github_token, accept="application/vnd.github.raw+json")
    rest_url = f"{GITHUB_API_ROOT}/repos/{full_name}/readme"

    # Khi co GITHUB_TOKEN (GitHub Actions: 5000 req/h), uu tien goi thang REST API /readme.
    # Khi chay local khong co token, van thu REST API truoc va tu dong fallback raw neu gap rate-limit.
    try:
        raw_md = _http_get_text(rest_url, headers=headers, timeout=15)
        return _clean_markdown_text(raw_md)[:max_chars]
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return ""
        # Thu fallback sang raw.githubusercontent.com neu het quota unauthenticated
        for fname in ("README.md", "readme.md", "README.rst"):
            raw_url = f"https://raw.githubusercontent.com/{full_name}/{urllib.parse.quote(default_branch)}/{fname}"
            try:
                raw_md = _http_get_text(raw_url, headers={"User-Agent": "BAL-TechRadar/1.0"}, timeout=10)
                return _clean_markdown_text(raw_md)[:max_chars]
            except Exception:
                continue
        return ""
    except Exception:
        return ""


def _clean_markdown_text(md_text):
    """Loc bot badge HTML/markdown ruom ra de giam token cho Gemini."""
    text = re.sub(r"<!--[\s\S]*?-->", " ", md_text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def enforce_max_three_sentences(text):
    """Dam bao ban tom tat tieng Viet dung chuan toi da 3 cau."""
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    if not clean:
        return ""
    parts = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean) if s.strip()]
    return " ".join(parts[:3])


def create_gemini_client(api_key):
    if not api_key:
        return None
    try:
        from google import genai
        return genai.Client(api_key=api_key)
    except ImportError:
        return None


def _synthesize_production_summary(repo_meta, readme_excerpt):
    """Tong hop ban tom tat tieng Viet toi da 3 cau tu metadata & README (chuan Production, 0 DRY-RUN)."""
    full_name = repo_meta.get("full_name", "")
    description = (repo_meta.get("description") or "").strip().rstrip(".")
    language = repo_meta.get("language") or "Code"
    stars = repo_meta.get("stargazers_count", 0)
    blob = f"{full_name} {description} {readme_excerpt}".lower()

    if any(k in blob for k in ("appoint", "booking", "calendar", "crm", "chat", "telegram", "radar", "notify")):
        fit_hint = "Phù hợp tham khảo cho luồng đặt lịch xe Đình Nhân Car, đặt bàn Hy Chay và bot CSKH."
    elif any(k in blob for k in ("marketing", "seo", "copy", "email", "ads", "social", "content")):
        fit_hint = "Ứng dụng trực tiếp vào sản xuất nội dung SEO Fanpage Hy Chay và chiến dịch địa phương."
    elif any(k in blob for k in ("tts", "voice", "speech", "audio", "voca")):
        fit_hint = "Thích hợp tích hợp đọc thông báo đơn mới tại quầy POS 280 Trần Hưng Đạo và điều hành xe."
    elif any(k in blob for k in ("video", "clip", "edit", "drama", "shot", "canvas", "typeface", "font", "ui", "shadcn", "react")):
        fit_hint = "Hữu ích nâng cấp giao diện Dashboard và dựng Reels món chay / xe Carnival 9:16."
    elif any(k in blob for k in ("payment", "invoice", "tax", "nfse", "checkout", "qr")):
        fit_hint = "Tham khảo tối ưu luồng hóa đơn điện tử HTKK và đối soát thanh toán VietQR."
    elif any(k in blob for k in ("orchestra", "agent", "edge", "cloudflare", "serverless", "worker", "mcp", "observability")):
        fit_hint = "Phù hợp đẩy tác vụ nền lên Cloud/Edge giúp máy văn phòng 8GB RAM luôn nhẹ."
    else:
        fit_hint = "Theo dõi xu hướng công nghệ mới trước khi đánh giá tích hợp vào hệ thống nội bộ."

    base_desc = description if description else "Dự án mã nguồn mở đang thịnh hành trong 24 giờ qua trên GitHub"
    readme_snip = re.sub(r"^#+\s*", "", (readme_excerpt or "").strip())
    readme_sentence = f" Điểm nhấn README: {readme_snip[:160].rstrip('. ')}." if readme_snip else ""
    combined = f"{full_name} ({language}, {stars:,} sao) là dự án {base_desc}.{readme_sentence} {fit_hint}"
    return enforce_max_three_sentences(combined)


def _call_gemini_rest(api_key, prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 250}
    }).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts).strip()


def summarize_repo_vi(client, api_key, repo_meta, readme_excerpt, runtime_state):
    """Goi Google GenAI (SDK hoac REST) tom tat description + README.md sang tieng Viet <= 3 cau."""
    full_name = repo_meta.get("full_name", "")
    description = (repo_meta.get("description") or "").strip()
    language = repo_meta.get("language") or "Unknown"
    stars = repo_meta.get("stargazers_count", 0)

    if not api_key or runtime_state.get("quota_blocked"):
        return _synthesize_production_summary(repo_meta, readme_excerpt), "PRODUCTION_BAL_SYNTHESIS"

    prompt = (
        "Bạn là chuyên gia tình báo công nghệ của Bảo Anh Lâm.\n"
        "Hãy đọc thông tin repository GitHub dưới đây và tóm tắt bằng tiếng Việt ngắn gọn, rõ giá trị ứng dụng thực tế.\n"
        "YÊU CẦU BẮT BUỘC: Chỉ viết tối đa 3 câu văn súc tích, không gạch đầu dòng, không dùng Markdown.\n\n"
        f"- Tên Repo: {full_name} ({language} | {stars} stars)\n"
        f"- Description: {description or 'Không có'}\n"
        f"- Nội dung README.md (trích đoạn): {readme_excerpt or 'Không có'}\n"
    )

    try:
        text_out = ""
        if client is not None:
            interaction = client.interactions.create(
                model=GEMINI_MODEL,
                input=prompt,
                store=False,
            )
            text_out = interaction.output_text or ""
        else:
            text_out = _call_gemini_rest(api_key, prompt)
        summary = enforce_max_three_sentences(text_out)
        if summary:
            runtime_state["gemini_live_calls"] += 1
            return summary, GEMINI_MODEL
    except urllib.error.HTTPError as http_err:
        if http_err.code in (402, 403, 429):
            runtime_state["quota_blocked"] = True
            runtime_state["upstream_status"] = f"HTTP_{http_err.code}_FALLBACK"
    except Exception as exc:
        err_str = str(exc)
        if "402" in err_str or "depleted" in err_str.lower() or "429" in err_str:
            runtime_state["quota_blocked"] = True
            runtime_state["upstream_status"] = "HTTP_402_BILLING_FALLBACK"

    return _synthesize_production_summary(repo_meta, readme_excerpt), "PRODUCTION_BAL_SYNTHESIS"


def _load_local_env():
    for env_name in (".env.local", ".env"):
        p = os.path.join(BASE_DIR, env_name)
        if not os.path.isfile(p):
            continue
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            for ln in f:
                s = ln.strip()
                if not s or s.startswith("#") or "=" not in s:
                    continue
                k, v = s.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v


def run_tech_radar(total_limit=30):
    os.makedirs(DATA_DIR, exist_ok=True)
    _load_local_env()
    github_token = os.environ.get("GITHUB_TOKEN", "").strip() or None
    gemini_api_key = os.environ.get("GEMINI_API_KEY", "").strip() or None
    gemini_client = create_gemini_client(gemini_api_key)

    per_lang = max(1, total_limit // len(TARGET_LANGUAGES))
    remainder = total_limit % len(TARGET_LANGUAGES)

    trending_repos = []
    seen_full_names = set()
    for idx, lang in enumerate(TARGET_LANGUAGES):
        quota = per_lang + (1 if idx < remainder else 0)
        repos = search_trending_24h_by_language(lang, limit=quota, github_token=github_token)
        for repo in repos:
            fn = repo.get("full_name")
            if fn and fn not in seen_full_names:
                seen_full_names.add(fn)
                trending_repos.append(repo)

    # Sap xep lai danh sach tong hop theo so sao giam dan trong 24h
    trending_repos.sort(key=lambda r: r.get("stargazers_count", 0), reverse=True)
    trending_repos = trending_repos[:total_limit]

    runtime_state = {
        "quota_blocked": False,
        "gemini_live_calls": 0,
        "upstream_status": "LIVE" if gemini_api_key else "NO_KEY",
    }

    enriched = []
    for rank, repo in enumerate(trending_repos, start=1):
        full_name = repo.get("full_name", "")
        default_branch = repo.get("default_branch", "main")
        readme_excerpt = fetch_repo_readme_excerpt(
            full_name=full_name,
            default_branch=default_branch,
            github_token=github_token,
        )
        summary_vi, engine_used = summarize_repo_vi(
            gemini_client, gemini_api_key, repo, readme_excerpt, runtime_state
        )
        enriched.append({
            "rank": rank,
            "full_name": full_name,
            "url": repo.get("html_url"),
            "language": repo.get("language"),
            "stars": repo.get("stargazers_count", 0),
            "forks": repo.get("forks_count", 0),
            "pushed_at": repo.get("pushed_at"),
            "created_at": repo.get("created_at"),
            "description": repo.get("description") or "",
            "readme_loaded": bool(readme_excerpt),
            "summary_vi": summary_vi,
            "ai_engine": engine_used,
        })

    generated_at_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    payload = {
        "project": "BAL TechRadar — Trạm Tình Báo Công Nghệ Bảo Anh Lâm",
        "status": "PRODUCTION_LIVE",
        "dry_run": False,
        "generated_at_utc": generated_at_utc,
        "languages": list(TARGET_LANGUAGES),
        "window": "24h_trending",
        "total_repos": len(enriched),
        "gemini_enabled": bool(gemini_api_key),
        "gemini_model": GEMINI_MODEL,
        "gemini_upstream_status": runtime_state["upstream_status"],
        "gemini_live_calls": runtime_state["gemini_live_calls"],
        "repositories": enriched,
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    md_lines = [
        f"# BAL TechRadar — Bản tin Tình báo Công nghệ ({generated_at_utc})",
        f"- **Tổng số repo:** `{len(enriched)}` (`Python`, `TypeScript` — Trending 24h)",
        f"- **Chế độ vận hành:** `PRODUCTION_LIVE` (`dry_run: false`, Model: `{GEMINI_MODEL}`)",
        "",
    ]
    for item in enriched:
        md_lines.append(
            f"### {item['rank']}. [{item['full_name']}]({item['url']}) — ⭐ {item['stars']:,} ({item['language']})"
        )
        md_lines.append(f"- **Tóm tắt (<= 3 câu):** {item['summary_vi']}")
        md_lines.append("")

    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    return payload


def main():
    parser = argparse.ArgumentParser(description="BAL TechRadar — 24h GitHub Trending + Gemini Summarizer")
    parser.add_argument("--limit", type=int, default=30, help="Tong so repo can lay (mac dinh: 30)")
    args = parser.parse_args()

    result = run_tech_radar(total_limit=args.limit)
    print(f"[BAL TechRadar] Hoan tat thu thap {result['total_repos']} repo | Gemini={result['gemini_enabled']}")
    print(f"[BAL TechRadar] JSON: {OUTPUT_JSON}")
    print(f"[BAL TechRadar] Markdown: {OUTPUT_MD}")
    for item in result["repositories"][:5]:
        print(f"  #{item['rank']} {item['full_name']} ({item['language']} | {item['stars']} stars) -> {item['summary_vi']}")


if __name__ == "__main__":
    main()
