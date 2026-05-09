"""
Universal content ingestor.
Supports: YouTube (via Apify), TikTok, Instagram Reels, Instagram Posts, articles.
"""

import os
import re
import requests
from typing import Tuple
from apify_client import ApifyClient


def detect_url_type(url: str) -> str:
    url_lower = url.lower()
    if "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "youtube"
    elif "tiktok.com" in url_lower:
        return "tiktok"
    elif "instagram.com/reel" in url_lower:
        return "instagram_reel"
    elif "instagram.com/p/" in url_lower:
        return "instagram_post"
    elif "instagram.com" in url_lower:
        return "instagram"
    elif "twitter.com" in url_lower or "x.com" in url_lower:
        return "twitter"
    elif "substack.com" in url_lower:
        return "substack"
    elif "spotify.com" in url_lower:
        return "spotify_podcast"
    else:
        return "article"


def _apify_client() -> ApifyClient:
    return ApifyClient(os.getenv("APIFY_API_KEY"))


def _parse_vtt(vtt_text: str) -> str:
    """Extract plain text from a WebVTT subtitle string."""
    lines = []
    for line in vtt_text.splitlines():
        line = line.strip()
        if not line or line.startswith("WEBVTT") or "-->" in line:
            continue
        line = re.sub(r'<[^>]+>', '', line)
        if line:
            lines.append(line)
    return " ".join(lines)


def ingest_youtube(url: str) -> Tuple[str, dict]:
    """Extract transcript via Apify dz_omar/youtube-transcript-metadata-extractor."""
    client = _apify_client()
    run_input = {
        "youtubeUrl": [{"url": url}],
        "cleaningLevel": "mild",
        "includeTimestamps": True,
    }

    print(f"[INGESTOR] Fetching YouTube transcript via Apify: {url}")
    try:
        run = client.actor("dz_omar/youtube-transcript-metadata-extractor").call(
            run_input=run_input, timeout_secs=120
        )
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        if not items:
            raise ValueError("Apify returned no data")

        item = items[0]
        title = item.get("Video_title", "Unknown")
        channel_raw = item.get("channel", {})
        channel_name = channel_raw.get("name", "Unknown") if isinstance(channel_raw, dict) else str(channel_raw)
        views = item.get("Views", "0")
        duration = item.get("estimatedDuration", "Unknown")
        transcript_text = item.get("transcriptText", "")

        timestamps = item.get("timestamps", [])
        if timestamps:
            ts_lines = [f"[{t.get('time', '?')}] {t.get('text', '')}" for t in timestamps]
            transcript_formatted = "\n".join(ts_lines)
        else:
            transcript_formatted = transcript_text

        metadata = {
            "title": title,
            "channel": channel_name,
            "duration_s": 0,
            "view_count": int(re.sub(r'[^0-9]', '', str(views))) if views else 0,
            "url": url,
            "transcript_text": transcript_text,
        }

        content = f"""VIDEO TITLE: {title}
CHANNEL: {channel_name}
DURATION: {duration}
VIEWS: {views}
URL: {url}

TRANSCRIPT:
{transcript_formatted}
"""
        return content, metadata

    except Exception as e:
        print(f"[INGESTOR] Apify YouTube failed ({e}), falling back to yt-dlp...")
        return _ingest_youtube_fallback(url)


