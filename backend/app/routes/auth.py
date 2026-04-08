"""
Authentication routes: register, login, logout, me.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User, AuditLog
from app.schemas import UserRegister, UserLogin, TokenResponse, UserOut
from app.auth import hash_password, verify_password, create_access_token, get_current_user

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
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate and return a JWT token, also set in HttpOnly cookie.
    
    In the Swagger Authorize dialog, use your **email** as the username.
    """
    user_result = await db.execute(select(User).filter(User.email == form_data.username))
    user = user_result.scalars().first()
    
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(data={"sub": user.id, "role": user.role})

    # Set HttpOnly Cookie
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=7200, # 2 hours
    )

    # Audit
    db.add(AuditLog(actor_id=user.id, action_type="login", action_data={}))
    await db.commit()

    return TokenResponse(
        access_token=token, role=user.role, user_id=user.id, name=user.name
    )


@router.post("/logout")
async def logout(response: Response, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Log out (server-side audit only — client discards the token)."""
    response.delete_cookie("access_token")
    
    db.add(AuditLog(actor_id=current_user.id, action_type="logout", action_data={}))
    await db.commit()
    return {"detail": "Logged out successfully"}


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return current_user
