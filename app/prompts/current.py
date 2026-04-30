"""Active prompt loader. Old versions stay in source so the iteration
history (see `prompts_log.md`) is greppable."""
from __future__ import annotations

from pathlib import Path

PROMPT_VERSION = "v2"

_PROMPT_DIR = Path(__file__).parent


def load_system_prompt() -> str:
    return (_PROMPT_DIR / f"system_{PROMPT_VERSION}.md").read_text(encoding="utf-8")
