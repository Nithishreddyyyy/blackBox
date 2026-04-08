"""
Chat routes: send prompt, get history.

Fixes from UPGRADED_DEEP_REPO_AUDIT:
  - Issue 5.4: TOCTOU race fixed — re-check limit in DB Scope 2 before saving
  - Issue 5.6: prompt_count only incremented on LLM success (not on error)
  - Issue 3.5: _get_admin_settings replaced with shared crud.get_admin_settings
  - Issue 9.4: Replaced print() with structured logging
"""

import logging
from datetime import datetime
from typing import List, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.crud import get_admin_settings
from app.database import get_db, SessionLocal
from app.models import User, Message, UserSession, AdminSettings, Session
from app.schemas import ChatSend, ChatResponse, ChatHistoryResponse
from app.auth import get_current_user, get_current_user_id_only
from app.llm_provider import generate_response
from app.config import settings
from app.websocket_manager import ws_manager
from app.limiter import limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["Chat"])


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

    msgs = list(reversed(msgs))
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

    # ── DB Scope 1: Validation ──────────────────────────
    async with SessionLocal() as db:
        user = (await db.execute(select(User).filter(User.id == user_id))).scalars().first()
        if not user or user.role != "user":
            raise HTTPException(status_code=403, detail="Only participants can chat")

        session = (
            await db.execute(select(Session).filter(Session.id == payload.session_id))
        ).scalars().first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if session.status != "active":
            raise HTTPException(
                status_code=400, detail=f"Session is {session.status}, not active"
            )

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

        if user_session.achieved_target:
            raise HTTPException(status_code=400, detail="You have already achieved the target!")

        admin_settings = await get_admin_settings(db)
        if user_session.prompt_count >= admin_settings.max_messages_per_user:
            raise HTTPException(status_code=429, detail="Message limit reached")

        history = await _get_conversation_history(db, user_id, payload.session_id)
        provider_name = admin_settings.llm_provider
        model_name = admin_settings.llm_model
        max_messages = admin_settings.max_messages_per_user

    # ── End DB Scope 1 ── connection is released ──────────

    # ── LLM call (no DB connection held) ─────────────────
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
        logger.error("LLM error for user_id=%d: %s", user_id, e)
        response_text = f"[Error]: {str(e)}"
        latency_ms = 0
        success = False

    response_ts = datetime.utcnow()

    # ── DB Scope 2: Save results ──────────────────────────
    async with SessionLocal() as db:
        # Issue 5.4: Re-fetch user_session to get the freshest prompt_count
        user_session = (
            await db.execute(
                select(UserSession).filter(
                    UserSession.user_id == user_id,
                    UserSession.session_id == payload.session_id,
                )
            )
        ).scalars().first()

        # Issue 5.4: TOCTOU guard — re-check limit before saving
        if user_session and user_session.prompt_count >= max_messages:
            raise HTTPException(status_code=429, detail="Message limit reached")

        user = (await db.execute(select(User).filter(User.id == user_id))).scalars().first()

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

        if user_session:
            # Issue 5.6: Only increment prompt_count when LLM completed successfully
            if success:
                user_session.prompt_count += 1

            if success and settings.TARGET_OUTPUT.lower() in response_text.lower():
                user_session.achieved_target = True
                user_session.completed_at = datetime.utcnow()
                time_diff = (user_session.completed_at - user_session.joined_at).total_seconds()
                user_session.score = round(
                    1000 / (user_session.prompt_count + time_diff / 60), 2
                )

                if user:
                    await ws_manager.broadcast({
                        "type": "target_achieved",
                        "user_id": user_id,
                        "user_name": user.name,
                        "prompt_count": user_session.prompt_count,
                    })
                logger.info(
                    "TARGET ACHIEVED: user_id=%d (%s) in session_id=%d, prompts=%d",
                    user_id, user.name if user else "?", payload.session_id,
                    user_session.prompt_count,
                )

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

    admin_settings = await get_admin_settings(db)
    messages = list(messages)
    total_used = len(messages)
    remaining = max(0, admin_settings.max_messages_per_user - total_used)

    return ChatHistoryResponse(
        messages=messages,
        remaining_messages=remaining,
        total_used=total_used,
    )
