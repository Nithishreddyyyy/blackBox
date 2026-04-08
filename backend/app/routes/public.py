"""
Public routes available to authenticated participants (non-admin).
"""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import User, Session, Notification
from app.schemas import SessionOut, NotificationOut
from app.auth import get_current_user

router = APIRouter(tags=["Public"])


@router.get("/sessions/active", response_model=List[SessionOut])
async def get_active_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all active sessions a participant can join."""
    return (
        await db.execute(
            select(Session)
            .filter(Session.status == "active")
            .order_by(Session.start_time.desc())
        )
    ).scalars().all()


@router.get("/notifications/recent", response_model=List[NotificationOut])
async def get_recent_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Polling endpoint for notifications (fallback if WebSocket unavailable)."""
    return (
        await db.execute(
            select(Notification)
            .order_by(Notification.created_at.desc())
            .limit(10)
        )
    ).scalars().all()


@router.get("/leaderboard/{session_id}")
async def public_leaderboard(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Public leaderboard (limited info — no prompt texts)."""
    from app.models import UserSession

    user_sessions = (
        await db.execute(
            select(UserSession)
            .options(selectinload(UserSession.user))
            .filter(UserSession.session_id == session_id)
        )
    ).scalars().all()

    entries = []
    for us in user_sessions:
        entries.append({
            "user_name": us.user.name if us.user else "Unknown",
            "prompt_count": us.prompt_count,
            "achieved_target": us.achieved_target,
            "score": us.score,
        })

    entries.sort(key=lambda e: (-e["score"], e["prompt_count"]))
    for i, entry in enumerate(entries, 1):
        entry["rank"] = i

    return {"session_id": session_id, "entries": entries}
