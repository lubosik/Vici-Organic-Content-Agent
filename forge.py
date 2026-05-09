"""FORGE — Content Production Engine."""

import os
import re
import json
from datetime import datetime
from pathlib import Path
import ai_client as anthropic
from brand import TOPIC_QUEUE, CTA, BANNED_WORDS, INSTAGRAM_BANNED_TERMS
from dedup import next_topic, is_duplicate, record, mark_topic_done
from elevenlabs_client import generate_voiceover
from content_db import get_recent_analyses


def _claude(prompt: str, max_tokens: int = 1500) -> str:
    client = anthropic.Anthropic()
    r = client.messages.create(
        model=os.getenv("AI_MODEL", "anthropic/claude-sonnet-4-6"),
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    return r.content[0].text.strip()


def _contains_banned(text: str) -> bool:
    text_lower = text.lower()
    return any(b in text_lower for b in BANNED_WORDS)


def _regenerate_if_banned(text: str, prompt: str, max_attempts: int = 3) -> str:
    for attempt in range(max_attempts):
        if not _contains_banned(text):
            return text
        print(f"  Warning: Banned language detected (attempt {attempt+1}). Regenerating...")
        text = _claude(prompt)
    return text


def generate_script(topic: dict) -> str:
    prompt = f"""Write a TikTok voiceover script for Vici Peptides — a research peptide brand (vicipeptides.com).

TOPIC: {topic['title']}
FORMAT: {topic['format']} — Target duration: ~{topic['duration_s']} seconds
HOOK (use this verbatim as the opening line): {topic['hook']}
COMPOUND FOCUS: {topic['compound']}
KEY DATA TO INCLUDE: {topic['key_data']}

MANDATORY RULES:
- Begin with the hook word-for-word
- Speak as a knowledgeable, credible insider — not a salesman or doctor
- Plain English. When using technical terms, define them immediately
- Every factual claim must cite a source inline: "published in [journal]" or "researchers found that"
- NEVER say any of these: {', '.join(BANNED_WORDS[:8])}
- NEVER imply personal use, medical advice, or purchasing
- End with EXACTLY this CTA: "{CTA['standard']}"
- Target word count: {int(topic['duration_s'] * 2.3)} words

Output ONLY the script. No stage directions, no headers, no commentary.
"""
    script = _claude(prompt, max_tokens=800)
    script = _regenerate_if_banned(script, prompt)

    if is_duplicate(script, "scripts"):
        prompt += "\n\nIMPORTANT: A previous version of this script exists. Use a completely different structure, different opening examples, and different data points. Make it fresh."
        script = _claude(prompt, max_tokens=800)

    record(script, "scripts", {"topic_id": topic["id"]})
    return script


def generate_broll_list(topic: dict, script: str) -> str:
    prompt = f"""Generate a B-roll download list for this faceless TikTok video.

SCRIPT:
{script}

TOTAL DURATION: ~{topic['duration_s']} seconds

Rules:
- List exactly 8-10 B-roll clips, each 3-6 seconds
- For each: SEARCH TERM (for Pexels or Artgrid) | SOURCE | PLAYS DURING (quote script line) | VISUAL description
- All footage: science/medical/lab aesthetic. NO gym influencer footage.
- 3 from Pexels (free), 5-7 from Artgrid (premium)

Format:
[N]. SEARCH: "..." | SOURCE: Pexels/Artgrid | DURING: "..." | SHOWS: ...

Output only the numbered list.
"""
    return _claude(prompt, max_tokens=600)


def generate_capcut_guide(topic: dict, script: str) -> str:
    words = len(script.split())
    est_duration = round(words / 2.3)
    return f"""CapCut Guide — {topic['title']}
Format: {topic['format']} | Duration: ~{est_duration}s

Setup: New project -> 9:16 -> 1080x1920 -> 30fps

Step 1: Import
- Drag voiceover.mp3 to audio track first (this is your timeline anchor)

Step 2: B-roll
- Download all clips from broll_list.txt
- Arrange on video track in order, trimmed to fill audio length
- 0.3s dissolve transitions between clips

Step 3: Opening Hook Card (first 2 seconds)
- Black background (#000000)
- Text: "{topic['hook'].split('.')[0].strip()}"
- Font: Montserrat ExtraBold, white, fills ~70% screen width
- Duration: 2.0 seconds — this is your thumbnail frame

Step 4: Auto Captions
- Select audio -> Auto Caption -> English
- Style: White text, black pill background, Montserrat Bold
- Position: Lower-middle
- After generating: highlight compound names in teal (#00D4AA)

Step 5: Key Data Overlays
- Add bold text overlays for any percentages or specific numbers in script
- Style: White text, black outline 3px, teal for numbers
- Each overlay: hold for 3-4 seconds

Step 6: Music
- CapCut free library -> "ambient science" or "lo-fi focus"
- Volume: -18dB under voiceover

Step 7: Closing Overlay (last 5 seconds)
- "Free research guide — link in bio"
- Sub-text: "vicipeptides.com"

Step 8: Export
- 1080p -> H.264 -> MP4
- Filename: {topic['id']}_{est_duration}s.mp4
"""


def generate_x_posts(count: int = 5) -> str:
    recent = get_recent_analyses(3)
    source_context = ""
    if recent:
        source_context = "\n\nRECENT SCOUTED CONTENT (draw from these if relevant):\n"
        for a in recent:
            source_context += f"\nSource: {a['title']} ({a['source_type']})\nKey analysis:\n{a['analysis'][:400]}\n---"

    prompt = f"""Generate {count} X (Twitter) posts for Vici Peptides — a research peptide brand.

BRAND VOICE: Scientific. Bold. Credible. Truth the mainstream hasn't said yet. No promotional language.
AUDIENCE: Biohackers, longevity researchers, GLP-1 informed adults.

TOPICS TO DRAW FROM:
- BPC-157 endogenous origin and tissue repair research
- GLP-1 tier comparison (Semaglutide vs Tirzepatide vs Retatrutide receptor count)
- Purity standards and what HPLC CoA actually verifies
- GHK-Cu age-related natural decline
- GLP-1 dopamine system effects (nucleus accumbens research)
- Tesamorelin — FDA-approved, underexplored
- Longevity compound stacks
{source_context}

MIX (across {count} posts):
- 2 single data-drop tweets (bold, <=280 chars, shareable stat or mechanism)
- 1 thread opener + 4 follow-up tweets (number them 2/, 3/, 4/, 5/)
- 1 research citation post (cite real journal, 1-2 sentence context)
- 1 contrarian take (challenges common belief with evidence)

RULES:
- Every claim must be based on published science
- Never say: buy, order, take, results, transformation, cure, treat, diagnose
- Max 1 CTA across all posts: "Full compound research guides at vicipeptides.com"
- No hashtag spam — max 2 hashtags only where they add value

Output each post clearly labelled:
POST 1 [type]:
[content]
---
"""
    result = _claude(prompt, max_tokens=2000)
    record(result, "x_posts")
    return result


def generate_instagram_carousel(topic: dict = None) -> dict:
    if topic is None:
        from brand import TOPIC_QUEUE
        topic = TOPIC_QUEUE[0]

    recent = get_recent_analyses(2)
    source_context = ""
    if recent:
        source_context = "\n\nRECENT SCOUTED CONTENT (reference if relevant to topic):\n"
        for a in recent:
            source_context += f"\nSource: {a['title']} ({a['source_type']})\nAnalysis excerpt:\n{a['analysis'][:300]}\n---"

    prompt = f"""Create an Instagram carousel for Vici Peptides (research peptide brand).

TOPIC: {topic['title']}
HOOK: {topic['hook']}
KEY DATA: {topic['key_data']}
{source_context}

CRITICAL — INSTAGRAM SAFE LANGUAGE (account was previously banned):
ALWAYS USE: research compounds, longevity research, metabolic science, scientific wellness,
laboratory research use only, research-grade, published literature suggests, compound mechanisms,
cellular research, third-party tested, certificate of analysis, HPLC verified

NEVER USE: {', '.join(INSTAGRAM_BANNED_TERMS)}

CAROUSEL STRUCTURE (9 slides):
- Slide 1: Hook — bold statement on dark background
- Slides 2-7: One key fact per slide, cited ("Published research shows...")
- Slide 8: Summary — the one-line takeaway
- Slide 9: CTA — "Research compound profiles — link in bio | For laboratory research use only"

Brand colours: Background #0A0A0A | Accent #00D4AA | Text #FFFFFF

Output as JSON:
{{
  "slides": [
    {{"n": 1, "heading": "...", "body": "...", "visual": "design direction"}}
  ],
  "caption": "full Instagram caption using ONLY safe language",
  "hashtags": ["#longevityresearch", "#metabolicscience", "#researchcompounds"]
}}
"""
    raw = _claude(prompt, max_tokens=1500)
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {"raw": raw}


def produce_content_package(topic: dict = None) -> dict:
    if topic is None:
        topic = next_topic(TOPIC_QUEUE)

    print(f"\n[FORGE] Producing: {topic['title']}")
    date_str = datetime.now().strftime("%Y-%m-%d")
    output_dir = Path(f"output/{date_str}/{topic['id']}")
    output_dir.mkdir(parents=True, exist_ok=True)

    assets = {"topic": topic, "dir": str(output_dir)}

    print("  -> Writing script...")
    script = generate_script(topic)
    (output_dir / "script.txt").write_text(script)
    assets["script"] = script

    print("  -> Generating voiceover...")
    vo_path = str(output_dir / "voiceover.mp3")
    vo_success = generate_voiceover(script, vo_path)
    assets["voiceover_path"] = vo_path if vo_success else None
    assets["voiceover_ok"] = vo_success

    print("  -> Writing B-roll list...")
    broll = generate_broll_list(topic, script)
    (output_dir / "broll_list.txt").write_text(broll)
    assets["broll"] = broll

    guide = generate_capcut_guide(topic, script)
    (output_dir / "capcut_guide.md").write_text(guide)
    assets["capcut_guide"] = guide

    mark_topic_done(topic["id"])
    print(f"  Done. Package saved: {output_dir}/")
    return assets