def _ingest_youtube_fallback(url: str) -> Tuple[str, dict]:
    """yt-dlp + youtube-transcript-api fallback."""
    import yt_dlp
    try:
        from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
        HAS_YTA = True
    except ImportError:
        HAS_YTA = False

    video_id = None
    for pattern in [r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
                    r'youtube\.com/embed/([a-zA-Z0-9_-]{11})']:
        match = re.search(pattern, url)
        if match:
            video_id = match.group(1)
            break

    metadata = {"video_id": video_id, "url": url, "title": "Unknown", "duration_s": 0, "view_count": 0}
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True}) as ydl:
            info = ydl.extract_info(url, download=False)
            metadata.update({
                "title": info.get("title", "Unknown"),
                "channel": info.get("channel", "Unknown"),
                "duration_s": info.get("duration", 0),
                "view_count": info.get("view_count", 0),
            })
    except Exception as e:
        print(f"[INGESTOR] yt-dlp metadata error: {e}")

    transcript_text = "[No transcript available — video may lack captions]"
    if video_id and HAS_YTA:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "en-US", "en-GB"])
            segs = [f"[{int(e['start'])//60:02d}:{int(e['start'])%60:02d}] {e['text']}" for e in transcript_list]
            transcript_text = "\n".join(segs)
        except Exception:
            pass

    content = f"""VIDEO TITLE: {metadata.get('title', 'Unknown')}
CHANNEL: {metadata.get('channel', 'Unknown')}
DURATION: {metadata.get('duration_s', 0) // 60}m {metadata.get('duration_s', 0) % 60}s
VIEWS: {metadata.get('view_count', 0):,}
URL: {url}

TRANSCRIPT:
{transcript_text}
"""
    return content, metadata


def ingest_tiktok(url: str) -> Tuple[str, dict]:
    """Extract TikTok video data via Apify clockworks/tiktok-scraper."""
    client = _apify_client()
    run_input = {
        "postURLs": [url],
        "shouldDownloadSubtitles": True,
        "shouldDownloadVideos": False,
    }

    print(f"[INGESTOR] Fetching TikTok via Apify: {url}")
    run = client.actor("clockworks/tiktok-scraper").call(run_input=run_input, timeout_secs=120)
    items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    if not items:
        raise ValueError("TikTok scraper returned no data")

    item = items[0]
    author = item.get("authorMeta", {})
    video_meta = item.get("videoMeta", {})

    title = (item.get("text", "") or "TikTok Video")[:120]
    username = author.get("name", "unknown")
    plays = item.get("playCount", 0)
    likes = item.get("diggCount", 0)
    comments_count = item.get("commentCount", 0)
    shares = item.get("shareCount", 0)
    duration = video_meta.get("duration", 0)
    hashtags = " ".join(f"#{h.get('name', '')}" for h in item.get("hashtags", []))
    created = (item.get("createTimeISO", "") or "")[:10]

    transcript_text = ""
    subtitle_links = video_meta.get("subtitleLinks", [])
    for sub in subtitle_links:
        lang = sub.get("language", "")
        if "en" in lang.lower() and sub.get("source", "MT") != "MT":
            try:
                r = requests.get(sub.get("downloadLink") or sub.get("tiktokLink", ""), timeout=15)
                if r.status_code == 200:
                    transcript_text = _parse_vtt(r.text)
                    break
            except Exception:
                pass

    if not transcript_text:
        transcript_text = f"[Caption]: {item.get('text', '')}"

    metadata = {
        "title": title,
        "channel": f"@{username}",
        "view_count": plays,
        "url": url,
        "platform": "TikTok",
        "duration_s": duration,
    }

    content = f"""TIKTOK VIDEO
Author: @{username} ({author.get('fans', 0):,} followers)
Caption: {item.get('text', '')}
Stats: {plays:,} plays | {likes:,} likes | {comments_count:,} comments | {shares:,} shares
Duration: {duration}s | Posted: {created}
Hashtags: {hashtags}
URL: {url}

TRANSCRIPT / CONTENT:
{transcript_text}
"""
    return content, metadata


