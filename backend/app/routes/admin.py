"""
Admin routes: stats, user management, settings, notifications, leaderboard, sessions, logs.
"""

from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession

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

router = APIRouter(prefix="/admin", tags=["Admin"])


# ── Helpers ──────────────────────────────────────────────

def _get_admin_settings(db: DBSession) -> AdminSettings:
    s = db.query(AdminSettings).first()
    if not s:
        s = AdminSettings()
        db.add(s)
        db.commit()
        db.refresh(s)
    return s


# ── Dashboard Stats ────────────────────────────────────

@router.get("/stats", response_model=AdminStatsResponse)
def get_stats(
    admin: User = Depends(require_admin),
    db: DBSession = Depends(get_db),
):
    """Real-time dashboard statistics."""
    total_users = db.query(User).filter(User.role == "user").count()
    active_sessions = db.query(Session).filter(Session.status == "active").count()
    total_messages = db.query(Message).count()

    # Active users = users who sent a message in the last 5 minutes
    five_min_ago = datetime.utcnow() - timedelta(minutes=5)
    active_users = (
        db.query(func.count(func.distinct(Message.user_id)))
        .filter(Message.prompt_timestamp >= five_min_ago)
        .scalar()
    )

    one_min_ago = datetime.utcnow() - timedelta(minutes=1)
    messages_last_minute = (
        db.query(Message).filter(Message.prompt_timestamp >= one_min_ago).count()
    )

    return AdminStatsResponse(
        total_users=total_users,
        active_sessions=active_sessions,
        total_messages=total_messages,
        active_users=active_users or 0,
        messages_last_minute=messages_last_minute,
    )


# ── User Management ─────────────────────────────────────

@router.get("/users", response_model=List[UserOut])
def list_users(
    admin: User = Depends(require_admin),
    db: DBSession = Depends(get_db),
):
    """List all registered users."""
    return db.query(User).order_by(User.created_at.desc()).all()


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(
    payload: UserRegister,
    admin: User = Depends(require_admin),
    db: DBSession = Depends(get_db),
):
    """Admin creates a new user (pre-registration before event)."""
    if db.query(User).filter(User.email == payload.email).first():
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
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: DBSession = Depends(get_db),
):
    """Delete a user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role == "admin":
        raise HTTPException(status_code=400, detail="Cannot delete admin accounts")

    db.add(AuditLog(
        actor_id=admin.id,
        action_type="delete_user",
        action_data={"user_id": user_id, "email": user.email},
    ))
    db.delete(user)
    db.commit()
    return {"detail": "User deleted"}


# ── Admin Settings ───────────────────────────────────────

@router.get("/settings", response_model=AdminSettingsOut)
def get_settings(
    admin: User = Depends(require_admin),
    db: DBSession = Depends(get_db),
):
    return _get_admin_settings(db)


@router.post("/settings", response_model=AdminSettingsOut)
def update_settings(
    payload: AdminSettingsUpdate,
    admin: User = Depends(require_admin),
    db: DBSession = Depends(get_db),
):
    """Update competition settings."""
    s = _get_admin_settings(db)
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(s, key, value)

    db.add(AuditLog(
        actor_id=admin.id,
        action_type="update_settings",
        action_data=update_data,
    ))
    db.commit()
    db.refresh(s)
    return s


# ── Sessions ─────────────────────────────────────────────

@router.get("/sessions", response_model=List[SessionOut])
def list_sessions(
    admin: User = Depends(require_admin),
    db: DBSession = Depends(get_db),
):
    return db.query(Session).order_by(Session.id.desc()).all()


@router.post("/sessions", response_model=SessionOut, status_code=201)
def create_session(
    payload: SessionCreate,
    admin: User = Depends(require_admin),
    db: DBSession = Depends(get_db),
):
    session = Session(session_name=payload.session_name)
    db.add(session)
    db.add(AuditLog(
        actor_id=admin.id,
        action_type="create_session",
        action_data={"session_name": payload.session_name},
    ))
    db.commit()
    db.refresh(session)
    return session


@router.post("/sessions/{session_id}/action", response_model=SessionOut)
async def session_action(
    session_id: int,
    payload: SessionAction,
    admin: User = Depends(require_admin),
    db: DBSession = Depends(get_db),
):
    """Start, pause, resume, or end a session."""
    session = db.query(Session).filter(Session.id == session_id).first()
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

    if action == "start" or action == "resume":
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
    db.commit()
    db.refresh(session)

    # Broadcast session state change
    await ws_manager.broadcast({
        "type": "session_update",
        "session_id": session.id,
        "status": session.status,
        "action": action,
    })

    return session


@router.get("/sessions/{session_id}/participants", response_model=List[UserSessionOut])
def session_participants(
    session_id: int,
    admin: User = Depends(require_admin),
    db: DBSession = Depends(get_db),
):
    """List all participants in a session with their stats."""
    user_sessions = (
        db.query(UserSession)
        .filter(UserSession.session_id == session_id)
        .all()
    )
    results = []
    for us in user_sessions:
        user = db.query(User).filter(User.id == us.user_id).first()
        entry = UserSessionOut(
            id=us.id,
            user_id=us.user_id,
            session_id=us.session_id,
            joined_at=us.joined_at,
            completed_at=us.completed_at,
            score=us.score,
            achieved_target=us.achieved_target,
            prompt_count=us.prompt_count,
            user_name=user.name if user else None,
            user_email=user.email if user else None,
        )
        results.append(entry)
    return results


@router.post("/sessions/{session_id}/reset/{user_id}")
def reset_user_session(
    session_id: int,
    user_id: int,
    admin: User = Depends(require_admin),
    db: DBSession = Depends(get_db),
):
    """Reset a user's session (clear messages and stats)."""
    user_session = (
        db.query(UserSession)
        .filter(UserSession.user_id == user_id, UserSession.session_id == session_id)
        .first()
    )
    if not user_session:
        raise HTTPException(status_code=404, detail="User session not found")

    # Delete messages
    db.query(Message).filter(
        Message.user_id == user_id, Message.session_id == session_id
    ).delete()

    # Reset stats
    user_session.prompt_count = 0
    user_session.achieved_target = False
    user_session.completed_at = None
    user_session.score = 0.0

    db.add(AuditLog(
        actor_id=admin.id,
        action_type="reset_user_session",
        action_data={"user_id": user_id, "session_id": session_id},
    ))
    db.commit()
    return {"detail": "User session reset"}


