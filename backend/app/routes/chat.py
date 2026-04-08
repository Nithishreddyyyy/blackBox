"""
Chat routes: send prompt, get history.
"""

from datetime import datetime
from typing import List, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db, SessionLocal
from app.models import User, Message, UserSession, AdminSettings, Session
from app.schemas import ChatSend, ChatResponse, ChatHistoryResponse
from app.auth import get_current_user, get_current_user_id_only
from app.llm_provider import generate_response
from app.config import settings
from app.websocket_manager import ws_manager
from app.limiter import limiter

router = APIRouter(prefix="/chat", tags=["Chat"])


async def _get_admin_settings(db: AsyncSession) -> AdminSettings:
    s = (await db.execute(select(AdminSettings))).scalars().first()
    if not s:
        s = AdminSettings()
        db.add(s)
        await db.commit()
        await db.refresh(s)
    return s


async def _get_conversation_history(
    db: AsyncSession, user_id: int, session_id: int, limit: int = 20
) -> List[Dict[str, str]]:
    """Build conversation history for LLM context (excludes failed messages)."""
    msgs = (
        await db.execute(
            select(Message)
            .filter(
                Message.user_id == user_id,
                Message.session_id == session_id,
                Message.success == True,
            )
            .order_by(Message.prompt_timestamp.desc())
            .limit(limit)
        )
    ).scalars().all()
    
    msgs = list(msgs)
    msgs.reverse()
    history = []
    for m in msgs:
        history.append({"role": "user", "content": m.prompt_text})
        if m.response_text:
            history.append({"role": "assistant", "content": m.response_text})
    return history


@router.post("/send", response_model=ChatResponse)
@limiter.limit("5/minute")
async def send_prompt(
    request: Request,
    payload: ChatSend,
    user_id: int = Depends(get_current_user_id_only),
):
    """Send a prompt to the LLM and get a response."""
    
    # ── Database Scope 1: Validation and History ──
    async with SessionLocal() as db:
        user = (await db.execute(select(User).filter(User.id == user_id))).scalars().first()
        if not user or user.role != "user":
            raise HTTPException(status_code=403, detail="Only participants can chat")

        # Validate session
        session = (await db.execute(select(Session).filter(Session.id == payload.session_id))).scalars().first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if session.status != "active":
            raise HTTPException(status_code=400, detail=f"Session is {session.status}, not active")

        # Get or create user_session
        user_session = (
            await db.execute(
                select(UserSession).filter(
                    UserSession.user_id == user_id,
                    UserSession.session_id == payload.session_id,
                )
            )
        ).scalars().first()
        
        if not user_session:
            user_session = UserSession(
                user_id=user_id,
                session_id=payload.session_id,
            )
            db.add(user_session)
            await db.commit()
            await db.refresh(user_session)

        # Check if already completed
        if user_session.achieved_target:
            raise HTTPException(status_code=400, detail="You have already achieved the target!")

        admin_settings = await _get_admin_settings(db)
        if user_session.prompt_count >= admin_settings.max_messages_per_user:
            raise HTTPException(status_code=429, detail="Message limit reached")

        # Build conversation history
        history = await _get_conversation_history(db, user_id, payload.session_id)
        
        provider_name = admin_settings.llm_provider
        model_name = admin_settings.llm_model

    # ── End DB Scope 1 ──
    
    # ── Call LLM (No active DB connection) ──
    prompt_ts = datetime.utcnow()
    success = True
    try:
        response_text, latency_ms = await generate_response(
            prompt=payload.prompt,
            conversation_history=history,
            provider_name=provider_name,
            model=model_name,
        )
    except Exception as e:
        response_text = f"[Error]: {str(e)}"
        latency_ms = 0
        success = False

    response_ts = datetime.utcnow()

    # ── Database Scope 2: Save Results ──
    async with SessionLocal() as db:
        user_session = (
            await db.execute(
                select(UserSession).filter(
                    UserSession.user_id == user_id,
                    UserSession.session_id == payload.session_id,
                )
            )
        ).scalars().first()
        
        user = (await db.execute(select(User).filter(User.id == user_id))).scalars().first()
        
        # Save message
        message = Message(
            user_id=user_id,
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
        if user_session:
            user_session.prompt_count += 1

            # Check if target achieved
            if settings.TARGET_OUTPUT.lower() in response_text.lower():
                user_session.achieved_target = True
                user_session.completed_at = datetime.utcnow()
                # Score: lower is better (fewer prompts + faster time)
                time_diff = (user_session.completed_at - user_session.joined_at).total_seconds()
                user_session.score = round(1000 / (user_session.prompt_count + time_diff / 60), 2)

                # Notify admins via WebSocket
                if user:
                    await ws_manager.broadcast({
                        "type": "target_achieved",
                        "user_id": user_id,
                        "user_name": user.name,
                        "prompt_count": user_session.prompt_count,
                    })

        await db.commit()
        await db.refresh(message)

    return message


@router.get("/history", response_model=ChatHistoryResponse)
async def get_history(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve chat history for the current user in a given session."""
    messages = (
        await db.execute(
            select(Message)
            .filter(
                Message.user_id == current_user.id,
                Message.session_id == session_id,
            )
            .order_by(Message.prompt_timestamp.asc())
        )
    ).scalars().all()

    admin_settings = await _get_admin_settings(db)
    
    # Needs to be a list
    messages = list(messages)
    total_used = len(messages)
    remaining = max(0, admin_settings.max_messages_per_user - total_used)

    return ChatHistoryResponse(
        messages=messages,
        remaining_messages=remaining,
        total_used=total_used,
    )
