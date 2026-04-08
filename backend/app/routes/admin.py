"""
Admin routes: stats, user management, settings, notifications, leaderboard, sessions, logs.

Fixes from UPGRADED_DEEP_REPO_AUDIT:
  - Issue 3.4: Fixed broken admin stats queries (select_from correct tables)
  - Issue 3.3: Leaderboard sort moved to SQL ORDER BY instead of Python sort
  - Issue 5.7: Removed duplicate `func` import
  - Issue 3.5: _get_admin_settings moved to app.crud
  - Issue 9.4: Replaced print() with structured logging
"""

import logging
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, asc, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.crud import get_admin_settings
from app.database import get_db
from app.models import (
    User,
    Session,
    UserSession,
    Message,
    AdminSettings,
    Notification,
    AuditLog,
)
from app.schemas import (
    AdminSettingsUpdate,
    AdminSettingsOut,
    AdminStatsResponse,
    UserOut,
    NotificationCreate,
    NotificationOut,
    LeaderboardResponse,
    LeaderboardEntry,
    SessionCreate,
    SessionOut,
    SessionAction,
    UserSessionOut,
    AuditLogOut,
    UserRegister,
)
from app.auth import require_admin, hash_password
from app.websocket_manager import ws_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["Admin"])


# ── Dashboard Stats ────────────────────────────────────

