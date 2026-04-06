"""
WebSocket connection manager for real-time notifications.
"""

from typing import Dict, Set
from fastapi import WebSocket


class ConnectionManager:
    """Manages active WebSocket connections for broadcasting notifications."""

    def __init__(self):
        # user_id -> set of websocket connections (supports multiple tabs)
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        # connections from anonymous / all users
        self.broadcast_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket, user_id: int | None = None):
        await websocket.accept()
        self.broadcast_connections.add(websocket)
        if user_id is not None:
            if user_id not in self.active_connections:
                self.active_connections[user_id] = set()
            self.active_connections[user_id].add(websocket)

    def disconnect(self, websocket: WebSocket, user_id: int | None = None):
        self.broadcast_connections.discard(websocket)
        if user_id is not None and user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def broadcast(self, message: dict):
        """Send a message to ALL connected clients."""
        dead = []
        for ws in self.broadcast_connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.broadcast_connections.discard(ws)

    async def send_to_user(self, user_id: int, message: dict):
        """Send a message to a specific user's connections."""
        if user_id not in self.active_connections:
            return
        dead = []
        for ws in self.active_connections[user_id]:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active_connections[user_id].discard(ws)

    @property
    def connected_user_count(self) -> int:
        return len(self.active_connections)

    @property
    def connected_user_ids(self) -> list[int]:
        return list(self.active_connections.keys())


# Singleton used across the app
ws_manager = ConnectionManager()
