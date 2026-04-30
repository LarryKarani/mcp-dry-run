"""MCP client integration tests against the hosted Meridian server.

Hits the real MCP for discovery (read-only). Maps to:
* SC-1 — dynamic discovery, zero hardcoded tool names in `app/`.
* SC-4 — graceful failure on unreachable MCP.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from app.config import Settings
from app.mcp_client import MCPClientHolder
from tests.conftest import MERIDIAN_TOOL_NAMES

APP_DIR = Path(__file__).resolve().parents[1] / "app"


async def test_discovery_returns_all_tools(mcp_tools_real: list[Any]) -> None:
    """SC-1: every Meridian tool surfaces via MCP discovery."""
    discovered = {t.name for t in mcp_tools_real}
    expected = set(MERIDIAN_TOOL_NAMES)
    assert expected.issubset(discovered), f"missing: {expected - discovered}"


async def test_every_tool_has_a_description(mcp_tools_real: list[Any]) -> None:
    """Without descriptions the LLM can't pick the right tool."""
    missing = [t.name for t in mcp_tools_real if not (t.description or "").strip()]
    assert missing == [], f"tools missing descriptions: {missing}"


async def test_every_tool_has_a_schema(mcp_tools_real: list[Any]) -> None:
    """LangChain tool wrappers must expose an args schema for the LLM."""
    schemaless = [t.name for t in mcp_tools_real if t.args_schema is None]
    assert schemaless == [], f"tools missing args_schema: {schemaless}"


def test_no_hardcoded_tool_names_in_app() -> None:
    """SC-1 enforced: no MCP tool name appears as a string literal in `app/`."""
    offences: list[tuple[Path, int, str]] = []
    for path in APP_DIR.rglob("*.py"):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for name in MERIDIAN_TOOL_NAMES:
                if re.search(rf'["\']({re.escape(name)})["\']', line):
                    offences.append((path, lineno, line.strip()))
    assert offences == [], (
        "Found hardcoded MCP tool names in app/:\n"
        + "\n".join(f"  {p.relative_to(APP_DIR.parent)}:{ln} | {ll}" for p, ln, ll in offences)
    )


async def test_connect_raises_on_unreachable_server() -> None:
    """Caller (UI) needs to be able to detect connection failure."""
    bogus = Settings(mcp_server_url="http://127.0.0.1:1/mcp", mcp_transport="http")
    holder = MCPClientHolder(bogus)
    with pytest.raises(Exception):
        await holder.connect()
