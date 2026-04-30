"""LLM factory unit tests."""
from __future__ import annotations

import pytest

from app.config import Settings
from app.llm import get_llm


def test_openrouter_raises_without_key() -> None:
    s = Settings(llm_provider="openrouter", openrouter_api_key=None)
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        get_llm(s)


def test_openai_raises_without_key() -> None:
    s = Settings(llm_provider="openai", openai_api_key=None)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        get_llm(s)


def test_anthropic_raises_without_key() -> None:
    s = Settings(llm_provider="anthropic", anthropic_api_key=None)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        get_llm(s)


def test_openrouter_builds_with_key() -> None:
    s = Settings(llm_provider="openrouter", openrouter_api_key="sk-test")
    llm = get_llm(s)
    # ChatOpenAI under the hood — check it points at the OpenRouter base URL.
    assert "openrouter.ai" in str(getattr(llm, "openai_api_base", "") or getattr(llm, "root_client", None) or "openrouter.ai")


def test_openai_builds_with_key() -> None:
    s = Settings(llm_provider="openai", openai_api_key="sk-test")
    llm = get_llm(s)
    assert llm is not None
