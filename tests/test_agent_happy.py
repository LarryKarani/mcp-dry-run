"""Happy-path agent tests — H1..H6 from DRY_RUN_SCENARIO.md.

Pattern: script a `FakeAgentModel` with the AIMessages we'd expect a real LLM
to produce (tool calls + final response), wire it into `AcmeAgent`, and
assert (a) the right MCP side effect occurred and (b) the user-facing text
came back coherent.

We never assert against tool *names* in `app/` source — tests are allowed to
know names; the rule is that `app/` discovers them via MCP.
"""
from __future__ import annotations

from typing import Any

from app.agent import AcmeAgent
from mcp_server import data as mcp_data
from tests.conftest import FakeAgentModel, ai_text, ai_tool_call


def _agent(tools: list[Any], fake: FakeAgentModel, session: str = "test") -> AcmeAgent:
    return AcmeAgent(tools=tools, session_id=session, llm=fake)


async def test_h1_search_espresso(mcp_tools: list[Any], tool_names: dict[str, str]) -> None:
    """H1: 'show me your espresso options' → search_products."""
    fake = FakeAgentModel(responses=[
        ai_tool_call(tool_names["search_products"], {"query": "espresso", "max_results": 5}),
        ai_text("We have AC-ESP-001 Acme House Espresso at $18.50."),
    ])
    agent = _agent(mcp_tools, fake)
    reply = await agent.ainvoke("Show me your espresso options")
    assert not reply.blocked
    assert "AC-ESP-001" in reply.text
    assert fake.i == 2  # one tool-call turn, one final-response turn


async def test_h2_get_product(mcp_tools: list[Any], tool_names: dict[str, str]) -> None:
    """H2: 'tell me about AC-ESP-001' → get_product."""
    fake = FakeAgentModel(responses=[
        ai_tool_call(tool_names["get_product"], {"sku": "AC-ESP-001"}),
        ai_text("AC-ESP-001 Acme House Espresso — dark roast blend, $18.50."),
    ])
    agent = _agent(mcp_tools, fake)
    reply = await agent.ainvoke("Tell me about AC-ESP-001")
    assert not reply.blocked
    assert "Acme House Espresso" in reply.text


async def test_h3_check_inventory(mcp_tools: list[Any], tool_names: dict[str, str]) -> None:
    """H3: 'is the Yirgacheffe in stock?' → check_inventory."""
    fake = FakeAgentModel(responses=[
        ai_tool_call(tool_names["check_inventory"], {"sku": "AC-FIL-002"}),
        ai_text("Yes — AC-FIL-002 has 17 units in stock."),
    ])
    agent = _agent(mcp_tools, fake)
    reply = await agent.ainvoke("Is the Yirgacheffe in stock?")
    assert not reply.blocked
    assert "17" in reply.text


async def test_h4_place_order(mcp_tools: list[Any], tool_names: dict[str, str]) -> None:
    """H4: 'I'd like 2 of AC-ESP-001, alice@example.com' → place_order; inventory drops."""
    starting = mcp_data.INVENTORY["AC-ESP-001"]
    fake = FakeAgentModel(responses=[
        ai_tool_call(
            tool_names["place_order"],
            {"sku": "AC-ESP-001", "quantity": 2, "customer_email": "alice@example.com"},
        ),
        ai_text("Order placed for 2x AC-ESP-001. You'll get a confirmation by email."),
    ])
    agent = _agent(mcp_tools, fake)
    reply = await agent.ainvoke("I'd like 2 bags of AC-ESP-001, my email is alice@example.com")
    assert not reply.blocked
    assert mcp_data.INVENTORY["AC-ESP-001"] == starting - 2
    assert len(mcp_data.ORDERS) == 1


async def test_h5_get_order(mcp_tools: list[Any], tool_names: dict[str, str]) -> None:
    """H5: existing-order lookup. Pre-create an order, then ask the agent for status."""
    order = mcp_data.create_order("AC-ESP-001", 1, "carol@example.com")
    fake = FakeAgentModel(responses=[
        ai_tool_call(tool_names["get_order"], {"order_id": order.order_id}),
        ai_text(f"Order {order.order_id} is pending."),
    ])
    agent = _agent(mcp_tools, fake)
    reply = await agent.ainvoke(f"What's the status of {order.order_id}?")
    assert not reply.blocked
    assert order.order_id in reply.text


async def test_h6_multi_turn_browse_to_cancel(
    mcp_tools: list[Any], tool_names: dict[str, str]
) -> None:
    """H6: browse → details → order → cancel, all in one session via the checkpointer."""
    fake = FakeAgentModel(responses=[
        # Turn 1 — browse decaf
        ai_tool_call(tool_names["search_products"], {"query": "decaf", "max_results": 5}),
        ai_text("Found one — AC-DEC-004 Swiss Water Decaf at $20.00."),
        # Turn 2 — details on "that one"
        ai_tool_call(tool_names["get_product"], {"sku": "AC-DEC-004"}),
        ai_text("Swiss Water Decaf — chemical-free, smooth, $20.00."),
        # Turn 3 — place an order
        ai_tool_call(
            tool_names["place_order"],
            {"sku": "AC-DEC-004", "quantity": 1, "customer_email": "bob@x.com"},
        ),
        ai_text("Order placed for 1x AC-DEC-004."),
        # Turn 4 — placeholder, the cancel call is appended after we know the ID
    ])
    agent = _agent(mcp_tools, fake, session="multi-turn-test")

    r1 = await agent.ainvoke("Show me your decaf options")
    assert not r1.blocked and "Swiss Water Decaf" in r1.text

    r2 = await agent.ainvoke("Tell me more about that one")
    assert not r2.blocked

    r3 = await agent.ainvoke("OK — order 1, my email is bob@x.com")
    assert not r3.blocked
    assert len(mcp_data.ORDERS) == 1
    order_id = next(iter(mcp_data.ORDERS))

    fake.responses.extend([
        ai_tool_call(tool_names["cancel_order"], {"order_id": order_id}),
        ai_text(f"Cancelled order {order_id}."),
    ])

    r4 = await agent.ainvoke("Actually cancel it")
    assert not r4.blocked
    assert mcp_data.ORDERS[order_id].status == "cancelled"
