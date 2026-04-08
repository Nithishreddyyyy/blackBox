"""
WebSocket endpoint for real-time communication.

Fixes from UPGRADED_DEEP_REPO_AUDIT:
  - Issue 5.3: Reject anonymous WebSocket connections (instead of silently accepting)
  - Issue 9.4: Replaced pass-on-exception with structured logging
"""

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import JWTError, jwt

from app.config import settings
from app.websocket_manager import ws_manager

logger = logging.getLogger(__name__)
router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(default=None),
):
    """
    WebSocket connection for real-time notifications.
    Uses 'access_token' HttpOnly cookie.
    Falls back to ?token= query parameter for environments where cookies
    are not forwarded (e.g. wscat testing).

    Issue 5.3: Unauthenticated connections are rejected with code 1008 (Policy Violation).
    """
    user_id: int | None = None

    actual_token = websocket.cookies.get("access_token") or token

    if actual_token:
        try:
            payload = jwt.decode(
                actual_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            sub = payload.get("sub")
            if sub is not None:
                user_id = int(sub)
        except (JWTError, ValueError, TypeError) as e:
            logger.warning("WebSocket auth failed: %s", e)

    # Issue 5.3: Reject unauthenticated connections
    if user_id is None:
        await websocket.close(code=1008)
        logger.warning("WebSocket rejected: no valid token presented")
        return

    await ws_manager.connect(websocket, user_id)
    logger.info("WebSocket connected: user_id=%d", user_id)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, user_id)
        logger.info("WebSocket disconnected: user_id=%d", user_id)
