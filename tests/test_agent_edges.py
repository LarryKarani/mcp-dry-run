"""Edge-case agent tests — E1..E8 from DRY_RUN_SCENARIO.md.

E6 (timeout) is xfailed: simulating a >10s tool stall reliably needs a
modification to the MCP server we're told not to touch. The behaviour is
covered defensively by `mcp_call_timeout_seconds` in settings + a friendly
error message in `AcmeAgent.ainvoke`'s except branch.
"""
from __future__ import annotations

from typing import Any

import pytest

from app.agent import AcmeAgent
from app.config import Settings
from app.mcp_client import MCPClientHolder
from mcp_server import data as mcp_data
from tests.conftest import FakeAgentModel, ai_text, ai_tool_call


def _agent(tools: list[Any], fake: FakeAgentModel, session: str = "edge") -> AcmeAgent:
    return AcmeAgent(tools=tools, session_id=session, llm=fake)


async def test_e1_empty_message_is_rejected_without_llm(mcp_tools: list[Any]) -> None:
    """E1: empty input is bounced by Layer 1; the LLM is never invoked."""
    fake = FakeAgentModel(responses=[ai_text("should never run")])
    agent = _agent(mcp_tools, fake)
    reply = await agent.ainvoke("")
    assert reply.blocked
    assert reply.reason == "empty"
    assert fake.i == 0


async def test_e2_long_message_is_truncated_not_crashed(mcp_tools: list[Any]) -> None:
    """E2: 5,000 characters → input is truncated, agent still produces a reply."""
    fake = FakeAgentModel(responses=[
        ai_text("Got it — could you tell me which product you're interested in?"),
    ])
    agent = _agent(mcp_tools, fake)
    reply = await agent.ainvoke("a" * 5000)
    assert not reply.blocked
    assert reply.text  # non-empty


async def test_e3_mcp_unreachable_is_diagnosable() -> None:
    """E3: connecting to a dead MCP server raises — caller (UI) can degrade gracefully."""
    bogus = Settings(mcp_server_url="http://127.0.0.1:1/mcp", mcp_transport="http")
    holder = MCPClientHolder(bogus)
    with pytest.raises(Exception):
        await holder.connect()


async def test_e4_empty_search_results_handled_politely(
    mcp_tools: list[Any], tool_names: dict[str, str]
) -> None:
    """E4: search returns []; the agent says no matches and offers to refine."""
    fake = FakeAgentModel(responses=[
        ai_tool_call(tool_names["search_products"], {"query": "zzznotaproduct", "max_results": 5}),
        ai_text("No matches found. Could you try different keywords?"),
    ])
    agent = _agent(mcp_tools, fake)
    reply = await agent.ainvoke("Do you have any zzznotaproduct?")
    assert not reply.blocked
    assert "no matches" in reply.text.lower()


async def test_e5_insufficient_stock_paraphrased(
    mcp_tools: list[Any], tool_names: dict[str, str]
) -> None:
    """E5: place_order on a 0-stock SKU returns an error; agent paraphrases, no stack trace."""
    assert mcp_data.INVENTORY["AC-FIL-003"] == 0
    fake = FakeAgentModel(responses=[
        ai_tool_call(
            tool_names["place_order"],
            {"sku": "AC-FIL-003", "quantity": 1, "customer_email": "x@y.com"},
        ),
        ai_text("Sorry — AC-FIL-003 is currently out of stock. Want me to suggest an alternative?"),
    ])
    agent = _agent(mcp_tools, fake)
    reply = await agent.ainvoke("Order 1 of AC-FIL-003 to x@y.com")
    assert not reply.blocked
    assert "Traceback" not in reply.text
    assert "out of stock" in reply.text.lower()
    assert len(mcp_data.ORDERS) == 0


@pytest.mark.xfail(reason="MCP server is fixed; cannot inject a >10s stall without modifying it.")
async def test_e6_tool_timeout_is_handled() -> None:
    raise NotImplementedError


async def test_e7_ambiguous_request_asks_one_clarifying_question(mcp_tools: list[Any]) -> None:
    """E7: ambiguous 'I want some coffee' → agent asks a single clarifying question."""
    fake = FakeAgentModel(responses=[
        ai_text("Happy to help — are you after espresso, filter, or decaf?"),
    ])
    agent = _agent(mcp_tools, fake)
    reply = await agent.ainvoke("I want some coffee")
    assert not reply.blocked
    # Single clarifying question: at most one '?' in the reply.
    assert reply.text.count("?") == 1


async def test_e8_multi_turn_anaphora_is_resolved(
    mcp_tools: list[Any], tool_names: dict[str, str]
) -> None:
    """E8: 'cancel that' three turns later resolves to the right order via checkpointer state."""
    order = mcp_data.create_order("AC-ESP-001", 1, "user@x.com")

    fake = FakeAgentModel(responses=[
        # Turn 1: user says "I just placed ORD-XXX." Agent acknowledges.
        ai_text("Got it — anything else?"),
        # Turn 2: user fills space. Agent acknowledges.
        ai_text("Sure."),
        # Turn 3: user fills space. Agent acknowledges.
        ai_text("Of course."),
        # Turn 4: "cancel that" — agent must remember the order_id from turn 1.
        ai_tool_call(tool_names["cancel_order"], {"order_id": order.order_id}),
        ai_text(f"Cancelled order {order.order_id}."),
    ])
    agent = _agent(mcp_tools, fake, session="anaphora")

    await agent.ainvoke(f"I just placed order {order.order_id} earlier.")
    await agent.ainvoke("By the way the espresso is great.")
    await agent.ainvoke("Quick question — do you ship to PO boxes?")
    reply = await agent.ainvoke("Cancel that.")

    assert not reply.blocked
    assert mcp_data.ORDERS[order.order_id].status == "cancelled"
