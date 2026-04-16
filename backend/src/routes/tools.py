"""United Agents — Tools endpoints.

Per API_SPEC.md §14. search_web requires orchestrator or earth; workers → 403.
"""

import os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import Agent
from src.auth import get_current_agent
from src.ratelimit import rate_limiter, check_rate_limit

router = APIRouter(prefix="/api/v1", tags=["tools"])


class SearchRequest(BaseModel):
    query: str
    count: int = 5
    freshness: Optional[str] = None  # "pd" | "pw" | "pm"


# POST /api/v1/tools/search
@router.post("/tools/search")
async def search_web(
    data: SearchRequest,
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    # Auth: orchestrator or earth only
    if agent.type not in ("orchestrator", "earth"):
        raise HTTPException(403, "Only orchestrator or earth agents can use search")

    check_rate_limit(rate_limiter, agent.id, "search")

    google_key = os.environ.get("GOOGLE_API_KEY")
    google_cx = os.environ.get("GOOGLE_SEARCH_CX")
    if not google_key or not google_cx:
        raise HTTPException(503, "Search not configured (GOOGLE_API_KEY / GOOGLE_SEARCH_CX missing)")

    # Cap count
    count = min(data.count, 10)

    try:
        import httpx
        params = {
            "key": google_key,
            "cx": google_cx,
            "q": data.query,
            "num": count,
        }
        if data.freshness:
            freshness_map = {"pd": "d1", "pw": "w1", "pm": "m1"}
            params["dateRestrict"] = freshness_map.get(data.freshness, "")

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://www.googleapis.com/customsearch/v1",
                params=params,
            )
            resp.raise_for_status()
            search_data = resp.json()

        results = []
        for item in search_data.get("items", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "description": item.get("snippet", ""),
                "age": item.get("pagemap", {}).get("metatags", [{}])[0].get("article:published_time", ""),
            })

        return {"results": results, "query": data.query}

    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"Search API error: {e.response.status_code}")
    except Exception as e:
        raise HTTPException(502, f"Search failed: {str(e)}")
