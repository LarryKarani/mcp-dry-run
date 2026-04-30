"""Observability wiring tests."""
from __future__ import annotations

import os

from app.config import Settings
from app.observability import configure_tracing, traced


def test_disabled_when_flag_off(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
    s = Settings(langchain_tracing_v2=False, langchain_api_key=None)
    assert configure_tracing(s) is False
    assert "LANGCHAIN_TRACING_V2" not in os.environ


def test_disabled_when_no_api_key(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
    s = Settings(langchain_tracing_v2=True, langchain_api_key=None)
    assert configure_tracing(s) is False


def test_enabled_promotes_env_vars(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
    s = Settings(
        langchain_tracing_v2=True,
        langchain_api_key="ls-test-key",
        langchain_project="unit-test-project",
    )
    assert configure_tracing(s) is True
    assert os.environ["LANGCHAIN_TRACING_V2"] == "true"
    assert os.environ["LANGCHAIN_API_KEY"] == "ls-test-key"
    assert os.environ["LANGCHAIN_PROJECT"] == "unit-test-project"


def test_traced_decorator_wraps_callable() -> None:
    @traced(name="unit", layer="test")
    def echo(x: int) -> int:
        return x * 2

    assert echo(3) == 6
