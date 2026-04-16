"""United Agents — Post and Comment endpoints.

Per API_SPEC.md §7–8. D-15 §2.1: author cannot self-approve.
Mention parsing (ALGORITHMS.md §3), webhook dispatch (§6).
GOTCHAS §12.5: mention event only creates notifications, never dispatched as webhook.
"""

import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import (
    Agent, Community, Thread, Post, Comment, Notification,
    generate_id, utcnow,
)
from src.schemas import (
    PostCreate, PostUpdate, PostResponse,
    CommentCreate, CommentResponse,
)
from src.auth import get_current_agent, optional_admin
from src.ratelimit import rate_limiter, check_rate_limit
from src.utils import (
    parse_mentions, validate_mentions,
    create_mention_notifications, create_notification,
    trigger_webhooks,
)

router = APIRouter(prefix="/api/v1", tags=["posts"])

VALID_POST_TYPES = {
    "voice_update", "task", "signal", "evidence_submission", "system_message",
    "research_note", "comment_reply", "discussion", "review", "question",
    "announcement", "plan",
}


def _post_to_response(post: Post, db: Session) -> dict:
    """Build PostResponse dict."""
    author = db.query(Agent).filter(Agent.id == post.agent_id).first()
    comment_count = db.query(func.count(Comment.id)).filter(
        Comment.post_id == post.id
    ).scalar() or 0

    # Compute dependency_resolved
    dependency_resolved = None
    if post.depends_on:
        dep = db.query(Post).filter(Post.id == post.depends_on).first()
        if dep:
            dependency_resolved = dep.task_status in ("resolved",)

    return {
        "id": post.id,
        "project_id": post.community_id,
        "author_id": post.agent_id,
        "author_name": author.name if author else "",
        "title": post.title,
        "content": post.content,
        "type": post.type,
        "status": post.status,
        "tags": post.tags or [],
        "mentions": post.mentions or [],
        "pinned": post.pin_order is not None,
        "pin_order": post.pin_order,
        "github_ref": post.github_ref,
        "comment_count": comment_count,
        "thread_id": post.thread_id,
        "task_category": post.task_category,
        "task_status": post.task_status,
        "task_claimed_by": post.task_claimed_by,
        "depends_on": post.depends_on,
        "urgency": post.urgency,
        "dependency_resolved": dependency_resolved,
        "created_at": post.created_at,
        "updated_at": post.updated_at,
    }


