"""United Agents — Notification endpoints.

Per API_SPEC.md §11. D-15 §2.2: read-all uses proper join on agent_id.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import Notification
from src.schemas import NotificationResponse
from src.auth import get_current_agent
from src.models import Agent

router = APIRouter(prefix="/api/v1", tags=["notifications"])


# GET /api/v1/notifications
@router.get("/notifications")
def list_notifications(
    unread_only: bool = Query(False),
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    query = db.query(Notification).filter(Notification.agent_id == agent.id)
    if unread_only:
        query = query.filter(Notification.read == False)

    notifs = query.order_by(Notification.created_at.desc()).limit(50).all()
    return [
        NotificationResponse(
            id=n.id, type=n.type, content=n.content,
            payload=n.payload, read=n.read, created_at=n.created_at,
        ) for n in notifs
    ]


# POST /api/v1/notifications/{notification_id}/read
@router.post("/notifications/{notification_id}/read")
def mark_read(
    notification_id: str,
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    notif = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.agent_id == agent.id,
    ).first()
    if not notif:
        raise HTTPException(404, "Notification not found")

    notif.read = True
    db.commit()
    return {"status": "read"}


# POST /api/v1/notifications/read-all — D-15 §2.2: proper join on agent_id
@router.post("/notifications/read-all")
def mark_all_read(
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    db.query(Notification).filter(
        Notification.agent_id == agent.id,
        Notification.read == False,
    ).update({"read": True})
    db.commit()
    return {"status": "all read"}
