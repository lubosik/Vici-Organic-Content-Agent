"""
Conversational agent loop.
Routes natural language to the right tool using OpenAI function calling.
Uses cheap model (haiku) for routing, sonnet for content generation.
"""

import os
import json
import asyncio
from openai import OpenAI
from conversation_store import get_history, add_message


class _ScoutComplete(Exception):
    """Raised after scout_url sends analysis — stops the agent loop cleanly."""
    def __init__(self, result: str):
        self.result = result


_stop_flags: dict[int, bool] = {}


def stop_agent(chat_id: int):
    _stop_flags[chat_id] = True


def clear_stop(chat_id: int):
    _stop_flags.pop(chat_id, None)


def _is_stopped(chat_id: int) -> bool:
    return _stop_flags.get(chat_id, False)

ROUTER_MODEL = os.getenv("ROUTER_MODEL", "openai/gpt-4o-mini")

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "scout_url",
            "description": "Analyse a YouTube video or article URL for viral clip moments using Lubosi's Viral Formula. Returns timestamps, hooks, virality scores, and Vici adaptation notes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The full URL to analyse"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cut_and_render_clip",
            "description": "Download a YouTube video, cut it at specific timestamps, add Vici hook text overlay and brand watermark, render to MP4. Only call after scout_url has identified timestamps.",
            "parameters": {
                "type": "object",
                "properties": {
                    "youtube_url": {"type": "string"},
                    "start_time": {"type": "string", "description": "Start timestamp e.g. '02:15'"},
                    "end_time": {"type": "string", "description": "End timestamp e.g. '03:45'"},
                    "hook_text": {"type": "string", "description": "Hook text to overlay on the clip (from the SCOUT analysis)"}
                },
                "required": ["youtube_url", "start_time", "end_time", "hook_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "forge_content_package",
            "description": "Generate a full content package for the next topic: voiceover script + ElevenLabs MP3 + B-roll list + CapCut guide.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_x_posts",
            "description": "Generate 5 X (Twitter) posts for the week. Dedup-protected — never repeats previous posts.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_instagram_carousel",
            "description": "Generate a 9-slide Instagram carousel with Instagram-safe language and caption.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_trend_brief",
            "description": "Pull Google Trends data for the peptide/longevity niche and generate a Vici-adapted content brief.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web for recent articles or research on a topic. Use before generating Instagram/X posts on a specific topic to get real, current source material.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query e.g. 'BPC-157 tissue repair research 2025'"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_memory",
            "description": "Check the knowledge base for prior research on a topic. ALWAYS call this before searching the web on any topic. Returns what was researched, when, and what content was produced.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The topic or compound to look up e.g. 'BPC-157' or 'GLP-1 dopamine'"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_research",
            "description": "Save research findings to the persistent knowledge base after completing a research + content cycle. Call this after search_web + content generation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Topic name e.g. 'BPC-157 tissue repair'"},
                    "compound": {"type": "string", "description": "Primary compound if applicable e.g. 'BPC-157'"},
                    "key_facts": {"type": "string", "description": "2-4 key facts learned from the research"},
                    "sources": {"type": "array", "items": {"type": "string"}, "description": "List of source URLs used"},
                    "content_type": {"type": "string", "description": "What content was produced e.g. 'X posts', 'Instagram carousel', 'voiceover script'"}
                },
                "required": ["topic", "compound", "key_facts", "sources"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_memory_digest",
            "description": "Show a digest of everything researched and produced in the past N days.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "How many days to look back. Default 7.", "default": 7}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "seo_keyword_research",
            "description": "Get SEO data for peptide/longevity topics: search volumes, related keywords, Google Trends. Use to find high-opportunity content topics and validate what people are actually searching for. Call with mode='opportunities' for a full report.",
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "description": "What to fetch: 'volumes' (search volumes), 'related' (related keywords for a seed), 'trends' (Google Trends), 'opportunities' (full content opportunity report)",
                        "enum": ["volumes", "related", "trends", "opportunities"]
                    },
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Keywords to research e.g. ['BPC-157', 'semaglutide']"
                    },
                    "seed_keyword": {
                        "type": "string",
                        "description": "Single seed keyword for related mode"
                    }
                },
                "required": ["mode"]
            }
        }
    },
]


def _sanitize_history(history: list) -> list:
    """
    Remove orphaned tool_use/tool_result pairs.
    A corrupted history (mismatched IDs or unpaired blocks) causes API 400s.
    This happens when Bedrock-routed models mangle tool call IDs (strips underscores),
    leaving tool_result blocks whose tool_call_id never matches any tool_use id.
    """
    sanitized = []
    i = 0
    while i < len(history):
        msg = history[i]
        role = msg.get("role", "")

        if role == "assistant" and msg.get("tool_calls"):
            # Collect tool_call IDs from this assistant turn
            tc_ids = set()
            for tc in msg["tool_calls"]:
                if isinstance(tc, dict):
                    tc_ids.add(tc.get("id", ""))
                else:
                    try:
                        tc_ids.add(tc.id)
                    except Exception:
                        pass

            # Look ahead for matching tool results
            j = i + 1
            following_results = []
            while j < len(history) and history[j].get("role") == "tool":
                following_results.append(history[j])
                j += 1

            result_ids = {r.get("tool_call_id", "") for r in following_results}

            if result_ids and result_ids == tc_ids:
                # Perfect match — keep the pair
                sanitized.append(msg)
                sanitized.extend(following_results)
                i = j
            elif result_ids:
                # Partial or mismatched IDs — drop the whole pair to avoid 400
                i = j
            else:
                # No results at all — drop the assistant tool_calls message
                i += 1
        elif role == "tool":
            # Orphaned tool result (no preceding assistant tool_calls) — drop it
            i += 1
        else:
            sanitized.append(msg)
            i += 1

    return sanitized


