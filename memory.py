"""
Knowledge base interface — persistent memory of what's been researched.
The bot learns as it goes and surfaces prior research when relevant.
"""

import json
from datetime import datetime
from content_db import save_knowledge, get_knowledge, get_all_recent_topics


def check_memory(query: str) -> str:
    """
    Check if this topic has been researched before.
    Returns a formatted summary of prior research, or a 'no prior research' message.
    """
    entries = get_knowledge(query, max_age_days=90)
    if not entries:
        return f"No prior research found on: {query}"

    lines = [f"PRIOR RESEARCH — {query}\n{'='*40}"]
    for e in entries:
        dt = e["researched_at"][:10]
        lines.append(
            f"\nResearched: {dt}"
            + (f"\nCompound: {e['compound']}" if e.get("compound") else "")
            + (f"\nKey facts:\n{e['key_facts']}" if e.get("key_facts") else "")
            + (f"\nContent produced: {e['content_produced']}" if e.get("content_produced") else "")
            + (f"\nSummary: {e['summary']}" if e.get("summary") else "")
        )

    return "\n".join(lines)


def save_research(topic: str, compound: str, key_facts: str,
                  sources: list, content_type: str = None) -> str:
    """
    Save research to the knowledge base. Call after any substantial web search + content generation.
    Returns confirmation string.
    """
    articles_json = json.dumps(sources[:5])
    summary = f"{key_facts[:150]}..." if len(key_facts) > 150 else key_facts
    save_knowledge(
        topic=topic,
        compound=compound,
        key_facts=key_facts,
        articles_json=articles_json,
        content_produced=content_type,
        summary=summary,
    )
    return f"Saved to knowledge base: {topic} ({datetime.now().strftime('%Y-%m-%d')})"


def get_memory_digest(days: int = 7) -> str:
    """
    Return a weekly digest of everything researched and produced.
    """
    topics = get_all_recent_topics(days=days)
    if not topics:
        return f"No research logged in the past {days} days."

    lines = [f"KNOWLEDGE BASE — Past {days} days\n{'='*40}"]
    for t in topics:
        dt = t["researched_at"][:10]
        compound_str = f" ({t['compound']})" if t.get("compound") else ""
        summary_str = f"\n   {t['summary']}" if t.get("summary") else ""
        lines.append(f"\n- {dt} — {t['topic']}{compound_str}{summary_str}")

    return "\n".join(lines)
