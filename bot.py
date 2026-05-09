"""
VICI CONTENT ENGINE — Telegram Bot

Commands (shortcuts — you can also just talk to me naturally):
  /scout <url>     — Analyse URL for viral clip moments
  /forge           — Produce next content package (script + voiceover + guides)
  /forge_x         — Generate X posts for the week
  /forge_ig        — Generate Instagram carousel
  /trend           — Pull trend data
  /podcasts        — Find new peptide podcasts from the past 7 days
  /clip <url> <start> <end> <hook> — Cut and render a clip
  /analytics       — Fastlane post analytics
  /setup           — Configure Fastlane workspace
  /clear           — Clear in-memory conversation history (history persists in DB)
  /forget          — Permanently delete all conversation history (fresh start)
  /stop            — Cancel any running pipeline, clear in-memory history
  /help            — Show this message

Or just talk to me naturally: "analyse this video", "make me 5 posts", "what's trending"
"""

import os
import logging
import asyncio
from pathlib import Path
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes
)

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AUTHORIZED_CHAT = int(os.getenv("TELEGRAM_CHAT_ID", "0"))
MAX_MSG = 4096


def authorized(update: Update) -> bool:
    return update.effective_chat.id == AUTHORIZED_CHAT


async def send_long(update: Update, text: str):
    chunks = [text[i:i+MAX_MSG] for i in range(0, len(text), MAX_MSG)]
    for chunk in chunks:
        try:
            await update.message.reply_text(chunk, parse_mode="Markdown", disable_web_page_preview=True)
        except Exception:
            await update.message.reply_text(chunk, disable_web_page_preview=True)


# ── Shared send helpers for agent ─────────────────────────────────────────────

def _make_senders(update: Update):
    async def send_progress(text: str):
        try:
            await update.message.reply_text(text)
        except Exception:
            pass

    async def send_text(text: str):
        await send_long(update, text)

    async def send_audio(path: str, caption: str):
        try:
            with open(path, "rb") as f:
                await update.message.reply_audio(audio=f, caption=caption)
        except Exception as e:
            await update.message.reply_text(f"Could not send audio: {e}")

    async def send_video(path: str, caption: str):
        size = Path(path).stat().st_size if Path(path).exists() else 0
        if size > 50 * 1024 * 1024:  # > 50MB — Telegram limit
            await update.message.reply_text(f"Clip too large for Telegram ({size // 1024 // 1024}MB). Saved at: {path}")
            return
        try:
            with open(path, "rb") as f:
                await update.message.reply_video(video=f, caption=caption, supports_streaming=True)
        except Exception as e:
            await update.message.reply_text(f"Could not send video: {e}\nSaved at: {path}")

    return send_progress, send_text, send_audio, send_video


# ── Command Handlers ──────────────────────────────────────────────────────────

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    await update.message.reply_text(__doc__)


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    from conversation_store import clear_history
    clear_history(update.effective_chat.id)
    await update.message.reply_text("Conversation history cleared.")


async def cmd_forget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Permanently delete all conversation history for this chat."""
    if not authorized(update):
        return
    from conversation_store import clear_all_history
    clear_all_history(update.effective_chat.id)
    await update.message.reply_text(
        "All conversation history deleted. Fresh start — I have no memory of previous chats.\n\n"
        "Note: The knowledge base (researched topics, article cache) is separate and unchanged."
    )


async def _safe_run_agent(update: Update, message: str, sp, st, sa, sv):
    """Run agent with error handling — always responds, never silent."""
    from agent import run_agent
    try:
        await run_agent(update.effective_chat.id, message, sp, st, sa, sv)
    except Exception as e:
        logger.exception("run_agent failed")
        try:
            await update.message.reply_text(f"Something went wrong: {e}\n\nPlease try again.")
        except Exception:
            pass


async def cmd_scout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /scout <url>")
        return
    sp, st, sa, sv = _make_senders(update)
    await _safe_run_agent(update, f"Analyse this URL: {args[0]}", sp, st, sa, sv)


async def cmd_forge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    sp, st, sa, sv = _make_senders(update)
    await _safe_run_agent(update, "forge content package", sp, st, sa, sv)


async def cmd_forge_x(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    sp, st, sa, sv = _make_senders(update)
    await _safe_run_agent(update, "generate X posts for the week", sp, st, sa, sv)


async def cmd_forge_ig(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    sp, st, sa, sv = _make_senders(update)
    await _safe_run_agent(update, "generate instagram carousel", sp, st, sa, sv)


async def cmd_trend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    sp, st, sa, sv = _make_senders(update)
    await _safe_run_agent(update, "pull trend brief", sp, st, sa, sv)


async def cmd_podcasts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Find new peptide podcasts from the past 7 days."""
    if not authorized(update):
        return
    sp, st, sa, sv = _make_senders(update)
    await _safe_run_agent(update, "find new peptide podcasts this week", sp, st, sa, sv)


