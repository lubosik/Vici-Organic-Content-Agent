"""
Web research via Perplexity Sonar (live web, ~$0.001/query via OpenRouter).
"""

import os
from openai import OpenAI
from content_db import cache_search, get_cached_search


def search_web(query: str, max_age_days: int = 7) -> str:
    """Search the live web using Perplexity Sonar. Results cached 4 hours."""
    cache_key = f"perplexity::{query}::{max_age_days}d"
    cached = get_cached_search(cache_key)
    if cached:
        return f"[CACHED RESULT]\n{cached}"

    try:
        client = OpenAI(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1",
        )

        prompt = f"""Research this topic. Focus only on information from the last {max_age_days} days:

{query}

Priority sources: PubMed, bioRxiv, medical journals, biotech news, peer-reviewed literature.
For peptide/longevity topics: clinical trial data, mechanism research, safety data.

Return:
- 5-8 bullet points with key findings
- Date of publication where known
- Source URL for each finding
- Flag anything older than {max_age_days} days

Be concise and factual only."""

        response = client.chat.completions.create(
            model=os.getenv("RESEARCH_MODEL", "perplexity/sonar"),
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )

        result = response.choices[0].message.content or "No results returned."

        try:
            cache_search(cache_key, result)
        except Exception:
            pass

        return result

    except Exception as e:
        return f"Web research failed: {e}"
