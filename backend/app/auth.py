"""
JWT & password hashing utilities.

Security model:
  - Tokens are validated from HttpOnly cookies ONLY (Issue 5.1 fix).
  - All issued tokens carry a unique JTI (JWT ID) claim.
  - On logout, the JTI is added to an in-memory blocklist (Issue 5.2 fix).
  - decode_token() rejects any token whose JTI is on the blocklist.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from fastapi import Depends, HTTPException, status, Request
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.database import get_db
from app.models import User

logger = logging.getLogger(__name__)

# ── Password helpers ─────────────────────────────────────
# Using bcrypt via passlib. The bcrypt.__about__ monkey-patch below keeps
# passlib 1.7.4 compatible with bcrypt 4.1+ which removed that attribute.
import bcrypt as _bcrypt_mod
if not hasattr(_bcrypt_mod, "__about__"):
    class _BcryptAbout:
        __version__ = _bcrypt_mod.__version__
    _bcrypt_mod.__about__ = _BcryptAbout()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT blocklist (in-memory, fix for Issue 5.2) ─────────
# Maps jti → expiry datetime. Cleaned up lazily on each check.
_token_blocklist: dict[str, datetime] = {}


def _purge_expired_blocklist() -> None:
    """Remove expired entries to prevent unbounded memory growth."""
    now = datetime.utcnow()
    expired = [jti for jti, exp in _token_blocklist.items() if exp < now]
    for jti in expired:
        del _token_blocklist[jti]


def revoke_token(payload: dict) -> None:
    """Add a token's JTI to the blocklist. Called on logout."""
    jti = payload.get("jti")
    exp = payload.get("exp")
    if jti and exp:
        _purge_expired_blocklist()
        _token_blocklist[jti] = datetime.utcfromtimestamp(exp)
    logger.info("Token revoked: jti=%s", jti)


# ── JWT helpers ──────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    # JWT spec: 'sub' must be a string
    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    # Add a unique JTI so tokens can be individually revoked
    to_encode.update({"exp": expire, "jti": str(uuid4())})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Blocklist check (Issue 5.2)
    jti = payload.get("jti")
    if jti and jti in _token_blocklist:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )

    return payload


# ── FastAPI dependencies ─────────────────────────────────

def get_token(request: Request) -> str:
    """
    Extract JWT from HttpOnly cookie ONLY (Issue 5.1 fix).
    Bearer-header auth is intentionally removed to prevent XSS bypass.
    """
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        return cookie_token
    raise HTTPException(status_code=401, detail="Not authenticated")


async def get_current_user_id_only(
    token: str = Depends(get_token),
) -> int:
    payload = decode_token(token)
    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    try:
        return int(sub)
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid token payload")


async def get_current_user(
    user_id: int = Depends(get_current_user_id_only),
    db: AsyncSession = Depends(get_db),
) -> User:
    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalars().first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user
