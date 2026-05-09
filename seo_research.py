"""
DataForSEO integration — keyword search volumes, related keywords, Google Trends.
Credentials: ZHBAYml6emF1dG9tYXRlLmlvOjYxYjU4ZjRhNTMwYTBmNWI= (Base64 login:password)
"""

import os
import requests

DATAFORSEO_B64 = os.getenv("DATAFORSEO_B64", "")
BASE_URL = "https://api.dataforseo.com/v3"


def _headers() -> dict:
    return {
        "Authorization": f"Basic {DATAFORSEO_B64}",
        "Content-Type": "application/json",
    }


def _post(path: str, body: list) -> dict:
    r = requests.post(f"{BASE_URL}{path}", headers=_headers(), json=body, timeout=30)
    r.raise_for_status()
    return r.json()


def get_keyword_search_volumes(keywords: list) -> str:
    """Get Google Ads monthly search volumes for a list of keywords."""
    try:
        body = [{
            "keywords": keywords[:20],
            "location_name": "United States",
            "language_name": "English",
        }]
        data = _post("/keywords_data/google_ads/search_volume/live", body)
        tasks = data.get("tasks", [])
        if not tasks or tasks[0].get("status_code") != 20000:
            msg = tasks[0].get("status_message", "unknown error") if tasks else "no tasks returned"
            return f"Search volume lookup failed: {msg}"

        results = tasks[0].get("result", []) or []
        if not results:
            return "No search volume data returned."

        lines = ["KEYWORD SEARCH VOLUMES (Monthly, US)\n" + "="*40]
        for item in sorted(results, key=lambda x: x.get("search_volume", 0), reverse=True):
            kw = item.get("keyword", "?")
            vol = item.get("search_volume", 0)
            comp = item.get("competition_level", "?")
            cpc = item.get("cpc", 0) or 0
            lines.append(f"• {kw}: {vol:,}/mo | Competition: {comp} | CPC: ${float(cpc):.2f}")

        return "\n".join(lines)
    except Exception as e:
        return f"DataForSEO search volume error: {e}"


def get_related_keywords(seed_keyword: str, limit: int = 20) -> str:
    """Find related keywords with search volumes for a seed topic."""
    try:
        body = [{
            "keywords": [seed_keyword],
            "location_name": "United States",
            "language_name": "English",
            "limit": limit,
            "filters": [["search_volume", ">", 100]],
            "order_by": ["search_volume,desc"],
        }]
        data = _post("/dataforseo_labs/google/keywords_for_keywords/live", body)
        tasks = data.get("tasks", [])
        if not tasks or tasks[0].get("status_code") != 20000:
            msg = tasks[0].get("status_message", "?") if tasks else "no tasks"
            return f"Related keywords lookup failed: {msg}"

        results = tasks[0].get("result", []) or []
        if not results:
            return "No related keywords found."

        items = results[0].get("items", []) or []
        lines = [f"RELATED KEYWORDS FOR: {seed_keyword}\n" + "="*40]
        for item in items[:20]:
            kw = item.get("keyword", "?")
            vol = item.get("keyword_info", {}).get("search_volume", 0)
            diff = item.get("keyword_properties", {}).get("keyword_difficulty", "?")
            lines.append(f"• {kw}: {vol:,}/mo | Difficulty: {diff}")

        return "\n".join(lines)
    except Exception as e:
        return f"DataForSEO related keywords error: {e}"


def get_google_trends(keywords: list, time_range: str = "past_7_days") -> str:
    """Get Google Trends interest scores for keywords."""
    try:
        body = [{
            "keywords": keywords[:5],
            "location_name": "United States",
            "language_name": "English",
            "time_range": time_range,
            "type": "web",
        }]
        data = _post("/keywords_data/google_trends/explore/live", body)
        tasks = data.get("tasks", [])
        if not tasks or tasks[0].get("status_code") != 20000:
            msg = tasks[0].get("status_message", "?") if tasks else "no tasks"
            return f"Google Trends lookup failed: {msg}"

        results = tasks[0].get("result", []) or []
        if not results:
            return "No Google Trends data returned."

        lines = [f"GOOGLE TRENDS — {', '.join(keywords)}\nPeriod: {time_range}\n" + "="*40]
        for result in results:
            kw = result.get("keyword", "?")
            items = result.get("items", []) or []
            if items:
                values = [i.get("values", [0])[0] for i in items if i.get("values")]
                if values:
                    avg = sum(values) // len(values)
                    peak = max(values)
                    lines.append(f"• {kw}: avg {avg}/100 | peak {peak}/100 | {len(values)} data points")

        return "\n".join(lines)
    except Exception as e:
        return f"DataForSEO Google Trends error: {e}"


def get_content_opportunities(niche_keywords: list = None) -> str:
    """Full content opportunity report: volumes + trends + related keywords."""
    if niche_keywords is None:
        niche_keywords = [
            "BPC-157", "semaglutide", "tirzepatide", "retatrutide",
            "peptides longevity", "GLP-1", "GHK-Cu", "tesamorelin"
        ]

    lines = ["SEO CONTENT OPPORTUNITIES — VICI PEPTIDES\n" + "="*50]

    vol_data = get_keyword_search_volumes(niche_keywords)
    lines.append("\n" + vol_data)

    trend_data = get_google_trends(niche_keywords[:5], "past_7_days")
    lines.append("\n" + trend_data)

    related = get_related_keywords("peptides research")
    lines.append("\n" + related)

    return "\n".join(lines)