@router.get("/stats", response_model=AdminStatsResponse)
async def get_stats(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Real-time dashboard statistics."""

    # Issue 3.4 Fix: select_from the correct table for each count
    total_users = (
        await db.execute(
            select(func.count()).select_from(User).filter(User.role == "user")
        )
    ).scalar()

    active_sessions = (
        await db.execute(
            select(func.count()).select_from(Session).filter(Session.status == "active")
        )
    ).scalar()

    total_messages = (
        await db.execute(select(func.count()).select_from(Message))
    ).scalar()

    five_min_ago = datetime.utcnow() - timedelta(minutes=5)
    active_users = (
        await db.execute(
            select(func.count(func.distinct(Message.user_id))).filter(
                Message.prompt_timestamp >= five_min_ago
            )
        )
    ).scalar()

    one_min_ago = datetime.utcnow() - timedelta(minutes=1)
    messages_last_minute = (
        await db.execute(
            select(func.count()).select_from(Message).filter(
                Message.prompt_timestamp >= one_min_ago
            )
        )
    ).scalar()

    return AdminStatsResponse(
        total_users=total_users or 0,
        active_sessions=active_sessions or 0,
        total_messages=total_messages or 0,
        active_users=active_users or 0,
        messages_last_minute=messages_last_minute or 0,
    )


# ── User Management ─────────────────────────────────────

@router.get("/users", response_model=List[UserOut])
async def list_users(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all registered users."""
    return (
        await db.execute(select(User).order_by(User.created_at.desc()))
    ).scalars().all()


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(
    payload: UserRegister,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin creates a new user (pre-registration before event)."""
    if (await db.execute(select(User).filter(User.email == payload.email))).scalars().first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role="user",
    )
    db.add(user)
    db.add(AuditLog(
        actor_id=admin.id,
        action_type="create_user",
        action_data={"email": payload.email, "name": payload.name},
    ))
    await db.commit()
    await db.refresh(user)
    logger.info("Admin %s created user %s", admin.email, payload.email)
    return user


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete a user and all their related data (cascades via ORM)."""
    user = (await db.execute(select(User).filter(User.id == user_id))).scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role == "admin":
        raise HTTPException(status_code=400, detail="Cannot delete admin accounts")

    db.add(AuditLog(
        actor_id=admin.id,
        action_type="delete_user",
        action_data={"user_id": user_id, "email": user.email},
    ))
    await db.delete(user)
    await db.commit()
    logger.info("Admin %s deleted user_id=%d", admin.email, user_id)
    return {"detail": "User deleted"}


# ── Admin Settings ───────────────────────────────────────

@router.get("/settings", response_model=AdminSettingsOut)
async def get_settings(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await get_admin_settings(db)


@router.post("/settings", response_model=AdminSettingsOut)
async def update_settings(
    payload: AdminSettingsUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update competition settings."""
    s = await get_admin_settings(db)
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(s, key, value)

    db.add(AuditLog(
        actor_id=admin.id,
        action_type="update_settings",
        action_data=update_data,
    ))
    await db.commit()
    await db.refresh(s)
    logger.info("Admin %s updated settings: %s", admin.email, update_data)
    return s


# ── Sessions ─────────────────────────────────────────────

@router.get("/sessions", response_model=List[SessionOut])
async def list_sessions(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return (await db.execute(select(Session).order_by(Session.id.desc()))).scalars().all()


@router.post("/sessions", response_model=SessionOut, status_code=201)
async def create_session(
    payload: SessionCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    session = Session(session_name=payload.session_name)
    db.add(session)
    db.add(AuditLog(
        actor_id=admin.id,
        action_type="create_session",
        action_data={"session_name": payload.session_name},
    ))
    await db.commit()
    await db.refresh(session)
    logger.info("Admin %s created session '%s'", admin.email, payload.session_name)
    return session


@router.post("/sessions/{session_id}/action", response_model=SessionOut)
async def session_action(
    session_id: int,
    payload: SessionAction,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Start, pause, resume, or end a session."""
    session = (
        await db.execute(select(Session).filter(Session.id == session_id))
    ).scalars().first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    action = payload.action.lower()
    valid_transitions = {
        "start": {"pending", "paused"},
        "pause": {"active"},
        "resume": {"paused"},
        "end": {"active", "paused", "pending"},
    }

    if action not in valid_transitions:
        raise HTTPException(status_code=400, detail=f"Invalid action: {action}")
    if session.status not in valid_transitions[action]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot {action} a session in '{session.status}' status",
        )

    if action in ("start", "resume"):
        session.status = "active"
        if action == "start":
            session.start_time = datetime.utcnow()
    elif action == "pause":
        session.status = "paused"
    elif action == "end":
        session.status = "completed"
        session.end_time = datetime.utcnow()

    db.add(AuditLog(
        actor_id=admin.id,
        action_type=f"session_{action}",
        action_data={"session_id": session_id},
    ))
    await db.commit()
    await db.refresh(session)

    await ws_manager.broadcast({
        "type": "session_update",
        "session_id": session.id,
        "status": session.status,
        "action": action,
    })
    logger.info("Admin %s performed '%s' on session_id=%d", admin.email, action, session_id)
    return session


@router.get("/sessions/{session_id}/participants", response_model=List[UserSessionOut])
async def session_participants(
    session_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all participants in a session with their stats."""
    user_sessions = (
        await db.execute(
            select(UserSession)
            .options(selectinload(UserSession.user))
            .filter(UserSession.session_id == session_id)
        )
    ).scalars().all()

    return [
        UserSessionOut(
            id=us.id,
            user_id=us.user_id,
            session_id=us.session_id,
            joined_at=us.joined_at,
            completed_at=us.completed_at,
            score=us.score,
            achieved_target=us.achieved_target,
            prompt_count=us.prompt_count,
            user_name=us.user.name if us.user else None,
            user_email=us.user.email if us.user else None,
        )
        for us in user_sessions
    ]


@router.post("/sessions/{session_id}/reset/{user_id}")
async def reset_user_session(
    session_id: int,
    user_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Reset a user's session (clear messages and stats)."""
    user_session = (await db.execute(
        select(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.session_id == session_id,
        )
    )).scalars().first()

    if not user_session:
        raise HTTPException(status_code=404, detail="User session not found")

    await db.execute(
        Message.__table__.delete().where(
            Message.user_id == user_id,
            Message.session_id == session_id,
        )
    )

    user_session.prompt_count = 0
    user_session.achieved_target = False
    user_session.completed_at = None
    user_session.score = 0.0

    db.add(AuditLog(
        actor_id=admin.id,
        action_type="reset_user_session",
        action_data={"user_id": user_id, "session_id": session_id},
    ))
    await db.commit()
    logger.info("Admin %s reset user_id=%d in session_id=%d", admin.email, user_id, session_id)
    return {"detail": "User session reset"}


# ── Notifications ────────────────────────────────────────

@router.post("/notify", response_model=NotificationOut, status_code=201)
async def send_notification(
    payload: NotificationCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Broadcast a notification to all participants."""
    notification = Notification(
        message=payload.message,
        priority=payload.priority,
        created_by=admin.id,
    )
    db.add(notification)
    db.add(AuditLog(
        actor_id=admin.id,
        action_type="broadcast_notification",
        action_data={"message": payload.message, "priority": payload.priority},
    ))
    await db.commit()
    await db.refresh(notification)

    await ws_manager.broadcast({
        "type": "notification",
        "id": notification.id,
        "message": notification.message,
        "priority": notification.priority,
        "created_at": notification.created_at.isoformat(),
    })

    logger.info("Admin %s broadcast notification id=%d", admin.email, notification.id)
    return notification


@router.get("/notifications", response_model=List[NotificationOut])
async def list_notifications(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return (
        await db.execute(
            select(Notification).order_by(Notification.created_at.desc()).limit(50)
        )
    ).scalars().all()


# ── Leaderboard (Issue 3.3: Sort in SQL, not Python) ─────

@router.get("/leaderboard/{session_id}", response_model=LeaderboardResponse)
async def get_leaderboard(
    session_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Leaderboard for a specific session — sorted by SQL ORDER BY."""
    session = (
        await db.execute(select(Session).filter(Session.id == session_id))
    ).scalars().first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Issue 3.3: Use DB-level ordering instead of Python sort
    user_sessions = (
        await db.execute(
            select(UserSession)
            .options(selectinload(UserSession.user))
            .filter(UserSession.session_id == session_id)
            .order_by(
                desc(UserSession.achieved_target),
                desc(UserSession.score),
                asc(UserSession.prompt_count),
                asc(UserSession.completed_at),
            )
        )
    ).scalars().all()

    entries = []
    for rank, us in enumerate(user_sessions, 1):
        completion_time = None
        if us.completed_at and us.joined_at:
            completion_time = (us.completed_at - us.joined_at).total_seconds()
        entries.append(LeaderboardEntry(
            rank=rank,
            user_id=us.user_id,
            user_name=us.user.name if us.user else "Unknown",
            prompt_count=us.prompt_count,
            achieved_target=us.achieved_target,
            completion_time_seconds=completion_time,
            score=us.score,
        ))

    return LeaderboardResponse(
        session_id=session_id,
        session_name=session.session_name,
        entries=entries,
    )


# ── Prompt Logs ──────────────────────────────────────────

@router.get("/messages/{session_id}")
async def get_session_messages(
    session_id: int,
    user_id: int | None = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """View all messages in a session, optionally filtered by user."""
    query = select(Message).filter(Message.session_id == session_id)
    if user_id:
        query = query.filter(Message.user_id == user_id)
    query = query.order_by(Message.prompt_timestamp.asc())
    messages = (await db.execute(query)).scalars().all()

    return [
        {
            "id": m.id,
            "user_id": m.user_id,
            "prompt_text": m.prompt_text,
            "response_text": m.response_text,
            "prompt_timestamp": m.prompt_timestamp.isoformat() if m.prompt_timestamp else None,
            "response_timestamp": m.response_timestamp.isoformat() if m.response_timestamp else None,
            "latency_ms": m.latency_ms,
            "success": m.success,
        }
        for m in messages
    ]


# ── Audit Logs ───────────────────────────────────────────

@router.get("/audit-logs", response_model=List[AuditLogOut])
async def get_audit_logs(
    limit: int = 100,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return (
        await db.execute(
            select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        )
    ).scalars().all()
