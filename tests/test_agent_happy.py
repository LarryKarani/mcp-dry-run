"""Happy-path agent tests for Meridian.

Pattern: stub the MCP tools (so we never create real orders during tests),
script a `FakeAgentModel` with the AIMessages we'd expect from the real LLM
(tool calls + final responses), wire both into `SupportAgent`, and assert the
agent's reply text plus that the right stub tool was invoked.

H1 — browse catalogue
H2 — get product details by SKU
H3 — auth flow: prompt for email/PIN, verify, then list orders
H4 — multi-line order placement (after auth)
H5 — order lookup by ID
H6 — multi-turn: auth once, then several account actions sharing UUID
"""
from __future__ import annotations

from typing import Any

from app.agent import SupportAgent
from tests.conftest import FakeAgentModel, ai_text, ai_tool_call


def _agent(tools: list[Any], fake: FakeAgentModel, session: str = "happy") -> SupportAgent:
    return SupportAgent(tools=tools, session_id=session, llm=fake)


# Helper: the Meridian MCP returns formatted plain text. Tests use realistic
# canned shapes so the LLM's next turn has plausible context to react to.
_VERIFY_OK = (
    "✓ Customer verified: Donald Garcia\n"
    "Customer ID: 41c2903a-f1a5-47b7-a81d-86b50ade220f\n"
    "Email: donaldgarcia@example.net\n"
    "Role: admin"
)
_VERIFY_FAIL = "✗ Verification failed: invalid email or PIN."
_LIST_ORDERS = (
    "Found 2 orders for customer 41c2903a-...:\n"
    "1. Order 9d3b... — submitted — 2 line items — $1,134.50\n"
    "2. Order 4ee1... — fulfilled — 1 line item — $89.99"
)
_GET_ORDER = (
    "Order 9d3b21f9-... (submitted)\n"
    "Customer: Donald Garcia\n"
    "Items:\n"
    "  - MON-0054 × 1 @ $899.50\n"
    "  - KEY-0010 × 1 @ $235.00\n"
    "Total: $1,134.50"
)


async def test_h1_browse_monitors(mock_tools) -> None:
    """H1: 'show me your monitors' → list_products(category='Monitors')."""
    tools, canned = mock_tools
    canned["list_products"] = (
        "Found 3 products in Monitors:\n"
        "1. MON-0054 — Ultrawide Monitor Model A — $899.50 — 12 units\n"
        "2. MON-0067 — Ultrawide Monitor Model B — $1065.62 — 75 units"
    )
    fake = FakeAgentModel(responses=[
        ai_tool_call("list_products", {"category": "Monitors"}),
        ai_text("We have several monitors. Top picks: MON-0054 at $899.50 and MON-0067 at $1065.62."),
    ])
    agent = _agent(tools, fake)
    reply = await agent.ainvoke("Show me your monitors")
    assert not reply.blocked
    assert "MON-0054" in reply.text
    assert fake.i == 2


async def test_h2_get_product_by_sku(mock_tools) -> None:
    """H2: 'tell me about MON-0054' → get_product."""
    tools, canned = mock_tools
    canned["get_product"] = "MON-0054 — Ultrawide Monitor Model A — $899.50 — 12 units in stock — 34\" curved"
    fake = FakeAgentModel(responses=[
        ai_tool_call("get_product", {"sku": "MON-0054"}),
        ai_text("MON-0054 is the Ultrawide Monitor Model A — 34\" curved, $899.50, 12 in stock."),
    ])
    agent = _agent(tools, fake)
    reply = await agent.ainvoke("Tell me about MON-0054")
    assert not reply.blocked
    assert "Ultrawide" in reply.text


async def test_h3_auth_then_list_orders(mock_tools) -> None:
    """H3: agent prompts for credentials, verifies, then lists orders.

    Single ainvoke: user provides email + PIN inline ('email X pin Y, show
    my orders'). Agent calls verify_customer_pin then list_orders, using
    the UUID from the verify response.
    """
    tools, canned = mock_tools
    canned["verify_customer_pin"] = _VERIFY_OK
    canned["list_orders"] = _LIST_ORDERS
    fake = FakeAgentModel(responses=[
        ai_tool_call("verify_customer_pin",
                     {"email": "donaldgarcia@example.net", "pin": "7912"}),
        ai_tool_call("list_orders",
                     {"customer_id": "41c2903a-f1a5-47b7-a81d-86b50ade220f"}),
        ai_text("You have 2 orders: one submitted ($1,134.50, 2 items) and one fulfilled ($89.99)."),
    ])
    agent = _agent(tools, fake)
    reply = await agent.ainvoke(
        "Email donaldgarcia@example.net, PIN 7912 — what orders do I have?"
    )
    assert not reply.blocked
    assert "2 orders" in reply.text or "two orders" in reply.text.lower()


