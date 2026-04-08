"""
SQLAlchemy async-compatible engine & session factory.
"""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

from app.config import settings

# SQLite needs special connect args; MySQL/PostgreSQL use pool sizing
connect_args = {}
extra_kwargs = {"pool_pre_ping": True, "echo": False}

if settings.async_database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
else:
    extra_kwargs["pool_size"] = 20
    extra_kwargs["max_overflow"] = 10

engine = create_async_engine(
    settings.async_database_url,
    connect_args=connect_args,
    **extra_kwargs,
)

SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)

Base = declarative_base()


async def get_db():
    """FastAPI dependency that yields an async DB session."""
    async with SessionLocal() as db:
        yield db
