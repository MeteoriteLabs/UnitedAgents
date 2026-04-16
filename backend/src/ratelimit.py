"""United Agents — Sliding-window rate limiter.

Per ALGORITHMS.md §4. In-memory, per-agent.
"""

import time
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

from fastapi import HTTPException
from fastapi.responses import JSONResponse


DEFAULT_LIMITS: Dict[str, Tuple[int, int]] = {
    "post":      (10, 60),
    "comment":   (60, 60),
    "register":  (5, 3600),
    "claim":     (20, 3600),
    "search":    (60, 3600),
    "heartbeat": (30, 60),
}


class RateLimiter:
    def __init__(self):
        self.history: Dict[str, List[Tuple[float, str]]] = defaultdict(list)
        self.limits = dict(DEFAULT_LIMITS)

    def _get_limit(self, action: str) -> Tuple[int, int]:
        return self.limits.get(action, (100, 60))

    def check(self, agent_id: str, action: str) -> bool:
        """Check if action is allowed. Returns True if OK, False if rate-limited."""
        limit, window = self._get_limit(action)
        now = time.time()
        self.history[agent_id] = [
            (ts, a) for ts, a in self.history[agent_id]
            if ts > now - window
        ]
        count = sum(1 for ts, a in self.history[agent_id] if a == action)
        if count >= limit:
            return False
        self.history[agent_id].append((now, action))
        return True

    def get_retry_after(self, agent_id: str, action: str) -> int:
        """Get seconds until the rate limit resets for this action."""
        limit, window = self._get_limit(action)
        now = time.time()
        entries = sorted(
            [ts for ts, a in self.history.get(agent_id, []) if a == action]
        )
        if not entries:
            return 0
        return max(1, int(entries[0] + window - now))

    def get_status(self, agent_id: str) -> dict:
        """Get rate limit status for all actions."""
        now = time.time()
        result = {}
        for action, (limit, window) in self.limits.items():
            entries = [
                ts for ts, a in self.history.get(agent_id, [])
                if a == action and ts > now - window
            ]
            used = len(entries)
            oldest = min(entries) if entries else now
            reset_in = max(0, int(oldest + window - now)) if entries else 0
            result[action] = {
                "used": used,
                "limit": limit,
                "window_seconds": window,
                "remaining": max(0, limit - used),
                "reset_in_seconds": reset_in,
            }
        return result


def check_rate_limit(limiter: "RateLimiter", agent_id: str, action: str):
    """Raise 429 if rate-limited."""
    if not limiter.check(agent_id, action):
        retry_after = limiter.get_retry_after(agent_id, action)
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded for '{action}'",
            headers={"Retry-After": str(retry_after)},
        )


# Global instance
rate_limiter = RateLimiter()
