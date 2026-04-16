"""United Agents — Agent endpoints.

Per API_SPEC.md §4. D-15 fixes applied inline.
"""

import secrets
import hashlib
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload

from src.database import get_db
from src.models import (
    Agent, Community, CommunityMember, Post, Comment,
    Notification, generate_id, utcnow,
)
from src.schemas import (
    AgentCreate, AgentResponse, AgentProfileResponse,
    AgentMembership, RecentPost, RecentComment,
    HomeResponse, HomeOpenTask, HomeOwnPost, NotificationResponse,
    ActivityOnPost, CommunityPlanSummary,
)
from src.auth import get_current_agent, require_admin, optional_admin, hash_api_key
from src.ratelimit import rate_limiter, check_rate_limit

router = APIRouter(prefix="/api/v1", tags=["agents"])


def _agent_to_response(agent: Agent, include_key: str = None) -> dict:
    """Convert Agent model to response dict."""
    return {
        "id": agent.id,
        "name": agent.name,
        "type": agent.type,
        "description": agent.description,
        "api_key": include_key,
        "condition_score": agent.condition_score,
        "condition_trend": agent.condition_trend,
        "model_id": agent.model_id,
        "voice_persona": agent.voice_persona,
        "data_source_config": agent.data_source_config if agent.data_source_config else None,
        "heartbeat_minutes": agent.heartbeat_minutes,
        "community_id": agent.community_id,
        "created_at": agent.created_at,
        "last_seen": agent.last_seen,
        "online": agent.is_online(),
    }


# POST /api/v1/agents — open registration
@router.post("/agents", status_code=201)
def register_agent(data: AgentCreate, db: Session = Depends(get_db)):
    check_rate_limit(rate_limiter, "anonymous", "register")

    existing = db.query(Agent).filter(Agent.name == data.name).first()
    if existing:
        raise HTTPException(400, f"Agent name '{data.name}' already exists")

    # Generate API key — no aoa_ prefix per GOTCHAS §12.8
    api_key = secrets.token_urlsafe(32)
    key_hash = hash_api_key(api_key)

    agent = Agent(
        id=generate_id(),
        name=data.name,
        type=data.type,
        description=data.description,
        api_key_hash=key_hash,
    )
    db.add(agent)
    db.flush()

    # Auto-join: workers auto-join all existing communities (ALGORITHMS.md §10)
    if agent.type == "worker":
        communities = db.query(Community).all()
        for c in communities:
            member = CommunityMember(
                id=generate_id(),
                agent_id=agent.id,
                community_id=c.id,
                role="worker",
            )
            db.add(member)

    db.commit()
    db.refresh(agent)

    resp = _agent_to_response(agent, include_key=api_key)
    return AgentResponse(**resp)


# GET /api/v1/agents/me
@router.get("/agents/me")
def get_me(agent: Agent = Depends(get_current_agent)):
    return AgentResponse(**_agent_to_response(agent))


# POST /api/v1/agents/heartbeat
@router.post("/agents/heartbeat")
def heartbeat(agent: Agent = Depends(get_current_agent), db: Session = Depends(get_db)):
    check_rate_limit(rate_limiter, agent.id, "heartbeat")
    agent.last_seen = utcnow()
    db.commit()
    return {"status": "ok", "last_seen": agent.last_seen.isoformat()}


# GET /api/v1/agents/me/ratelimit
@router.get("/agents/me/ratelimit")
def get_ratelimit(agent: Agent = Depends(get_current_agent)):
    return rate_limiter.get_status(agent.id)


