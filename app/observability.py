"""LangSmith wiring. `configure_tracing()` promotes settings into the env vars
LangChain reads at import. `traced(name, layer)` wraps `langsmith.traceable`
with a no-op fallback when langsmith isn't importable."""
from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any, TypeVar

from app.config import Settings, get_settings

log = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def configure_tracing(settings: Settings | None = None) -> bool:
    """Promote app settings into the env vars LangChain reads at import time.

    Returns True if tracing is on. Safe to call multiple times.
    """
    s = settings or get_settings()

    if not s.langchain_tracing_v2 or not s.langchain_api_key:
        log.info("LangSmith tracing disabled (LANGCHAIN_TRACING_V2 off or no API key).")
        os.environ.pop("LANGCHAIN_TRACING_V2", None)
        return False

    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = s.langchain_api_key
    os.environ["LANGCHAIN_PROJECT"] = s.langchain_project
    log.info("LangSmith tracing enabled, project=%s", s.langchain_project)
    return True


def traced(name: str, layer: str) -> Callable[[F], F]:
    """Decorator that tags a function with a LangSmith span name and layer label.

    Falls back to a no-op decorator if `langsmith` is not importable, so
    tests and offline runs never break on the dependency.
    """
    try:
        from langsmith import traceable  # type: ignore[import-not-found]
    except ImportError:  # pragma: no cover — langsmith is in requirements
        log.debug("langsmith unavailable; @traced is a no-op for %s", name)

        def _noop(fn: F) -> F:
            return fn

        return _noop

    def _decorator(fn: F) -> F:
        return traceable(name=name, metadata={"layer": layer})(fn)  # type: ignore[return-value]

    return _decorator
