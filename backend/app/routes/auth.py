"""
Authentication routes: register, login, logout, me.

Fixes from UPGRADED_DEEP_REPO_AUDIT:
  - Issue 7.8: Rate limiting applied to /auth/login
  - Issue 5.2: JWT revocation on logout via token blocklist
  - Issue 4.5: Login always sends credentials:include (handled at frontend)
  - Issue 9.4: Replaced print() with structured logging
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User, AuditLog
from app.schemas import UserRegister, TokenResponse, UserOut
from app.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    get_token,
    decode_token,
    revoke_token,
)
from app.limiter import limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserOut, status_code=201)
async def register(payload: UserRegister, db: AsyncSession = Depends(get_db)):
    """Register a new participant account."""
    existing_user = await db.execute(select(User).filter(User.email == payload.email))
    if existing_user.scalars().first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role="user",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    logger.info("New participant registered: %s", payload.email)
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")   # Issue 7.8: Prevent brute-force attacks
async def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate and set an HttpOnly cookie.
    Use your email as the 'username' field in Swagger.
    """
    user_result = await db.execute(select(User).filter(User.email == form_data.username))
    user = user_result.scalars().first()

    if not user or not verify_password(form_data.password, user.password_hash):
        logger.warning("Failed login attempt for: %s", form_data.username)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(data={"sub": user.id, "role": user.role})

    # Set HttpOnly cookie — never accessible by JS
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=True,          # HTTPS only in production
        samesite="lax",
        max_age=60 * 60,      # Match ACCESS_TOKEN_EXPIRE_MINUTES (60 min)
    )

    db.add(AuditLog(actor_id=user.id, action_type="login", action_data={}))
    await db.commit()
    logger.info("User logged in: %s (role=%s)", user.email, user.role)

    return TokenResponse(
        access_token=token, role=user.role, user_id=user.id, name=user.name
    )


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    raw_token: str = Depends(get_token),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Log out: delete the HttpOnly cookie AND revoke the JWT via JTI blocklist.
    (Issue 5.2 fix: token can no longer be reused after logout)
    """
    # Revoke token in the in-memory blocklist
    try:
        payload = decode_token(raw_token)
        revoke_token(payload)
    except Exception:
        pass  # If token is already invalid, still proceed with cookie deletion

    response.delete_cookie("access_token")

    db.add(AuditLog(actor_id=current_user.id, action_type="logout", action_data={}))
    await db.commit()
    logger.info("User logged out: %s", current_user.email)
    return {"detail": "Logged out successfully"}


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return current_user