async def cmd_clip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shortcut: /clip <youtube_url> <start_MM:SS> <end_MM:SS> <hook_text>"""
    if not authorized(update):
        return
    args = context.args
    if len(args) < 4:
        await update.message.reply_text("Usage: /clip <youtube_url> <start_MM:SS> <end_MM:SS> <hook text>")
        return
    hook = " ".join(args[3:])
    sp, st, sa, sv = _make_senders(update)
    await _safe_run_agent(
        update,
        f"cut and render clip from {args[0]} from {args[1]} to {args[2]} with hook text: {hook}",
        sp, st, sa, sv
    )


async def cmd_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    from trend import get_analytics_summary
    try:
        summary = await asyncio.to_thread(get_analytics_summary)
        await send_long(update, summary)
    except Exception as e:
        await update.message.reply_text(f"Analytics error: {e}")


async def cmd_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    if not os.getenv("FASTLANE_API_KEY"):
        await update.message.reply_text(
            "Fastlane API key not configured.\n\n"
            "You're on the free trial — add FASTLANE_API_KEY to .env once you upgrade.\n\n"
            "TREND mode is using Apify Google Trends as fallback."
        )
        return
    await update.message.reply_text("Setting up Fastlane workspace...")
    try:
        from fastlane import setup_vici_workspace
        await asyncio.to_thread(setup_vici_workspace)
        await update.message.reply_text("Fastlane workspace configured.")
    except Exception as e:
        await update.message.reply_text(f"Setup failed: {e}")


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel any running pipeline and clear in-memory history."""
    if not authorized(update):
        return
    from agent import stop_agent
    from conversation_store import clear_history
    chat_id = update.effective_chat.id
    stop_agent(chat_id)
    clear_history(chat_id)
    await update.message.reply_text(
        "Stopped. Any running clip pipeline has been cancelled.\n\n"
        "In-memory history cleared — you can start fresh."
    )


# ── Natural language handler (all non-command messages) ───────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    text = update.message.text.strip()
    if not text:
        return
    sp, st, sa, sv = _make_senders(update)
    await _safe_run_agent(update, text, sp, st, sa, sv)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    os.makedirs("data", exist_ok=True)
    os.makedirs("output", exist_ok=True)
    os.makedirs("output/clips", exist_ok=True)

    try:
        from content_db import init_db
        init_db()
        print("[DB] PostgreSQL connected and schema ready.")
    except Exception as e:
        print(f"[DB] WARNING: Could not connect to PostgreSQL: {e}")
        print("[DB] Bot will run but data will not be persisted.")

    fastlane_key = os.getenv("FASTLANE_API_KEY")
    if fastlane_key and not os.path.exists("data/fastlane_angles.json"):
        print("First run — setting up Fastlane workspace...")
        from fastlane import setup_vici_workspace
        setup_vici_workspace()

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("scout", cmd_scout))
    app.add_handler(CommandHandler("forge", cmd_forge))
    app.add_handler(CommandHandler("forge_x", cmd_forge_x))
    app.add_handler(CommandHandler("forge_ig", cmd_forge_ig))
    app.add_handler(CommandHandler("trend", cmd_trend))
    app.add_handler(CommandHandler("podcasts", cmd_podcasts))
    app.add_handler(CommandHandler("clip", cmd_clip))
    app.add_handler(CommandHandler("analytics", cmd_analytics))
    app.add_handler(CommandHandler("setup", cmd_setup))
    app.add_handler(CommandHandler("forget", cmd_forget))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("VICI CONTENT ENGINE v2 — Conversational agent running.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