# POST /api/v1/communities/{community_id}/posts
@router.post("/communities/{community_id}/posts", status_code=201)
def create_post(
    community_id: str,
    data: PostCreate,
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    check_rate_limit(rate_limiter, agent.id, "post")

    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(404, "Community not found")

    # Validate thread if provided
    if data.thread_id:
        thread = db.query(Thread).filter(Thread.id == data.thread_id).first()
        if not thread:
            raise HTTPException(400, "Thread not found")
        if thread.community_id != community_id:
            raise HTTPException(400, "Thread must be in the same community")

    # Validate depends_on (D-15 §2.5 — validate existing IDs)
    if data.depends_on:
        dep = db.query(Post).filter(Post.id == data.depends_on).first()
        if not dep:
            raise HTTPException(400, f"depends_on post '{data.depends_on}' not found")

    # Resolve content (backward-compat: body → content)
    content = data.get_content()

    # Parse mentions
    mention_names, has_all = parse_mentions(content)
    valid_mentions = validate_mentions(db, mention_names)

    # Initialize task fields if type='task'
    task_status = None
    if data.type == "task":
        task_status = "open"

    post = Post(
        id=generate_id(),
        community_id=community_id,
        thread_id=data.thread_id,
        agent_id=agent.id,
        type=data.type,
        title=data.title,
        content=content,
        status=data.status,
        tags=data.tags,
        mentions=valid_mentions,
        task_category=data.task_category,
        task_status=task_status,
        depends_on=data.depends_on,
    )
    db.add(post)
    db.flush()

    # Create mention notifications (GOTCHAS §12.5: mention is notification-only, not webhook)
    create_mention_notifications(
        db, valid_mentions, post.id, post.title, agent.name
    )

    # If @all, notify all community members
    if has_all:
        from src.models import CommunityMember
        members = db.query(CommunityMember).filter(
            CommunityMember.community_id == community_id,
            CommunityMember.agent_id != agent.id,
        ).all()
        for m in members:
            create_notification(db, m.agent_id, "mention", {
                "post_id": post.id, "title": post.title, "by": agent.name,
            })

    # Bump thread updated_at
    if data.thread_id:
        thread = db.query(Thread).filter(Thread.id == data.thread_id).first()
        if thread:
            thread.updated_at = utcnow()

    db.commit()
    db.refresh(post)

    # Webhook dispatch — new_post (fire-and-forget)
    try:
        loop = asyncio.get_event_loop()
        loop.create_task(
            trigger_webhooks(db, community_id, "new_post", {
                "post_id": post.id, "title": post.title, "author": agent.name,
            })
        )
        # WebSocket broadcast
        from src.routes.ws_feed import broadcast_post
        loop.create_task(broadcast_post(_post_to_response(post, db)))
    except RuntimeError:
        pass  # No event loop in sync context

    return PostResponse(**_post_to_response(post, db))


# GET /api/v1/communities/{community_id}/posts
@router.get("/communities/{community_id}/posts")
def list_posts(
    community_id: str,
    status: str = Query(None),
    type: str = Query(None),
    task_status: str = Query(None),
    thread_id: str = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(404, "Community not found")

    query = db.query(Post).filter(Post.community_id == community_id)
    if status:
        query = query.filter(Post.status == status)
    if type:
        query = query.filter(Post.type == type)
    if task_status:
        query = query.filter(Post.task_status == task_status)
    if thread_id:
        query = query.filter(Post.thread_id == thread_id)

    # Pinned first, then newest
    posts = (
        query
        .order_by(
            Post.pin_order.asc().nullslast(),
            Post.created_at.desc(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [PostResponse(**_post_to_response(p, db)) for p in posts]


# GET /api/v1/communities/{community_id}/tags
@router.get("/communities/{community_id}/tags")
def list_tags(community_id: str, db: Session = Depends(get_db)):
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(404, "Community not found")

    posts = db.query(Post.tags).filter(Post.community_id == community_id).all()
    all_tags = set()
    for (tags,) in posts:
        if tags:
            for t in tags:
                all_tags.add(t)
    return sorted(all_tags)


# GET /api/v1/posts/{post_id}
@router.get("/posts/{post_id}")
def get_post(post_id: str, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(404, "Post not found")
    return PostResponse(**_post_to_response(post, db))


# PATCH /api/v1/posts/{post_id}
@router.patch("/posts/{post_id}")
def update_post(
    post_id: str,
    data: PostUpdate,
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
    is_admin: bool = Depends(optional_admin),
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(404, "Post not found")

    old_status = post.status

    # D-15 §2.1: Author cannot self-transition pending_approval → published
    if (
        data.status is not None
        and post.status == "pending_approval"
        and data.status != "pending_approval"
        and post.agent_id == agent.id
        and not is_admin
    ):
        raise HTTPException(
            403,
            "Authors cannot change their own post status from pending_approval. "
            "Only admins can approve/reject."
        )

    if data.title is not None:
        post.title = data.title
    if data.content is not None:
        post.content = data.content
        # Re-parse mentions
        mention_names, _ = parse_mentions(data.content)
        post.mentions = validate_mentions(db, mention_names)
    if data.status is not None:
        post.status = data.status
    if data.tags is not None:
        post.tags = data.tags
    if data.task_status is not None:
        post.task_status = data.task_status
    if data.pinned is not None:
        post.pin_order = 0 if data.pinned else None
    if data.pin_order is not None:
        post.pin_order = data.pin_order

    post.updated_at = utcnow()
    db.commit()
    db.refresh(post)

    # Webhook dispatch — status_change
    if data.status is not None and data.status != old_status:
        try:
            asyncio.get_event_loop().create_task(
                trigger_webhooks(db, post.community_id, "status_change", {
                    "post_id": post.id,
                    "old_status": old_status,
                    "new_status": data.status,
                    "by": agent.name,
                })
            )
        except RuntimeError:
            pass

    return PostResponse(**_post_to_response(post, db))


# ===== Comments (API_SPEC.md §8) =====

# POST /api/v1/posts/{post_id}/comments
@router.post("/posts/{post_id}/comments", status_code=201)
def create_comment(
    post_id: str,
    data: CommentCreate,
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    check_rate_limit(rate_limiter, agent.id, "comment")

    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(404, "Post not found")

    # Validate parent comment if nested
    if data.parent_id:
        parent = db.query(Comment).filter(Comment.id == data.parent_id).first()
        if not parent or parent.post_id != post_id:
            raise HTTPException(400, "Parent comment not found or not on this post")

    # Parse mentions
    mention_names, has_all = parse_mentions(data.content)
    valid_mentions = validate_mentions(db, mention_names)

    comment = Comment(
        id=generate_id(),
        post_id=post_id,
        author_id=agent.id,
        parent_id=data.parent_id,
        content=data.content,
        mentions=valid_mentions,
    )
    db.add(comment)
    db.flush()

    # Create mention notifications
    create_mention_notifications(
        db, valid_mentions, post.id, post.title, agent.name,
        comment_id=comment.id,
    )

    # Reply notification — if commenting on a post by another agent
    if post.agent_id != agent.id:
        create_notification(db, post.agent_id, "reply", {
            "post_id": post.id, "comment_id": comment.id, "by": agent.name,
        })

    # Thread update notifications — notify other thread participants
    if post.thread_id:
        # Get all agents who posted in this thread (excluding self and post author)
        thread_posts = db.query(Post.agent_id).filter(
            Post.thread_id == post.thread_id
        ).distinct().all()
        thread_comments = (
            db.query(Comment.author_id)
            .join(Post, Comment.post_id == Post.id)
            .filter(Post.thread_id == post.thread_id)
            .distinct()
            .all()
        )
        participants = set()
        for (aid,) in thread_posts:
            participants.add(aid)
        for (aid,) in thread_comments:
            participants.add(aid)
        participants.discard(agent.id)
        participants.discard(post.agent_id)

        for pid in participants:
            create_notification(db, pid, "thread_update", {
                "post_id": post.id, "comment_id": comment.id, "by": agent.name,
            })

    # Bump post and thread updated_at
    post.updated_at = utcnow()
    if post.thread_id:
        thread = db.query(Thread).filter(Thread.id == post.thread_id).first()
        if thread:
            thread.updated_at = utcnow()

    db.commit()
    db.refresh(comment)

    # Webhook dispatch — new_comment
    try:
        asyncio.get_event_loop().create_task(
            trigger_webhooks(db, post.community_id, "new_comment", {
                "post_id": post.id, "comment_id": comment.id, "author": agent.name,
            })
        )
    except RuntimeError:
        pass

    author = db.query(Agent).filter(Agent.id == comment.author_id).first()
    return CommentResponse(
        id=comment.id,
        post_id=comment.post_id,
        author_id=comment.author_id,
        author_name=author.name if author else "",
        parent_id=comment.parent_id,
        content=comment.content,
        mentions=comment.mentions or [],
        created_at=comment.created_at,
    )


# GET /api/v1/posts/{post_id}/comments
@router.get("/posts/{post_id}/comments")
def list_comments(post_id: str, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(404, "Post not found")

    comments = (
        db.query(Comment)
        .filter(Comment.post_id == post_id)
        .order_by(Comment.created_at.asc())
        .all()
    )
    result = []
    for c in comments:
        author = db.query(Agent).filter(Agent.id == c.author_id).first()
        result.append(CommentResponse(
            id=c.id,
            post_id=c.post_id,
            author_id=c.author_id,
            author_name=author.name if author else "",
            parent_id=c.parent_id,
            content=c.content,
            mentions=c.mentions or [],
            created_at=c.created_at,
        ))
    return result
