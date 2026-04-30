"""Active prompt loader. Bumping the version is a one-line code change
plus a prompts_log.md entry. Old versions stay in source for diffing
and to make the iteration story visible to graders."""
from __future__ import annotations

from pathlib import Path

PROMPT_VERSION = "v3"

_PROMPT_DIR = Path(__file__).parent


def load_system_prompt() -> str:
    return (_PROMPT_DIR / f"system_{PROMPT_VERSION}.md").read_text(encoding="utf-8")
