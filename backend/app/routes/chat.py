"""
Chat routes: send prompt, get history.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session as DBSession

from app.database import SessionLocal, get_db
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


def _prepare_prompt_context(user_id: int, session_id: int) -> Dict[str, Any]:
    """Validate the request and gather LLM context in a short-lived DB session."""
    db = SessionLocal()
    try:
        session = db.query(Session).filter(Session.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if session.status != "active":
            raise HTTPException(
                status_code=400,
                detail=f"Session is {session.status}, not active",
            )

        user_session = (
            db.query(UserSession)
            .filter(
                UserSession.user_id == user_id,
                UserSession.session_id == session_id,
            )
            .first()
        )
        if not user_session:
            user_session = UserSession(user_id=user_id, session_id=session_id)
            db.add(user_session)
            db.commit()
            db.refresh(user_session)

        if user_session.achieved_target:
            raise HTTPException(
                status_code=400,
                detail="You have already achieved the target!",
            )

        admin_settings = _get_admin_settings(db)
        if user_session.prompt_count >= admin_settings.max_messages_per_user:
            raise HTTPException(status_code=429, detail="Message limit reached")

        one_minute_ago = datetime.utcnow() - timedelta(minutes=1)
        recent_count = (
            db.query(Message)
            .filter(
                Message.user_id == user_id,
                Message.session_id == session_id,
                Message.prompt_timestamp >= one_minute_ago,
            )
            .count()
        )
        if recent_count >= admin_settings.max_messages_per_minute:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please wait before sending another prompt.",
            )

        return {
            "history": _get_conversation_history(db, user_id, session_id),
            "llm_provider": admin_settings.llm_provider,
            "llm_model": admin_settings.llm_model,
        }
    finally:
        db.close()


def _store_prompt_result(
    user_id: int,
    user_name: str,
    session_id: int,
    prompt_text: str,
    prompt_ts: datetime,
    response_text: str,
    response_ts: datetime,
    latency_ms: int,
    success: bool,
) -> tuple[Dict[str, Any], Dict[str, Any] | None]:
    """Persist the message and update leaderboard state in a fresh DB session."""
    db = SessionLocal()
    try:
        admin_settings = _get_admin_settings(db)
        user_session = (
            db.query(UserSession)
            .filter(
                UserSession.user_id == user_id,
                UserSession.session_id == session_id,
            )
            .with_for_update()
            .first()
        )
        if not user_session:
            raise HTTPException(status_code=404, detail="User session not found")
        if user_session.achieved_target:
            raise HTTPException(
                status_code=400,
                detail="You have already achieved the target!",
            )
        if user_session.prompt_count >= admin_settings.max_messages_per_user:
            raise HTTPException(status_code=429, detail="Message limit reached")

        message = Message(
            user_id=user_id,
            session_id=session_id,
            prompt_text=prompt_text,
            response_text=response_text,
            prompt_timestamp=prompt_ts,
            response_timestamp=response_ts,
            latency_ms=latency_ms,
            success=success,
        )
        db.add(message)

        target_event = None
        if success:
            user_session.prompt_count += 1

            if settings.TARGET_OUTPUT.lower() in response_text.lower():
                user_session.achieved_target = True
                user_session.completed_at = datetime.utcnow()
                time_diff = (
                    user_session.completed_at - user_session.joined_at
                ).total_seconds()
                attempts = max(user_session.prompt_count, 1)
                user_session.score = round(
                    1000 / (attempts + time_diff / 60),
                    2,
                )
                target_event = {
                    "type": "target_achieved",
                    "user_id": user_id,
                    "user_name": user_name,
                    "prompt_count": user_session.prompt_count,
                }

        db.commit()
        db.refresh(message)
        return ChatResponse.model_validate(message).model_dump(), target_event
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/send", response_model=ChatResponse)
async def send_prompt(
    payload: ChatSend,
    current_user: User = Depends(get_current_user),
):
    """Send a prompt to the LLM and get a response."""
    if current_user.role != "user":
        raise HTTPException(status_code=403, detail="Only participants can chat")

    prompt_context = await run_in_threadpool(
        _prepare_prompt_context,
        current_user.id,
        payload.session_id,
    )

    # Call LLM
    prompt_ts = datetime.utcnow()
    success = True
    try:
        response_text, latency_ms = await generate_response(
            prompt=payload.prompt,
            conversation_history=prompt_context["history"],
            provider_name=prompt_context["llm_provider"],
            model=prompt_context["llm_model"],
        )
    except Exception as e:
        response_text = f"[Error]: {str(e)}"
        latency_ms = 0
        success = False

    response_ts = datetime.utcnow()
    message_payload, target_event = await run_in_threadpool(
        _store_prompt_result,
        current_user.id,
        current_user.name,
        payload.session_id,
        payload.prompt,
        prompt_ts,
        response_text,
        response_ts,
        latency_ms,
        success,
    )

    if target_event:
        await ws_manager.broadcast(target_event)

    return message_payload


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
    user_session = (
        db.query(UserSession)
        .filter(
            UserSession.user_id == current_user.id,
            UserSession.session_id == session_id,
        )
        .first()
    )

    admin_settings = _get_admin_settings(db)
    total_used = user_session.prompt_count if user_session else 0
    remaining = max(0, admin_settings.max_messages_per_user - total_used)

    return ChatHistoryResponse(
        messages=messages,
        remaining_messages=remaining,
        total_used=total_used,
    )
