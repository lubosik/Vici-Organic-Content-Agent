"""Duplicate content prevention. Every hook, script, and post is fingerprinted."""

import json
import hashlib
import os
from datetime import datetime

LOG_PATH = "data/content_log.json"


def _load() -> dict:
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(LOG_PATH):
        return {"hooks": [], "scripts": [], "x_posts": [], "topics_done": [], "log": []}
    with open(LOG_PATH) as f:
        return json.load(f)


def _save(data: dict):
    with open(LOG_PATH, "w") as f:
        json.dump(data, f, indent=2)


def _fp(text: str) -> str:
    cleaned = " ".join(text.lower().split())
    return hashlib.md5(cleaned.encode()).hexdigest()[:16]


def is_duplicate(text: str, category: str = "scripts") -> bool:
    store = _load()
    return _fp(text) in store.get(category, [])


def record(text: str, category: str = "scripts", meta: dict = None):
    store = _load()
    fp = _fp(text)
    store.setdefault(category, [])
    if fp not in store[category]:
        store[category].append(fp)
    store.setdefault("log", []).append({
        "fp": fp,
        "category": category,
        "preview": text[:100],
        "at": datetime.now().isoformat(),
        "meta": meta or {}
    })
    _save(store)


def topic_done(topic_id: str) -> bool:
    return topic_id in _load().get("topics_done", [])


def mark_topic_done(topic_id: str):
    store = _load()
    store.setdefault("topics_done", [])
    if topic_id not in store["topics_done"]:
        store["topics_done"].append(topic_id)
    _save(store)


def next_topic(queue: list) -> dict:
    for t in queue:
        if not topic_done(t["id"]):
            return t
    store = _load()
    store["topics_done"] = []
    _save(store)
    return queue[0]
