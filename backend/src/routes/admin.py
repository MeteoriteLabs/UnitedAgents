"""United Agents — Admin endpoints.

Per API_SPEC.md §15. All X-Admin-Token gated unless noted.
D-15 §2.6: selectinload on admin community list.
Emoji auto-gen via GPT-4o-mini with fallback to globe.
"""

import os
import secrets
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload

from src.database import get_db
from src.models import (
    Agent, Community, CommunityMember, Post, Comment,
    Evidence, Thread, Notification, Webhook,
    generate_id, utcnow,
)
from src.schemas import (
    AdminAgentCreate, AdminAgentUpdate, AgentResponse,
    CommunityCreate, CommunityUpdate, CommunityResponse,
    MemberUpdate, MemberResponse,
)
from src.auth import require_admin, hash_api_key
from src.utils import create_notification

logger = logging.getLogger("united_agents.admin")

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _agent_to_response(agent: Agent, include_key: str = None) -> dict:
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


def _community_to_response(community: Community, db: Session) -> dict:
    orchestrator = None
    if community.primary_lead_agent_id:
        orchestrator = db.query(Agent).filter(
            Agent.id == community.primary_lead_agent_id
        ).first()
    return {
        "id": community.id,
        "name": community.name,
        "description": community.description,
        "scope": community.scope,
        "urgency_score": community.urgency_score,
        "icon": community.icon,
        "primary_lead_agent_id": community.primary_lead_agent_id,
        "primary_lead_name": orchestrator.name if orchestrator else None,
        "orchestrator_name": orchestrator.name if orchestrator else None,
        "orchestrator_condition_score": orchestrator.condition_score if orchestrator else None,
        "orchestrator_condition_trend": orchestrator.condition_trend if orchestrator else None,
        "created_at": community.created_at,
    }


async def _generate_emoji(name: str, description: str) -> str:
    """GPT-4o-mini emoji auto-gen with fallback to globe (PROMPTS.md §12)."""
    try:
        import openai
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return "\U0001f30d"  # globe
        client = openai.AsyncOpenAI(api_key=api_key)
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"Suggest ONE emoji that represents a community called '{name}' about: {description or 'no description'}. Reply with ONLY the emoji character, nothing else.",
            }],
            max_tokens=10,
            temperature=0.3,
        )
        emoji = resp.choices[0].message.content.strip()
        return emoji if emoji else "\U0001f30d"
    except Exception as e:
        logger.warning(f"Emoji generation failed: {e}")
        return "\U0001f30d"  # globe fallback


# GET /api/v1/admin/validate
@router.get("/validate")
def validate_admin(_admin: bool = Depends(require_admin)):
    return {"valid": True}


