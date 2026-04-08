"""
SQLAlchemy ORM models matching the PRD database design.

Fixes applied from UPGRADED_DEEP_REPO_AUDIT.md:
  - Added UniqueConstraint on user_sessions(user_id, session_id) [DB Audit]
  - Added ondelete="CASCADE" to all FK columns referencing users/sessions [Issue 5.9]
  - Added cascade="all, delete-orphan" to User relationships [Issue 5.9]
  - Added missing DB indexes: users.created_at, sessions.status,
    notifications.created_at, audit_logs.created_at [DB Audit]
"""

from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Float,
    Boolean,
    Enum,
    ForeignKey,
    JSON,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    __table_args__ = (
        Index("idx_users_created_at", "created_at"),  # Issue: ORDER BY created_at
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum("admin", "user", name="user_role"), default="user", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Cascade deletes: removing a User removes all their related rows (Issue 5.9)
    user_sessions = relationship(
        "UserSession", back_populates="user", cascade="all, delete-orphan"
    )
    messages = relationship(
        "Message", back_populates="user", cascade="all, delete-orphan"
    )
    audit_logs = relationship(
        "AuditLog", back_populates="actor", cascade="all, delete-orphan"
    )
    notifications_sent = relationship("Notification", back_populates="creator")


class Session(Base):
    __tablename__ = "sessions"

    __table_args__ = (
        Index("idx_sessions_status", "status"),  # Issue: frequent filter by status
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_name = Column(String(200), nullable=False)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    status = Column(
        Enum("pending", "active", "paused", "completed", name="session_status"),
        default="pending",
        nullable=False,
    )

    user_sessions = relationship(
        "UserSession", back_populates="session", cascade="all, delete-orphan"
    )
    messages = relationship(
        "Message", back_populates="session", cascade="all, delete-orphan"
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    __table_args__ = (
        Index("idx_us_user_session", "user_id", "session_id"),
        # Unique constraint prevents duplicate rows from TOCTOU race (DB Audit)
        UniqueConstraint("user_id", "session_id", name="uq_user_session"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    # ondelete="CASCADE" ensures FK rows are removed when parent is deleted (Issue 5.9)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    score = Column(Float, default=0.0)
    achieved_target = Column(Boolean, default=False)
    prompt_count = Column(Integer, default=0)

    user = relationship("User", back_populates="user_sessions")
    session = relationship("Session", back_populates="user_sessions")


class Message(Base):
    __tablename__ = "messages"

    __table_args__ = (
        Index("idx_msg_user_session", "user_id", "session_id"),
        Index("idx_msg_prompt_timestamp", "prompt_timestamp"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    prompt_text = Column(Text, nullable=False)
    response_text = Column(Text, nullable=True)
    prompt_timestamp = Column(DateTime, default=datetime.utcnow)
    response_timestamp = Column(DateTime, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    success = Column(Boolean, default=True)

    user = relationship("User", back_populates="messages")
    session = relationship("Session", back_populates="messages")


class AdminSettings(Base):
    __tablename__ = "admin_settings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    max_messages_per_user = Column(Integer, default=50)
    max_messages_per_minute = Column(Integer, default=5)
    challenge_duration = Column(Integer, default=3600)  # seconds
    llm_provider = Column(String(50), default="ollama")
    llm_model = Column(String(100), default="llama3")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Notification(Base):
    __tablename__ = "notifications"

    __table_args__ = (
        Index("idx_notif_created_at", "created_at"),  # Issue: ORDER BY created_at
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    message = Column(Text, nullable=False)
    priority = Column(
        Enum("low", "normal", "high", "urgent", name="notification_priority"),
        default="normal",
    )
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    creator = relationship("User", back_populates="notifications_sent")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    __table_args__ = (
        Index("idx_audit_created_at", "created_at"),  # Issue: ORDER BY created_at
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    action_type = Column(String(100), nullable=False)
    action_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    actor = relationship("User", back_populates="audit_logs")
