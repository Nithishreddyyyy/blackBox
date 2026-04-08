"""
WebSocket endpoint for real-time communication.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import JWTError, jwt

from app.config import settings
from app.websocket_manager import ws_manager

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(default=None),
):
    """
    WebSocket connection for real-time notifications.
    Uses 'access_token' cookie primarily, falls back to ?token= query param.
    """
    user_id: int | None = None

    # Try cookie first, then query param
    actual_token = websocket.cookies.get("access_token") or token

    if actual_token:
        try:
            payload = jwt.decode(
                actual_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            sub = payload.get("sub")
            if sub is not None:
                user_id = int(sub)
        except (JWTError, ValueError, TypeError):
            pass  # Allow anonymous connections for public displays

    await ws_manager.connect(websocket, user_id)
    try:
        while True:
            # Keep connection alive; we don't expect client messages
            # but we read to detect disconnects
            data = await websocket.receive_text()
            # Optionally handle ping/pong
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, user_id)