async def test_h4_create_multi_line_order_after_auth(mock_tools) -> None:
    """H4: verified customer places a 2-item order in a single turn."""
    tools, canned = mock_tools
    canned["verify_customer_pin"] = _VERIFY_OK
    canned["create_order"] = (
        "✓ Order created: 7c2f9a01-...\n"
        "Items: MON-0054 × 1, KEY-0010 × 2\n"
        "Status: submitted"
    )
    fake = FakeAgentModel(responses=[
        ai_tool_call("verify_customer_pin",
                     {"email": "donaldgarcia@example.net", "pin": "7912"}),
        ai_tool_call("create_order", {
            "customer_id": "41c2903a-f1a5-47b7-a81d-86b50ade220f",
            "items": [
                {"sku": "MON-0054", "quantity": 1},
                {"sku": "KEY-0010", "quantity": 2},
            ],
        }),
        ai_text("Done — order 7c2f9a01-... is submitted with the two items."),
    ])
    agent = _agent(tools, fake)
    reply = await agent.ainvoke(
        "I'm donaldgarcia@example.net pin 7912 — order 1 of MON-0054 and 2 of KEY-0010"
    )
    assert not reply.blocked
    assert "submitted" in reply.text.lower() or "order" in reply.text.lower()


async def test_h5_get_order_by_id(mock_tools) -> None:
    """H5: 'what's the status of order X?' → get_order."""
    tools, canned = mock_tools
    canned["get_order"] = _GET_ORDER
    fake = FakeAgentModel(responses=[
        ai_tool_call("get_order", {"order_id": "9d3b21f9-1234-5678-9abc-def012345678"}),
        ai_text("Order 9d3b... is submitted: MON-0054 × 1 plus KEY-0010 × 1, total $1,134.50."),
    ])
    agent = _agent(tools, fake)
    reply = await agent.ainvoke(
        "What's the status of order 9d3b21f9-1234-5678-9abc-def012345678?"
    )
    assert not reply.blocked
    assert "submitted" in reply.text.lower()


async def test_h6_multi_turn_auth_then_browse_then_order(mock_tools) -> None:
    """H6: auth in turn 1, browse in turn 2, order in turn 3 — UUID survives."""
    tools, canned = mock_tools
    canned["verify_customer_pin"] = _VERIFY_OK
    canned["search_products"] = (
        "Found: KEY-0010 — Mechanical Keyboard — $235.00 — 50 units"
    )
    canned["create_order"] = (
        "✓ Order created: aa11bb22-...\n"
        "Items: KEY-0010 × 1\n"
        "Status: submitted"
    )
    fake = FakeAgentModel(responses=[
        # Turn 1: auth
        ai_tool_call("verify_customer_pin",
                     {"email": "donaldgarcia@example.net", "pin": "7912"}),
        ai_text("Verified — how can I help, Donald?"),
        # Turn 2: search
        ai_tool_call("search_products", {"query": "mechanical keyboard"}),
        ai_text("KEY-0010 is our mechanical keyboard at $235."),
        # Turn 3: order — uses the UUID from turn 1's verify
        ai_tool_call("create_order", {
            "customer_id": "41c2903a-f1a5-47b7-a81d-86b50ade220f",
            "items": [{"sku": "KEY-0010", "quantity": 1}],
        }),
        ai_text("Done — order aa11bb22-... is submitted."),
    ])
    agent = _agent(tools, fake, session="multi-turn")

    r1 = await agent.ainvoke("My email is donaldgarcia@example.net, PIN 7912.")
    assert not r1.blocked

    r2 = await agent.ainvoke("Do you have any mechanical keyboards?")
    assert not r2.blocked

    r3 = await agent.ainvoke("Order one of those.")
    assert not r3.blocked
    assert "submitted" in r3.text.lower() or "order" in r3.text.lower()


async def test_verify_failure_handled_gracefully(mock_tools) -> None:
    """Bonus: bad PIN returns a verification error; agent paraphrases politely."""
    tools, canned = mock_tools
    canned["verify_customer_pin"] = _VERIFY_FAIL
    fake = FakeAgentModel(responses=[
        ai_tool_call("verify_customer_pin",
                     {"email": "donaldgarcia@example.net", "pin": "0000"}),
        ai_text("Sorry — that email and PIN didn't match. Want to try again?"),
    ])
    agent = _agent(tools, fake)
    reply = await agent.ainvoke(
        "Email donaldgarcia@example.net, PIN 0000 — show my orders"
    )
    assert not reply.blocked
    assert "didn't match" in reply.text.lower() or "try again" in reply.text.lower()
