"""TREND — Fastlane Blitz + Apify trend scraping."""

import os
import time
import json
from datetime import datetime
import ai_client as anthropic
import fastlane as fl
from fastlane import FastlaneNotConfigured
from brand import TOPIC_QUEUE


def pull_fastlane_suggestion() -> dict:
    print("[TREND] Hitting Fastlane Blitz...")
    result = fl.blitz_pop()
    if result is None:
        return {"error": "queue_empty", "message": "Fastlane queue is empty. Will refill shortly."}
    if isinstance(result, dict) and result.get("error") == "quota_exceeded":
        return result
    content_id = result["content_id"]
    print(f"[TREND] Build started: {content_id}. Polling for completion...")
    content = fl.poll_content(content_id, max_wait_s=180)
    if content is None:
        return {"error": "build_failed", "content_id": content_id}
    content["suggestion"] = {
        "content_type": result["content_type"],
        "generated_text": result["generated_text"],
        "ai_explanation": result["ai_explanation"],
    }
    return content


def _curated_topic_brief() -> dict:
    """Generate a trend brief from curated high-value topics when Apify is unavailable."""
    import random
    curated_signals = [
        "GLP-1 receptor agonists and dopamine reward pathway — new research interest spike",
        "Tirzepatide vs Retatrutide triple-agonist comparison — rising search volume",
        "BPC-157 endogenous origin — organic discovery from gastric protection research",
        "GHK-Cu natural decline after 40 — longevity research angle trending",
        "HPLC purity verification — research community focus on compound quality standards",
    ]
    signal = random.choice(curated_signals)
    ai = anthropic.Anthropic()
    prompt = f"""Based on this trending topic signal in the peptide/longevity space:
{signal}

Create a Vici Peptides content brief using Lubosi's Viral Formula:
1. BELIEF REVERSAL: What assumption does this trend allow us to challenge?
2. EMOTIONAL ENGINE: What emotion should this trigger?
3. COMMENT WAR HOOK: What's the audience split?

VICI ADAPTATION:
- Hook (first 3 seconds):
- Full 60-second script outline:
- Visual instructions (faceless format, voiceover + B-roll):
- Caption (Instagram safe language only):
- Best platform: TikTok / Instagram / X

Rules: Research framing only. No personal use. No: buy, order, results, treat, cure.
End with: "Free research guide — link in bio. For research use only."
"""
    adaptation = ai.messages.create(
        model=os.getenv("AI_MODEL", "anthropic/claude-sonnet-4-6"),
        max_tokens=700,
        messages=[{"role": "user", "content": prompt}]
    ).content[0].text.strip()

    return {
        "content_id": "curated_trend",
        "content_type": "TREND-REPORT",
        "fastlane_text": signal,
        "vici_adaptation": adaptation,
        "media_urls": [],
        "thumbnail_url": "",
        "status": "curated",
        "source": "curated_topics",
    }


def get_apify_trends() -> dict:
    """Pull trending peptide/longevity topics via Apify Google Trends Scraper."""
    try:
        from apify_client import ApifyClient
        client = ApifyClient(os.getenv("APIFY_API_KEY"))
        run_input = {
            "searchTerms": ["BPC-157", "semaglutide", "tirzepatide", "peptides longevity", "GLP-1"],
            "geo": "US",
            "timeRange": "now 7-d",
        }
        print("[TREND] Pulling Google Trends via Apify...")
        run = client.actor("apify/google-trends-scraper").call(run_input=run_input, timeout_secs=120)
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())

        if not items:
            print("[TREND] Apify returned no items — falling back to curated topic brief.")
            return _curated_topic_brief()

        top_terms = sorted(items, key=lambda x: x.get("value", 0), reverse=True)[:5]
        trends_text = "\n".join(
            f"- {t.get('term', t.get('keyword', '?'))}: interest {t.get('value', 0)}/100"
            for t in top_terms
        )

        ai = anthropic.Anthropic()
        prompt = f"""Based on these trending search topics this week:
{trends_text}

Create a Vici Peptides content brief using Lubosi's Viral Formula:
1. BELIEF REVERSAL: What assumption does this trend allow us to challenge?
2. EMOTIONAL ENGINE: What emotion should this trigger?
3. COMMENT WAR HOOK: What's the audience split?

VICI ADAPTATION:
- Hook (first 3 seconds):
- Full 60-second script outline:
- Visual instructions (faceless format, voiceover + B-roll):
- Caption (Instagram safe language only):
- Best platform: TikTok / Instagram / X

Rules: Research framing only. No personal use. No: buy, order, results, treat, cure.
End with: "Free research guide — link in bio. For research use only."
"""
        adaptation = ai.messages.create(
            model=os.getenv("AI_MODEL", "anthropic/claude-sonnet-4-6"),
            max_tokens=700,
            messages=[{"role": "user", "content": prompt}]
        ).content[0].text.strip()

        return {
            "content_id": "apify_trend",
            "content_type": "TREND-REPORT",
            "fastlane_text": f"Top trending: {', '.join(t.get('term', t.get('keyword', '?')) for t in top_terms[:3])}",
            "vici_adaptation": adaptation,
            "media_urls": [],
            "thumbnail_url": "",
            "status": "apify",
            "source": "apify_google_trends",
        }
    except Exception as e:
        print(f"[TREND] Apify failed: {e} — falling back to curated topic brief.")
        return _curated_topic_brief()


