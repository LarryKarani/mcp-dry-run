# Architecture

## Diagram

```
            ┌────────────────────────────┐
            │     Chainlit UI            │
            │  app/ui_chainlit.py        │
            └────────────┬───────────────┘
                         │ user message
                         ▼
            ┌────────────────────────────┐
            │     Guardrails L1          │
            │  guardrails.validate_input │   length cap, ctrl-char strip,
            └────────────┬───────────────┘   non-string reject
                         │ cleaned text
                         ▼
            ┌────────────────────────────┐
            │     LangGraph agent        │
            │  agent.AcmeAgent           │   built via langchain.agents.
            │  (system prompt = L2)      │   create_agent + InMemorySaver
            └────────┬───────────┬───────┘
                     │           │
       (LLM decides) │           │ (LLM decides)
                     ▼           ▼
       ┌──────────────────┐   ┌──────────────────────┐
       │ AIMessage(text)  │   │ ToolNode dispatches  │
       │  → final reply   │   │ MCP tool call        │
       └──────────────────┘   └──────────┬───────────┘
                                         ▼
                              ┌──────────────────────┐
                              │   MCP client         │
                              │  mcp_client.py       │
                              │ (langchain-mcp-      │   only module that
                              │  adapters)           │   knows MCP exists
                              └──────────┬───────────┘
                                         ▼
                              ┌──────────────────────┐
                              │   MCP server         │
                              │  Streamable HTTP     │
                              │  (Acme catalogue,    │
                              │   inventory, orders) │
                              └──────────────────────┘

            ┌────────────────────────────┐
            │     Guardrails L3          │   prompt-leak / identity-hijack
            │  guardrails.validate_output│   / secret-shape / stack-trace
            └────────────┬───────────────┘   blockers
                         │ safe text
                         ▼
                     to user

            (LangSmith traces every span — observability.py wires it)
```

## Why this layering

Four layers, each independently testable, each with a single concern.

**`mcp_client.py`** is the only module that imports `langchain_mcp_adapters`. Tools are discovered dynamically — no tool name is a string literal anywhere in `app/`, and the architecture test in `tests/test_mcp_client.py` greps to enforce that. On bootcamp day this means the only file change is `MCP_SERVER_URL` in `.env`.

**`agent.py`** consumes `BaseTool` objects, not MCP details. It has no Chainlit imports either. The graph is built once with `create_agent` (LangChain 1.x) which compiles a LangGraph state graph internally — this is how multi-turn anaphora (E8) works without us writing a checkpointer by hand. We attach `handle_tool_error=True` to every tool so MCP errors become `ToolMessage`s the LLM can paraphrase, instead of bubbling up and aborting the turn (this is what makes E5 / SC-4 actually work).

**`guardrails.py`** is pure functions. Layer 1 (`validate_input`) caps length, strips C0/C1 control chars, and rejects non-strings before the LLM is ever called. Layer 2 lives in `prompts/system_v3.md` (scope, identity, secrecy clauses). Layer 3 (`validate_output`) catches what the prompt can't: prompt-leak fragments, identity hijacks (DAN, *unrestricted assistant*, jailbreak claims), API-key shapes (`sk-…`, `AKIA…`, `ls__…`, `ghp_…`), and raw tracebacks. The 22-case adversarial corpus in `tests/test_guardrails.py` exercises Layer 3.

**`ui_chainlit.py`** is a thin shell. `@cl.on_chat_start` opens MCP and instantiates `AcmeAgent`; `@cl.on_message` runs one turn; `@cl.on_chat_end` closes MCP. If MCP is unreachable at startup, the chat still loads with a degraded message rather than crashing (E3).

## Cross-cutting

`config.py` validates env vars via Pydantic Settings. `observability.py` promotes settings into the `LANGCHAIN_*` env vars LangChain reads at import, then exposes a `traced(name, layer)` decorator that wraps `langsmith.traceable` (with a no-op fallback so offline tests don't break). One LangSmith trace covers the full pipeline: input → agent → tool call → MCP round-trip → output.

## Test seam

`tests/conftest.py` starts the Acme MCP server in-thread on a free port via `uvicorn`, resets `mcp_server.data` between tests, and ships a `FakeAgentModel` that scripts the LLM's `AIMessage` outputs (including `tool_calls`). This lets the same code path be exercised end-to-end — through `create_agent`, the tool node, and a real MCP round-trip — without an API call. Coverage on `app/` is 91% (excluding `smoke.py` and `ui_chainlit.py`, which are entry-point shells).
