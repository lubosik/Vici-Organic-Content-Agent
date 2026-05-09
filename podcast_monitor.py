"""
Morning podcast discovery: find new peptide podcasts on YouTube (<7 days old)
not already in the database. Uses streamers/youtube-scraper.
"""

import os
from datetime import datetime, timedelta
from apify_client import ApifyClient
from content_db import url_already_scouted, save_scout_analysis


MAX_AGE_DAYS = 7
MIN_VIEWS = 1000  # Filter out micro-channels


def _generate_search_terms() -> list:
    """
    Generate dynamic YouTube search queries based on:
    - Current date (for recency signals)
    - Topics already researched (to avoid redundancy)
    - Trending keywords from DataForSEO
    Falls back to date-stamped static queries if AI generation fails.
    """
    import re
    import json
    import anthropic as anthropic_lib

    today = datetime.now()
    month_year = today.strftime("%B %Y")
    year = today.strftime("%Y")
    day_of_week = today.strftime("%A")

    # What topics are already covered?
    covered_topics = []
    try:
        from content_db import get_all_recent_topics, get_recent_analyses
        recent = get_all_recent_topics(days=14)
        covered_topics = [t['topic'] for t in recent[:8]]
        analyses = get_recent_analyses(limit=5)
        for a in analyses:
            if a.get('title'):
                covered_topics.append(a['title'])
    except Exception:
        pass

    # What is trending this week?
    trending_text = ""
    try:
        from seo_research import get_google_trends
        trending_text = get_google_trends(
            ["BPC-157", "semaglutide", "tirzepatide", "GLP-1", "peptides longevity"],
            "past_7_days"
        )
    except Exception:
        pass

    covered_str = "\n".join(f"- {t}" for t in covered_topics[:8]) if covered_topics else "- Nothing researched yet"

    prompt = f"""Today is {day_of_week}, {today.strftime('%B %d, %Y')}.

Generate 6 YouTube search queries to find NEW peptide/longevity podcast episodes or expert interviews published THIS WEEK.

Already covered in our database (skip these topics):
{covered_str}

Trending keywords this week:
{trending_text[:400] if trending_text else "Data unavailable"}

Rules for the queries:
1. Include "{month_year}" or "{year}" in at least 4 of the 6 queries to filter for recent content
2. Target expert interviews, podcast episodes, scientific discussions - not short-form content
3. Cover different compounds/angles so each query finds different content
4. Avoid topics already in our database
5. Mix: specific compounds (BPC-157, GHK-Cu, Tesamorelin), general longevity, GLP-1/weight research

Return ONLY a valid JSON array of exactly 6 strings. No explanation, no markdown, just the array."""

    try:
        client = anthropic_lib.Anthropic()
        response = client.messages.create(
            model=os.getenv("AI_MODEL", "claude-sonnet-4-6"),
            max_tokens=250,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip()
        match = re.search(r'\[.*?\]', text, re.DOTALL)
        if match:
            queries = json.loads(match.group())
            if isinstance(queries, list) and len(queries) >= 4:
                print(f"[PODCAST MONITOR] Generated {len(queries)} dynamic queries for {month_year}")
                return queries[:6]
    except Exception as e:
        print(f"[PODCAST MONITOR] AI query generation failed: {e}")

    # Date-stamped fallback (still better than static)
    return [
        f"peptides podcast {month_year}",
        f"BPC-157 longevity interview {year}",
        f"semaglutide GLP-1 research {month_year}",
        f"biohacking peptides {month_year}",
        f"tesamorelin GHK-Cu compound profile {year}",
        f"retatrutide tirzepatide science discussion {year}",
    ]


def _parse_date(date_str: str):
    """Try to parse YouTube date string to datetime."""
    if not date_str:
        return None
    # YouTube returns dates like "2025-05-09" or "3 days ago" or "1 week ago"
    try:
        return datetime.strptime(date_str[:10], "%Y-%m-%d")
    except Exception:
        pass
    now = datetime.now()
    try:
        if "hour" in date_str:
            n = int(''.join(filter(str.isdigit, date_str)) or '1')
            return now - timedelta(hours=n)
        if "day" in date_str:
            n = int(''.join(filter(str.isdigit, date_str)) or '1')
            return now - timedelta(days=n)
        if "week" in date_str:
            n = int(''.join(filter(str.isdigit, date_str)) or '1')
            return now - timedelta(weeks=n)
        if "month" in date_str:
            return now - timedelta(days=35)
        if "year" in date_str:
            return now - timedelta(days=400)
    except Exception:
        pass
    return None


def find_new_peptide_podcasts() -> str:
    """
    Search YouTube for new peptide podcasts, filter to <7 days old,
    skip ones already in DB. Returns formatted report.
    """
    client = ApifyClient(os.getenv("APIFY_API_KEY"))
    cutoff = datetime.now() - timedelta(days=MAX_AGE_DAYS)

    all_videos = []
    seen_ids = set()

    search_terms = _generate_search_terms()
    print(f"[PODCAST MONITOR] Using {len(search_terms)} dynamic search queries")
    print(f"[PODCAST MONITOR] Search queries this run: {search_terms}")
    for term in search_terms:
        try:
            print(f"[PODCAST MONITOR] Searching: {term}")
            run = client.actor("streamers/youtube-scraper").call(
                run_input={
                    "searchKeywords": [term],
                    "maxResultsShorts": 0,
                    "maxResultsStreams": 3,
                    "maxResults": 10,
                    "dateFilter": "week",  # Past week only
                },
                timeout_secs=120
            )
            items = list(client.dataset(run["defaultDatasetId"]).iterate_items())

            for item in items:
                vid_id = item.get("id", "")
                if not vid_id or vid_id in seen_ids:
                    continue
                seen_ids.add(vid_id)

                url = item.get("url", f"https://www.youtube.com/watch?v={vid_id}")
                views = item.get("viewCount", 0) or 0
                date_str = item.get("date", "")
                duration = item.get("duration", "")
                title = item.get("title", "Untitled")
                channel = item.get("channelName", "Unknown")

                # Filter: minimum views
                if views < MIN_VIEWS:
                    continue

                # Filter: date (must be within MAX_AGE_DAYS)
                pub_date = _parse_date(date_str)
                if pub_date and pub_date < cutoff:
                    continue

                # Filter: minimum duration (skip shorts < 5 min)
                try:
                    parts = str(duration).split(":")
                    if len(parts) == 2:
                        total_mins = int(parts[0])
                    elif len(parts) == 3:
                        total_mins = int(parts[0]) * 60 + int(parts[1])
                    else:
                        total_mins = 0
                    if total_mins < 5:
                        continue
                except Exception:
                    pass

                # Check if already in DB
                if url_already_scouted(url):
                    continue

                all_videos.append({
                    "title": title,
                    "channel": channel,
                    "url": url,
                    "views": views,
                    "date": date_str,
                    "duration": duration,
                })

        except Exception as e:
            print(f"[PODCAST MONITOR] Search '{term}' failed: {e}")

    if not all_videos:
        query_preview = ", ".join(f'"{q}"' for q in search_terms[:3])
        return (
            f"No new peptide podcasts found this week.\n\n"
            f"Searched YouTube for: {query_preview} (and {max(len(search_terms) - 3, 0)} more queries).\n\n"
            f"This could mean:\n"
            f"- All recent podcasts are already in your database\n"
            f"- YouTube returned no results under 7 days for these terms\n\n"
            f"Try again tomorrow or send me a specific YouTube channel URL to scout."
        )

    # Sort by views
    all_videos.sort(key=lambda x: x["views"], reverse=True)

    lines = [
        f"NEW PEPTIDE PODCASTS - {datetime.now().strftime('%Y-%m-%d')}\n"
        f"Found {len(all_videos)} new videos not in database.\n"
        f"{'=' * 40}\n"
    ]

    for i, v in enumerate(all_videos[:10], 1):
        lines.append(
            f"{i}. {v['title']}\n"
            f"   Channel: {v['channel']}\n"
            f"   Views: {v['views']:,}  Duration: {v['duration']}  Date: {v['date']}\n"
            f"   URL: {v['url']}\n"
        )

    lines.append("\nTo scout any of these for viral clips, just send me the URL.")
    return "\n".join(lines)
