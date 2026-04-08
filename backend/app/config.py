"""
Application configuration loaded from environment variables.
"""

from typing import Any, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Database ─────────────────────────────────────────
    DATABASE_URL: str = "mysql+pymysql://root:password@localhost:3306/blackbox"

    # ── JWT ──────────────────────────────────────────────
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    ACCESS_TOKEN_COOKIE_NAME: str = "access_token"
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"
    ALLOWED_ORIGINS: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )
    ALGORITHM: str = "HS256"

    # ── LLM Provider ────────────────────────────────────
    LLM_PROVIDER: str = "ollama"  # ollama | openai | openrouter

    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3"

    # OpenAI
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    # OpenRouter
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_MODEL: str = "meta-llama/llama-3-8b-instruct"

    # ── Challenge ────────────────────────────────────────
    LLM_SYSTEM_PROMPT: str
    TARGET_OUTPUT: str

    # ── Admin Seed ───────────────────────────────────────
    ADMIN_EMAIL: str = "admin@blackbox.io"
    ADMIN_PASSWORD: str
    ADMIN_NAME: str = "Platform Admin"

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: Any) -> list[str]:
        if value is None or value == "":
            return ["http://localhost:3000", "http://127.0.0.1:3000"]
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        if isinstance(value, list):
            return value
        raise ValueError("ALLOWED_ORIGINS must be a comma-separated string or list")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
