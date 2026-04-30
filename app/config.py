"""Centralised, validated configuration. Imported by every other module.

Why Pydantic settings: env vars typo'd or missing fail loudly at startup,
not silently mid-conversation. This is the cheapest production-readiness
win available — one file, ten minutes, prevents whole classes of bugs.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- LLM ---
    # --- LLM ---
    llm_provider: Literal["openrouter", "openai", "anthropic"] = "openrouter"
    llm_model: str = "openai/gpt-4o-mini"  # OpenRouter format: "<provider>/<model>"
    openrouter_api_key: str | None = None
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    openrouter_app_name: str = "mcp-bootcamp-dryrun"
    openrouter_app_url: str = "https://github.com/yourname/mcp-bootcamp"

    # --- MCP ---
    mcp_server_url: str = "http://127.0.0.1:8765/mcp"
    mcp_transport: Literal["http", "sse"] = "http"
    mcp_call_timeout_seconds: float = 10.0

    # --- Observability (LangSmith) ---
    langchain_tracing_v2: bool = False
    langchain_api_key: str | None = None
    langchain_project: str = "mcp-bootcamp-dryrun"

    # --- Guardrails ---
    max_user_message_chars: int = Field(default=2000, ge=100, le=10000)

    # --- App ---
    log_level: str = "INFO"
    app_port: int = 8000


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton settings accessor. Cached so we read env once."""
    return Settings()


def configure_logging(settings: Settings | None = None) -> None:
    """Wire up logging. Called once from app entrypoints."""
    s = settings or get_settings()
    logging.basicConfig(
        level=s.log_level,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )
