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
import time
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
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
PREFERRED_FLASH_MODELS = (
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-flash-latest",
)
BATCH_SIZE = 6
BATCH_SLEEP_SECONDS = 5


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


def _parse_http_error(http_err):
    raw_body = ""
    try:
        raw_body = http_err.read().decode("utf-8", errors="ignore")
        parsed = json.loads(raw_body)
        err_obj = parsed.get("error") or {}
        msg = err_obj.get("message") or raw_body or http_err.reason
        return f"HTTP {http_err.code}: {str(msg).strip()}"
    except Exception:
        detail = raw_body.strip() or str(http_err.reason)
        return f"HTTP {http_err.code}: {detail}"


def discover_active_flash_model(api_key):
    """Kiem tra ListModels thuc te cua GEMINI_API_KEY va chon model dong Flash ho tro generateContent."""
    if not api_key:
        return DEFAULT_GEMINI_MODEL, [], "Thieu GEMINI_API_KEY"

    url = "https://generativelanguage.googleapis.com/v1beta/models"
    req = urllib.request.Request(
        url,
        headers={"x-goog-api-key": api_key},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        flash_models = []
        for m in data.get("models", []):
            name = str(m.get("name", "")).replace("models/", "")
            methods = m.get("supportedGenerationMethods") or []
            if "generateContent" in methods and "flash" in name.lower():
                flash_models.append(name)

        selected = None
        for preferred in PREFERRED_FLASH_MODELS:
            if preferred in flash_models:
                selected = preferred
                break
        if not selected and flash_models:
            selected = flash_models[0]
        if not selected:
            return DEFAULT_GEMINI_MODEL, flash_models, "ListModels khong tim thay model Flash ho tro generateContent"
        return selected, flash_models, None
    except urllib.error.HTTPError as http_err:
        return DEFAULT_GEMINI_MODEL, [], _parse_http_error(http_err)
    except Exception as exc:
        return DEFAULT_GEMINI_MODEL, [], f"ListModels error: {exc}"


def _extract_json_array(raw_text):
    clean = str(raw_text or "").strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```(?:json)?\s*", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\s*```$", "", clean)
    try:
        parsed = json.loads(clean)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict) and isinstance(parsed.get("items"), list):
            return parsed["items"]
    except Exception:
        pass
    match = re.search(r"\[[\s\S]*\]", clean)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
    return None


