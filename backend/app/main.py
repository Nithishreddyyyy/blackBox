"""
BlackBox — AI Red-Team Challenge Platform
FastAPI application entry point.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.database import engine, Base, SessionLocal
from app.models import User, AdminSettings
from app.auth import hash_password
from app.config import settings

from app.routes.auth import router as auth_router
from app.routes.chat import router as chat_router
from app.routes.admin import router as admin_router
from app.routes.public import router as public_router
from app.routes.websocket import router as ws_router


def ensure_schema_compatibility():
    """Apply safe, non-destructive schema compatibility patches."""
    if not settings.DATABASE_URL.startswith("mysql"):
        return

    with engine.begin() as conn:
        has_plural = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM information_schema.columns
                WHERE table_schema = DATABASE()
                  AND table_name = 'sessions'
                  AND column_name = 'llm_system_prompts'
                """
            )
        ).scalar() or 0

        has_singular = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM information_schema.columns
                WHERE table_schema = DATABASE()
                  AND table_name = 'sessions'
                  AND column_name = 'llm_system_prompt'
                """
            )
        ).scalar() or 0

        if has_plural == 0:
            conn.execute(text("ALTER TABLE sessions ADD COLUMN llm_system_prompts TEXT NULL"))
            print("[MIGRATION] Added sessions.llm_system_prompts")

        if has_singular > 0:
            conn.execute(
                text(
                    """
                    UPDATE sessions
                    SET llm_system_prompts = llm_system_prompt
                    WHERE (llm_system_prompts IS NULL OR llm_system_prompts = '')
                      AND llm_system_prompt IS NOT NULL
                      AND llm_system_prompt <> ''
                    """
                )
            )
            print("[MIGRATION] Backfilled llm_system_prompts from llm_system_prompt")

        # Add leaderboard_enabled column if it doesn't exist
        has_leaderboard_enabled = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM information_schema.columns
                WHERE table_schema = DATABASE()
                  AND table_name = 'admin_settings'
                  AND column_name = 'leaderboard_enabled'
                """
            )
        ).scalar() or 0

        if has_leaderboard_enabled == 0:
            conn.execute(text("ALTER TABLE admin_settings ADD COLUMN leaderboard_enabled BOOLEAN DEFAULT TRUE"))
            print("[MIGRATION] Added admin_settings.leaderboard_enabled")


def seed_database():
    """Create default admin user and settings if they don't exist."""
    db = SessionLocal()
    try:
        # Seed admin
        admin = db.query(User).filter(User.email == settings.ADMIN_EMAIL).first()
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
        admin_settings = db.query(AdminSettings).first()
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

        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    # Create all tables
    Base.metadata.create_all(bind=engine)
    print("[STARTUP] Database tables created")

    # Ensure schema compatibility for evolved columns
    ensure_schema_compatibility()
    print("[STARTUP] Schema compatibility checks complete")

    # Seed default data
    seed_database()
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

# ── CORS ─────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
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
