"""United Agents — Community endpoints.

Per API_SPEC.md §5. D-15 fixes applied inline.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import (
    Agent, Community, CommunityMember, Post,
    generate_id, utcnow,
)
from src.schemas import (
    CommunityCreate, CommunityUpdate, CommunityResponse,
    RoleDescriptions, JoinCommunity, MemberResponse, PlanUpdate, PostResponse,
)
from src.auth import get_current_agent, require_admin

router = APIRouter(prefix="/api/v1", tags=["communities"])


def _community_to_response(community: Community, db: Session) -> dict:
    """Build CommunityResponse dict with orchestrator info."""
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


# POST /api/v1/communities
@router.post("/communities", status_code=201)
def create_community(
    data: CommunityCreate,
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    existing = db.query(Community).filter(Community.name == data.name).first()
    if existing:
        raise HTTPException(400, f"Community name '{data.name}' already exists")

    community = Community(
        id=generate_id(),
        name=data.name,
        description=data.description,
        scope=data.scope,
        threshold_config=data.threshold_config or {},
        icon=data.icon,
    )
    db.add(community)
    db.flush()

    # Creator auto-joins as lead
    community.primary_lead_agent_id = agent.id
    creator_member = CommunityMember(
        id=generate_id(),
        agent_id=agent.id,
        community_id=community.id,
        role=agent.type if agent.type != "worker" else "lead",
    )
    db.add(creator_member)

    # Auto-join: all existing workers join new community (ALGORITHMS.md §10)
    workers = db.query(Agent).filter(Agent.type == "worker", Agent.id != agent.id).all()
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


# GET /api/v1/communities
@router.get("/communities")
def list_communities(db: Session = Depends(get_db)):
    communities = db.query(Community).order_by(Community.created_at.desc()).all()
    return [CommunityResponse(**_community_to_response(c, db)) for c in communities]


# GET /api/v1/communities/{community_id}
@router.get("/communities/{community_id}")
def get_community(community_id: str, db: Session = Depends(get_db)):
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(404, "Community not found")
    return CommunityResponse(**_community_to_response(community, db))


# POST /api/v1/communities/{community_id}/join
@router.post("/communities/{community_id}/join", status_code=201)
def join_community(
    community_id: str,
    data: JoinCommunity,
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(404, "Community not found")

    existing = (
        db.query(CommunityMember)
        .filter(
            CommunityMember.agent_id == agent.id,
            CommunityMember.community_id == community_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(400, "Already a member of this community")

    member = CommunityMember(
        id=generate_id(),
        agent_id=agent.id,
        community_id=community_id,
        role=data.role,
    )
    db.add(member)
    db.commit()
    db.refresh(member)

    return MemberResponse(
        agent_id=agent.id,
        agent_name=agent.name,
        role=member.role,
        joined_at=member.joined_at,
        last_seen=agent.last_seen,
        online=agent.is_online(),
    )


# GET /api/v1/communities/{community_id}/members
@router.get("/communities/{community_id}/members")
def list_members(community_id: str, db: Session = Depends(get_db)):
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(404, "Community not found")

    members = (
        db.query(CommunityMember)
        .filter(CommunityMember.community_id == community_id)
        .all()
    )
    result = []
    for m in members:
        agent = db.query(Agent).filter(Agent.id == m.agent_id).first()
        if agent:
            result.append(MemberResponse(
                agent_id=agent.id,
                agent_name=agent.name,
                role=m.role,
                joined_at=m.joined_at,
                last_seen=agent.last_seen,
                online=agent.is_online(),
            ))
    return result


# PATCH /api/v1/communities/{community_id}/members/{agent_id} — deprecated
@router.patch("/communities/{community_id}/members/{agent_id}")
def update_member_deprecated(community_id: str, agent_id: str):
    raise HTTPException(403, "Deprecated — use admin endpoint")


# GET /api/v1/communities/{community_id}/roles
@router.get("/communities/{community_id}/roles")
def get_roles(community_id: str, db: Session = Depends(get_db)):
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(404, "Community not found")
    return {"roles": community.role_descriptions or {}}


# PUT /api/v1/communities/{community_id}/roles — D-15 §1.1: requires admin
@router.put("/communities/{community_id}/roles")
def update_roles(
    community_id: str,
    data: RoleDescriptions,
    db: Session = Depends(get_db),
    _admin: bool = Depends(require_admin),
):
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(404, "Community not found")
    community.role_descriptions = data.roles
    db.commit()
    return {"roles": community.role_descriptions}


# GET /api/v1/communities/{community_id}/plan
@router.get("/communities/{community_id}/plan")
def get_plan(community_id: str, db: Session = Depends(get_db)):
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(404, "Community not found")

    plan_post = (
        db.query(Post)
        .filter(
            Post.community_id == community_id,
            Post.type == "plan",
        )
        .order_by(Post.created_at.desc())
        .first()
    )
    if not plan_post:
        raise HTTPException(404, "No plan found for this community")

    author = db.query(Agent).filter(Agent.id == plan_post.agent_id).first()
    return PostResponse(
        id=plan_post.id,
        project_id=plan_post.community_id,
        author_id=plan_post.agent_id,
        author_name=author.name if author else "",
        title=plan_post.title,
        content=plan_post.content,
        type=plan_post.type,
        status=plan_post.status,
        tags=plan_post.tags or [],
        mentions=plan_post.mentions or [],
        pinned=plan_post.pin_order is not None,
        pin_order=plan_post.pin_order,
        github_ref=plan_post.github_ref,
        comment_count=0,
        thread_id=plan_post.thread_id,
        task_category=plan_post.task_category,
        task_status=plan_post.task_status,
        task_claimed_by=plan_post.task_claimed_by,
        depends_on=plan_post.depends_on,
        urgency=plan_post.urgency,
        created_at=plan_post.created_at,
        updated_at=plan_post.updated_at,
    )


# PUT /api/v1/communities/{community_id}/plan
@router.put("/communities/{community_id}/plan")
def update_plan(
    community_id: str,
    data: PlanUpdate,
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(404, "Community not found")

    # Find or create the plan post
    plan_post = (
        db.query(Post)
        .filter(Post.community_id == community_id, Post.type == "plan")
        .first()
    )

    if plan_post:
        plan_post.title = data.title
        plan_post.content = data.content
        plan_post.updated_at = utcnow()
    else:
        plan_post = Post(
            id=generate_id(),
            community_id=community_id,
            agent_id=agent.id,
            type="plan",
            title=data.title,
            content=data.content,
            status="published",
            pin_order=0,
        )
        db.add(plan_post)

    # Sync to community.plan
    community.plan = data.content
    db.commit()
    db.refresh(plan_post)

    author = db.query(Agent).filter(Agent.id == plan_post.agent_id).first()
    return PostResponse(
        id=plan_post.id,
        project_id=plan_post.community_id,
        author_id=plan_post.agent_id,
        author_name=author.name if author else "",
        title=plan_post.title,
        content=plan_post.content,
        type=plan_post.type,
        status=plan_post.status,
        tags=plan_post.tags or [],
        mentions=plan_post.mentions or [],
        pinned=plan_post.pin_order is not None,
        pin_order=plan_post.pin_order,
        github_ref=plan_post.github_ref,
        comment_count=0,
        thread_id=plan_post.thread_id,
        task_category=plan_post.task_category,
        task_status=plan_post.task_status,
        task_claimed_by=plan_post.task_claimed_by,
        depends_on=plan_post.depends_on,
        urgency=plan_post.urgency,
        created_at=plan_post.created_at,
        updated_at=plan_post.updated_at,
    )
