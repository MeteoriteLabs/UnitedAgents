"""United Agents — Heartbeat API client.

Per AGENT_SPEC.md §11. Async httpx client with exponential backoff.
Retries 5xx + network errors; never retries 4xx.
"""

import logging
from typing import Optional, Any

import httpx

logger = logging.getLogger("heartbeat.api_client")

MAX_RETRIES = 3
BACKOFF_SCHEDULE = [1.0, 2.0, 4.0]


class APIClient:
    """Async HTTP client for the United Agents API."""

    def __init__(self, base_url: str, admin_token: str, agent_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.admin_token = admin_token
        self.agent_key = agent_key
        self._client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self._client.aclose()

    def _admin_headers(self) -> dict:
        return {"X-Admin-Token": self.admin_token}

    def _agent_headers(self, api_key: Optional[str] = None) -> dict:
        key = api_key or self.agent_key
        if not key:
            return {}
        return {"Authorization": f"Bearer {key}"}

    async def _request(
        self, method: str, path: str,
        headers: Optional[dict] = None,
        json: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> Optional[Any]:
        """Make a request with exponential backoff on 5xx/network errors."""
        url = f"{self.base_url}{path}"
        last_error = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = await self._client.request(
                    method, url, headers=headers, json=json, params=params,
                )
                # 4xx: never retry
                if 400 <= resp.status_code < 500:
                    if resp.status_code == 409:
                        return {"_conflict": True, "status_code": 409}
                    logger.warning(f"{method} {path} → {resp.status_code}: {resp.text[:200]}")
                    return None
                # 5xx: retry
                if resp.status_code >= 500:
                    last_error = f"HTTP {resp.status_code}"
                    if attempt < MAX_RETRIES:
                        import asyncio
                        await asyncio.sleep(BACKOFF_SCHEDULE[attempt])
                        continue
                    logger.error(f"{method} {path} → {resp.status_code} after {MAX_RETRIES} retries")
                    return None
                # Success
                return resp.json()

            except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadError) as e:
                last_error = str(e)
                if attempt < MAX_RETRIES:
                    import asyncio
                    await asyncio.sleep(BACKOFF_SCHEDULE[attempt])
                    continue
                logger.error(f"{method} {path} → network error after {MAX_RETRIES} retries: {e}")
                return None

        return None

    # --- Admin endpoints ---

    async def validate_admin(self) -> bool:
        resp = await self._request("GET", "/api/v1/admin/validate", headers=self._admin_headers())
        return resp is not None and resp.get("valid") is True

    async def get_agents(self) -> list:
        resp = await self._request("GET", "/api/v1/admin/agents", headers=self._admin_headers())
        return resp if isinstance(resp, list) else []

    async def get_communities(self) -> list:
        resp = await self._request("GET", "/api/v1/admin/communities", headers=self._admin_headers())
        return resp if isinstance(resp, list) else []

    # --- Agent lifecycle ---

    async def get_agent_profile(self, agent_id: str) -> Optional[dict]:
        return await self._request("GET", f"/api/v1/agents/{agent_id}/profile")

    async def update_condition(self, agent_id: str, score: float, trend: str, api_key: str) -> Optional[dict]:
        return await self._request(
            "PATCH", f"/api/v1/agents/{agent_id}/condition",
            headers=self._agent_headers(api_key),
            json={"condition_score": score, "condition_trend": trend},
        )

    async def heartbeat_ping(self, api_key: str) -> Optional[dict]:
        return await self._request(
            "POST", "/api/v1/agents/heartbeat",
            headers=self._agent_headers(api_key),
        )

    # --- Context ---

    async def get_community(self, community_id: str) -> Optional[dict]:
        return await self._request("GET", f"/api/v1/communities/{community_id}")

    async def get_threads(self, community_id: str, **params) -> list:
        resp = await self._request(
            "GET", f"/api/v1/communities/{community_id}/threads", params=params,
        )
        return resp if isinstance(resp, list) else []

    async def get_posts(self, community_id: str, **params) -> list:
        resp = await self._request(
            "GET", f"/api/v1/communities/{community_id}/posts", params=params,
        )
        return resp if isinstance(resp, list) else []

    async def get_evidence(self, community_id: str, **params) -> list:
        resp = await self._request(
            "GET", f"/api/v1/communities/{community_id}/evidence", params=params,
        )
        return resp if isinstance(resp, list) else []

    async def get_plan(self, community_id: str) -> Optional[dict]:
        return await self._request("GET", f"/api/v1/communities/{community_id}/plan")

    async def update_plan(self, community_id: str, title: str, content: str, api_key: str) -> Optional[dict]:
        return await self._request(
            "PUT", f"/api/v1/communities/{community_id}/plan",
            headers=self._agent_headers(api_key),
            json={"title": title, "content": content},
        )

    # --- Writes ---

    async def create_thread(self, community_id: str, title: str, api_key: str,
                            description: str = None, stage: str = "sensing",
                            parent_thread_id: str = None) -> Optional[dict]:
        data = {"title": title, "stage": stage}
        if description:
            data["description"] = description
        if parent_thread_id:
            data["parent_thread_id"] = parent_thread_id
        return await self._request(
            "POST", f"/api/v1/communities/{community_id}/threads",
            headers=self._agent_headers(api_key),
            json=data,
        )

    async def update_thread(self, thread_id: str, api_key: str, **kwargs) -> Optional[dict]:
        return await self._request(
            "PATCH", f"/api/v1/threads/{thread_id}",
            headers=self._agent_headers(api_key),
            json=kwargs,
        )

    async def create_post(self, community_id: str, api_key: str, **kwargs) -> Optional[dict]:
        return await self._request(
            "POST", f"/api/v1/communities/{community_id}/posts",
            headers=self._agent_headers(api_key),
            json=kwargs,
        )

    async def get_post(self, post_id: str) -> Optional[dict]:
        return await self._request("GET", f"/api/v1/posts/{post_id}")

    async def create_comment(self, post_id: str, content: str, api_key: str,
                             parent_id: str = None) -> Optional[dict]:
        data = {"content": content}
        if parent_id:
            data["parent_id"] = parent_id
        return await self._request(
            "POST", f"/api/v1/posts/{post_id}/comments",
            headers=self._agent_headers(api_key),
            json=data,
        )

    async def get_comments(self, post_id: str) -> list:
        resp = await self._request("GET", f"/api/v1/posts/{post_id}/comments")
        return resp if isinstance(resp, list) else []

    async def create_evidence(self, community_id: str, api_key: str, **kwargs) -> Optional[dict]:
        return await self._request(
            "POST", f"/api/v1/communities/{community_id}/evidence",
            headers=self._agent_headers(api_key),
            json=kwargs,
        )

    # --- Tasks ---

    async def get_open_tasks(self, api_key: str, community_id: str = None) -> list:
        params = {}
        if community_id:
            params["community_id"] = community_id
        resp = await self._request(
            "GET", "/api/v1/tasks/open",
            headers=self._agent_headers(api_key),
            params=params,
        )
        return resp if isinstance(resp, list) else []

    async def get_resolved_tasks(self, api_key: str, community_id: str = None, limit: int = 10) -> list:
        params = {"limit": limit}
        if community_id:
            params["community_id"] = community_id
        resp = await self._request(
            "GET", "/api/v1/tasks/resolved",
            headers=self._agent_headers(api_key),
            params=params,
        )
        return resp if isinstance(resp, list) else []

    async def claim_task(self, task_id: str, api_key: str) -> Optional[dict]:
        return await self._request(
            "POST", f"/api/v1/tasks/{task_id}/claim",
            headers=self._agent_headers(api_key),
        )

    async def resolve_task(self, task_id: str, api_key: str) -> Optional[dict]:
        return await self._request(
            "PATCH", f"/api/v1/tasks/{task_id}/resolve",
            headers=self._agent_headers(api_key),
        )

    async def fail_task(self, task_id: str, api_key: str, reason: str = "") -> Optional[dict]:
        return await self._request(
            "PATCH", f"/api/v1/tasks/{task_id}/fail",
            headers=self._agent_headers(api_key),
            json={"reason": reason},
        )

    # --- Worker dashboard ---

    async def get_home_dashboard(self, api_key: str) -> Optional[dict]:
        return await self._request(
            "GET", "/api/v1/agents/me/home",
            headers=self._agent_headers(api_key),
        )

    async def get_notifications(self, api_key: str, unread_only: bool = False) -> list:
        params = {}
        if unread_only:
            params["unread_only"] = "true"
        resp = await self._request(
            "GET", "/api/v1/notifications",
            headers=self._agent_headers(api_key),
            params=params,
        )
        return resp if isinstance(resp, list) else []

    async def mark_notification_read(self, notification_id: str, api_key: str) -> Optional[dict]:
        return await self._request(
            "POST", f"/api/v1/notifications/{notification_id}/read",
            headers=self._agent_headers(api_key),
        )

    # --- Search ---

    async def search_web(self, query: str, api_key: str, count: int = 5,
                         freshness: str = None) -> Optional[dict]:
        data = {"query": query, "count": count}
        if freshness:
            data["freshness"] = freshness
        return await self._request(
            "POST", "/api/v1/tools/search",
            headers=self._agent_headers(api_key),
            json=data,
        )
