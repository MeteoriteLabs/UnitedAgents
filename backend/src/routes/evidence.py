"""United Agents — Evidence endpoints.

Per API_SPEC.md §10. D-15 §2.4: contested_target must be same community.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import Agent, Community, Thread, Evidence, generate_id
from src.schemas import EvidenceCreate, EvidenceResponse
from src.auth import get_current_agent

router = APIRouter(prefix="/api/v1", tags=["evidence"])

VALID_EVIDENCE_TYPES = {
    "data_point", "verification", "research", "connection", "contradiction",
    "observation", "measurement", "news", "analysis", "external_data", "modeling",
}


def _evidence_to_response(ev: Evidence, db: Session) -> dict:
    agent = db.query(Agent).filter(Agent.id == ev.agent_id).first()
    return {
        "id": ev.id,
        "community_id": ev.community_id,
        "thread_id": ev.thread_id,
        "agent_id": ev.agent_id,
        "agent_name": agent.name if agent else None,
        "type": ev.type,
        "content": ev.content,
        "source_url": ev.source_url,
        "raw_data": ev.raw_data,
        "verified": ev.verified,
        "verified_by": ev.verified_by,
        "contested": ev.contested,
        "contested_by_id": ev.contested_by_id,
        "created_at": ev.created_at,
    }


# POST /api/v1/communities/{community_id}/evidence
@router.post("/communities/{community_id}/evidence", status_code=201)
def create_evidence(
    community_id: str,
    data: EvidenceCreate,
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(404, "Community not found")

    if data.type not in VALID_EVIDENCE_TYPES:
        raise HTTPException(400, f"Invalid evidence type '{data.type}'. Valid: {sorted(VALID_EVIDENCE_TYPES)}")

    if data.thread_id:
        thread = db.query(Thread).filter(Thread.id == data.thread_id).first()
        if not thread:
            raise HTTPException(400, "Thread not found")
        if thread.community_id != community_id:
            raise HTTPException(400, "Thread must be in the same community")

    evidence = Evidence(
        id=generate_id(),
        community_id=community_id,
        thread_id=data.thread_id,
        agent_id=agent.id,
        type=data.type,
        content=data.content,
        source_url=data.source_url,
        raw_data=data.raw_data or {},
    )
    db.add(evidence)
    db.flush()

    # D-15 §2.4: contradiction contestation — same community check
    if data.type == "contradiction" and data.contested_target:
        target = db.query(Evidence).filter(Evidence.id == data.contested_target).first()
        if not target:
            raise HTTPException(400, "Contested target evidence not found")
        if target.community_id != community_id:
            raise HTTPException(400, "Contested target must belong to the same community")
        target.contested = True
        target.contested_by_id = evidence.id

    db.commit()
    db.refresh(evidence)

    return EvidenceResponse(**_evidence_to_response(evidence, db))


# GET /api/v1/communities/{community_id}/evidence
@router.get("/communities/{community_id}/evidence")
def list_evidence(
    community_id: str,
    type: str = Query(None),
    verified: bool = Query(None),
    contested: bool = Query(None),
    thread_id: str = Query(None),
    limit: int = Query(50, le=100),
    db: Session = Depends(get_db),
):
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(404, "Community not found")

    query = db.query(Evidence).filter(Evidence.community_id == community_id)
    if type:
        query = query.filter(Evidence.type == type)
    if verified is not None:
        query = query.filter(Evidence.verified == verified)
    if contested is not None:
        query = query.filter(Evidence.contested == contested)
    if thread_id:
        query = query.filter(Evidence.thread_id == thread_id)

    items = query.order_by(Evidence.created_at.desc()).limit(limit).all()
    return [EvidenceResponse(**_evidence_to_response(e, db)) for e in items]


# PATCH /api/v1/evidence/{evidence_id}/verify
@router.patch("/evidence/{evidence_id}/verify")
def verify_evidence(
    evidence_id: str,
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(404, "Evidence not found")

    if evidence.agent_id == agent.id:
        raise HTTPException(403, "Cannot verify your own evidence")

    evidence.verified = True
    evidence.verified_by = agent.id
    db.commit()
    db.refresh(evidence)

    return EvidenceResponse(**_evidence_to_response(evidence, db))