def _get_openai_client() -> OpenAI:
    return OpenAI(
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
    )


async def _dispatch_tool(tool_name: str, args: dict, send_progress, send_text=None) -> str:
    """Execute a tool and return the result as a string."""
    try:
        if tool_name == "scout_url":
            await send_progress(f"Analysing {args['url']}...")
            from scout import analyse_url
            result = await asyncio.to_thread(analyse_url, args["url"])
            # Send full analysis immediately — Telegram 4096 char limit, split if needed
            if send_text:
                chunks = [result[i:i+4000] for i in range(0, len(result), 4000)]
                for chunk in chunks:
                    await send_text(chunk)
            # Signal the agent loop to stop — raise a sentinel so run_agent can catch it
            raise _ScoutComplete(result)

        elif tool_name == "cut_and_render_clip":
            await send_progress(f"Downloading and cutting clip {args['start_time']} -> {args['end_time']}... (2-4 min)")
            from clipper import produce_clip
            path = await asyncio.to_thread(
                produce_clip,
                args["youtube_url"],
                args["start_time"],
                args["end_time"],
                args["hook_text"]
            )
            if path:
                return json.dumps({"status": "success", "path": path})
            return json.dumps({"status": "failed", "error": "Clip production failed"})

        elif tool_name == "forge_content_package":
            await send_progress("FORGE running — generating script, voiceover, and B-roll guide...")
            from forge import produce_content_package
            assets = await asyncio.to_thread(produce_content_package)
            return json.dumps({
                "topic": assets["topic"]["title"],
                "script": assets["script"],
                "broll": assets["broll"],
                "capcut_guide": assets["capcut_guide"],
                "voiceover_ok": assets["voiceover_ok"],
                "voiceover_path": assets.get("voiceover_path"),
                "dir": assets["dir"],
            })

        elif tool_name == "generate_x_posts":
            await send_progress("Generating X posts...")
            from forge import generate_x_posts
            return await asyncio.to_thread(generate_x_posts, 5)

        elif tool_name == "generate_instagram_carousel":
            await send_progress("Generating Instagram carousel...")
            from forge import generate_instagram_carousel
            from brand import TOPIC_QUEUE
            from dedup import next_topic
            topic = next_topic(TOPIC_QUEUE)
            result = await asyncio.to_thread(generate_instagram_carousel, topic)
            return json.dumps(result)

        elif tool_name == "get_trend_brief":
            await send_progress("Pulling trend data...")
            from trend import get_trend_brief
            brief = await asyncio.to_thread(get_trend_brief)
            return json.dumps(brief)

        elif tool_name == "search_web":
            await send_progress(f"Searching: {args['query']}...")
            from web_search import search_web
            return await asyncio.to_thread(search_web, args["query"])

        elif tool_name == "check_memory":
            from memory import check_memory
            return await asyncio.to_thread(check_memory, args.get("query", ""))

        elif tool_name == "save_research":
            from memory import save_research
            return await asyncio.to_thread(
                save_research,
                args.get("topic", ""),
                args.get("compound", ""),
                args.get("key_facts", ""),
                args.get("sources", []),
                args.get("content_type"),
            )

        elif tool_name == "get_memory_digest":
            from memory import get_memory_digest
            days = args.get("days", 7)
            result = await asyncio.to_thread(get_memory_digest, days)
            if send_text:
                await send_text(result)
            return result

        elif tool_name == "seo_keyword_research":
            mode = args.get("mode", "opportunities")
            await send_progress(f"Pulling SEO data ({mode})...")
            from seo_research import (
                get_keyword_search_volumes, get_related_keywords,
                get_google_trends, get_content_opportunities
            )
            keywords = args.get("keywords", [])
            seed = args.get("seed_keyword", "")
            if mode == "volumes" and keywords:
                result = await asyncio.to_thread(get_keyword_search_volumes, keywords)
            elif mode == "related" and seed:
                result = await asyncio.to_thread(get_related_keywords, seed)
            elif mode == "trends" and keywords:
                result = await asyncio.to_thread(get_google_trends, keywords)
            else:
                result = await asyncio.to_thread(get_content_opportunities)
                if send_text:
                    await send_text(result)
            return result

        else:
            return f"Unknown tool: {tool_name}"

    except Exception as e:
        return f"Tool error ({tool_name}): {e}"