# ── Notifications ────────────────────────────────────────

@router.post("/notify", response_model=NotificationOut, status_code=201)
async def send_notification(
    payload: NotificationCreate,
    admin: User = Depends(require_admin),
    db: DBSession = Depends(get_db),
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
    db.commit()
    db.refresh(notification)

    # Broadcast via WebSocket
    await ws_manager.broadcast({
        "type": "notification",
        "id": notification.id,
        "message": notification.message,
        "priority": notification.priority,
        "created_at": notification.created_at.isoformat(),
    })

    return notification


@router.get("/notifications", response_model=List[NotificationOut])
def list_notifications(
    admin: User = Depends(require_admin),
    db: DBSession = Depends(get_db),
):
    return db.query(Notification).order_by(Notification.created_at.desc()).limit(50).all()


# ── Leaderboard ──────────────────────────────────────────

@router.get("/leaderboard/{session_id}", response_model=LeaderboardResponse)
def get_leaderboard(
    session_id: int,
    admin: User = Depends(require_admin),
    db: DBSession = Depends(get_db),
):
    """Leaderboard for a specific session."""
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    user_sessions = (
        db.query(UserSession)
        .filter(UserSession.session_id == session_id)
        .all()
    )

    entries = []
    for us in user_sessions:
        user = db.query(User).filter(User.id == us.user_id).first()
        completion_time = None
        if us.completed_at and us.joined_at:
            completion_time = (us.completed_at - us.joined_at).total_seconds()

        entries.append(LeaderboardEntry(
            rank=0,  # will be set after sorting
            user_id=us.user_id,
            user_name=user.name if user else "Unknown",
            prompt_count=us.prompt_count,
            achieved_target=us.achieved_target,
            completion_time_seconds=completion_time,
            score=us.score,
        ))

    # Sort: achieved_target first, then by score descending, then by fewer prompts
    entries.sort(
        key=lambda e: (
            not e.achieved_target,  # True first
            -e.score,
            e.prompt_count,
            e.completion_time_seconds or float("inf"),
        )
    )

    for i, entry in enumerate(entries, 1):
        entry.rank = i

    return LeaderboardResponse(
        session_id=session_id,
        session_name=session.session_name,
        entries=entries,
    )


# ── Prompt Logs ──────────────────────────────────────────

@router.get("/messages/{session_id}")
def get_session_messages(
    session_id: int,
    user_id: int | None = None,
    admin: User = Depends(require_admin),
    db: DBSession = Depends(get_db),
):
    """View all messages in a session, optionally filtered by user."""
    query = db.query(Message).filter(Message.session_id == session_id)
    if user_id:
        query = query.filter(Message.user_id == user_id)
    messages = query.order_by(Message.prompt_timestamp.asc()).all()

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
def get_audit_logs(
    limit: int = 100,
    admin: User = Depends(require_admin),
    db: DBSession = Depends(get_db),
):
    return db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
