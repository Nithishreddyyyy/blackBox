"""
BlackBox — AI Red-Team Challenge Platform
FastAPI application entry point.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base, SessionLocal
from app.models import User, AdminSettings
from app.auth import hash_password
from app.config import settings

from app.routes.auth import router as auth_router
from app.routes.chat import router as chat_router
from app.routes.admin import router as admin_router
from app.routes.public import router as public_router
from app.routes.websocket import router as ws_router


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
