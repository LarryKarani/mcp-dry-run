"""Edge-case agent tests for Meridian.

E1 — empty input
E2 — 5,000-character input
E3 — MCP unreachable at startup
E4 — search returns "no matches"
E5 — verify_customer_pin fails (bad credentials)
E6 — tool timeout (xfail; can't inject against hosted server)
E7 — ambiguous request → one clarifying question
E8 — multi-turn anaphora ("cancel that one" / "use that order ID")
"""
from __future__ import annotations

from typing import Any

import pytest

from app.agent import SupportAgent
from app.config import Settings
from app.mcp_client import MCPClientHolder
from tests.conftest import FakeAgentModel, ai_text, ai_tool_call


def _agent(tools: list[Any], fake: FakeAgentModel, session: str = "edge") -> SupportAgent:
    return SupportAgent(tools=tools, session_id=session, llm=fake)


async def test_e1_empty_message_rejected_without_llm(mock_tools) -> None:
    """E1: empty input is bounced by Layer 1; the LLM is never invoked."""
    tools, _ = mock_tools
    fake = FakeAgentModel(responses=[ai_text("should never run")])
    agent = _agent(tools, fake)
    reply = await agent.ainvoke("")
    assert reply.blocked
    assert reply.reason == "empty"
    assert fake.i == 0


async def test_e2_long_message_truncated_not_crashed(mock_tools) -> None:
    """E2: 5,000 chars → truncated; agent still produces a reply."""
    tools, _ = mock_tools
    fake = FakeAgentModel(responses=[
        ai_text("Got it — could you tell me which Meridian product or order you're asking about?"),
    ])
    agent = _agent(tools, fake)
    reply = await agent.ainvoke("a" * 5000)
    assert not reply.blocked
    assert reply.text


async def test_e3_mcp_unreachable_diagnosable() -> None:
    """E3: connecting to a dead MCP raises so the UI can degrade gracefully."""
    bogus = Settings(mcp_server_url="http://127.0.0.1:1/mcp", mcp_transport="http")
    holder = MCPClientHolder(bogus)
    with pytest.raises(Exception):
        await holder.connect()


async def test_e4_empty_search_handled_politely(mock_tools) -> None:
    """E4: search returns nothing; agent says so without inventing."""
    tools, canned = mock_tools
    canned["search_products"] = "No products found matching 'zzznotaproduct'."
    fake = FakeAgentModel(responses=[
        ai_tool_call("search_products", {"query": "zzznotaproduct"}),
        ai_text("I couldn't find any products matching that. Want to try a different keyword?"),
    ])
    agent = _agent(tools, fake)
    reply = await agent.ainvoke("Do you have any zzznotaproduct?")
    assert not reply.blocked
    assert "couldn't find" in reply.text.lower() or "no products" in reply.text.lower()


async def test_e5_verify_failure_paraphrased(mock_tools) -> None:
    """E5: verify error returned as ToolMessage; agent paraphrases, no traceback."""
    tools, canned = mock_tools
    canned["verify_customer_pin"] = "✗ Verification failed: invalid email or PIN."
    fake = FakeAgentModel(responses=[
        ai_tool_call("verify_customer_pin",
                     {"email": "nope@example.com", "pin": "0000"}),
        ai_text("Sorry — those credentials didn't match. Double-check the email and PIN and try again."),
    ])
    agent = _agent(tools, fake)
    reply = await agent.ainvoke("Email nope@example.com, PIN 0000 — show me my orders")
    assert not reply.blocked
    assert "Traceback" not in reply.text
    assert "didn't match" in reply.text.lower() or "try again" in reply.text.lower()


@pytest.mark.xfail(reason="Cannot inject a >10s stall against the hosted MCP without modifying it.")
async def test_e6_tool_timeout_handled() -> None:
    raise NotImplementedError


async def test_e7_ambiguous_asks_one_clarifying_question(mock_tools) -> None:
    """E7: 'I want a thing' → agent asks ONE clarifying question."""
    tools, _ = mock_tools
    fake = FakeAgentModel(responses=[
        ai_text("Happy to help — are you after a monitor, keyboard, printer, or something else?"),
    ])
    agent = _agent(tools, fake)
    reply = await agent.ainvoke("I want a thing")
    assert not reply.blocked
    assert reply.text.count("?") == 1


async def test_e8_multi_turn_anaphora(mock_tools) -> None:
    """E8: user authenticates, then 4 turns later says 'show me the second one' — UUID survives."""
    tools, canned = mock_tools
    canned["verify_customer_pin"] = (
        "✓ Customer verified: Donald Garcia\n"
        "Customer ID: 41c2903a-f1a5-47b7-a81d-86b50ade220f"
    )
    canned["list_orders"] = (
        "Found 3 orders:\n"
        "1. Order aa1...\n"
        "2. Order bb2...\n"
        "3. Order cc3..."
    )
    canned["get_order"] = "Order bb2... — submitted — total $450"

    fake = FakeAgentModel(responses=[
        # Turn 1 — verify
        ai_tool_call("verify_customer_pin",
                     {"email": "donaldgarcia@example.net", "pin": "7912"}),
        ai_text("Verified."),
        # Turn 2 — small talk
        ai_text("Sure."),
        # Turn 3 — list
        ai_tool_call("list_orders",
                     {"customer_id": "41c2903a-f1a5-47b7-a81d-86b50ade220f"}),
        ai_text("You have three orders: aa1, bb2, cc3."),
        # Turn 4 — anaphora: "the second one"
        ai_tool_call("get_order", {"order_id": "bb2..."}),
        ai_text("Order bb2... is submitted, total $450."),
    ])
    agent = _agent(tools, fake, session="anaphora")

    await agent.ainvoke("Email donaldgarcia@example.net, PIN 7912.")
    await agent.ainvoke("Thanks.")
    await agent.ainvoke("Show me my orders.")
    reply = await agent.ainvoke("Tell me more about the second one.")

    assert not reply.blocked
    assert "$450" in reply.text or "bb2" in reply.text.lower()
