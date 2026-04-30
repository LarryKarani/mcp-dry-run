"""MCP client integration tests.

Maps to SC-1 (dynamic discovery, no hardcoded names) and SC-4 (graceful
failures when MCP is unreachable).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from app.config import Settings
from app.mcp_client import MCPClientHolder

APP_DIR = Path(__file__).resolve().parents[1] / "app"


async def test_discovery_returns_all_tools(mcp_tools: list[Any]) -> None:
    """SC-1: all six Acme tools surface via the MCP protocol."""
    assert len(mcp_tools) == 6


async def test_every_tool_has_a_description(mcp_tools: list[Any]) -> None:
    """Without descriptions the LLM can't pick the right tool."""
    missing = [t.name for t in mcp_tools if not (t.description or "").strip()]
    assert missing == [], f"tools missing descriptions: {missing}"


async def test_every_tool_has_a_schema(mcp_tools: list[Any]) -> None:
    """LangChain tool wrappers must expose an args schema for the LLM."""
    schemaless = [t.name for t in mcp_tools if t.args_schema is None]
    assert schemaless == [], f"tools missing args_schema: {schemaless}"


def test_no_hardcoded_tool_names_in_app(mcp_tools: list[Any]) -> None:
    """The whole point of MCP discovery: tool names live on the server, not in app/."""
    names = [t.name for t in mcp_tools]
    offences: list[tuple[Path, int, str]] = []
    for path in APP_DIR.rglob("*.py"):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for name in names:
                if re.search(rf'["\']({re.escape(name)})["\']', line):
                    offences.append((path, lineno, line.strip()))
    assert offences == [], (
        "Found hardcoded MCP tool names in app/:\n"
        + "\n".join(f"  {p.relative_to(APP_DIR.parent)}:{ln} | {ll}" for p, ln, ll in offences)
    )


async def test_connect_raises_on_unreachable_server() -> None:
    """SC-4 prerequisite: caller can detect connection failure."""
    bogus = Settings(mcp_server_url="http://127.0.0.1:1/mcp", mcp_transport="http")
    holder = MCPClientHolder(bogus)
    with pytest.raises(Exception):
        await holder.connect()


async def test_connect_is_idempotent(mcp_tools: list[Any]) -> None:
    """Repeated connect() calls return the same tools without reconnecting."""
    holder = MCPClientHolder()
    first = await holder.connect()
    second = await holder.connect()
    assert [t.name for t in first] == [t.name for t in second]
