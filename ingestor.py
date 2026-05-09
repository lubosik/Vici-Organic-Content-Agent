"""Universal content ingestor. Accepts any URL."""

import os
import re
import requests
from typing import Tuple


def detect_url_type(url: str) -> str:
    url_lower = url.lower()
    if "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "youtube"
    elif "twitter.com" in url_lower or "x.com" in url_lower:
        return "twitter"
    elif "substack.com" in url_lower:
        return "substack"
    elif "spotify.com" in url_lower:
        return "spotify_podcast"
    else:
        return "article"


def ingest_youtube(url: str) -> Tuple[str, dict]:
    from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
    import yt_dlp

    video_id = None
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/embed\/([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            video_id = match.group(1)
            break

    if not video_id:
        raise ValueError(f"Could not extract YouTube video ID from: {url}")

    metadata = {"video_id": video_id, "url": url}
    try:
        ydl_opts = {"quiet": True, "skip_download": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            metadata.update({
                "title": info.get("title", "Unknown"),
                "channel": info.get("channel", "Unknown"),
                "duration_s": info.get("duration", 0),
                "view_count": info.get("view_count", 0),
                "upload_date": info.get("upload_date", ""),
            })
    except Exception as e:
        print(f"yt-dlp metadata error: {e}")

    transcript_text = ""
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "en-US", "en-GB"])
        segments = []
        for entry in transcript_list:
            start_s = int(entry["start"])
            mins = start_s // 60
            secs = start_s % 60
            segments.append(f"[{mins:02d}:{secs:02d}] {entry['text']}")
        transcript_text = "\n".join(segments)
    except (TranscriptsDisabled, NoTranscriptFound):
        transcript_text = f"[No transcript available for {url}. Metadata only.]"
    except Exception as e:
        transcript_text = f"[Transcript error: {e}]"

    content = f"""
VIDEO TITLE: {metadata.get('title', 'Unknown')}
CHANNEL: {metadata.get('channel', 'Unknown')}
DURATION: {metadata.get('duration_s', 0) // 60}m {metadata.get('duration_s', 0) % 60}s
VIEWS: {metadata.get('view_count', 0):,}
URL: {url}

TRANSCRIPT:
{transcript_text}
"""
    return content, metadata


def ingest_article(url: str) -> Tuple[str, dict]:
    import trafilatura

    downloaded = trafilatura.fetch_url(url)
    if downloaded:
        text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
        if text:
            metadata = trafilatura.extract_metadata(downloaded)
            title = metadata.title if metadata else url
            return f"ARTICLE: {title}\nURL: {url}\n\n{text}", {"title": title, "url": url}

    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; ViciBot/1.0)"}
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        text = re.sub(r'<[^>]+>', ' ', r.text)
        text = re.sub(r'\s+', ' ', text).strip()
        return f"ARTICLE: {url}\n\n{text[:8000]}", {"url": url}
    except Exception as e:
        raise ValueError(f"Could not ingest URL {url}: {e}")


def ingest_url(url: str) -> Tuple[str, dict, str]:
    url_type = detect_url_type(url)
    if url_type == "youtube":
        content, meta = ingest_youtube(url)
        return content, meta, "YouTube Video"
    else:
        content, meta = ingest_article(url)
        return content, meta, "Article/Web Page"
