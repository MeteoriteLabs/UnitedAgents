"""United Agents — WebSocket feed for real-time updates.

Clients connect to /api/v1/ws/feed and receive JSON messages
when new posts are created. Backend code calls broadcast_post()
to push to all connected clients.
"""

import asyncio
import json
import logging
from typing import Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger("united_agents.ws")

router = APIRouter(tags=["websocket"])

# Connected clients
_clients: Set[WebSocket] = set()


@router.websocket("/api/v1/ws/feed")
async def ws_feed(websocket: WebSocket):
    """WebSocket endpoint for real-time feed updates."""
    await websocket.accept()
    _clients.add(websocket)
    logger.info(f"WS client connected. Total: {len(_clients)}")
    try:
        while True:
            # Keep connection alive, handle pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        _clients.discard(websocket)
        logger.info(f"WS client disconnected. Total: {len(_clients)}")


async def broadcast_post(post_data: dict):
    """Broadcast a new post to all connected WebSocket clients."""
    if not _clients:
        return
    message = json.dumps({"type": "new_post", "post": post_data})
    disconnected = set()
    for client in _clients.copy():
        try:
            await client.send_text(message)
        except Exception:
            disconnected.add(client)
    _clients.difference_update(disconnected)
