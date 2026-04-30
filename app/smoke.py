"""End-to-end smoke test.

Connects to the MCP server, lists discovered tools, runs one canned query
through the full agent pipeline (guardrails included), and prints the result.

Run with:
    python -m app.smoke

Exits non-zero on any failure so it can be wired into CI / a Railway health
job. Treats this as the "is everything wired up?" check before recording.
"""
from __future__ import annotations

import asyncio
import logging
import sys
import uuid

from app.agent import AcmeAgent
from app.config import configure_logging, get_settings
from app.mcp_client import MCPClientHolder
from app.observability import configure_tracing

CANNED_QUERY = "What categories of products do you have? Show me a few monitors."

log = logging.getLogger("app.smoke")


async def _run() -> int:
    configure_logging()
    configure_tracing()
    settings = get_settings()

    log.info("Smoke test against MCP_SERVER_URL=%s", settings.mcp_server_url)
    holder = MCPClientHolder(settings)

    try:
        tools = await holder.connect()
    except Exception as exc:  # noqa: BLE001 — friendly diagnostic on connection failure
        log.exception("MCP connect failed: %s", exc)
        return 2

    log.info("Discovered %d tools: %s", len(tools), [t.name for t in tools])
    if not tools:
        log.error("No tools discovered — server is reachable but exposes nothing.")
        return 3

    agent = AcmeAgent(tools=tools, session_id=str(uuid.uuid4()))
    try:
        reply = await agent.ainvoke(CANNED_QUERY)
    except Exception as exc:  # noqa: BLE001 — surface root cause and fail loudly
        log.exception("Agent invoke failed: %s", exc)
        await holder.close()
        return 4

    log.info("Agent reply: %s", reply.text)
    await holder.close()

    if reply.blocked:
        log.error("Smoke reply was blocked by guardrails: %s", reply.reason)
        return 5
    return 0


def main() -> None:
    sys.exit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