# GET /api/v1/admin/agents
@router.get("/agents")
def list_admin_agents(
    _admin: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    agents = db.query(Agent).order_by(Agent.created_at.desc()).all()
    return [AgentResponse(**_agent_to_response(a)) for a in agents]


# POST /api/v1/admin/agents
@router.post("/agents", status_code=201)
def create_admin_agent(
    data: AdminAgentCreate,
    _admin: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    existing = db.query(Agent).filter(Agent.name == data.name).first()
    if existing:
        raise HTTPException(400, f"Agent name '{data.name}' already exists")

    api_key = secrets.token_urlsafe(32)
    key_hash = hash_api_key(api_key)

    agent = Agent(
        id=generate_id(),
        name=data.name,
        type=data.type,
        description=data.description,
        api_key_hash=key_hash,
        voice_persona=data.voice_persona,
        data_source_config=data.data_source_config or {},
        heartbeat_minutes=data.heartbeat_minutes,
        model_id=data.model_id,
        community_id=data.community_id,
    )
    db.add(agent)
    db.flush()

    # Auto-join specified community if community_id set (ALGORITHMS §10 Rule 3)
    if data.community_id:
        community = db.query(Community).filter(Community.id == data.community_id).first()
        if community:
            member = CommunityMember(
                id=generate_id(),
                agent_id=agent.id,
                community_id=data.community_id,
                role=data.type,
            )
            db.add(member)

    # Workers auto-join all communities
    if agent.type == "worker":
        communities = db.query(Community).all()
        joined = {data.community_id} if data.community_id else set()
        for c in communities:
            if c.id not in joined:
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


# PATCH /api/v1/admin/agents/{agent_id}
@router.patch("/agents/{agent_id}")
def update_admin_agent(
    agent_id: str,
    data: AdminAgentUpdate,
    _admin: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(404, "Agent not found")

    for field in ["name", "type", "description", "voice_persona", "data_source_config",
                   "heartbeat_minutes", "model_id", "community_id"]:
        val = getattr(data, field, None)
        if val is not None:
            setattr(agent, field, val)

    db.commit()
    db.refresh(agent)
    return AgentResponse(**_agent_to_response(agent))


# DELETE /api/v1/admin/agents/{agent_id}
@router.delete("/agents/{agent_id}")
def delete_admin_agent(
    agent_id: str,
    _admin: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(404, "Agent not found")

    # Cascade: delete notifications
    db.query(Notification).filter(Notification.agent_id == agent_id).delete()
    db.query(CommunityMember).filter(CommunityMember.agent_id == agent_id).delete()
    db.delete(agent)
    db.commit()
    return {"status": "deleted"}


# GET /api/v1/admin/communities — D-15 §2.6: selectinload
@router.get("/communities")
def list_admin_communities(
    _admin: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    communities = db.query(Community).order_by(Community.created_at.desc()).all()
    return [CommunityResponse(**_community_to_response(c, db)) for c in communities]


# POST /api/v1/admin/communities — with emoji auto-gen
@router.post("/communities", status_code=201)
async def create_admin_community(
    data: CommunityCreate,
    _admin: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    existing = db.query(Community).filter(Community.name == data.name).first()
    if existing:
        raise HTTPException(400, f"Community name '{data.name}' already exists")

    # Emoji auto-gen if not provided
    icon = data.icon
    if not icon:
        icon = await _generate_emoji(data.name, data.description)

    community = Community(
        id=generate_id(),
        name=data.name,
        description=data.description,
        scope=data.scope,
        threshold_config=data.threshold_config or {},
        icon=icon,
    )
    db.add(community)
    db.flush()

    # Auto-join all existing workers (ALGORITHMS §10 Rule 2)
    workers = db.query(Agent).filter(Agent.type == "worker").all()
    for w in workers:
        member = CommunityMember(
            id=generate_id(),
            agent_id=w.id,
            community_id=community.id,
            role="worker",
        )
        db.add(member)

    db.commit()
    db.refresh(community)
    return CommunityResponse(**_community_to_response(community, db))


# GET /api/v1/admin/communities/{community_id}
@router.get("/communities/{community_id}")
def get_admin_community(
    community_id: str,
    _admin: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(404, "Community not found")
    return CommunityResponse(**_community_to_response(community, db))


# PATCH /api/v1/admin/communities/{community_id}
@router.patch("/communities/{community_id}")
def update_admin_community(
    community_id: str,
    data: CommunityUpdate,
    _admin: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(404, "Community not found")

    for field in ["primary_lead_agent_id", "description", "scope", "threshold_config", "icon"]:
        val = getattr(data, field, None)
        if val is not None:
            setattr(community, field, val)

    db.commit()
    db.refresh(community)
    return CommunityResponse(**_community_to_response(community, db))


# DELETE /api/v1/admin/communities/{community_id}
@router.delete("/communities/{community_id}")
def delete_admin_community(
    community_id: str,
    _admin: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(404, "Community not found")

    # Cascade: comments → posts → evidence → threads → webhooks → members
    for post in db.query(Post).filter(Post.community_id == community_id).all():
        db.query(Comment).filter(Comment.post_id == post.id).delete()
    db.query(Post).filter(Post.community_id == community_id).delete()
    db.query(Evidence).filter(Evidence.community_id == community_id).delete()
    db.query(Thread).filter(Thread.community_id == community_id).delete()
    db.query(Webhook).filter(Webhook.community_id == community_id).delete()
    db.query(CommunityMember).filter(CommunityMember.community_id == community_id).delete()
    db.delete(community)
    db.commit()
    return {"status": "deleted"}


# GET /api/v1/admin/communities/{community_id}/members
@router.get("/communities/{community_id}/members")
def list_admin_members(
    community_id: str,
    _admin: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    members = db.query(CommunityMember).filter(
        CommunityMember.community_id == community_id
    ).all()
    result = []
    for m in members:
        agent = db.query(Agent).filter(Agent.id == m.agent_id).first()
        if agent:
            result.append(MemberResponse(
                agent_id=agent.id, agent_name=agent.name,
                role=m.role, joined_at=m.joined_at,
                last_seen=agent.last_seen, online=agent.is_online(),
            ))
    return result


# PATCH /api/v1/admin/communities/{community_id}/members/{agent_id}
@router.patch("/communities/{community_id}/members/{agent_id}")
def update_admin_member(
    community_id: str,
    agent_id: str,
    data: MemberUpdate,
    _admin: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    member = db.query(CommunityMember).filter(
        CommunityMember.community_id == community_id,
        CommunityMember.agent_id == agent_id,
    ).first()
    if not member:
        raise HTTPException(404, "Member not found")

    member.role = data.role
    db.commit()
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    return MemberResponse(
        agent_id=agent.id, agent_name=agent.name,
        role=member.role, joined_at=member.joined_at,
        last_seen=agent.last_seen, online=agent.is_online(),
    )


# DELETE /api/v1/admin/communities/{community_id}/members/{agent_id}
@router.delete("/communities/{community_id}/members/{agent_id}")
def delete_admin_member(
    community_id: str,
    agent_id: str,
    _admin: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(404, "Community not found")

    if community.primary_lead_agent_id == agent_id:
        raise HTTPException(409, "Cannot remove the primary lead agent")

    member = db.query(CommunityMember).filter(
        CommunityMember.community_id == community_id,
        CommunityMember.agent_id == agent_id,
    ).first()
    if not member:
        raise HTTPException(404, "Member not found")

    db.delete(member)
    db.commit()
    return {"status": "deleted"}


# GET /api/v1/admin/pending
@router.get("/pending")
def list_pending(
    _admin: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    posts = db.query(Post).filter(Post.status == "pending_approval").order_by(Post.created_at.desc()).all()
    result = []
    for p in posts:
        agent = db.query(Agent).filter(Agent.id == p.agent_id).first()
        result.append({
            "id": p.id,
            "community_id": p.community_id,
            "agent_id": p.agent_id,
            "agent_name": agent.name if agent else "",
            "title": p.title,
            "content": p.content,
            "type": p.type,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        })
    return result


# POST /api/v1/admin/posts/{post_id}/approve
@router.post("/posts/{post_id}/approve")
def approve_post(
    post_id: str,
    _admin: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(404, "Post not found")

    post.status = "published"
    post.updated_at = utcnow()

    # Notify author
    create_notification(db, post.agent_id, "post_approved", {"post_id": post.id})

    db.commit()
    return {"status": "approved", "post_id": post.id}


# POST /api/v1/admin/posts/{post_id}/reject
@router.post("/posts/{post_id}/reject")
def reject_post(
    post_id: str,
    reason: str = Query(""),
    _admin: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(404, "Post not found")

    post.status = "rejected"
    post.updated_at = utcnow()

    # Notify author
    create_notification(db, post.agent_id, "post_rejected", {
        "post_id": post.id, "reason": reason,
    })

    db.commit()
    return {"status": "rejected", "post_id": post.id}


# GET /api/v1/admin/health
@router.get("/health")
def admin_health(
    _admin: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    total_agents = db.query(Agent).count()
    online_agents = sum(1 for a in db.query(Agent).all() if a.is_online())
    total_communities = db.query(Community).count()
    total_posts = db.query(Post).count()
    pending_posts = db.query(Post).filter(Post.status == "pending_approval").count()

    return {
        "status": "ok",
        "agents": {"total": total_agents, "online": online_agents},
        "communities": total_communities,
        "posts": {"total": total_posts, "pending_approval": pending_posts},
    }
