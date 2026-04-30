"""MCP client wrapper.

The ONLY module in the app that knows MCP exists. Tool discovery is dynamic:
no tool name appears as a string literal anywhere in app/. The LLM decides
which tool to call based on descriptions surfaced from the server.

This is the architectural choice that lets us swap MCP servers without
touching agent.py — on bootcamp day, only MCP_SERVER_URL changes.
"""
from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from app.config import Settings, get_settings

log = logging.getLogger(__name__)


class MCPClientHolder:
    """Owns the lifecycle of a MultiServerMCPClient and the discovered tools.

    Why a class: Chainlit's per-session lifecycle (on_chat_start / on_chat_end)
    needs an object we can store on cl.user_session and tear down cleanly.
    A module-level singleton would leak connections across sessions.
    """

    def __init__(self, settings: Settings | None = None):
        self._settings = settings or get_settings()
        self._client: MultiServerMCPClient | None = None
        self._tools: list[BaseTool] = []

    async def connect(self) -> list[BaseTool]:
        """Open the MCP connection and discover tools. Idempotent."""
        if self._client is not None:
            return self._tools

        config: dict[str, Any] = {
            "business": {
                "url": self._settings.mcp_server_url,
                "transport": self._settings.mcp_transport,
            }
        }
        log.info("Connecting to MCP server: %s", self._settings.mcp_server_url)
        self._client = MultiServerMCPClient(config)
        self._tools = await self._client.get_tools()
        log.info("Discovered %d MCP tools: %s", len(self._tools), [t.name for t in self._tools])
        return self._tools

    @property
    def tools(self) -> list[BaseTool]:
        return self._tools

    async def close(self) -> None:
        """Best-effort connection cleanup. Errors logged but not raised."""
        # MultiServerMCPClient creates per-call sessions; nothing persistent
        # to close in 0.2.x. Method kept for forward-compatibility with
        # future versions and for symmetry with connect().
        self._client = None
        self._tools = []
        log.info("MCP client closed")
