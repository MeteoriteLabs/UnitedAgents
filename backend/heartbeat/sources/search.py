"""United Agents — Web search via Google Custom Search.

Per AGENT_SPEC.md §10. Module-level function (not a class).
Freshness mapping: pd → d1, pw → w1, pm → m1.
"""

import os
import logging
from typing import Optional

import httpx

logger = logging.getLogger("heartbeat.sources.search")

FRESHNESS_MAP = {"pd": "d1", "pw": "w1", "pm": "m1"}


async def search_web(query: str, count: int = 5, freshness: Optional[str] = None) -> dict:
    """Search the web via Google Custom Search API."""
    try:
        api_key = os.environ.get("GOOGLE_API_KEY")
        cx = os.environ.get("GOOGLE_SEARCH_CX")
        if not api_key or not cx:
            return {"results": [], "error": "GOOGLE_API_KEY or GOOGLE_SEARCH_CX not configured"}

        params = {
            "key": api_key,
            "cx": cx,
            "q": query,
            "num": min(count, 10),
        }
        if freshness and freshness in FRESHNESS_MAP:
            params["dateRestrict"] = FRESHNESS_MAP[freshness]

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://www.googleapis.com/customsearch/v1", params=params)
            resp.raise_for_status()
            data = resp.json()

        results = []
        for item in data.get("items", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "description": item.get("snippet", ""),
            })

        return {"results": results, "query": query}

    except Exception as e:
        logger.warning(f"search_web failed: {e}")
        return {"results": [], "error": str(e)}
