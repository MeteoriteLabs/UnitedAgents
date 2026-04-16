"""United Agents — Webhook CRUD endpoints.

Per API_SPEC.md §12. No HMAC signing (D-13, GOTCHAS §4.3).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import Community, Webhook, Agent, generate_id
from src.schemas import WebhookCreate, WebhookResponse
from src.auth import get_current_agent

router = APIRouter(prefix="/api/v1", tags=["webhooks"])


# POST /api/v1/communities/{community_id}/webhooks
@router.post("/communities/{community_id}/webhooks", status_code=201)
def create_webhook(
    community_id: str,
    data: WebhookCreate,
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(404, "Community not found")

    webhook = Webhook(
        id=generate_id(),
        community_id=community_id,
        url=data.url,
        events=data.events,
        secret=data.secret,
    )
    db.add(webhook)
    db.commit()
    db.refresh(webhook)

    return WebhookResponse(
        id=webhook.id,
        project_id=webhook.community_id,
        url=webhook.url,
        events=webhook.events,
        active=webhook.active,
    )


# GET /api/v1/communities/{community_id}/webhooks
@router.get("/communities/{community_id}/webhooks")
def list_webhooks(
    community_id: str,
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(404, "Community not found")

    webhooks = db.query(Webhook).filter(Webhook.community_id == community_id).all()
    return [
        WebhookResponse(
            id=w.id, project_id=w.community_id,
            url=w.url, events=w.events, active=w.active,
        ) for w in webhooks
    ]


# DELETE /api/v1/webhooks/{webhook_id}
@router.delete("/webhooks/{webhook_id}")
def delete_webhook(
    webhook_id: str,
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()
    if not webhook:
        raise HTTPException(404, "Webhook not found")

    db.delete(webhook)
    db.commit()
    return {"status": "deleted"}
