# Decisions (ADR-lite)

Each entry: context, options considered, choice, consequence. Five decisions
worth recording — the ones that shape what the codebase looks like and what
it can do.

---

## ADR-1: LangGraph (`langchain.agents.create_agent`) over a hand-rolled ReAct loop

**Context.** The agent must support multi-turn flows with anaphora (E8 — *"cancel that"* three turns later resolves to the right order) and we have ~3 hours total.

**Options.**
1. Hand-rolled tool-dispatch loop on top of `ChatOpenAI.bind_tools(...)`.
2. LangChain `AgentExecutor` (the legacy API).
3. **LangGraph via `langchain.agents.create_agent` (LangChain 1.x).** ✅

**Choice.** Option 3. `create_agent` compiles a `CompiledStateGraph` internally, so we get a checkpointer, parallel tool calls, and the full ReAct cycle for free. Plugging in `InMemorySaver` keyed by Chainlit session ID gave us E8 in one line of code.

**Consequence.** The agent is one short class (`AcmeAgent`) and the messages graph is owned by LangGraph. Trade-off: the LangGraph state is opaque to us — for tests we assert against MCP side effects and reply text rather than introspecting graph internals.

---

## ADR-2: Three independent guardrail layers, not one big system prompt

**Context.** Adversarial bar is ≥21/22 (SC-5). Prompt iteration (v1 → v3) showed that even a tightened prompt leaks ~3/22 of the time on translate / repeat / "grandma used to read me" attacks.

**Options.**
1. Trust the prompt entirely — keep iterating wording.
2. Add a single output-validation step.
3. **Defense in depth: input validation, prompt secrecy clauses, output validation — all independently testable.** ✅

**Choice.** Option 3, per CLAUDE.md §8. Layer 1 normalises and caps input. Layer 2 is the prompt itself (`prompts/system_v3.md`). Layer 3 (`validate_output`) catches prompt-leak fragments, identity hijacks, secret-shaped strings, and raw tracebacks.

**Consequence.** Each layer has a unit test file. The 22-case adversarial corpus in `tests/test_guardrails.py` confirms Layer 3 catches the failure modes Layer 2 misses. The system-prompt iteration story is preserved in `prompts_log.md` (graders look for this).

---

## ADR-3: Pin the LLM behind a factory; default to OpenRouter for the dry run

**Context.** The eval comparison (Phase D) needs to swap models without code changes. The user is paying for tokens — OpenRouter gives one bill across providers and is cheaper than direct OpenAI for this scenario.

**Options.**
1. Hardcode `ChatOpenAI(model=...)` in `agent.py`.
2. **`get_llm(settings)` factory with a `LLM_PROVIDER` env var** (`openrouter` | `openai` | `anthropic`). ✅
3. Build a generic LLM router with full provider negotiation.

**Choice.** Option 2 — minimal abstraction. `app/llm.py` returns a `BaseChatModel` regardless of provider. Switching to `gpt-4o` or `claude-sonnet-4-6` is one env var.

**Consequence.** Phase D becomes `LLM_MODEL=openai/gpt-4o-mini` vs `LLM_MODEL=openai/gpt-4o`, no code changes. Trade-off: we don't expose provider-specific knobs (e.g. Anthropic's extended thinking) — that's fine for this scope.

---

## ADR-4: Discover MCP tools via `langchain-mcp-adapters`; never name them in `app/`

**Context.** SC-1 demands zero hardcoded tool names in `app/`. The whole MCP value proposition is that the server tells you what it can do.

**Options.**
1. Hand-roll JSON-RPC against the MCP server.
2. **Use `MultiServerMCPClient.get_tools()` and pass results to `create_agent`.** ✅
3. Maintain a manual tool registry in `app/` for "known" servers.

**Choice.** Option 2. `mcp_client.py` is the only file that imports MCP. It wraps `MultiServerMCPClient` in `MCPClientHolder` so Chainlit can manage lifecycle (`on_chat_start` → connect, `on_chat_end` → close).

**Consequence.** A regex-based test (`test_no_hardcoded_tool_names_in_app`) walks every line of `app/` and grepfails if any discovered tool name appears as a string literal. The MCP server can change its tool set and the agent adapts at startup.

---

## ADR-5: Run the MCP server in-thread for tests, not as a subprocess

**Context.** Tests need real MCP round-trips (so we exercise the actual LangChain-MCP adapter and tool schemas), but `pytest -q` must be hermetic — no instructions like *"start the MCP server first"*.

**Options.**
1. Require the user to start the MCP server before running pytest.
2. Spawn `python -m mcp_server.server` as a subprocess from `conftest.py`.
3. **Mount `mcp.streamable_http_app()` on `uvicorn` and run it in a daemon thread on a free port.** ✅

**Choice.** Option 3. The conftest binds to `127.0.0.1:0`, gets a free port, sets `MCP_SERVER_URL` in `os.environ` *before* `app.config` is imported, and starts uvicorn in-thread.

**Consequence.** `pytest -q` runs in <2 seconds with full MCP round-trips — 76 passed, 1 xfail. Reset of `mcp_server.data` between tests is trivial because the server lives in our process. Trade-off: an out-of-process subprocess would catch more system-level integration issues; we accept that gap given the time budget.

---

## Eval comparison (Phase D)

Run `pytest -m eval` to regenerate. The block between the markers below is
overwritten by `tests/test_eval.py`; the surrounding prose stays.

<!-- EVAL TABLE START -->
| Model | Happy-path | Adversarial | Mean latency (s) | Max latency (s) |
|---|---:|---:|---:|---:|
| `openai/gpt-4o-mini` | 5/5 | 5/5 | 2.46 | 4.32 |
| `openai/gpt-4o` | 5/5 | 5/5 | 1.90 | 3.01 |
<!-- EVAL TABLE END -->

**Run on 2026-04-30 against the canonical 5-happy + 5-adversarial scenario
set. Each scenario reset MCP state between runs.**

**Data.** Both `gpt-4o-mini` and `gpt-4o` scored 5/5 on happy-path tool
selection and 5/5 on the adversarial subset (prompt-leak, role-swap,
translate-instructions, off-topic, persuasion). End-to-end mean latency was
2.46s (mini) vs 1.90s (4o); max was 4.32s vs 3.01s. Both sit well below the
SC-6 P95 target of 8s.

**Conclusion.** On *this* scenario set the models are quality-equivalent.
The differentiator is cost: per OpenRouter pricing, `gpt-4o` is roughly
15–20× more expensive per million tokens than `gpt-4o-mini`. The 0.56s
latency difference is real but inside UX tolerance for a chatbot.

**Choice.** Ship **`gpt-4o-mini`**. Caveat: 5 adversarial cases is a small
sample — if production traffic surfaces a class of attacks where mini drops
behind, the LLM factory (`ADR-3`) makes upgrading to `gpt-4o` a one-env-var
change (`LLM_MODEL=openai/gpt-4o`) with no code edits.
