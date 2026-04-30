"""Chainlit chat UI. Thin shell around `SupportAgent`. MCP connection
opens on chat start, closes on chat end. MCP failures are caught so
the deployed URL never serves a hard error page."""
from __future__ import annotations

import logging
import sys
import uuid
from pathlib import Path

# Chainlit's module loader puts the *file's* directory at the front of sys.path
# (i.e. .../app), not the project root. Make `from app.… import …` resolvable
# whether we're run locally (PYTHONPATH=.) or in a container (WORKDIR=/app).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import chainlit as cl  # noqa: E402

from app.agent import SupportAgent  # noqa: E402
from app.config import configure_logging, get_settings  # noqa: E402
from app.mcp_client import MCPClientHolder  # noqa: E402
from app.observability import configure_tracing  # noqa: E402

_AGENT_KEY = "agent"
_MCP_KEY = "mcp_holder"

log = logging.getLogger(__name__)

configure_logging()
configure_tracing()


@cl.on_chat_start
async def on_chat_start() -> None:
    """Connect to MCP and instantiate the agent for this session."""
    session_id = str(uuid.uuid4())
    settings = get_settings()
    holder = MCPClientHolder(settings)

    try:
        tools = await holder.connect()
    except Exception as exc:  # noqa: BLE001 — never crash the UI on MCP failure
        log.exception("MCP connection failed at chat start: %s", exc)
        await cl.Message(
            content=(
                "I'm having trouble reaching the Meridian catalogue right now. "
                "Please try again in a minute."
            ),
        ).send()
        cl.user_session.set(_MCP_KEY, holder)
        cl.user_session.set(_AGENT_KEY, None)
        return

    agent = SupportAgent(tools=tools, session_id=session_id)
    cl.user_session.set(_MCP_KEY, holder)
    cl.user_session.set(_AGENT_KEY, agent)

    tool_names = ", ".join(t.name for t in tools)
    log.info("Chat started session=%s tools=[%s]", session_id, tool_names)
    await cl.Message(
        content=(
            "Hi — I'm Meridian Electronics' support assistant. I can help you browse the "
            "catalogue, look up your order history, or place a new order. For anything that "
            "touches your account, I'll ask for your email and 4-digit PIN. What can I help with?"
        ),
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """Route the user's message through the guardrail-wrapped agent."""
    agent: SupportAgent | None = cl.user_session.get(_AGENT_KEY)
    if agent is None:
        await cl.Message(
            content="Service is in a degraded state — please refresh to retry.",
        ).send()
        return

    reply = await agent.ainvoke(message.content)
    await cl.Message(content=reply.text).send()


@cl.on_chat_end
async def on_chat_end() -> None:
    """Close the MCP connection when the user leaves."""
    holder: MCPClientHolder | None = cl.user_session.get(_MCP_KEY)
    if holder is None:
        return
    try:
        await holder.close()
    except Exception as exc:  # noqa: BLE001 — cleanup must not raise
        log.warning("MCP close raised on chat end: %s", exc)
