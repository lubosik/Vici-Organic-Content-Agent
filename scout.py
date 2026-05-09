"""SCOUT — Viral Clip Identification Engine."""

import os
import json
from datetime import datetime
import ai_client as anthropic
from ingestor import ingest_url
from formula import build_clip_analysis_prompt
from dedup import record
from content_db import save_scout_analysis, save_identified_clip, url_already_scouted


def analyse_url(url: str) -> str:
    print(f"[SCOUT] Ingesting: {url}")
    try:
        content, metadata, source_type = ingest_url(url)
    except Exception as e:
        return f"SCOUT couldn't ingest that URL.\n\nError: {e}\n\nMake sure it's a public YouTube video, article, or webpage."

    title = metadata.get("title", url)
    print(f"[SCOUT] Content ingested: {title[:60]}")

    # Check if already scouted
    try:
        if url_already_scouted(url):
            print(f"[SCOUT] URL already scouted: {url}")
            # Still run analysis but note it's a repeat
    except Exception:
        pass

    client = anthropic.Anthropic()
    prompt = build_clip_analysis_prompt(content, source_type, url)

    print("[SCOUT] Running viral formula analysis...")
    try:
        response = client.messages.create(
            model=os.getenv("AI_MODEL", "anthropic/claude-sonnet-4-6"),
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        analysis = response.content[0].text
    except Exception as e:
        return f"AI analysis failed: {e}"

    try:
        scout_id = save_scout_analysis(
            url=url,
            title=title,
            source_type=source_type,
            analysis=analysis,
            channel=metadata.get("channel"),
            duration_s=metadata.get("duration_s"),
            view_count=metadata.get("view_count"),
            transcript=metadata.get("transcript_text"),
        )
    except Exception as e:
        print(f"[SCOUT] DB save failed: {e}")
        scout_id = None

    if source_type == "YouTube Video":
        duration = metadata.get("duration_s", 0)
        views = metadata.get("view_count", 0)
        source_line = f"*{source_type}*: {title[:60]}\n{duration // 60}m {duration % 60}s | {views:,} views"
    else:
        source_line = f"*{source_type}*: {title[:60]}"

    header = f"SCOUT CLIP ANALYSIS\n{'='*30}\n{source_line}\n{'='*30}\n\n"
    return header + analysis
