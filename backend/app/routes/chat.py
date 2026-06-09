"""
Chat routes: send prompt, get history.
"""

from datetime import datetime
from typing import List, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.models import User, Message, UserSession, AdminSettings, Session
from app.schemas import ChatSend, ChatResponse, ChatHistoryResponse
from app.auth import get_current_user
from app.llm_provider import generate_response
from app.config import settings
from app.websocket_manager import ws_manager

router = APIRouter(prefix="/chat", tags=["Chat"])


def _get_admin_settings(db: DBSession) -> AdminSettings:
    s = db.query(AdminSettings).first()
    if not s:
        s = AdminSettings()
        db.add(s)
        db.commit()
        db.refresh(s)
    return s


def _get_conversation_history(
    db: DBSession, user_id: int, session_id: int, limit: int = 20
) -> List[Dict[str, str]]:
    """Build conversation history for LLM context (excludes failed messages)."""
    msgs = (
        db.query(Message)
        .filter(
            Message.user_id == user_id,
            Message.session_id == session_id,
            Message.success == True,
        )
        .order_by(Message.prompt_timestamp.desc())
        .limit(limit)
        .all()
    )
    msgs.reverse()
    history = []
    for m in msgs:
        history.append({"role": "user", "content": m.prompt_text})
        if m.response_text:
            history.append({"role": "assistant", "content": m.response_text})
    return history


@router.post("/send", response_model=ChatResponse)
async def send_prompt(
    payload: ChatSend,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """Send a prompt to the LLM and get a response."""
    if current_user.role != "user":
        raise HTTPException(status_code=403, detail="Only participants can chat")

    # Validate session
    session = db.query(Session).filter(Session.id == payload.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "active":
        raise HTTPException(status_code=400, detail=f"Session is {session.status}, not active")

    # Get or create user_session
    user_session = (
        db.query(UserSession)
        .filter(
            UserSession.user_id == current_user.id,
            UserSession.session_id == payload.session_id,
        )
        .first()
    )
    if not user_session:
        user_session = UserSession(
            user_id=current_user.id,
            session_id=payload.session_id,
        )
        db.add(user_session)
        db.commit()
        db.refresh(user_session)

    # Check if already completed
    if user_session.achieved_target:
        raise HTTPException(status_code=400, detail="You have already achieved the target!")

    # Rate / message limits
    admin_settings = _get_admin_settings(db)
    if user_session.prompt_count >= admin_settings.max_messages_per_user:
        raise HTTPException(status_code=429, detail="Message limit reached")

    # Per-minute rate limit
    one_minute_ago = datetime.utcnow().replace(second=0, microsecond=0)
    recent_count = (
        db.query(Message)
        .filter(
            Message.user_id == current_user.id,
            Message.session_id == payload.session_id,
            Message.prompt_timestamp >= one_minute_ago,
        )
        .count()
    )
    if recent_count >= admin_settings.max_messages_per_minute:
        raise HTTPException(
            status_code=429, detail="Rate limit exceeded. Please wait before sending another prompt."
        )

    # Build conversation history
    history = _get_conversation_history(db, current_user.id, payload.session_id)
    session_system_prompt = session.llm_system_prompts or settings.LLM_SYSTEM_PROMPT

    # Call LLM
    prompt_ts = datetime.utcnow()
    success = True
    try:
        response_text, latency_ms = await generate_response(
            prompt=payload.prompt,
            conversation_history=history,
            system_prompt=session_system_prompt,
            provider_name=admin_settings.llm_provider,
            model=admin_settings.llm_model,
        )
    except Exception as e:
        response_text = f"[Error]: {str(e)}"
        latency_ms = 0
        success = False

    response_ts = datetime.utcnow()

    # Save message
    message = Message(
        user_id=current_user.id,
        session_id=payload.session_id,
        prompt_text=payload.prompt,
        response_text=response_text,
        prompt_timestamp=prompt_ts,
        response_timestamp=response_ts,
        latency_ms=latency_ms,
        success=success,
    )
    db.add(message)

    # Update user_session
    user_session.prompt_count += 1

    # Check if target achieved
    if settings.TARGET_OUTPUT.lower() in response_text.lower():
        user_session.achieved_target = True
        user_session.completed_at = datetime.utcnow()
        # Score: lower is better (fewer prompts + faster time)
        time_diff = (user_session.completed_at - user_session.joined_at).total_seconds()
        user_session.score = round(1000 / (user_session.prompt_count + time_diff / 60), 2)

        # Notify admins via WebSocket
        await ws_manager.broadcast({
            "type": "target_achieved",
            "user_id": current_user.id,
            "user_name": current_user.name,
            "prompt_count": user_session.prompt_count,
        })

    db.commit()
    db.refresh(message)

    return message


@router.get("/history", response_model=ChatHistoryResponse)
def get_history(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """Retrieve chat history for the current user in a given session."""
    messages = (
        db.query(Message)
        .filter(
            Message.user_id == current_user.id,
            Message.session_id == session_id,
        )
        .order_by(Message.prompt_timestamp.asc())
        .all()
    )

    admin_settings = _get_admin_settings(db)
    total_used = len(messages)
    remaining = max(0, admin_settings.max_messages_per_user - total_used)

    return ChatHistoryResponse(
        messages=messages,
        remaining_messages=remaining,
        total_used=total_used,
    )
