"""
LLM Provider abstraction layer.

Supports:
  - Ollama  (local)
  - OpenAI  (API)
  - OpenRouter (API, OpenAI-compatible)

Switch provider via LLM_PROVIDER env var without touching code.
"""

import time
import asyncio
from typing import List, Dict

import httpx
from openai import AsyncOpenAI

from app.config import settings


# Global concurrency limit for LLM calls
LLM_SEMAPHORE = asyncio.Semaphore(5)


class LLMProvider:
    """Base class for LLM providers."""

    async def chat(
        self, messages: List[Dict[str, str]], model: str | None = None
    ) -> str:
        raise NotImplementedError


class OllamaProvider(LLMProvider):
    """Local Ollama server."""

    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.default_model = settings.OLLAMA_MODEL

    async def chat(
        self, messages: List[Dict[str, str]], model: str | None = None
    ) -> str:
        model = model or self.default_model

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={"model": model, "messages": messages, "stream": False},
            )

            response.raise_for_status()
            data = response.json()

            return data.get("message", {}).get("content", "")


class OpenAIProvider(LLMProvider):
    """OpenAI API (gpt-4o, etc.)."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.default_model = settings.OPENAI_MODEL

    async def chat(
        self, messages: List[Dict[str, str]], model: str | None = None
    ) -> str:
        model = model or self.default_model

        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
        )

        return response.choices[0].message.content or ""


class OpenRouterProvider(LLMProvider):
    """OpenRouter API (OpenAI-compatible)."""

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
        )
        self.default_model = settings.OPENROUTER_MODEL

    async def chat(
        self, messages: List[Dict[str, str]], model: str | None = None
    ) -> str:
        model = model or self.default_model

        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
        )

        return response.choices[0].message.content or ""


# ── Factory ──────────────────────────────────────────────

_providers: Dict[str, type] = {
    "ollama": OllamaProvider,
    "openai": OpenAIProvider,
    "openrouter": OpenRouterProvider,
}

_instance: LLMProvider | None = None


def get_llm_provider(provider_name: str | None = None) -> LLMProvider:
    """Return a cached LLM provider instance (or build a new one if provider changed)."""

    global _instance

    name = (provider_name or settings.LLM_PROVIDER).lower()

    if _instance is None or type(_instance).__name__.lower().replace("provider", "") != name:
        cls = _providers.get(name)

        if cls is None:
            raise ValueError(
                f"Unknown LLM provider: {name}. Choose from {list(_providers)}"
            )

        _instance = cls()

    return _instance


async def generate_response(
    prompt: str,
    conversation_history: List[Dict[str, str]] | None = None,
    system_prompt: str | None = None,
    provider_name: str | None = None,
    model: str | None = None,
) -> tuple[str, int]:
    """
    High-level helper: build messages list → call LLM → return (response_text, latency_ms).
    """

    messages = []

    if system_prompt or settings.LLM_SYSTEM_PROMPT:
        messages.append(
            {"role": "system", "content": system_prompt or settings.LLM_SYSTEM_PROMPT}
        )

    if conversation_history:
        messages.extend(conversation_history)

    messages.append({"role": "user", "content": prompt})

    provider = get_llm_provider(provider_name)

    try:
        async with LLM_SEMAPHORE:

            start = time.perf_counter()

            response_text = await provider.chat(messages, model=model)

            latency_ms = int((time.perf_counter() - start) * 1000)

            return response_text, latency_ms

    except Exception as e:

        print("LLM ERROR:", e)

        return "⚠️ Model is currently busy. Please try again.", 0