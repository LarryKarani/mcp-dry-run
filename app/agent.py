"""Agent assembly.

Wraps an MCP-aware tool-using agent with the three guardrail layers around
every turn. Built on `langchain.agents.create_agent` (LangChain 1.x) which
compiles a LangGraph state graph internally — checkpointing, streaming, and
ReAct-style tool dispatch come for free.

This module knows nothing about Chainlit. Same `SupportAgent` could power a
FastAPI endpoint, a CLI, or a Slack bot without modification.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import InMemorySaver

from app.guardrails import (
    OUTPUT_BLOCKED_FALLBACK,
    SAFE_REFUSAL,
    InputCheck,
    validate_input,
    validate_output,
)
from app.llm import get_llm
from app.observability import traced
from app.prompts import PROMPT_VERSION, load_system_prompt

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentReply:
    """One turn's worth of output. `blocked` flags layer-1 or layer-3 rejection."""

    text: str
    blocked: bool
    reason: str | None = None


class SupportAgent:
    """A guardrail-wrapped, tool-using agent bound to one user session.

    The MCP tools come in pre-discovered from `MCPClientHolder` — this class
    contains zero knowledge of MCP itself, which is the architectural seam
    that lets us swap MCP servers without touching agent code.
    """

    def __init__(
        self,
        tools: list[BaseTool],
        session_id: str,
        llm: BaseChatModel | None = None,
    ) -> None:
        self._session_id = session_id
        self._checkpointer = InMemorySaver()
        self._agent = create_agent(
            model=llm or get_llm(),
            tools=_with_error_handling(tools),
            system_prompt=load_system_prompt(),
            checkpointer=self._checkpointer,
        )
        log.info(
            "SupportAgent ready: session=%s prompt=%s tools=%d",
            session_id, PROMPT_VERSION, len(tools),
        )

    @property
    def prompt_version(self) -> str:
        return PROMPT_VERSION

    @traced(name="agent_turn", layer="agent")
    async def ainvoke(self, user_message: object) -> AgentReply:
        """Run one turn end-to-end with input + output guardrails applied."""
        check: InputCheck = validate_input(user_message)
        if not check.ok:
            log.info("agent input rejected reason=%s", check.reason)
            text = SAFE_REFUSAL if check.reason == "non_string" else "Could you say that again? I didn't catch a message."
            return AgentReply(text=text, blocked=True, reason=check.reason)

        try:
            state = await self._agent.ainvoke(
                {"messages": [HumanMessage(content=check.cleaned)]},
                config={"configurable": {"thread_id": self._session_id}},
            )
        except Exception as exc:  # noqa: BLE001 — surface a friendly message, log the cause
            log.exception("agent invoke failed: %s", exc)
            return AgentReply(
                text="Something went wrong on my side. Please try again in a moment.",
                blocked=True,
                reason="agent_error",
            )

        raw = _extract_final_text(state)
        safe = validate_output(raw)
        blocked = safe is OUTPUT_BLOCKED_FALLBACK and raw != OUTPUT_BLOCKED_FALLBACK
        if blocked:
            log.warning("agent output replaced by guardrail fallback")
        return AgentReply(text=safe, blocked=blocked, reason="output_blocked" if blocked else None)


def _with_error_handling(tools: list[BaseTool]) -> list[BaseTool]:
    """Make MCP tool errors visible to the LLM as text instead of raising.

    Without this, an `Insufficient stock` error from `place_order` would
    abort the whole turn — the LLM never gets to paraphrase it for the user.
    Setting `handle_tool_error=True` converts the exception into a
    `ToolMessage` the agent can reason about. This is what makes E5 / SC-4
    actually work.
    """
    for tool in tools:
        tool.handle_tool_error = True
    return tools


def _extract_final_text(state: dict) -> str:
    """Pull the last assistant message text out of an agent state."""
    messages = state.get("messages", []) if isinstance(state, dict) else []
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            content = msg.content
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = [p.get("text", "") for p in content if isinstance(p, dict)]
                joined = "".join(parts).strip()
                if joined:
                    return joined
    log.warning("agent produced no AI message; returning fallback")
    return "I don't have a response for that. Could you rephrase?"