async def run_agent(chat_id: int, user_message: str, send_progress, send_text, send_audio, send_video) -> None:
    """
    Main agent loop. Runs until model returns a final text response (no more tool calls).
    send_progress: async fn(str) — sends a short status update
    send_text: async fn(str) — sends text to user
    send_audio: async fn(path, caption) — sends audio file
    send_video: async fn(path, caption) — sends video file
    """
    client = _get_openai_client()
    add_message(chat_id, "user", user_message)
    history = get_history(chat_id)

    MAX_ITERATIONS = 8
    iteration = 0

    while iteration < MAX_ITERATIONS:
        iteration += 1

        if _is_stopped(chat_id):
            clear_stop(chat_id)
            await send_text("Stopped.")
            return

        clean_history = _sanitize_history(history)
        try:
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=ROUTER_MODEL,
                messages=clean_history,
                tools=TOOLS,
                tool_choice="auto",
            )
        except Exception as e:
            await send_text(f"Agent error calling AI: {e}\n\nPlease try again.")
            return

        msg = response.choices[0].message

        # Add assistant message to history
        if msg.tool_calls:
            add_message(chat_id, "assistant", msg.tool_calls)
        else:
            add_message(chat_id, "assistant", msg.content or "")

        # No tool calls — final response
        if not msg.tool_calls:
            if msg.content:
                await send_text(msg.content)
            break

        # Execute tool calls
        for tc in msg.tool_calls:
            fn_name = tc.function.name
            try:
                fn_args = json.loads(tc.function.arguments)
            except Exception:
                fn_args = {}

            try:
                result = await _dispatch_tool(fn_name, fn_args, send_progress, send_text)
            except _ScoutComplete as sc:
                # Analysis already sent to user. Add to history and stop.
                add_message(chat_id, "tool", json.dumps({
                    "tool_call_id": tc.id,
                    "role": "tool",
                    "content": sc.result[:1000]
                }))
                # Ask which clips they want without calling any tools
                add_message(chat_id, "assistant", "Analysis complete. Which clips do you want me to cut? Just say \"cut clip 1\", \"cut clip 3\", etc.")
                await send_text("Which clips do you want cut? Say \"cut clip 1\" or \"cut clips 1, 3, 5\" etc.")
                return

            # Handle special outputs (audio, video)
            if fn_name == "forge_content_package":
                try:
                    data = json.loads(result)
                    topic_title = data.get("topic", "Content")

                    # Send script as text
                    script = data.get("script", "")
                    if script:
                        await send_text(f"SCRIPT — {topic_title}\n\n{script}")

                    # Send voiceover
                    vo_path = data.get("voiceover_path")
                    if data.get("voiceover_ok") and vo_path:
                        await send_audio(vo_path, f"Voiceover — {topic_title}")
                    else:
                        await send_text("Voiceover generation failed — script is ready for ElevenLabs.")

                    # Send B-roll list
                    broll = data.get("broll", "")
                    if broll:
                        await send_text(f"B-ROLL LIST:\n\n{broll}")

                    # Send CapCut guide
                    guide = data.get("capcut_guide", "")
                    if guide:
                        await send_text(f"CAPCUT GUIDE:\n\n{guide}")

                except Exception:
                    await send_text(result)

            elif fn_name == "cut_and_render_clip":
                try:
                    data = json.loads(result)
                    if data.get("status") == "success":
                        clip_path = data["path"]
                        await send_video(clip_path, "Vici clip — ready to post")
                        result = "Clip rendered and sent successfully."
                    else:
                        await send_text(f"Clip failed: {data.get('error', 'Unknown error')}")
                except Exception:
                    await send_text(result)

            elif fn_name == "generate_instagram_carousel":
                try:
                    data = json.loads(result)
                    if "slides" in data:
                        slides_text = "\n\n".join(
                            f"Slide {s['n']}:\n{s.get('heading', '')}\n{s.get('body', '')}"
                            for s in data["slides"]
                        )
                        caption = data.get("caption", "")
                        hashtags = " ".join(data.get("hashtags", []))
                        await send_text(f"INSTAGRAM CAROUSEL\n\n{slides_text}\n\nCaption:\n{caption}\n\n{hashtags}")
                        result = "Instagram carousel sent."
                    else:
                        await send_text(result)
                except Exception:
                    await send_text(result)

            elif fn_name == "get_trend_brief":
                try:
                    data = json.loads(result)
                    if "error" not in data:
                        source = data.get("source", "fastlane")
                        label = "APIFY TRENDS" if source == "apify_google_trends" else "FASTLANE TREND"
                        msg_text = (
                            f"{label}\n\n"
                            f"Signal: {data.get('fastlane_text', '')}\n\n"
                            f"{'='*30}\n\n"
                            f"Vici Adaptation:\n{data.get('vici_adaptation', '')}"
                        )
                        await send_text(msg_text)
                        result = "Trend brief sent."
                except Exception:
                    pass

            # Add tool result to history
            add_message(chat_id, "tool", json.dumps({
                "tool_call_id": tc.id,
                "role": "tool",
                "content": result[:2000],  # Truncate huge results
            }))

    if iteration >= MAX_ITERATIONS:
        await send_text("Reached max tool iterations. Type your request again if needed.")