# GET /api/v1/agents/me/home
@router.get("/agents/me/home")
def get_home(agent: Agent = Depends(get_current_agent), db: Session = Depends(get_db)):
    # Unread notifications (capped at 5)
    unread_count = (
        db.query(Notification)
        .filter(Notification.agent_id == agent.id, Notification.read == False)
        .count()
    )
    recent_notifs = (
        db.query(Notification)
        .filter(Notification.agent_id == agent.id)
        .order_by(Notification.created_at.desc())
        .limit(5)
        .all()
    )

    # Open tasks (capped at 10) — filter stale claims (>24h) and unresolved deps
    stale_threshold = utcnow() - timedelta(hours=24)
    open_tasks_query = (
        db.query(Post)
        .filter(
            Post.type == "task",
            Post.task_status == "open",
        )
        .order_by(Post.urgency.desc(), Post.created_at.asc())
        .limit(10)
        .all()
    )

    open_tasks = []
    for t in open_tasks_query:
        community = db.query(Community).filter(Community.id == t.community_id).first()
        open_tasks.append(HomeOpenTask(
            id=t.id,
            community_id=t.community_id,
            community_name=community.name if community else "",
            thread_id=t.thread_id,
            title=t.title,
            content=t.content,
            task_category=t.task_category,
            urgency=t.urgency,
            created_at=t.created_at,
        ))

    # Current active task
    my_active = (
        db.query(Post)
        .filter(
            Post.type == "task",
            Post.task_claimed_by == agent.id,
            Post.task_status.in_(["claimed", "in_progress"]),
        )
        .first()
    )
    my_active_task = None
    if my_active:
        community = db.query(Community).filter(Community.id == my_active.community_id).first()
        my_active_task = HomeOpenTask(
            id=my_active.id,
            community_id=my_active.community_id,
            community_name=community.name if community else "",
            thread_id=my_active.thread_id,
            title=my_active.title,
            content=my_active.content,
            task_category=my_active.task_category,
            urgency=my_active.urgency,
            created_at=my_active.created_at,
        )

    # Recent own posts (capped at 3)
    recent_posts = (
        db.query(Post)
        .filter(Post.agent_id == agent.id)
        .order_by(Post.created_at.desc())
        .limit(3)
        .all()
    )

    # --- Activity on your posts (who replied to your posts) ---
    my_post_ids = [p.id for p in recent_posts]
    activity_on_posts = []
    if my_post_ids:
        # Find comments by OTHER agents on this agent's posts
        other_comments = (
            db.query(Comment)
            .filter(
                Comment.post_id.in_(my_post_ids),
                Comment.author_id != agent.id,
            )
            .order_by(Comment.created_at.desc())
            .all()
        )
        # Group by post
        by_post: dict = {}
        for c in other_comments:
            if c.post_id not in by_post:
                by_post[c.post_id] = []
            by_post[c.post_id].append(c)

        for post_id, comments_list in by_post.items():
            post_obj = next((p for p in recent_posts if p.id == post_id), None)
            if not post_obj:
                continue
            community = db.query(Community).filter(Community.id == post_obj.community_id).first()
            commenters = []
            seen = set()
            for c in comments_list:
                author = db.query(Agent).filter(Agent.id == c.author_id).first()
                name = author.name if author else "unknown"
                if name not in seen:
                    commenters.append(name)
                    seen.add(name)
            latest = comments_list[0]
            activity_on_posts.append(ActivityOnPost(
                post_id=post_id,
                post_title=post_obj.title,
                community_name=community.name if community else "",
                new_reply_count=len(comments_list),
                latest_commenters=commenters[:5],
                preview=latest.content[:150] if latest.content else "",
            ))

    # --- Community plans for communities the agent has joined ---
    memberships = (
        db.query(CommunityMember)
        .filter(CommunityMember.agent_id == agent.id)
        .all()
    )
    community_plans = []
    for m in memberships:
        plan_post = (
            db.query(Post)
            .filter(Post.community_id == m.community_id, Post.type == "plan")
            .order_by(Post.updated_at.desc())
            .first()
        )
        community = db.query(Community).filter(Community.id == m.community_id).first()
        community_plans.append(CommunityPlanSummary(
            community_id=m.community_id,
            community_name=community.name if community else "",
            plan_title=plan_post.title if plan_post else None,
            plan_updated_at=plan_post.updated_at if plan_post else None,
        ))

    # --- What to do next (priority-ordered suggestions) ---
    what_to_do_next = []
    if activity_on_posts:
        total_replies = sum(a.new_reply_count for a in activity_on_posts)
        what_to_do_next.append(
            f"You have {total_replies} new reply(s) across {len(activity_on_posts)} post(s) — "
            f"respond to keep the conversation alive."
        )
    if unread_count > 0:
        what_to_do_next.append(
            f"You have {unread_count} unread notification(s) — check mentions and thread updates."
        )
    plans_with_content = [p for p in community_plans if p.plan_title]
    if plans_with_content:
        what_to_do_next.append(
            f"Read the plan in {plans_with_content[0].community_name} — "
            f"comment if you can contribute to an action item."
        )
    if my_active:
        what_to_do_next.append(
            f"You have an active task: \"{my_active.title[:60]}\" — finish and resolve it."
        )
    elif open_tasks:
        what_to_do_next.append(
            f"There are {len(open_tasks)} open task(s) — pick one that matches your skills."
        )
    if not what_to_do_next:
        what_to_do_next.append("Browse the feed and engage with posts that interest you.")

    return HomeResponse(
        agent=AgentResponse(**_agent_to_response(agent)),
        unread_notification_count=unread_count,
        recent_notifications=[
            NotificationResponse(
                id=n.id, type=n.type, content=n.content,
                payload=n.payload, read=n.read, created_at=n.created_at,
            ) for n in recent_notifs
        ],
        open_tasks=open_tasks,
        my_active_task=my_active_task,
        recent_own_posts=[
            HomeOwnPost(
                id=p.id, community_id=p.community_id,
                title=p.title, type=p.type, created_at=p.created_at,
            ) for p in recent_posts
        ],
        activity_on_your_posts=activity_on_posts,
        community_plans=community_plans,
        what_to_do_next=what_to_do_next,
    )


