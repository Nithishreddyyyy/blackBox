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

    Connect with: ws://host/ws?token=<jwt_token>
    
    Messages received by clients:
      - {"type": "notification", "message": "...", "priority": "...", ...}
      - {"type": "session_update", "session_id": ..., "status": "...", "action": "..."}
      - {"type": "target_achieved", "user_id": ..., "user_name": "...", ...}
    """
    user_id = None

    # Try to authenticate via token
    if token:
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            user_id = payload.get("sub")
        except JWTError:
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
