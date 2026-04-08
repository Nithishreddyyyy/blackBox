"""
BlackBox — AI Red-Team Challenge Platform
FastAPI application entry point.

Fixes from UPGRADED_DEEP_REPO_AUDIT:
  - Health check is now async and tests real DB connectivity (Issue 5.5)
  - CORS uses configurable ALLOWED_ORIGINS from settings (Issue 5.10)
  - CORS allows only necessary methods/headers (Issue 5.10)
  - All print() replaced with logger calls (Issue 9.4)
"""

import logging
import logging.config
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine, Base, SessionLocal, get_db
from app.models import User, AdminSettings
from app.auth import hash_password
from app.config import settings
from app.limiter import limiter

from app.routes.auth import router as auth_router
from app.routes.chat import router as chat_router
from app.routes.admin import router as admin_router
from app.routes.public import router as public_router
from app.routes.websocket import router as ws_router

# ── Structured logging setup ─────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("blackbox")


async def seed_database() -> None:
    """Create default admin user and settings if they don't exist."""
    async with SessionLocal() as db:
        # Seed admin
        admin = (
            await db.execute(select(User).filter(User.email == settings.ADMIN_EMAIL))
        ).scalars().first()
        if not admin:
            admin = User(
                name=settings.ADMIN_NAME,
                email=settings.ADMIN_EMAIL,
                password_hash=hash_password(settings.ADMIN_PASSWORD),
                role="admin",
            )
            db.add(admin)
            logger.info("Admin user seeded: %s", settings.ADMIN_EMAIL)

        # Seed default settings
        admin_settings = (await db.execute(select(AdminSettings))).scalars().first()
        if not admin_settings:
            default_model = {
                "ollama": settings.OLLAMA_MODEL,
                "openai": settings.OPENAI_MODEL,
                "openrouter": settings.OPENROUTER_MODEL,
            }.get(settings.LLM_PROVIDER.lower(), settings.OLLAMA_MODEL)

            admin_settings = AdminSettings(
                max_messages_per_user=50,
                max_messages_per_minute=5,
                challenge_duration=3600,
                llm_provider=settings.LLM_PROVIDER,
                llm_model=default_model,
            )
            db.add(admin_settings)
            logger.info("Default admin settings seeded")

        await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables verified/created")

    await seed_database()
    logger.info("Database seed complete — application ready")

    yield

    logger.info("Application shutting down")


app = FastAPI(
    title="BlackBox — AI Red-Team Challenge Platform",
    description=(
        "A web-based competition platform where participants interact with a "
        "controlled LLM and attempt to bypass its constraints."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── Rate Limiting ────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS (Issue 5.10: configurable origins, minimal methods) ──────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)

# ── Routes ───────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(admin_router)
app.include_router(public_router)
app.include_router(ws_router)


# ── Health Check (Issue 5.5: async + real DB connectivity test) ──────────

@app.get("/health", tags=["Health"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Liveness probe. Returns 200 only if the database is reachable.
    A broken DB connection will return 500, allowing load balancers to
    route traffic away from sick instances.
    """
    await db.execute(select(1))
    return {"status": "healthy", "service": "blackbox-backend"}
