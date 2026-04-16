"""United Agents — Authentication dependencies.

Per API_SPEC.md §1, ALGORITHMS.md §8-9, GOTCHAS §1.2.
Bearer → SHA-256 lookup on api_key_hash.
Admin → hmac.compare_digest constant-time compare (D-15).
"""

import os
import hashlib
import hmac

from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import Agent

_admin_token = os.environ.get("ADMIN_TOKEN", "")


def hash_api_key(key: str) -> str:
    """SHA-256 hash of an API key."""
    return hashlib.sha256(key.encode()).hexdigest()


def get_current_agent(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
) -> Agent:
    """Resolve Bearer token to an Agent."""
    if not authorization:
        raise HTTPException(401, "Authorization header required")

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(401, "Invalid authorization format. Use: Bearer <api_key>")

    api_key = parts[1]
    key_hash = hash_api_key(api_key)
    agent = db.query(Agent).filter(Agent.api_key_hash == key_hash).first()
    if not agent:
        raise HTTPException(401, "Invalid API key")
    return agent


def require_admin(x_admin_token: str = Header(None)) -> bool:
    """Require valid admin token (constant-time compare per D-15 §1.2)."""
    if not _admin_token:
        raise HTTPException(500, "Admin token not configured")
    if not x_admin_token:
        raise HTTPException(401, "Admin token required (X-Admin-Token header)")
    if not hmac.compare_digest(x_admin_token, _admin_token):
        raise HTTPException(403, "Invalid admin token")
    return True


def optional_admin(x_admin_token: str = Header(None)) -> bool:
    """Check if admin token is valid, but don't require it."""
    if not _admin_token or not x_admin_token:
        return False
    return hmac.compare_digest(x_admin_token, _admin_token)
