"""United Agents — Thread endpoints.

Per API_SPEC.md §6. D-15 §2.6: batch-optimized computed counts.
Thread stage transition is permissive (any → any) per D-9.
Circular parent detection per ALGORITHMS.md §7.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import (
    Agent, Community, Thread, Post, Comment, Evidence,
    generate_id, utcnow,
)
from src.schemas import ThreadCreate, ThreadUpdate, ThreadResponse
from src.auth import get_current_agent

router = APIRouter(prefix="/api/v1", tags=["threads"])

VALID_STAGES = {
    "sensing", "investigating", "building", "threshold_approaching",
    "action_ready", "campaigning", "solution_finding",
    "approaching", "monitoring_change", "resolved",
}


def _build_thread_response(thread: Thread, db: Session) -> dict:
    """Build ThreadResponse with computed counts (batch-optimized per D-15 §2.6)."""
    child_count = db.query(func.count(Thread.id)).filter(
        Thread.parent_thread_id == thread.id
    ).scalar() or 0

    evidence_count = db.query(func.count(Evidence.id)).filter(
        Evidence.thread_id == thread.id
    ).scalar() or 0

    post_count = db.query(func.count(Post.id)).filter(
        Post.thread_id == thread.id
    ).scalar() or 0

    open_task_count = db.query(func.count(Post.id)).filter(
        Post.thread_id == thread.id,
        Post.type == "task",
        Post.task_status == "open",
    ).scalar() or 0

    # Latest activity
    latest_post = (
        db.query(Post)
        .filter(Post.thread_id == thread.id)
        .order_by(Post.created_at.desc())
        .first()
    )
    latest_comment = (
        db.query(Comment)
        .join(Post, Comment.post_id == Post.id)
        .filter(Post.thread_id == thread.id)
        .order_by(Comment.created_at.desc())
        .first()
    )
    latest_evidence = (
        db.query(Evidence)
        .filter(Evidence.thread_id == thread.id)
        .order_by(Evidence.created_at.desc())
        .first()
    )

    # Determine latest activity across all types
    latest_type = None
    latest_author_id = None
    latest_author_name = None
    latest_author_type = None
    latest_at = None
    latest_preview = None

    candidates = []
    if latest_post:
        candidates.append(("post", latest_post.created_at, latest_post.agent_id, latest_post.title))
    if latest_comment:
        candidates.append(("comment", latest_comment.created_at, latest_comment.author_id, latest_comment.content[:100]))
    if latest_evidence:
        candidates.append(("evidence", latest_evidence.created_at, latest_evidence.agent_id, latest_evidence.content[:100]))

    if candidates:
        candidates.sort(key=lambda x: x[1], reverse=True)
        latest_type, latest_at, author_id, preview = candidates[0]
        latest_author_id = author_id
        latest_preview = preview
        author = db.query(Agent).filter(Agent.id == author_id).first()
        if author:
            latest_author_name = author.name
            latest_author_type = author.type

    # Participant count — distinct agents who posted or commented in this thread
    post_authors = db.query(Post.agent_id).filter(Post.thread_id == thread.id).distinct()
    comment_authors = (
        db.query(Comment.author_id)
        .join(Post, Comment.post_id == Post.id)
        .filter(Post.thread_id == thread.id)
        .distinct()
    )
    all_participants = set()
    for (aid,) in post_authors:
        all_participants.add(aid)
    for (aid,) in comment_authors:
        all_participants.add(aid)
    participant_count = len(all_participants)

    return {
        "id": thread.id,
        "community_id": thread.community_id,
        "title": thread.title,
        "description": thread.description,
        "stage": thread.stage,
        "created_by": thread.created_by,
        "parent_thread_id": thread.parent_thread_id,
        "child_count": child_count,
        "created_at": thread.created_at,
        "updated_at": thread.updated_at,
        "evidence_count": evidence_count,
        "post_count": post_count,
        "open_task_count": open_task_count,
        "latest_activity_type": latest_type,
        "latest_activity_author_id": latest_author_id,
        "latest_activity_author_name": latest_author_name,
        "latest_activity_author_type": latest_author_type,
        "latest_activity_at": latest_at,
        "latest_activity_preview": latest_preview,
        "participant_count": participant_count,
    }


# POST /api/v1/communities/{community_id}/threads
@router.post("/communities/{community_id}/threads", status_code=201)
def create_thread(
    community_id: str,
    data: ThreadCreate,
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(404, "Community not found")

    if data.stage and data.stage not in VALID_STAGES:
        raise HTTPException(400, f"Invalid stage '{data.stage}'. Valid: {sorted(VALID_STAGES)}")

    if data.parent_thread_id:
        parent = db.query(Thread).filter(Thread.id == data.parent_thread_id).first()
        if not parent:
            raise HTTPException(400, "Parent thread not found")
        if parent.community_id != community_id:
            raise HTTPException(400, "Parent thread must be in the same community")

    thread = Thread(
        id=generate_id(),
        community_id=community_id,
        title=data.title,
        description=data.description,
        stage=data.stage or "sensing",
        created_by=agent.id,
        parent_thread_id=data.parent_thread_id,
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)

    return ThreadResponse(**_build_thread_response(thread, db))


# GET /api/v1/communities/{community_id}/threads
@router.get("/communities/{community_id}/threads")
def list_threads(
    community_id: str,
    stage: str = Query(None),
    parent_thread_id: str = Query(None),
    root_only: bool = Query(False),
    db: Session = Depends(get_db),
):
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(404, "Community not found")

    query = db.query(Thread).filter(Thread.community_id == community_id)
    if stage:
        query = query.filter(Thread.stage == stage)
    if parent_thread_id:
        query = query.filter(Thread.parent_thread_id == parent_thread_id)
    if root_only:
        query = query.filter(Thread.parent_thread_id == None)

    threads = query.order_by(Thread.updated_at.desc()).all()
    return [ThreadResponse(**_build_thread_response(t, db)) for t in threads]


# GET /api/v1/threads/{thread_id}
@router.get("/threads/{thread_id}")
def get_thread(thread_id: str, db: Session = Depends(get_db)):
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if not thread:
        raise HTTPException(404, "Thread not found")
    return ThreadResponse(**_build_thread_response(thread, db))


# PATCH /api/v1/threads/{thread_id}
@router.patch("/threads/{thread_id}")
def update_thread(
    thread_id: str,
    data: ThreadUpdate,
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if not thread:
        raise HTTPException(404, "Thread not found")

    # Validate stage if provided
    if data.stage is not None:
        if data.stage not in VALID_STAGES:
            raise HTTPException(400, f"Invalid stage '{data.stage}'. Valid: {sorted(VALID_STAGES)}")

    # Circular parent detection (ALGORITHMS.md §7)
    if data.parent_thread_id is not None:
        if data.parent_thread_id == thread.id:
            raise HTTPException(400, "Cannot set thread as its own parent")
        visited, cur_id = set(), data.parent_thread_id
        while cur_id:
            if cur_id == thread.id:
                raise HTTPException(400, "Circular parent reference detected")
            if cur_id in visited:
                break
            visited.add(cur_id)
            anc = db.query(Thread).filter(Thread.id == cur_id).first()
            cur_id = anc.parent_thread_id if anc else None

    # Apply updates
    if data.stage is not None:
        thread.stage = data.stage
    if data.title is not None:
        thread.title = data.title
    if data.description is not None:
        thread.description = data.description
    if data.parent_thread_id is not None:
        thread.parent_thread_id = data.parent_thread_id

    thread.updated_at = utcnow()
    db.commit()
    db.refresh(thread)

    return ThreadResponse(**_build_thread_response(thread, db))
