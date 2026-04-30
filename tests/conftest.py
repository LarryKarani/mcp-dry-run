"""Test fixtures.

Strategy:
* Spin up the Acme MCP server in-process on a free port (uvicorn in a daemon
  thread). Tests get real tool discovery + real round-trips, but no external
  process to manage.
* Reset MCP server state between tests so order/inventory mutations don't leak.
* `FakeAgentModel` lets agent tests run without API calls — it cycles through
  pre-canned `AIMessage` objects (including tool_calls) and overrides
  `bind_tools` to be a no-op (`create_agent` calls `model.bind_tools(tools)`).
"""
from __future__ import annotations

import os
import socket
import threading
import time
from collections.abc import Iterator
from typing import Any

import pytest
import uvicorn
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

# --- Make sure the agent talks to OUR test server, not whatever .env points to.
# Must happen before any `app.*` import that reads settings.
_TEST_PORT = 0  # set in `_pick_free_port` below


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


_TEST_PORT = _pick_free_port()
os.environ["MCP_SERVER_URL"] = f"http://127.0.0.1:{_TEST_PORT}/mcp"
os.environ["MCP_TRANSPORT"] = "http"
# Tests must never accidentally hit a real LLM provider.
os.environ.setdefault("LLM_PROVIDER", "openrouter")
os.environ.setdefault("OPENROUTER_API_KEY", "sk-test-not-used")
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")

from app.config import get_settings  # noqa: E402  — env must be set first
from mcp_server import data as mcp_data  # noqa: E402
from mcp_server.server import mcp as mcp_app  # noqa: E402

get_settings.cache_clear()


class FakeAgentModel(FakeMessagesListChatModel):
    """FakeMessagesListChatModel with two test-friendly tweaks:

    * `bind_tools` is a no-op (returns self) so `create_agent` accepts it.
    * `_generate` walks the response list linearly without cycling — that lets
      tests append responses *between* agent turns to inject a dynamic value
      (e.g. an order_id only known after `place_order` runs).
    """

    def bind_tools(self, tools: list[Any], **_: Any) -> "FakeAgentModel":  # type: ignore[override]
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


def _wait_until_listening(port: int, timeout: float = 5.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise RuntimeError(f"MCP test server failed to come up on port {port}")


@pytest.fixture(scope="session", autouse=True)
def mcp_test_server() -> Iterator[None]:
    """Start the Acme MCP server in-thread for the duration of the suite."""
    config = uvicorn.Config(
        app=mcp_app.streamable_http_app(),
        host="127.0.0.1",
        port=_TEST_PORT,
        log_level="warning",
        lifespan="on",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="mcp-test-server", daemon=True)
    thread.start()
    _wait_until_listening(_TEST_PORT)
    yield
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(autouse=True)
def reset_mcp_state() -> Iterator[None]:
    """Reset Acme inventory + orders before every test."""
    mcp_data.reset_state()
    yield
    mcp_data.reset_state()


@pytest.fixture
async def mcp_tools() -> list[Any]:
    """Discover MCP tools via the real client. One connection per test."""
    from app.mcp_client import MCPClientHolder

    holder = MCPClientHolder()
    tools = await holder.connect()
    return tools


def make_fake(messages: list[BaseMessage]) -> FakeAgentModel:
    """Tiny helper used by agent tests to script a turn."""
    return FakeAgentModel(responses=messages)


def ai_tool_call(name: str, args: dict[str, Any], call_id: str = "call_1") -> AIMessage:
    """Build an AIMessage that triggers exactly one tool call."""
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}],
    )


def ai_text(text: str) -> AIMessage:
    """Build an AIMessage with plain text content (no tool calls)."""
    return AIMessage(content=text)


@pytest.fixture
def tool_names(mcp_tools: list[Any]) -> dict[str, str]:
    """Map MCP tool names to themselves so tests can reference by intent.

    Test code is allowed to know tool names; the rule is that `app/` doesn't.
    The mapping makes it explicit which intent each test exercises.
    """
    by_name = {t.name: t.name for t in mcp_tools}
    return by_name
