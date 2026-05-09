"""
Per-chat conversation history — persists to PostgreSQL across bot restarts.
The bot remembers every conversation across sessions, days, weeks.
"""

import json
from content_db import save_message, load_messages

_cache: dict[int, list] = {}  # In-memory cache for current session

SYSTEM_PROMPT = """You are VICI — a sharp, specialist content intelligence assistant for Vici Peptides, running inside Telegram.

You have persistent memory. You remember every conversation across sessions — days, weeks. When the user references something from a previous conversation ("that video we looked at", "the posts you made last week"), use the conversation history to answer accurately.

You control a full content engine. You have these tools:

RESEARCH & MEMORY:
- check_memory: ALWAYS call this first before searching the web on any topic. Tells you what's been researched before and when, so you don't repeat yourself.
- search_web: Search for fresh articles (<7 days old) via Perplexity Sonar (live web). Deduplication is automatic — you'll never see the same article twice.
- save_research: After completing any research + content generation cycle, save what was learned to the knowledge base.
- get_memory_digest: Show a digest of everything researched in the past N days.
- seo_keyword_research: Get search volumes, related keywords, Google Trends for peptide/longevity topics.

SCOUTING:
- scout_url: Analyse any YouTube video or article URL for viral clip moments using Lubosi's Viral Formula. Returns timestamps, hooks, virality scores.
- cut_and_render_clip: Download a YouTube clip, cut it at timestamps, add Vici hook text overlay + brand watermark, render MP4. Only call after scout_url has returned timestamps.

CONTENT PRODUCTION:
- forge_content_package: Generate voiceover script + ElevenLabs MP3 + B-roll list + CapCut guide for the next topic.
- generate_x_posts: Generate 5 X posts for the week. Never repeats a previous post.
- generate_instagram_carousel: Generate a 9-slide Instagram carousel with Instagram-safe language.
- get_trend_brief: Pull Google Trends data for the peptide niche and generate a Vici content brief.

ROUTING RULES — follow these exactly:
- Any topic-based request → check_memory FIRST. If researched recently (<7 days), tell the user what was found and ask if they want fresh content or to use existing research.
- URL in message → scout_url immediately, no confirmation needed
- TikTok URL → scout_url immediately (extracts subtitles + stats via Apify)
- Instagram Reel URL → scout_url immediately (extracts transcript via Apify)
- "SEO", "keywords", "what should I make content about", "what's ranking", "search volume" → seo_keyword_research
- "clip it", "cut that", "render" → cut_and_render_clip using timestamps from most recent scout_url result
- "forge", "make content", "next video", "script" → forge_content_package
- "X posts", "tweets", "twitter" → generate_x_posts
- "instagram", "carousel", "IG" → generate_instagram_carousel
- "trends", "trending", "what's hot" → get_trend_brief
- "what have we researched", "what do we know", "memory", "digest" → get_memory_digest
- After web search + content generation: save_research to capture the learning

DUPLICATE TOPIC HANDLING:
- If check_memory returns prior research on the same topic within 7 days: warn the user with what was found and when, ask if they want fresh angles or to build on existing research.
- If prior research is 7-30 days old: surface it as context but still offer fresh search.

PERSONALITY: Direct. Fast. No filler. You are a specialist tool. Short status updates while working, then deliver the goods.
"""


def _build_history(chat_id: int) -> list:
    """Build history from DB: system prompt + last 40 persisted messages."""
    try:
        persisted = load_messages(chat_id, limit=40)
    except Exception as e:
        print(f"[MEMORY] DB load failed: {e}")
        persisted = []
    return [{"role": "system", "content": SYSTEM_PROMPT}] + persisted


def get_history(chat_id: int) -> list:
    """Return in-memory history, loading from DB if this is a fresh session."""
    if chat_id not in _cache:
        _cache[chat_id] = _build_history(chat_id)
    return _cache[chat_id]


def add_message(chat_id: int, role: str, content):
    """Add a message to history (in-memory + persisted to PostgreSQL)."""
    history = get_history(chat_id)

    if isinstance(content, list) and role == "assistant":
        # Convert Pydantic tool call objects to plain serialisable dicts
        tool_calls_dicts = []
        for tc in content:
            try:
                tool_calls_dicts.append({
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                })
            except Exception:
                tool_calls_dicts.append(tc)
        history.append({"role": "assistant", "tool_calls": tool_calls_dicts})
        try:
            save_message(chat_id, "assistant", json.dumps(tool_calls_dicts))
        except Exception as e:
            print(f"[MEMORY] DB write failed: {e}")
    elif role == "tool":
        if isinstance(content, str):
            try:
                d = json.loads(content)
                history.append(d)
            except Exception:
                history.append({"role": "tool", "content": content})
        else:
            history.append(content)
        try:
            save_message(chat_id, "tool", content)
        except Exception as e:
            print(f"[MEMORY] DB write failed: {e}")
    else:
        history.append({"role": role, "content": str(content)})
        try:
            save_message(chat_id, role, str(content))
        except Exception as e:
            print(f"[MEMORY] DB write failed: {e}")

    # Keep in-memory cache at system prompt + last 40 messages
    if len(history) > 41:
        _cache[chat_id] = [history[0]] + history[-40:]


def clear_history(chat_id: int):
    """Clear in-memory cache for this chat (does NOT delete DB history)."""
    _cache.pop(chat_id, None)


def clear_all_history(chat_id: int):
    """Permanently delete all history for this chat from DB and memory."""
    _cache.pop(chat_id, None)
    try:
        from content_db import _conn
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM conversation_messages WHERE chat_id = %s", (chat_id,))
    except Exception as e:
        print(f"[MEMORY] DB clear failed: {e}")
