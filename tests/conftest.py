"""Test fixtures for the Meridian Electronics MCP chatbot.

Two tool-list flavors:

* `mcp_tools_real` (session-scoped) hits the hosted MCP for discovery so we
  can verify schema/description integrity in `test_mcp_client.py`. Read-only.
* `mock_tools` builds permissive-schema stubs in-process — used by every
  agent test so happy/edge scenarios run hermetically without polluting the
  hosted MCP with test orders.
"""
from __future__ import annotations

import os
from typing import Any

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, ConfigDict

# Tests must never accidentally hit a real LLM provider. The eval suite reads
# the real key from .env directly (see tests/test_eval.py::_load_real_api_key).
os.environ.setdefault("OPENROUTER_API_KEY", "sk-test-not-used")
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")

# Real Meridian tool names. Tests are allowed to reference them; the rule is
# that `app/` discovers them dynamically. test_mcp_client.py greps to enforce.
MERIDIAN_TOOL_NAMES: tuple[str, ...] = (
    "list_products",
    "get_product",
    "search_products",
    "get_customer",
    "verify_customer_pin",
    "list_orders",
    "get_order",
    "create_order",
)


class _PermissiveArgs(BaseModel):
    """Args schema for stub tools: accept any kwargs without validation."""

    model_config = ConfigDict(extra="allow")


class FakeAgentModel(FakeMessagesListChatModel):
    """FakeMessagesListChatModel with two test-friendly tweaks.

    * `bind_tools` is a no-op (returns self) so `create_agent` accepts it.
    * `_generate` walks the response list linearly without cycling, so tests
      can append responses *between* agent turns to inject dynamic values
      (e.g. a customer UUID only known after `verify_customer_pin` runs).
    """

    def bind_tools(self, tools: list[Any], **_: Any) -> FakeAgentModel:  # type: ignore[override]
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # type: ignore[no-untyped-def, override]
        if self.i >= len(self.responses):
            raise AssertionError(
                f"FakeAgentModel exhausted at i={self.i}: scripted "
                f"{len(self.responses)} responses but agent asked for one more."
            )
        response = self.responses[self.i]
        self.i += 1
        return ChatResult(generations=[ChatGeneration(message=response)])


def _make_stub(name: str, canned: dict[str, Any]) -> BaseTool:
    """Build a hermetic stand-in for one MCP tool.

    The stub returns `canned[name]` if the test set it, otherwise echoes the
    call shape so test failures show why a stubbed call wasn't pre-canned.
    """

    async def stub(**kwargs: Any) -> Any:
        if name in canned:
            return canned[name]
        return f"[stub:{name}({kwargs})]"

    return StructuredTool(
        name=name,
        description=f"Stubbed {name} (test-only).",
        args_schema=_PermissiveArgs,
        coroutine=stub,
    )


@pytest.fixture
def mock_tools() -> tuple[list[BaseTool], dict[str, Any]]:
    """Per-test stub tool list + a writable canned-responses dict.

    Usage:
        def test_something(mock_tools):
            tools, canned = mock_tools
            canned["verify_customer_pin"] = "Verified — UUID abc-123"
    """
    canned: dict[str, Any] = {}
    tools = [_make_stub(name, canned) for name in MERIDIAN_TOOL_NAMES]
    return tools, canned


@pytest.fixture(scope="session")
async def mcp_tools_real() -> list[BaseTool]:
    """Discover tools from the hosted Meridian MCP. Read-only; session-scoped."""
    from app.mcp_client import MCPClientHolder

    holder = MCPClientHolder()
    return await holder.connect()


def ai_tool_call(name: str, args: dict[str, Any], call_id: str = "call_1") -> AIMessage:
    """Build an AIMessage that triggers exactly one tool call."""
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}],
    )


def ai_text(text: str) -> AIMessage:
    """Build an AIMessage with plain text content (no tool calls)."""
    return AIMessage(content=text)


def make_fake(messages: list[BaseMessage]) -> FakeAgentModel:
    return FakeAgentModel(responses=messages)
