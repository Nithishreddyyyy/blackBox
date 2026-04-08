"""
BlackBox — AI Red-Team Challenge Platform
FastAPI application entry point.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.database import engine, Base, SessionLocal
from app.models import User, AdminSettings
from app.auth import hash_password
from app.config import settings
from app.limiter import limiter
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from app.routes.auth import router as auth_router
from app.routes.chat import router as chat_router
from app.routes.admin import router as admin_router
from app.routes.public import router as public_router
from app.routes.websocket import router as ws_router


async def seed_database():
    """Create default admin user and settings if they don't exist."""
    async with SessionLocal() as db:
        # Seed admin
        admin = (await db.execute(select(User).filter(User.email == settings.ADMIN_EMAIL))).scalars().first()
        if not admin:
            admin = User(
                name=settings.ADMIN_NAME,
                email=settings.ADMIN_EMAIL,
                password_hash=hash_password(settings.ADMIN_PASSWORD),
                role="admin",
            )
            db.add(admin)
            print(f"[SEED] Admin user created: {settings.ADMIN_EMAIL}")

        # Seed default settings
        admin_settings = (await db.execute(select(AdminSettings))).scalars().first()
        if not admin_settings:
            # Determine the default model based on the configured provider
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
            print("[SEED] Default admin settings created")

        await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    # Create all tables safely with async engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[STARTUP] Database tables created")

    # Seed default data
    await seed_database()
    print("[STARTUP] Database seeded")

    yield

    print("[SHUTDOWN] Application shutting down")


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


# ── CORS ─────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ───────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(admin_router)
app.include_router(public_router)
app.include_router(ws_router)


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "blackbox-backend"}