def analyze_repo_batch_vi(api_key, model_id, batch_items):
    """
    Goi Gemini REST generateContent cho 1 batch 5-10 repo (chong 429 RPM).
    Tra ve (dict_theo_full_name_lower, error_str). KHONG sinh du lieu gia khi API loi.
    """
    repo_blocks = []
    for entry in batch_items:
        repo = entry["repo"]
        readme = (entry["readme_excerpt"] or "")[:900]
        repo_blocks.append({
            "full_name": repo.get("full_name", ""),
            "language": repo.get("language") or "Unknown",
            "stars": repo.get("stargazers_count", 0),
            "description": (repo.get("description") or "").strip(),
            "readme_excerpt": readme,
        })

    prompt = (
        "Bạn là chuyên gia tình báo công nghệ của Công ty Bảo Anh Lâm (Hy Chay F&B & Xe Du Lịch Đình Nhân).\n"
        "Hãy đọc danh sách repository GitHub JSON bên dưới và trả về ĐÚNG MỘT JSON ARRAY (không markdown, không giải thích ngoài JSON).\n"
        "Mỗi phần tử tương ứng 1 repo với các khóa bắt buộc:\n"
        '- "full_name": giữ nguyên chính xác tên repo đầu vào\n'
        '- "summary_vi": tóm tắt bằng tiếng Việt tối đa 3 câu văn súc tích, sát đúng nội dung description và readme_excerpt thật\n'
        '- "fit_score": số nguyên từ 0 đến 100 đánh giá mức độ phù hợp thực tế cho F&B Hy Chay / Xe Du Lịch Đình Nhân / vận hành Cloud nhẹ cho máy RAM 8GB (chấm thấp nếu không liên quan)\n'
        '- "sector": nhãn ngắn tiếng Việt (ví dụ: "F&B Hy Chay", "Xe Dịch Vụ", "Hạ tầng & DevTools", "Ngoài ngành F&B/Xe")\n'
        '- "ram_note": đánh giá ngắn bằng tiếng Việt về mức tiêu thụ tài nguyên / RAM 8GB\n'
        '- "suggestion": 1 câu khuyến nghị ứng dụng thực tế bằng tiếng Việt dựa đúng trên README\n\n'
        f"DỮ LIỆU ĐẦU VÀO:\n{json.dumps(repo_blocks, ensure_ascii=False)}"
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{urllib.parse.quote(model_id)}:generateContent"
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 2400,
            "responseMimeType": "application/json",
        },
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=35) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        raw_text = "".join(p.get("text", "") for p in parts).strip()
        items = _extract_json_array(raw_text)
        if not items:
            return None, f"HTTP 200 ParseError: Gemini khong tra ve JSON array hop le ({raw_text[:140]})"

        mapped = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            key = str(item.get("full_name", "")).strip().lower()
            if not key:
                continue
            raw_score = item.get("fit_score")
            try:
                fit_score = max(0, min(100, int(round(float(raw_score)))))
            except (TypeError, ValueError):
                fit_score = None
            mapped[key] = {
                "summary_vi": enforce_max_three_sentences(item.get("summary_vi", "")),
                "fit_score": fit_score,
                "sector": str(item.get("sector") or "").strip() or None,
                "ram_note": str(item.get("ram_note") or "").strip() or None,
                "suggestion": str(item.get("suggestion") or "").strip() or None,
            }
        return mapped, None
    except urllib.error.HTTPError as http_err:
        return None, _parse_http_error(http_err)
    except Exception as exc:
        return None, f"RequestError: {exc}"


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

    trending_repos.sort(key=lambda r: r.get("stargazers_count", 0), reverse=True)
    trending_repos = trending_repos[:total_limit]

    repo_inputs = []
    for repo in trending_repos:
        full_name = repo.get("full_name", "")
        default_branch = repo.get("default_branch", "main")
        readme_excerpt = fetch_repo_readme_excerpt(
            full_name=full_name,
            default_branch=default_branch,
            github_token=github_token,
        )
        repo_inputs.append({"repo": repo, "readme_excerpt": readme_excerpt})

    active_model, available_flash_models, list_models_error = discover_active_flash_model(gemini_api_key)
    print(f"[BAL TechRadar] ListModels Flash={available_flash_models[:8]} | Selected={active_model} | ListErr={list_models_error}")

    analysis_by_name = {}
    errors_by_name = {}
    gemini_live_calls = 0
    terminal_error = None if gemini_api_key else "Thieu bien moi truong GEMINI_API_KEY"
    last_api_error = terminal_error or list_models_error

    if gemini_api_key:
        for start in range(0, len(repo_inputs), BATCH_SIZE):
            batch = repo_inputs[start:start + BATCH_SIZE]
            if terminal_error:
                for entry in batch:
                    errors_by_name[entry["repo"].get("full_name", "").lower()] = terminal_error
                continue

            if start > 0:
                print(f"[BAL TechRadar] Cho {BATCH_SLEEP_SECONDS}s chong 429 truoc batch {start // BATCH_SIZE + 1}...")
                time.sleep(BATCH_SLEEP_SECONDS)

            gemini_live_calls += 1
            batch_result, batch_error = analyze_repo_batch_vi(gemini_api_key, active_model, batch)

            if batch_error and batch_error.startswith("HTTP 429"):
                print(f"[BAL TechRadar] Batch gap HTTP 429, cho them {BATCH_SLEEP_SECONDS}s thu lai 1 lan...")
                time.sleep(BATCH_SLEEP_SECONDS)
                gemini_live_calls += 1
                batch_result, batch_error = analyze_repo_batch_vi(gemini_api_key, active_model, batch)

            if batch_result:
                for entry in batch:
                    fn_lower = entry["repo"].get("full_name", "").lower()
                    if fn_lower in batch_result and batch_result[fn_lower].get("summary_vi"):
                        analysis_by_name[fn_lower] = batch_result[fn_lower]
                    else:
                        errors_by_name[fn_lower] = "Gemini khong tra ve ban tom tat cho repo nay trong batch JSON."
            else:
                last_api_error = batch_error
                for entry in batch:
                    errors_by_name[entry["repo"].get("full_name", "").lower()] = batch_error
                if batch_error and any(code in batch_error for code in ("HTTP 400", "HTTP 401", "HTTP 402", "HTTP 403", "HTTP 404")):
                    terminal_error = batch_error

    enriched = []
    translated_count = 0
    for rank, entry in enumerate(repo_inputs, start=1):
        repo = entry["repo"]
        full_name = repo.get("full_name", "")
        fn_lower = full_name.lower()
        ai_data = analysis_by_name.get(fn_lower)
        api_error = errors_by_name.get(fn_lower)
        if ai_data and ai_data.get("summary_vi"):
            translated_count += 1

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
            "readme_loaded": bool(entry["readme_excerpt"]),
            "summary_vi": ai_data.get("summary_vi") if ai_data else None,
            "fit_score": ai_data.get("fit_score") if ai_data else None,
            "sector": ai_data.get("sector") if ai_data else None,
            "ram_note": ai_data.get("ram_note") if ai_data else None,
            "suggestion": ai_data.get("suggestion") if ai_data else None,
            "ai_engine": active_model if ai_data else None,
            "api_error": api_error,
        })

    generated_at_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if translated_count == len(enriched) and not last_api_error:
        upstream_status = "LIVE_OK"
        radar_status = "LIVE"
    elif translated_count > 0:
        upstream_status = f"PARTIAL ({translated_count}/{len(enriched)})"
        radar_status = "PARTIAL"
    else:
        upstream_status = last_api_error or "NO_OUTPUT"
        radar_status = "API_ERROR"

    payload = {
        "project": "BAL TechRadar — Trạm Tình Báo Công Nghệ Bảo Anh Lâm",
        "status": radar_status,
        "dry_run": False,
        "generated_at_utc": generated_at_utc,
        "languages": list(TARGET_LANGUAGES),
        "window": "24h_trending",
        "total_repos": len(enriched),
        "translated_count": translated_count,
        "gemini_enabled": bool(gemini_api_key),
        "gemini_model": active_model,
        "available_flash_models": available_flash_models,
        "batch_size": BATCH_SIZE,
        "gemini_live_calls": gemini_live_calls,
        "gemini_upstream_status": upstream_status,
        "gemini_error": last_api_error if translated_count < len(enriched) else None,
        "repositories": enriched,
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    md_lines = [
        f"# BAL TechRadar — Bản tin Tình báo Công nghệ ({generated_at_utc})",
        f"- **Tổng số repo:** `{len(enriched)}` (`Python`, `TypeScript` — Trending 24h)",
        f"- **Trạng thái Gemini AI:** `{radar_status}` | Model: `{active_model}` | Đã dịch: `{translated_count}/{len(enriched)}` | Requests: `{gemini_live_calls}`",
    ]
    if payload["gemini_error"]:
        md_lines.append(f"- **Lỗi API thực tế:** `{payload['gemini_error']}`")
    md_lines.append("")

    for item in enriched:
        md_lines.append(
            f"### {item['rank']}. [{item['full_name']}]({item['url']}) — ⭐ {item['stars']:,} ({item['language']})"
        )
        if item["summary_vi"]:
            md_lines.append(f"- **Tóm tắt (<= 3 câu):** {item['summary_vi']}")
            if item["fit_score"] is not None:
                md_lines.append(f"- **BAL Fit:** {item['fit_score']}/100 ({item['sector']}) | {item['suggestion']}")
        else:
            md_lines.append(f"- **Description (gốc):** {item['description'] or 'Không có'}")
            md_lines.append(f"- **Trạng thái API:** `{item['api_error'] or 'Chưa phân tích'}`")
        md_lines.append("")

    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    return payload


def main():
    parser = argparse.ArgumentParser(description="BAL TechRadar — 24h GitHub Trending + Gemini Flash Batch Summarizer")
    parser.add_argument("--limit", type=int, default=30, help="Tong so repo can lay (mac dinh: 30)")
    args = parser.parse_args()

    result = run_tech_radar(total_limit=args.limit)
    print(
        f"[BAL TechRadar] Hoan tat: {result['translated_count']}/{result['total_repos']} repo da dich "
        f"| Model={result['gemini_model']} | Calls={result['gemini_live_calls']} | Status={result['gemini_upstream_status']}"
    )
    print(f"[BAL TechRadar] JSON: {OUTPUT_JSON}")
    print(f"[BAL TechRadar] Markdown: {OUTPUT_MD}")
    for item in result["repositories"][:5]:
        preview = item["summary_vi"] or item["api_error"] or item["description"]
        print(f"  #{item['rank']} {item['full_name']} ({item['language']} | {item['stars']} stars) -> {preview}")


if __name__ == "__main__":
    main()
