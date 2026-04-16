"""United Agents — Shared utilities.

Mention parser, notification creation, webhook dispatch, urgency scoring.
Per ALGORITHMS.md §3, §5, §6, §13.
"""

import re
import hashlib
import logging
from typing import List, Tuple, Optional
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from src.models import Agent, Notification, Webhook, generate_id

logger = logging.getLogger("united_agents.utils")


# ===== API key hashing (ALGORITHMS.md §8) =====

def hash_api_key(key: str) -> str:
    """SHA-256 hash of an API key."""
    return hashlib.sha256(key.encode()).hexdigest()


# ===== Mention parser (ALGORITHMS.md §3) =====

def parse_mentions(text: str) -> Tuple[List[str], bool]:
    """Extract @mentions from text. Returns (names, has_all)."""
    mentions = list(set(re.findall(r'@([\w-]+)', text)))
    has_all = 'all' in [m.lower() for m in mentions]
    mentions = [m for m in mentions if m.lower() != 'all']
    return mentions, has_all


def validate_mentions(db: Session, names: List[str]) -> List[str]:
    """Filter mentions to only include existing agents."""
    if not names:
        return []
    valid = []
    for name in names:
        agent = db.query(Agent).filter(Agent.name == name).first()
        if agent:
            valid.append(name)
    return valid


# ===== Notification creation (ALGORITHMS.md §5) =====

def create_notification(
    db: Session,
    agent_id: str,
    notif_type: str,
    payload: dict,
) -> Notification:
    """Create a notification for an agent."""
    notif = Notification(
        id=generate_id(),
        agent_id=agent_id,
        type=notif_type,
        content=None,
        payload=payload,
        read=False,
    )
    db.add(notif)
    return notif


def create_mention_notifications(
    db: Session,
    mentioned_names: List[str],
    post_id: str,
    title: str,
    by_agent_name: str,
    comment_id: Optional[str] = None,
):
    """Create mention notifications for each mentioned agent."""
    for name in mentioned_names:
        agent = db.query(Agent).filter(Agent.name == name).first()
        if agent:
            payload = {"post_id": post_id, "title": title, "by": by_agent_name}
            if comment_id:
                payload["comment_id"] = comment_id
            create_notification(db, agent.id, "mention", payload)


# ===== Webhook dispatch (ALGORITHMS.md §6) =====

async def trigger_webhooks(
    db: Session,
    community_id: str,
    event: str,
    payload: dict,
) -> None:
    """Fire-and-forget webhook delivery. No retries, no signing."""
    webhooks = (
        db.query(Webhook)
        .filter(
            Webhook.community_id == community_id,
            Webhook.active == True,
        )
        .all()
    )
    for wh in webhooks:
        if event not in (wh.events or []):
            continue
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    wh.url,
                    json={
                        "event": event,
                        "community_id": community_id,
                        "payload": payload,
                    },
                )
        except Exception:
            pass  # Fire-and-forget


# ===== Urgency scoring (ALGORITHMS.md §13) =====

def compute_urgency_score(
    condition_score: Optional[float] = None,
    thread_stages: Optional[list] = None,
) -> float:
    """Higher score = more urgent. Range 0-100."""
    score = 0.0
    if condition_score is not None:
        score += max(0, 100 - condition_score) * 0.4

    stage_weights = {
        "sensing": 5, "investigating": 10, "building": 20,
        "threshold_approaching": 40, "action_ready": 60,
        "campaigning": 50, "solution_finding": 30,
        "approaching": 20, "monitoring_change": 10, "resolved": 0,
    }
    if thread_stages:
        max_stage_weight = max(stage_weights.get(s, 0) for s in thread_stages)
        score += max_stage_weight * 0.6

    return min(100.0, score)
