"""
Public routes available to authenticated participants (non-admin).
"""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.models import User, Session, Notification
from app.schemas import SessionOut, NotificationOut
from app.auth import get_current_user

router = APIRouter(tags=["Public"])


@router.get("/sessions/active", response_model=List[SessionOut])
def get_active_sessions(
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """List all active sessions a participant can join."""
    return (
        db.query(Session)
        .filter(Session.status == "active")
        .order_by(Session.start_time.desc())
        .all()
    )


@router.get("/notifications/recent", response_model=List[NotificationOut])
def get_recent_notifications(
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """Polling endpoint for notifications (fallback if WebSocket unavailable)."""
    return (
        db.query(Notification)
        .order_by(Notification.created_at.desc())
        .limit(10)
        .all()
    )


@router.get("/leaderboard/{session_id}")
def public_leaderboard(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """Public leaderboard (limited info — no prompt texts)."""
    from app.models import UserSession

    user_sessions = (
        db.query(UserSession)
        .filter(UserSession.session_id == session_id)
        .all()
    )

    entries = []
    for us in user_sessions:
        user = db.query(User).filter(User.id == us.user_id).first()
        entries.append({
            "user_name": user.name if user else "Unknown",
            "prompt_count": us.prompt_count,
            "achieved_target": us.achieved_target,
            "score": us.score,
        })

    entries.sort(key=lambda e: (-e["score"], e["prompt_count"]))
    for i, entry in enumerate(entries, 1):
        entry["rank"] = i

    return {"session_id": session_id, "entries": entries}
