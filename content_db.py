"""SQLite store for SCOUT analyses, web search cache, knowledge base, and article dedup."""

import sqlite3
import json
import os
import hashlib
import re
from datetime import datetime, timedelta

DB_PATH = "data/vici_content.db"


def _conn():
    os.makedirs("data", exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    with _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS scout_analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                title TEXT,
                source_type TEXT,
                analysis TEXT,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS search_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT,
                results TEXT,
                cached_at TEXT
            );
            CREATE TABLE IF NOT EXISTS knowledge_base (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                compound TEXT,
                researched_at TEXT NOT NULL,
                articles_json TEXT,
                key_facts TEXT,
                content_produced TEXT,
                summary TEXT
            );
            CREATE TABLE IF NOT EXISTS article_seen (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url_hash TEXT UNIQUE NOT NULL,
                content_hash TEXT,
                title TEXT,
                url TEXT,
                published_date TEXT,
                first_seen TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS conversation_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                saved_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_knowledge_topic ON knowledge_base(topic);
            CREATE INDEX IF NOT EXISTS idx_article_url_hash ON article_seen(url_hash);
            CREATE INDEX IF NOT EXISTS idx_conv_chat_id ON conversation_messages(chat_id, saved_at);
        """)


def save_scout_analysis(url: str, title: str, source_type: str, analysis: str):
    init_db()
    with _conn() as conn:
        conn.execute(
            "INSERT INTO scout_analyses (url, title, source_type, analysis, created_at) VALUES (?,?,?,?,?)",
            (url, title, source_type, analysis, datetime.now().isoformat())
        )


def get_recent_analyses(limit: int = 5) -> list:
    init_db()
    with _conn() as conn:
        rows = conn.execute(
            "SELECT url, title, source_type, analysis, created_at FROM scout_analyses ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
    return [{"url": r[0], "title": r[1], "source_type": r[2], "analysis": r[3], "created_at": r[4]} for r in rows]


def cache_search(query: str, results: str):
    init_db()
    with _conn() as conn:
        conn.execute(
            "INSERT INTO search_cache (query, results, cached_at) VALUES (?,?,?)",
            (query, results, datetime.now().isoformat())
        )


def get_cached_search(query: str, max_age_hours: int = 6) -> str | None:
    init_db()
    with _conn() as conn:
        row = conn.execute(
            """SELECT results FROM search_cache
               WHERE query = ?
               AND cached_at > datetime('now', ? || ' hours')
               ORDER BY cached_at DESC LIMIT 1""",
            (query, f"-{max_age_hours}")
        ).fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------------------
# Knowledge base helpers
# ---------------------------------------------------------------------------

def _url_hash(url: str) -> str:
    """Normalise URL: strip tracking params, lowercase, then MD5."""
    url = url.lower().split("?")[0].split("#")[0].rstrip("/")
    return hashlib.md5(url.encode()).hexdigest()[:20]


def _content_hash(text: str) -> str:
    cleaned = " ".join(text.lower().split())[:1000]
    return hashlib.md5(cleaned.encode()).hexdigest()[:20]


def is_article_seen(url: str, content: str = None) -> bool:
    """Return True if this URL or content was already processed."""
    init_db()
    uh = _url_hash(url)
    with _conn() as conn:
        row = conn.execute("SELECT 1 FROM article_seen WHERE url_hash = ?", (uh,)).fetchone()
        if row:
            return True
        if content:
            ch = _content_hash(content)
            row = conn.execute("SELECT 1 FROM article_seen WHERE content_hash = ?", (ch,)).fetchone()
            return row is not None
    return False


def mark_article_seen(url: str, title: str = "", content: str = None, published_date: str = None):
    """Record that we've processed this article."""
    init_db()
    uh = _url_hash(url)
    ch = _content_hash(content) if content else None
    now = datetime.now().isoformat()
    with _conn() as conn:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO article_seen (url_hash, content_hash, title, url, published_date, first_seen) VALUES (?,?,?,?,?,?)",
                (uh, ch, title, url, published_date, now)
            )
        except Exception:
            pass


def save_knowledge(topic: str, compound: str, key_facts: str, articles_json: str,
                   content_produced: str = None, summary: str = None):
    """Save research to the knowledge base."""
    init_db()
    now = datetime.now().isoformat()
    with _conn() as conn:
        conn.execute(
            """INSERT INTO knowledge_base
               (topic, compound, researched_at, articles_json, key_facts, content_produced, summary)
               VALUES (?,?,?,?,?,?,?)""",
            (topic, compound, now, articles_json, key_facts, content_produced, summary)
        )


def get_knowledge(topic: str, max_age_days: int = 30) -> list:
    """
    Retrieve past research on a topic (fuzzy match on topic name).
    Returns entries within max_age_days.
    """
    init_db()
    cutoff = (datetime.now() - timedelta(days=max_age_days)).isoformat()
    with _conn() as conn:
        rows = conn.execute(
            """SELECT topic, compound, researched_at, key_facts, content_produced, summary
               FROM knowledge_base
               WHERE (topic LIKE ? OR topic LIKE ?)
               AND researched_at > ?
               ORDER BY researched_at DESC LIMIT 5""",
            (f"%{topic}%", f"%{topic.split()[0]}%", cutoff)
        ).fetchall()
    return [
        {
            "topic": r[0], "compound": r[1], "researched_at": r[2],
            "key_facts": r[3], "content_produced": r[4], "summary": r[5]
        }
        for r in rows
    ]


def save_message(chat_id: int, role: str, content):
    """Persist a single message to the conversation store."""
    init_db()
    if not isinstance(content, str):
        import json as _json
        content = _json.dumps(content)
    now = datetime.now().isoformat()
    with _conn() as conn:
        conn.execute(
            "INSERT INTO conversation_messages (chat_id, role, content, saved_at) VALUES (?,?,?,?)",
            (chat_id, role, content, now)
        )


def load_messages(chat_id: int, limit: int = 40) -> list:
    """Load the last N messages for a chat, oldest first (excluding system prompt)."""
    import json as _json
    init_db()
    with _conn() as conn:
        rows = conn.execute(
            """SELECT role, content FROM conversation_messages
               WHERE chat_id = ?
               ORDER BY saved_at DESC LIMIT ?""",
            (chat_id, limit)
        ).fetchall()
    rows = list(reversed(rows))
    messages = []
    for role, content in rows:
        if content.startswith('[') or content.startswith('{'):
            try:
                parsed = _json.loads(content)
                if role == "assistant" and isinstance(parsed, list):
                    messages.append({"role": "assistant", "tool_calls": parsed})
                    continue
                elif role == "tool" and isinstance(parsed, dict):
                    messages.append(parsed)
                    continue
            except Exception:
                pass
        messages.append({"role": role, "content": content})
    return messages


def get_all_recent_topics(days: int = 30) -> list:
    """List all topics researched in the past N days, newest first."""
    init_db()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    with _conn() as conn:
        rows = conn.execute(
            "SELECT topic, compound, researched_at, summary FROM knowledge_base WHERE researched_at > ? ORDER BY researched_at DESC",
            (cutoff,)
        ).fetchall()
    return [{"topic": r[0], "compound": r[1], "researched_at": r[2], "summary": r[3]} for r in rows]