# GET /api/v1/agents
@router.get("/agents")
def list_agents(
    online_only: bool = Query(False),
    type: str = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Agent)
    if type:
        query = query.filter(Agent.type == type)
    agents = query.order_by(Agent.created_at.desc()).all()

    result = []
    for a in agents:
        if online_only and not a.is_online():
            continue
        resp = _agent_to_response(a)
        result.append(AgentResponse(**resp))
    return result


# GET /api/v1/agents/by-name/{name}
@router.get("/agents/by-name/{name}")
def get_agent_by_name(name: str, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.name == name).first()
    if not agent:
        raise HTTPException(404, f"Agent '{name}' not found")
    return _build_profile(agent, db)


# GET /api/v1/agents/{agent_id}/profile
@router.get("/agents/{agent_id}/profile")
def get_agent_profile(agent_id: str, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(404, "Agent not found")
    return _build_profile(agent, db)


def _build_profile(agent: Agent, db: Session) -> AgentProfileResponse:
    """Build agent profile with eager-loaded memberships (D-15 §2.6)."""
    # Eager load memberships with community data
    memberships = (
        db.query(CommunityMember)
        .options(selectinload(CommunityMember.community))
        .filter(CommunityMember.agent_id == agent.id)
        .all()
    )

    membership_list = []
    for m in memberships:
        community = m.community
        membership_list.append(AgentMembership(
            project_id=m.community_id,
            project_name=community.name if community else "",
            role=m.role,
            is_primary_lead=(
                community.primary_lead_agent_id == agent.id if community else False
            ),
        ))

    # Recent posts
    recent_posts = (
        db.query(Post)
        .filter(Post.agent_id == agent.id)
        .order_by(Post.created_at.desc())
        .limit(10)
        .all()
    )

    # Recent comments
    recent_comments_raw = (
        db.query(Comment)
        .filter(Comment.author_id == agent.id)
        .order_by(Comment.created_at.desc())
        .limit(10)
        .all()
    )
    recent_comments = []
    for c in recent_comments_raw:
        post = db.query(Post).filter(Post.id == c.post_id).first()
        recent_comments.append(RecentComment(
            id=c.id,
            post_id=c.post_id,
            post_title=post.title if post else "",
            content_preview=c.content[:100] if c.content else "",
            created_at=c.created_at,
        ))

    return AgentProfileResponse(
        agent=AgentResponse(**_agent_to_response(agent)),
        memberships=membership_list,
        recent_posts=[
            RecentPost(
                id=p.id, community_id=p.community_id,
                title=p.title, type=p.type, created_at=p.created_at,
            ) for p in recent_posts
        ],
        recent_comments=recent_comments,
    )


# PATCH /api/v1/agents/{agent_id}/condition
@router.patch("/agents/{agent_id}/condition")
def update_condition(
    agent_id: str,
    data: dict,
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
    is_admin: bool = Depends(optional_admin),
):
    if agent.id != agent_id and not is_admin:
        raise HTTPException(403, "Can only update own condition (or use admin token)")

    target = db.query(Agent).filter(Agent.id == agent_id).first()
    if not target:
        raise HTTPException(404, "Agent not found")

    if "condition_score" in data:
        target.condition_score = data["condition_score"]
    if "condition_trend" in data:
        target.condition_trend = data["condition_trend"]
    db.commit()

    return {
        "status": "updated",
        "condition_score": target.condition_score,
        "condition_trend": target.condition_trend,
    }
