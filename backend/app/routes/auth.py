"""
Authentication routes: register, login, logout, me.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.models import User, AuditLog
from app.schemas import UserRegister, UserLogin, TokenResponse, UserOut
from app.auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(payload: UserRegister, db: DBSession = Depends(get_db)):
    """Register a new participant account."""
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role="user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: DBSession = Depends(get_db),
):
    """
    Authenticate and return a JWT token.
    
    In the Swagger Authorize dialog, use your **email** as the username.
    """
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(data={"sub": user.id, "role": user.role})

    # Audit
    db.add(AuditLog(actor_id=user.id, action_type="login", action_data={}))
    db.commit()

    return TokenResponse(
        access_token=token, role=user.role, user_id=user.id, name=user.name
    )


@router.post("/logout")
def logout(current_user: User = Depends(get_current_user), db: DBSession = Depends(get_db)):
    """Log out (server-side audit only — client discards the token)."""
    db.add(AuditLog(actor_id=current_user.id, action_type="logout", action_data={}))
    db.commit()
    return {"detail": "Logged out successfully"}


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return current_user