def ingest_instagram_reel(url: str) -> Tuple[str, dict]:
    """Extract Instagram Reel via Apify apify/instagram-reel-scraper."""
    client = _apify_client()
    run_input = {
        "directUrls": [url],
        "resultsLimit": 1,
    }

    print(f"[INGESTOR] Fetching Instagram Reel via Apify: {url}")
    run = client.actor("apify/instagram-reel-scraper").call(run_input=run_input, timeout_secs=120)
    items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    if not items:
        raise ValueError("Instagram Reel scraper returned no data")

    item = items[0]
    owner = item.get("ownerUsername", "unknown")
    owner_full = item.get("ownerFullName", owner)
    caption = item.get("caption", "")
    likes = item.get("likesCount", 0)
    views = item.get("videoViewCount", 0)
    plays = item.get("videoPlayCount", 0)
    comments_count = item.get("commentsCount", 0)
    shares = item.get("sharesCount", 0)
    duration = item.get("videoDuration", 0)
    transcript = item.get("transcript", "")
    timestamp = (item.get("timestamp", "") or "")[:10]
    hashtags = " ".join(f"#{h}" for h in item.get("hashtags", []))

    latest_comments = item.get("latestComments", [])
    comments_text = "\n".join(
        f"  @{c.get('ownerUsername', '?')}: {c.get('text', '')}"
        for c in latest_comments[:5]
    )

    metadata = {
        "title": caption[:100] or f"Instagram Reel by @{owner}",
        "channel": f"@{owner}",
        "view_count": plays or views,
        "url": url,
        "platform": "Instagram Reel",
        "duration_s": int(duration) if duration else 0,
    }

    content = f"""INSTAGRAM REEL
Author: @{owner} ({owner_full})
Caption: {caption}
Stats: {plays:,} plays | {views:,} views | {likes:,} likes | {comments_count:,} comments | {shares:,} shares
Duration: {duration}s | Posted: {timestamp}
Hashtags: {hashtags}
URL: {url}

TRANSCRIPT:
{transcript if transcript else '[No transcript available]'}

TOP COMMENTS:
{comments_text}
"""
    return content, metadata


def ingest_instagram_post(url: str) -> Tuple[str, dict]:
    """Extract Instagram post via Apify apify/instagram-scraper."""
    client = _apify_client()
    run_input = {
        "directUrls": [url],
        "resultsType": "posts",
        "resultsLimit": 1,
    }

    print(f"[INGESTOR] Fetching Instagram post via Apify: {url}")
    run = client.actor("apify/instagram-scraper").call(run_input=run_input, timeout_secs=120)
    items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    if not items:
        raise ValueError("Instagram scraper returned no data")

    item = items[0]
    caption = item.get("caption", "")
    owner = item.get("ownerUsername", "unknown")
    likes = item.get("likesCount", 0)
    comments_count = item.get("commentsCount", 0)
    timestamp = (item.get("timestamp", "") or "")[:10]

    metadata = {
        "title": caption[:100] or f"Instagram Post by @{owner}",
        "channel": f"@{owner}",
        "view_count": 0,
        "url": url,
        "platform": "Instagram",
    }

    content = f"""INSTAGRAM POST
Author: @{owner}
Caption: {caption}
Stats: {likes:,} likes | {comments_count:,} comments | Posted: {timestamp}
URL: {url}
"""
    return content, metadata


def ingest_article(url: str) -> Tuple[str, dict]:
    """Extract article text using trafilatura with requests fallback."""
    import trafilatura

    downloaded = trafilatura.fetch_url(url)
    if downloaded:
        text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
        if text:
            metadata_obj = trafilatura.extract_metadata(downloaded)
            title = metadata_obj.title if metadata_obj else url
            return f"ARTICLE: {title}\nURL: {url}\n\n{text}", {"title": title, "url": url}

    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; ViciBot/1.0)"}
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        text = re.sub(r'<[^>]+>', ' ', r.text)
        text = re.sub(r'\s+', ' ', text).strip()
        return f"ARTICLE: {url}\n\n{text[:8000]}", {"url": url, "title": url}
    except Exception as e:
        raise ValueError(f"Could not ingest URL {url}: {e}")


def ingest_url(url: str) -> Tuple[str, dict, str]:
    """Master ingestion router. Returns (content, metadata, source_type)."""
    url_type = detect_url_type(url)

    if url_type == "youtube":
        content, meta = ingest_youtube(url)
        return content, meta, "YouTube Video"
    elif url_type == "tiktok":
        content, meta = ingest_tiktok(url)
        return content, meta, "TikTok Video"
    elif url_type == "instagram_reel":
        content, meta = ingest_instagram_reel(url)
        return content, meta, "Instagram Reel"
    elif url_type in ("instagram_post", "instagram"):
        content, meta = ingest_instagram_post(url)
        return content, meta, "Instagram Post"
    else:
        content, meta = ingest_article(url)
        return content, meta, "Article/Web Page"
