# Decisions (ADR-lite)

Five decisions worth recording — the ones that shape what the codebase looks like and what it can do for Meridian.

---

## ADR-1: LangGraph (`langchain.agents.create_agent`) over a hand-rolled ReAct loop

**Context.** The chatbot needs multi-turn flows with anaphora (E8 — *"show me the second one"* three turns after authentication; the agent must still hold the customer UUID and the order list in state). Time budget is 3 hours.

**Options.**
1. Hand-rolled tool-dispatch loop on top of `ChatOpenAI.bind_tools(...)`.
2. LangChain `AgentExecutor` (the legacy API).
3. **LangGraph via `langchain.agents.create_agent` (LangChain 1.x).** ✅

**Choice.** Option 3. `create_agent` compiles a `CompiledStateGraph` internally, so we get a checkpointer, parallel tool calls, and the full ReAct cycle for free. Plugging in `InMemorySaver` keyed by Chainlit session ID gave us multi-turn anaphora in one line of code.

**Consequence.** The agent is one short class (`SupportAgent`) and the messages graph is owned by LangGraph. Trade-off: the LangGraph state is opaque to us — for tests we assert against tool side effects and reply text rather than introspecting graph internals.

---

## ADR-2: Three independent guardrail layers, not one big system prompt

**Context.** Adversarial bar is high; even a tightened prompt can leak on translate / repeat / "grandma used to read me" attacks. Layered defence keeps any single layer from being load-bearing on its own.

**Options.**
1. Trust the prompt entirely — keep iterating wording.
2. Add a single output-validation step.
3. **Defence in depth: input validation, prompt secrecy clauses, output validation — all independently testable.** ✅

**Choice.** Option 3. Layer 1 normalises and caps input. Layer 2 is the prompt itself (`prompts/system_v1.md`). Layer 3 (`validate_output`) catches prompt-leak fragments, identity hijacks, secret-shaped strings, and raw tracebacks.

**Consequence.** Each layer has unit tests. The 22-case adversarial corpus in `tests/test_guardrails.py` confirms Layer 3 catches the failure modes Layer 2 might miss. The system-prompt iteration story is preserved in `prompts_log.md`.

---

## ADR-3: LLM behind a factory; default to OpenRouter for cost-effective tier

**Context.** Brief constrains us to a cost-effective model (Gemini Flash, GPT-4o-mini, or Claude Haiku). The eval comparison needs to swap models without code changes. OpenRouter gives one bill across providers and one auth scheme.

**Options.**
1. Hardcode `ChatOpenAI(model=...)` in `agent.py`.
2. **`get_llm(settings)` factory with a `LLM_PROVIDER` env var** (`openrouter` | `openai` | `anthropic`). ✅
3. Build a generic LLM router with full provider negotiation.

**Choice.** Option 2 — minimal abstraction. `app/llm.py` returns a `BaseChatModel` regardless of provider. Switching from `openai/gpt-4o-mini` to `anthropic/claude-3.5-haiku` is one env var; no code touches.

**Consequence.** Phase D eval becomes parametrised over a model list with no code changes. Trade-off: provider-specific knobs (Anthropic's extended thinking, OpenAI's strict-mode tool calling) aren't surfaced — fine for this scope.

---

## ADR-4: Discover MCP tools via `langchain-mcp-adapters`; never name them in `app/`

**Context.** The brief explicitly says *"Connect to the MCP server, discover its available tools, and build a chatbot that uses them"*. Hardcoding tool names couples the chatbot to today's tool list and hides the discovery story we're meant to demonstrate.

**Options.**
1. Hand-roll JSON-RPC against the MCP server.
2. **Use `MultiServerMCPClient.get_tools()` and pass results to `create_agent`.** ✅
3. Maintain a manual tool registry in `app/` for "known" servers.

**Choice.** Option 2. `mcp_client.py` is the only file that imports MCP. It wraps `MultiServerMCPClient` in `MCPClientHolder` so Chainlit can manage lifecycle (`on_chat_start` → connect, `on_chat_end` → close).

**Consequence.** A regex-based test (`test_no_hardcoded_tool_names_in_app`) walks every `.py` in `app/` and grepfails if any of the 8 Meridian tool names appears as a string literal. If Meridian adds a `cancel_order` tool tomorrow, the chatbot picks it up at startup with no code change.

---

## ADR-5: The LLM walks the auth flow, not custom session-state code

**Context.** Meridian's auth gate is `verify_customer_pin(email, pin)` → returns a customer UUID. Account-touching tools (`list_orders`, `create_order`) need that UUID. The naïve approach is to write a session-state struct that captures the UUID after verify and injects it into subsequent calls.

**Options.**
1. Custom auth middleware in the agent that intercepts tool calls and rewrites args.
2. Server-side session token + cookie store on our side.
3. **Let the LLM hold the UUID in its message history (via the LangGraph checkpointer) and emit it as a tool argument when needed, guided by prompt clauses ("do not re-ask, do not invent, do not proceed without one").** ✅

**Choice.** Option 3 — zero custom code. The system prompt teaches the model the flow; the checkpointer keeps the prior turns visible; the model emits `list_orders(customer_id=<UUID it remembers>)`.

**Consequence.** Tomorrow's auth changes (MFA, refresh tokens, role-based scopes) hit the prompt and the MCP, not our agent code. Trade-off: we trust the LLM to not leak the UUID back to the user — the prompt forbids it explicitly, and Layer 3 output-validation catches the obvious echo cases.

---

## Eval comparison (Phase D)

Run `pytest -m eval` to regenerate. The block between the markers below is overwritten by `tests/test_eval.py`; the surrounding prose stays.

<!-- EVAL TABLE START -->
| Model | Happy-path | Adversarial | Mean latency (s) | Max latency (s) |
|---|---:|---:|---:|---:|
| `openai/gpt-4o-mini` | 5/5 | 5/5 | 7.96 | 33.60 |
| `anthropic/claude-3.5-haiku` | 4/5 | 5/5 | 5.86 | 16.08 |
<!-- EVAL TABLE END -->

**Decision (filled after eval runs):** which model ships, with the *data → conclusion → choice* chain that VIDEO_CHECKPOINTS calls out as the highest-leverage minute of the final pitch.
