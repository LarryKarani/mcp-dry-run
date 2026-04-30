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
            │     Guardrails L1          │   length cap, ctrl-char strip,
            │  guardrails.validate_input │   non-string reject
            └────────────┬───────────────┘
                         │ cleaned text
                         ▼
            ┌────────────────────────────┐
            │     LangGraph agent        │   built via
            │  agent.SupportAgent        │   langchain.agents.create_agent
            │  (system prompt = L2)      │   + InMemorySaver checkpointer
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
                              │  Meridian MCP server │
                              │  Streamable HTTP     │
                              │  Cloud Run-hosted    │
                              │  (catalogue, auth,   │
                              │   orders)            │
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

**`mcp_client.py`** is the only module that imports `langchain_mcp_adapters`. Tools are discovered dynamically — no MCP tool name appears as a string literal anywhere in `app/`, and `tests/test_mcp_client.py` greps to enforce that. On the day Meridian's MCP server changes shape (more tools, schema tweaks, transport switch), only the env var moves; the agent adapts at startup.

**`agent.py`** consumes `BaseTool` objects, not MCP details. It has no Chainlit imports either. The graph is built once with `create_agent` (LangChain 1.x), which compiles a LangGraph state graph internally — that's how multi-turn anaphora works (test E8: customer authenticates in turn 1, asks about *"the second one"* three turns later, the agent still has the customer UUID and the order list in checkpointed state). Tool errors get `handle_tool_error=True` so a failed `verify_customer_pin` becomes a `ToolMessage` the LLM paraphrases into *"those credentials didn't match"*, instead of bubbling up and aborting the turn.

**`guardrails.py`** is pure functions. Layer 1 (`validate_input`) caps length, strips C0/C1 control chars, and rejects non-strings *before* the LLM is ever called. Layer 2 lives in `prompts/system_v1.md` (scope, identity, auth flow, secrecy clauses). Layer 3 (`validate_output`) catches what the prompt can't: prompt-leak fragments, identity hijacks (DAN, *unrestricted assistant*, jailbreak claims), API-key shapes (`sk-…`, `AKIA…`, `ls__…`, `ghp_…`), and raw tracebacks. The 22-case adversarial corpus in `tests/test_guardrails.py` exercises Layer 3.

**`ui_chainlit.py`** is a thin shell. `@cl.on_chat_start` opens MCP and instantiates `SupportAgent`; `@cl.on_message` runs one turn; `@cl.on_chat_end` closes MCP. If MCP is unreachable at startup, the chat still loads with a degraded message rather than crashing.

## The auth flow — the architecturally interesting part

Meridian's MCP returns a **customer UUID** from `verify_customer_pin(email, pin)`. Account-touching tools (`list_orders`, `create_order`) need that UUID. We do *not* store it ourselves — instead, the LangGraph checkpointer keeps the full message history per session, including the AI's previous turn where it received the verify response and learned the UUID. On the next turn the LLM has that context and emits `list_orders(customer_id=<the UUID it remembers>)`.

This is a deliberate design choice: no custom session-state code, no auth middleware, no tokens to manage on our side. The LLM walks the auth flow, guided by the system prompt's "do not re-ask, do not invent UUIDs, do not proceed without one" clause. If MFA or refresh tokens are added later, they hit the prompt and the MCP, not our agent code.

## Cross-cutting

`config.py` validates env vars via Pydantic Settings. `observability.py` promotes settings into the `LANGCHAIN_*` env vars LangChain reads at import, then exposes a `traced(name, layer)` decorator that wraps `langsmith.traceable` (with a no-op fallback so offline tests don't break). One LangSmith trace covers the full pipeline: input → agent → tool call → MCP round-trip → output.

## Test seam

`tests/conftest.py` ships two tool flavours:
- `mcp_tools_real` (session-scoped) hits the hosted Meridian MCP for discovery so we can verify schema/description integrity in `test_mcp_client.py`. Read-only.
- `mock_tools` builds permissive-schema stubs in-process — every agent test uses these so we never accidentally create real orders against the hosted server.

`FakeAgentModel` scripts the LLM's `AIMessage` outputs (including `tool_calls`). This lets the same code path be exercised end-to-end — through `create_agent`, the tool node, and a stub MCP round-trip — without an API call. Coverage on `app/` is 91% (excluding `smoke.py` and `ui_chainlit.py`, which are entry-point shells).