def adapt_to_vici(fastlane_content: dict) -> str:
    client = anthropic.Anthropic()
    content_type = fastlane_content["suggestion"]["content_type"]
    generated_text = fastlane_content["suggestion"]["generated_text"]
    explanation = fastlane_content["suggestion"]["ai_explanation"]

    prompt = f"""Fastlane generated this {content_type} suggestion for Vici Peptides:

CONTENT TYPE: {content_type}
GENERATED TEXT: {generated_text}
AI EXPLANATION: {explanation}

Apply Lubosi's Viral Clip Formula:
1. BELIEF REVERSAL: What assumption does this challenge?
2. EMOTIONAL ENGINE: What emotion does it trigger?
3. COMMENT WAR HOOK: What is the audience split?

VICI ADAPTATION:
- Hook (first 3 seconds):
- Full script/text content:
- Visual instructions (faceless format):
- Caption:
- Hashtags (max 7):
- Content type: [Science Revelation / Data Drop / Versus / Compound Profile / Longevity Stack]

Rules: Research framing, no personal use, no buy/order/treat/cure.
CTA: "Free research guide — link in bio. For research use only."
"""
    return client.messages.create(
        model=os.getenv("AI_MODEL", "anthropic/claude-sonnet-4-6"),
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}]
    ).content[0].text.strip()


def get_trend_brief() -> dict:
    try:
        content = pull_fastlane_suggestion()
        if "error" in content:
            return content
        adaptation = adapt_to_vici(content)
        return {
            "content_id": content.get("_id", ""),
            "content_type": content["suggestion"]["content_type"],
            "fastlane_text": content["suggestion"]["generated_text"],
            "vici_adaptation": adaptation,
            "media_urls": content.get("files", []),
            "thumbnail_url": content.get("thumbnailUrl", ""),
            "status": content.get("status", ""),
        }
    except FastlaneNotConfigured:
        result = get_apify_trends()
        # If apify also errored, result already contains the curated fallback
        return result


def get_analytics_summary() -> str:
    try:
        posts = fl.list_posts(limit=20, status="POSTED")
    except FastlaneNotConfigured:
        return "Fastlane not configured — analytics unavailable. Add FASTLANE_API_KEY to enable."
    if not posts:
        return "No posted content found in Fastlane yet."
    post_ids = [p["_id"] for p in posts[:20]]
    analytics = fl.get_post_analytics(post_ids)
    valid = [a for a in analytics if not a.get("notFound")]
    if not valid:
        return "Analytics not yet available for recent posts."
    valid.sort(key=lambda x: x.get("views", 0), reverse=True)
    lines = ["FASTLANE POST ANALYTICS\n" + "="*30 + "\n"]
    for item in valid[:5]:
        lines.append(
            f"Platform: {item.get('platform', '?').upper()}\n"
            f"Views: {item.get('views', 0):,} | Likes: {item.get('likes', 0):,} | Comments: {item.get('comments', 0):,}\n"
            f"URL: {item.get('postUrl', 'N/A')}\n"
        )
    return "\n".join(lines)
