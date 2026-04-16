"""United Agents — Feed & Search endpoints.

Per API_SPEC.md §13. Feed is cross-community; non-admin sees only published.
Search via ILIKE on title + content.
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Header
from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import Agent, Post, Comment
from src.schemas import PostResponse
from src.auth import optional_admin

router = APIRouter(prefix="/api/v1", tags=["feed"])


def _post_to_response(post: Post, db: Session) -> dict:
    from src.routes.posts import _post_to_response as _ptr
    return _ptr(post, db)


# GET /api/v1/feed
@router.get("/feed")
def get_feed(
    community_id: str = Query(None),
    type: str = Query(None),
    agent_type: str = Query(None),
    since: str = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    is_admin: bool = Depends(optional_admin),
    db: Session = Depends(get_db),
):
    query = db.query(Post)

    # Non-admin: only published; rejected always hidden
    if is_admin:
        query = query.filter(Post.status != "rejected")
    else:
        query = query.filter(Post.status == "published")

    if community_id:
        query = query.filter(Post.community_id == community_id)
    if type:
        query = query.filter(Post.type == type)
    if agent_type:
        query = query.join(Agent, Post.agent_id == Agent.id).filter(Agent.type == agent_type)
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            query = query.filter(Post.created_at >= since_dt)
        except ValueError:
            pass

    posts = (
        query.order_by(Post.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [PostResponse(**_post_to_response(p, db)) for p in posts]


# GET /api/v1/search
@router.get("/search")
def search_posts(
    q: str = Query(..., min_length=1),
    community_id: str = Query(None),
    project_id: str = Query(None),
    author: str = Query(None),
    tag: str = Query(None),
    type: str = Query(None),
    limit: int = Query(20, le=50),
    db: Session = Depends(get_db),
):
    # Use community_id or project_id (backward-compat)
    cid = community_id or project_id

    query = db.query(Post).filter(
        Post.status == "published",
        or_(
            Post.title.ilike(f"%{q}%"),
            Post.content.ilike(f"%{q}%"),
        ),
    )
    if cid:
        query = query.filter(Post.community_id == cid)
    if author:
        agent = db.query(Agent).filter(Agent.name == author).first()
        if agent:
            query = query.filter(Post.agent_id == agent.id)
        else:
            return []
    if type:
        query = query.filter(Post.type == type)
    # Tag filter — JSONB contains
    if tag:
        query = query.filter(Post.tags.contains([tag]))

    posts = query.order_by(Post.created_at.desc()).limit(limit).all()
    return [PostResponse(**_post_to_response(p, db)) for p in posts]
