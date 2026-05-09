"""
Morning podcast discovery: find new peptide podcasts on YouTube (<7 days old)
not already in the database. Uses streamers/youtube-scraper.
"""

import os
from datetime import datetime, timedelta
from apify_client import ApifyClient
from content_db import url_already_scouted, save_scout_analysis


PEPTIDE_SEARCH_TERMS = [
    "peptides podcast 2025",
    "BPC-157 podcast",
    "semaglutide GLP-1 podcast",
    "longevity peptides interview",
    "biohacking peptides",
    "peptide research podcast",
]

MAX_AGE_DAYS = 7
MIN_VIEWS = 1000  # Filter out micro-channels


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

    for term in PEPTIDE_SEARCH_TERMS[:4]:  # Limit API calls
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
        return "No new peptide podcasts found in the past 7 days that are not already in the database."

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
