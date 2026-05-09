"""
Web search via Apify Google Search Scraper.
- Filters to articles published in the last 7 days (tbs=qdr:w at query level)
- Deduplicates: skips articles already seen in content_db
- Caches results 4 hours (reduced from 6 to balance freshness vs cost)
"""

import os
import re
import json
from datetime import datetime, timedelta
from apify_client import ApifyClient
from content_db import (
    cache_search, get_cached_search,
    is_article_seen, mark_article_seen
)


def _parse_date(date_str: str) -> datetime | None:
    """Try to parse a date string into a datetime. Returns None if unparseable."""
    if not date_str:
        return None
    formats = [
        "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d", "%B %d, %Y", "%b %d, %Y",
        "%d %B %Y", "%d %b %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str[:len(fmt)+4].strip(), fmt)
        except ValueError:
            continue
    # Try extracting YYYY-MM-DD from string
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', date_str)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return None


def _extract_date_from_url(url: str) -> datetime | None:
    """Extract publish date from URL patterns like /2025/05/09/ or /20250509."""
    m = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    m = re.search(r'[/-](\d{8})[/-]', url)
    if m:
        s = m.group(1)
        try:
            return datetime(int(s[:4]), int(s[4:6]), int(s[6:8]))
        except ValueError:
            pass
    return None


def _is_fresh(date_str: str, url: str = "", max_age_days: int = 7) -> bool:
    """
    Return True if the article appears to be within max_age_days.
    If no date can be determined, assume it's fresh (don't discard unknown dates).
    """
    cutoff = datetime.now() - timedelta(days=max_age_days)

    dt = _parse_date(date_str)
    if dt and dt < cutoff:
        return False
    if dt:
        return True

    # Try URL date
    dt = _extract_date_from_url(url)
    if dt and dt < cutoff:
        return False

    # Can't determine date — assume fresh
    return True


def search_web(query: str, max_age_days: int = 7) -> str:
    """
    Search for recent articles. Filters to past 7 days. Deduplicates.
    Returns formatted text results. Caches for 4 hours.
    """
    cache_key = f"{query}::{max_age_days}d"
    cached = get_cached_search(cache_key, max_age_hours=4)
    if cached:
        return cached

    try:
        client = ApifyClient(os.getenv("APIFY_API_KEY"))

        # Use Google's date filter via the query itself as a reliable fallback
        dated_query = f"{query} after:{(datetime.now() - timedelta(days=max_age_days)).strftime('%Y-%m-%d')}"

        run_input = {
            "queries": [dated_query],
            "maxPagesPerQuery": 1,
            "resultsPerPage": 10,  # Fetch more so dedup doesn't leave us with nothing
            "languageCode": "en",
            "countryCode": "US",
        }

        run = client.actor("apify/google-search-scraper").call(
            run_input=run_input, timeout_secs=60
        )
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())

        results = []
        seen_count = 0
        stale_count = 0

        for item in items:
            for r in item.get("organicResults", []):
                url = r.get("url", "")
                title = r.get("title", "")
                desc = r.get("description", "")
                date_str = r.get("date", "") or r.get("publishedAt", "")

                if not url or not title:
                    continue

                # Freshness check
                if not _is_fresh(date_str, url, max_age_days):
                    stale_count += 1
                    continue

                # Dedup check
                if is_article_seen(url):
                    seen_count += 1
                    continue

                # Mark as seen and add to results
                mark_article_seen(url, title=title, published_date=date_str)
                date_label = f" [{date_str}]" if date_str else " [date unknown]"
                results.append(f"- {title}{date_label}\n  {desc}\n  {url}")

                if len(results) >= 5:
                    break
            if len(results) >= 5:
                break

        suffix = ""
        if stale_count:
            suffix += f"\n\n[{stale_count} stale articles (>{max_age_days} days) filtered out]"
        if seen_count:
            suffix += f"\n[{seen_count} previously seen articles skipped]"

        if not results:
            output = f"No fresh, unseen results found for: {query}{suffix}"
        else:
            output = "\n\n".join(results) + suffix

        cache_search(cache_key, output)
        return output

    except Exception as e:
        return f"Web search unavailable: {e}"
