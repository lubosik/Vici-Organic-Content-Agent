"""
PostgreSQL database — single source of truth for all VICI data.
Every action the bot takes is stored here permanently.
DATABASE_URL must be set in .env (only reachable within Railway).
"""

import os
import json
import hashlib
import re
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta
from contextlib import contextmanager

DATABASE_URL = os.getenv("DATABASE_URL")


@contextmanager
def _conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL not set. Add it to .env.")
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create all tables. Safe to call multiple times (idempotent)."""
    sql = """
    -- Conversation history (persistent across restarts)
    CREATE TABLE IF NOT EXISTS conversation_messages (
        id SERIAL PRIMARY KEY,
        chat_id BIGINT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        saved_at TIMESTAMPTZ DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_conv_chat ON conversation_messages(chat_id, saved_at);

    -- Full SCOUT analyses (URL + transcript + full analysis text)
    CREATE TABLE IF NOT EXISTS scout_analyses (
        id SERIAL PRIMARY KEY,
        url TEXT NOT NULL,
        title TEXT,
        source_type TEXT,
        channel TEXT,
        duration_s INTEGER,
        view_count BIGINT,
        transcript TEXT,
        analysis TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_scout_url ON scout_analyses(url);
    CREATE INDEX IF NOT EXISTS idx_scout_created ON scout_analyses(created_at);

    -- Individual viral clips identified by SCOUT (one row per clip)
    CREATE TABLE IF NOT EXISTS identified_clips (
        id SERIAL PRIMARY KEY,
        scout_analysis_id INTEGER REFERENCES scout_analyses(id),
        source_url TEXT NOT NULL,
        clip_number INTEGER,
        virality_score INTEGER,
        start_time TEXT,
        end_time TEXT,
        exact_quote TEXT,
        hook_text TEXT,
        clip_type TEXT,
        belief_reversal TEXT,
        emotional_engine TEXT,
        vici_brand_fit TEXT,
        bonus_signals TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_clips_url ON identified_clips(source_url);

    -- Rendered/cut MP4 clips
    CREATE TABLE IF NOT EXISTS rendered_clips (
        id SERIAL PRIMARY KEY,
        identified_clip_id INTEGER REFERENCES identified_clips(id),
        source_url TEXT NOT NULL,
        start_time TEXT,
        end_time TEXT,
        hook_text TEXT,
        file_path TEXT,
        rendered_at TIMESTAMPTZ DEFAULT NOW()
    );

    -- Knowledge base (persistent research memory)
    CREATE TABLE IF NOT EXISTS knowledge_base (
        id SERIAL PRIMARY KEY,
        topic TEXT NOT NULL,
        compound TEXT,
        key_facts TEXT,
        articles_json JSONB DEFAULT '[]',
        content_produced TEXT,
        summary TEXT,
        researched_at TIMESTAMPTZ DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_kb_topic ON knowledge_base(topic);
    CREATE INDEX IF NOT EXISTS idx_kb_date ON knowledge_base(researched_at);

    -- Articles seen (deduplication)
    CREATE TABLE IF NOT EXISTS article_seen (
        id SERIAL PRIMARY KEY,
        url_hash TEXT UNIQUE NOT NULL,
        content_hash TEXT,
        title TEXT,
        url TEXT,
        published_date TEXT,
        first_seen TIMESTAMPTZ DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_article_hash ON article_seen(url_hash);

    -- Web search result cache (6h TTL enforced at query time)
    CREATE TABLE IF NOT EXISTS search_cache (
        id SERIAL PRIMARY KEY,
        query TEXT NOT NULL,
        results TEXT NOT NULL,
        cached_at TIMESTAMPTZ DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_search_query ON search_cache(query, cached_at);

    -- All produced content (every script, post, carousel, voiceover, etc.)
    CREATE TABLE IF NOT EXISTS produced_content (
        id SERIAL PRIMARY KEY,
        content_type TEXT NOT NULL,
        topic_id TEXT,
        topic_title TEXT,
        content TEXT NOT NULL,
        file_path TEXT,
        fingerprint TEXT,
        metadata JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_pc_type ON produced_content(content_type, created_at);
    CREATE INDEX IF NOT EXISTS idx_pc_fp ON produced_content(fingerprint);
    CREATE INDEX IF NOT EXISTS idx_pc_topic ON produced_content(topic_id);

    -- Content fingerprints for deduplication (replaces content_log.json)
    CREATE TABLE IF NOT EXISTS content_fingerprints (
        id SERIAL PRIMARY KEY,
        fingerprint TEXT NOT NULL,
        category TEXT NOT NULL,
        preview TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        metadata JSONB DEFAULT '{}'
    );
    CREATE UNIQUE INDEX IF NOT EXISTS idx_fp_unique ON content_fingerprints(fingerprint, category);
    CREATE INDEX IF NOT EXISTS idx_fp_cat ON content_fingerprints(category);

    -- Topics done (replaces topics_done in content_log.json)
    CREATE TABLE IF NOT EXISTS topics_done (
        topic_id TEXT PRIMARY KEY,
        done_at TIMESTAMPTZ DEFAULT NOW()
    );
    """
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
    print("[DB] Schema initialised.")


# ── URL / content hashing ─────────────────────────────────────────────────────

def _url_hash(url: str) -> str:
    url = url.lower().split("?")[0].split("#")[0].rstrip("/")
    return hashlib.md5(url.encode()).hexdigest()[:20]

def _content_hash(text: str) -> str:
    cleaned = " ".join(text.lower().split())[:1000]
    return hashlib.md5(cleaned.encode()).hexdigest()[:20]

def _fp(text: str) -> str:
    cleaned = " ".join(text.lower().split())
    return hashlib.md5(cleaned.encode()).hexdigest()[:16]


# ── Conversation messages ─────────────────────────────────────────────────────

def save_message(chat_id: int, role: str, content):
    if not isinstance(content, str):
        content = json.dumps(content)
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO conversation_messages (chat_id, role, content) VALUES (%s, %s, %s)",
                (chat_id, role, content)
            )

def load_messages(chat_id: int, limit: int = 40) -> list:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT role, content FROM conversation_messages
                   WHERE chat_id = %s ORDER BY saved_at DESC LIMIT %s""",
                (chat_id, limit)
            )
            rows = list(reversed(cur.fetchall()))
    messages = []
    for role, content in rows:
        if content.startswith('[') or content.startswith('{'):
            try:
                parsed = json.loads(content)
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


# ── Scout analyses ────────────────────────────────────────────────────────────

def save_scout_analysis(url: str, title: str, source_type: str, analysis: str,
                        channel: str = None, duration_s: int = None,
                        view_count: int = None, transcript: str = None) -> int:
    """Save a SCOUT analysis. Returns the new row ID."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO scout_analyses
                   (url, title, source_type, channel, duration_s, view_count, transcript, analysis)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (url, title, source_type, channel, duration_s, view_count, transcript, analysis)
            )
            return cur.fetchone()[0]

def save_identified_clip(scout_analysis_id: int, source_url: str, clip_number: int,
                          virality_score: int, start_time: str, end_time: str,
                          exact_quote: str, hook_text: str, clip_type: str,
                          belief_reversal: str = None, emotional_engine: str = None,
                          vici_brand_fit: str = None, bonus_signals: str = None) -> int:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO identified_clips
                   (scout_analysis_id, source_url, clip_number, virality_score,
                    start_time, end_time, exact_quote, hook_text, clip_type,
                    belief_reversal, emotional_engine, vici_brand_fit, bonus_signals)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (scout_analysis_id, source_url, clip_number, virality_score,
                 start_time, end_time, exact_quote, hook_text, clip_type,
                 belief_reversal, emotional_engine, vici_brand_fit, bonus_signals)
            )
            return cur.fetchone()[0]

def save_rendered_clip(source_url: str, start_time: str, end_time: str,
                       hook_text: str, file_path: str, identified_clip_id: int = None):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO rendered_clips
                   (identified_clip_id, source_url, start_time, end_time, hook_text, file_path)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (identified_clip_id, source_url, start_time, end_time, hook_text, file_path)
            )

def get_recent_analyses(limit: int = 5) -> list:
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT url, title, source_type, analysis, created_at FROM scout_analyses ORDER BY created_at DESC LIMIT %s",
                (limit,)
            )
            return [dict(r) for r in cur.fetchall()]

def url_already_scouted(url: str) -> bool:
    """Check if this exact URL has been analysed before."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM scout_analyses WHERE url = %s LIMIT 1", (url,))
            return cur.fetchone() is not None


# ── Produced content ──────────────────────────────────────────────────────────

def save_produced_content(content_type: str, content: str, topic_id: str = None,
                           topic_title: str = None, file_path: str = None,
                           metadata: dict = None):
    """Save any produced content — script, voiceover, X posts, carousel, etc."""
    fp = _fp(content)
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO produced_content
                   (content_type, topic_id, topic_title, content, file_path, fingerprint, metadata)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (content_type, topic_id, topic_title, content, file_path,
                 fp, json.dumps(metadata or {}))
            )

def get_recent_produced(content_type: str = None, limit: int = 10) -> list:
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if content_type:
                cur.execute(
                    "SELECT * FROM produced_content WHERE content_type = %s ORDER BY created_at DESC LIMIT %s",
                    (content_type, limit)
                )
            else:
                cur.execute(
                    "SELECT * FROM produced_content ORDER BY created_at DESC LIMIT %s",
                    (limit,)
                )
            return [dict(r) for r in cur.fetchall()]


# ── Content fingerprints (dedup) ──────────────────────────────────────────────

def is_duplicate_content(text: str, category: str) -> bool:
    fp = _fp(text)
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM content_fingerprints WHERE fingerprint = %s AND category = %s",
                (fp, category)
            )
            return cur.fetchone() is not None

def record_content_fingerprint(text: str, category: str, meta: dict = None):
    fp = _fp(text)
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO content_fingerprints (fingerprint, category, preview, metadata)
                   VALUES (%s, %s, %s, %s) ON CONFLICT (fingerprint, category) DO NOTHING""",
                (fp, category, text[:100], json.dumps(meta or {}))
            )


# ── Topics done ───────────────────────────────────────────────────────────────

def is_topic_done(topic_id: str) -> bool:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM topics_done WHERE topic_id = %s", (topic_id,))
            return cur.fetchone() is not None

def mark_topic_done(topic_id: str):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO topics_done (topic_id) VALUES (%s) ON CONFLICT DO NOTHING",
                (topic_id,)
            )

def reset_topics():
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM topics_done")


# ── Articles seen (dedup) ─────────────────────────────────────────────────────

def is_article_seen(url: str, content: str = None) -> bool:
    uh = _url_hash(url)
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM article_seen WHERE url_hash = %s", (uh,))
            if cur.fetchone():
                return True
            if content:
                ch = _content_hash(content)
                cur.execute("SELECT 1 FROM article_seen WHERE content_hash = %s", (ch,))
                return cur.fetchone() is not None
    return False

def mark_article_seen(url: str, title: str = "", content: str = None, published_date: str = None):
    uh = _url_hash(url)
    ch = _content_hash(content) if content else None
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO article_seen (url_hash, content_hash, title, url, published_date)
                   VALUES (%s,%s,%s,%s,%s) ON CONFLICT (url_hash) DO NOTHING""",
                (uh, ch, title, url, published_date)
            )


# ── Knowledge base ────────────────────────────────────────────────────────────

def save_knowledge(topic: str, compound: str, key_facts: str, articles_json: str,
                   content_produced: str = None, summary: str = None):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO knowledge_base
                   (topic, compound, key_facts, articles_json, content_produced, summary)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (topic, compound, key_facts,
                 articles_json if articles_json else '[]',
                 content_produced, summary)
            )

def get_knowledge(topic: str, max_age_days: int = 30) -> list:
    cutoff = datetime.now() - timedelta(days=max_age_days)
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT topic, compound, researched_at, key_facts, content_produced, summary
                   FROM knowledge_base
                   WHERE (topic ILIKE %s OR topic ILIKE %s)
                   AND researched_at > %s
                   ORDER BY researched_at DESC LIMIT 5""",
                (f"%{topic}%", f"%{topic.split()[0]}%", cutoff)
            )
            return [dict(r) for r in cur.fetchall()]

def get_all_recent_topics(days: int = 30) -> list:
    cutoff = datetime.now() - timedelta(days=days)
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT topic, compound, researched_at, summary FROM knowledge_base
                   WHERE researched_at > %s ORDER BY researched_at DESC""",
                (cutoff,)
            )
            return [dict(r) for r in cur.fetchall()]


# ── Search cache ──────────────────────────────────────────────────────────────

def cache_search(query: str, results: str):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO search_cache (query, results) VALUES (%s,%s)",
                (query, results)
            )

def get_cached_search(query: str, max_age_hours: int = 4) -> str | None:
    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT results FROM search_cache
                   WHERE query = %s AND cached_at > %s
                   ORDER BY cached_at DESC LIMIT 1""",
                (query, cutoff)
            )
            row = cur.fetchone()
    return row[0] if row else None
