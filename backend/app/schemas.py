"""
Pydantic schemas for request / response validation.

Fixes from UPGRADED_DEEP_REPO_AUDIT:
  - ChatSend.prompt: added min_length=1, max_length=2000 (Issue 5.8)
  - UserRegister.password: added min_length=8 (Issue 7.6)
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field


# ── Auth ─────────────────────────────────────────────────

class UserRegister(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    # Issue 7.6: Enforce minimum password length
    password: str = Field(..., min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int
    name: str


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Chat ─────────────────────────────────────────────────

class ChatSend(BaseModel):
    # Issue 5.8: Validate prompt length to prevent oversized payloads
    prompt: str = Field(..., min_length=1, max_length=2000)
    session_id: int


class ChatResponse(BaseModel):
    id: int
    prompt_text: str
    response_text: Optional[str]
    prompt_timestamp: datetime
    response_timestamp: Optional[datetime]
    latency_ms: Optional[int]
    success: bool

    model_config = {"from_attributes": True}


class ChatHistoryResponse(BaseModel):
    messages: List[ChatResponse]
    remaining_messages: int
    total_used: int


# ── Sessions ─────────────────────────────────────────────

class SessionCreate(BaseModel):
    session_name: str = Field(..., min_length=1, max_length=200)


class SessionOut(BaseModel):
    id: int
    session_name: str
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    status: str

    model_config = {"from_attributes": True}


class SessionAction(BaseModel):
    action: str  # start | pause | resume | end


class UserSessionOut(BaseModel):
    id: int
    user_id: int
    session_id: int
    joined_at: datetime
    completed_at: Optional[datetime]
    score: float
    achieved_target: bool
    prompt_count: int
    user_name: Optional[str] = None
    user_email: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Admin Settings ───────────────────────────────────────

class AdminSettingsUpdate(BaseModel):
    max_messages_per_user: Optional[int] = None
    max_messages_per_minute: Optional[int] = None
    challenge_duration: Optional[int] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None


class AdminSettingsOut(BaseModel):
    id: int
    max_messages_per_user: int
    max_messages_per_minute: int
    challenge_duration: int
    llm_provider: str
    llm_model: str

    model_config = {"from_attributes": True}


# ── Notifications ────────────────────────────────────────

class NotificationCreate(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    priority: str = "normal"  # low | normal | high | urgent


class NotificationOut(BaseModel):
    id: int
    message: str
    priority: str
    created_by: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Leaderboard ──────────────────────────────────────────

class LeaderboardEntry(BaseModel):
    rank: int
    user_id: int
    user_name: str
    prompt_count: int
    achieved_target: bool
    completion_time_seconds: Optional[float]
    score: float


class LeaderboardResponse(BaseModel):
    session_id: int
    session_name: str
    entries: List[LeaderboardEntry]


# ── Admin Stats ──────────────────────────────────────────

class AdminStatsResponse(BaseModel):
    total_users: int
    active_sessions: int
    total_messages: int
    active_users: int
    messages_last_minute: int


# ── Audit Log ────────────────────────────────────────────

class AuditLogOut(BaseModel):
    id: int
    actor_id: int
    action_type: str
    action_data: Optional[dict]
    created_at: datetime

    model_config = {"from_attributes": True}
