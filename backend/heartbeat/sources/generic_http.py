"""United Agents — Generic HTTP data source.

Per AGENT_SPEC.md §10. Dot-notation path traversal for response extraction.
"""

import logging
from typing import Any, Dict, Optional

import httpx

from heartbeat.sources.base import DataSource

logger = logging.getLogger("heartbeat.sources.generic_http")


def _traverse_path(data: Any, path: str) -> Any:
    """Traverse a dot-notation path (handles nested dict + list index).
    e.g. "$.data.readings.0.temp" → data["data"]["readings"][0]["temp"]
    """
    if not path or path == "$":
        return data
    parts = path.lstrip("$.").split(".")
    current = data
    for part in parts:
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, (list, tuple)):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return current


class GenericHTTP(DataSource):
    """Admin-configured REST endpoint (GET or POST)."""

    async def fetch_latest(self, config: dict) -> Dict[str, Any]:
        try:
            url = config.get("url")
            if not url:
                return {"error": "No URL configured"}

            method = config.get("method", "GET").upper()
            headers = dict(config.get("headers", {}))
            timeout = config.get("timeout", 15)

            # Auth
            auth = config.get("auth", {})
            if auth:
                auth_type = auth.get("type", "")
                if auth_type == "api_key":
                    header_name = auth.get("header", "x-api-key")
                    headers[header_name] = auth.get("key", "")
                elif auth_type == "bearer":
                    headers["Authorization"] = f"Bearer {auth.get('token', '')}"

            async with httpx.AsyncClient(timeout=timeout) as client:
                if method == "POST":
                    body = config.get("body", {})
                    resp = await client.post(url, headers=headers, json=body)
                else:
                    resp = await client.get(url, headers=headers)

                resp.raise_for_status()
                data = resp.json()

            # Extract values via response_paths
            response_paths = config.get("response_paths", {})
            result = {}
            for key, path in response_paths.items():
                result[key] = _traverse_path(data, path)

            # Extract timestamp
            ts_path = config.get("timestamp_path")
            if ts_path:
                result["timestamp"] = _traverse_path(data, ts_path)

            return result

        except Exception as e:
            logger.warning(f"GenericHTTP fetch failed: {e}")
            return {"error": str(e)}
