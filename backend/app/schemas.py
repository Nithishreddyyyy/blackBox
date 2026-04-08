"""
Pydantic schemas for request / response validation.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr


# ── Auth ─────────────────────────────────────────────────

class UserRegister(BaseModel):
    name: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
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
    prompt: str
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
    session_name: str


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
    message: str
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
