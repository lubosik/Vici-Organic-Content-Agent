"""SCOUT — Viral Clip Identification Engine."""

import os
import json
from datetime import datetime
import ai_client as anthropic
from ingestor import ingest_url
from formula import build_clip_analysis_prompt
from dedup import record
from content_db import save_scout_analysis


def analyse_url(url: str) -> str:
    print(f"[SCOUT] Ingesting: {url}")
    try:
        content, metadata, source_type = ingest_url(url)
    except Exception as e:
        return f"SCOUT couldn't ingest that URL.\n\nError: {e}\n\nMake sure it's a public YouTube video, article, or webpage."

    title = metadata.get("title", url)
    print(f"[SCOUT] Content ingested: {title[:60]}")

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

    os.makedirs("data", exist_ok=True)
    log_entry = {
        "url": url,
        "title": title,
        "source_type": source_type,
        "analysed_at": datetime.now().isoformat(),
        "analysis_preview": analysis[:300]
    }
    clips_log_path = "data/clips_log.json"
    clips_log = []
    if os.path.exists(clips_log_path):
        with open(clips_log_path) as f:
            clips_log = json.load(f)
    clips_log.append(log_entry)
    with open(clips_log_path, "w") as f:
        json.dump(clips_log[-100:], f, indent=2)

    try:
        save_scout_analysis(url, title, source_type, analysis)
    except Exception:
        pass

    if source_type == "YouTube Video":
        duration = metadata.get("duration_s", 0)
        views = metadata.get("view_count", 0)
        source_line = f"*{source_type}*: {title[:60]}\n{duration // 60}m {duration % 60}s | {views:,} views"
    else:
        source_line = f"*{source_type}*: {title[:60]}"

    header = f"SCOUT CLIP ANALYSIS\n{'='*30}\n{source_line}\n{'='*30}\n\n"
    return header + analysis
