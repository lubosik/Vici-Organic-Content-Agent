"""
Duplicate content prevention — backed by PostgreSQL.
Replaces data/content_log.json entirely.
"""

from content_db import (
    is_duplicate_content, record_content_fingerprint,
    is_topic_done, mark_topic_done as _mark_topic_done, reset_topics
)


def is_duplicate(text: str, category: str = "scripts") -> bool:
    try:
        return is_duplicate_content(text, category)
    except Exception:
        return False  # Fail open — better to allow than to block on DB error


def record(text: str, category: str = "scripts", meta: dict = None):
    try:
        record_content_fingerprint(text, category, meta)
    except Exception as e:
        print(f"[DEDUP] Failed to record fingerprint: {e}")


def topic_done(topic_id: str) -> bool:
    try:
        return is_topic_done(topic_id)
    except Exception:
        return False


def mark_topic_done(topic_id: str):
    try:
        _mark_topic_done(topic_id)
    except Exception as e:
        print(f"[DEDUP] Failed to mark topic done: {e}")


def next_topic(queue: list) -> dict:
    """Return next unused topic from queue. Resets cycle if all used."""
    for t in queue:
        if not topic_done(t["id"]):
            return t
    # Full cycle — reset
    try:
        reset_topics()
    except Exception:
        pass
    return queue[0]
