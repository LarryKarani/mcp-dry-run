"""LLM factory. Returns a `BaseChatModel`; provider is settings-driven so the
eval suite can compare models without code changes."""
from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from app.config import Settings, get_settings


def get_llm(settings: Settings | None = None) -> BaseChatModel:
    """Return a ChatModel based on settings. Fail fast if API key is missing."""
    s = settings or get_settings()

    if s.llm_provider == "openrouter":
        if not s.openrouter_api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not set.")
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=s.llm_model,
            api_key=s.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
            temperature=0,
            timeout=30,
            default_headers={
                "HTTP-Referer": s.openrouter_app_url,
                "X-Title": s.openrouter_app_name,
            },
        )

    if s.llm_provider == "openai":
        if not s.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not set. Set it in .env or your environment.")
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=s.llm_model,
            api_key=s.openai_api_key,
            temperature=0,  # tool-using agents want determinism
            timeout=30,
        )

    if s.llm_provider == "anthropic":
        if not s.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set.")
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=s.llm_model,
            api_key=s.anthropic_api_key,
            temperature=0,
            timeout=30,
        )

    raise ValueError(f"Unknown llm_provider: {s.llm_provider}")
