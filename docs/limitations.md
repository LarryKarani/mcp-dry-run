# Limitations

What this build does not do today, why, and what I would change next.

---

## Out of scope by design (not in scope for the brief)

These are deliberate omissions per `DRY_RUN_SCENARIO.md` §"Out-of-scope":

- **No authentication or customer accounts.** Orders are keyed by email; an order ID is the only handle for lookup/cancel.
- **No payment processing.** `place_order` returns a `pending` order; nothing is actually charged.
- **No persistent storage.** `mcp_server.data` lives in process memory; restart wipes orders and resets inventory.
- **No rate limiting.** Neither on the MCP server nor on the agent.
- **No internationalisation / currency conversion.** Prices are USD literals from the catalogue.

---

## Real gaps (caught these during the build)

- **Tool-call timeout (E6) is not exercised.** The MCP server is fixed and we can't inject a >10s stall without modifying it. `mcp_call_timeout_seconds` is configurable and the agent's broad-except branch surfaces a friendly message — but there is no automated test proving the cancel path works under a real stall. Marked `xfail` in `tests/test_agent_edges.py` with the reason recorded.
- **No content moderation API.** Layer-3 output validation is regex-based and catches obvious leaks (prompt fragments, identity hijacks, key shapes, tracebacks). It does not detect, say, *culturally inappropriate paraphrases* or PII echoing. With another day I would add a moderation pass against an OpenAI / Anthropic moderation endpoint as a fourth layer.
- **No retry-with-backoff on MCP calls.** A transient 503 from the MCP server fails the turn outright. The user retries by re-asking. With another day: idempotent retries with jitter on `place_order` would be wrong (could double-place); idempotent retries on read-only tools would be safe.
- **Smoke and Chainlit modules are not unit-tested.** `app/smoke.py` and `app/ui_chainlit.py` are excluded from coverage in `.coveragerc` because they are entry-point shells — `smoke.py` is exercised by running it; `ui_chainlit.py` is exercised end-to-end via the deployed URL. With another day: a httpx-based test that drives the deployed URL through one full conversation.
- **MCP server log message is misleading.** `mcp_server/server.py` logs `Starting … on http://127.0.0.1:8765/mcp`, but FastMCP's default port is 8000 and the constructor doesn't pass `port=`. The `.env` was updated to point at 8000 to match reality. The MCP server itself is marked DONE per `CLAUDE.md` so the log line is left as-is.
- **No graceful shutdown of LangGraph state.** `InMemorySaver` is a per-process dict; a crash or container restart drops every in-progress conversation. With another day: swap to `SqliteSaver` or `PostgresSaver` so multi-turn flows survive a redeploy.

---

## Roadmap (what I'd add next, in priority order)

1. **Persistent checkpointer.** SqliteSaver or PostgresSaver so a Railway redeploy doesn't drop in-progress conversations.
2. **Moderation as Layer-4 guardrail.** OpenAI / Anthropic moderation endpoint on every output, in parallel with Layer-3 regexes.
3. **Retry-with-backoff for read-only MCP tools.** Idempotency markers on write tools (`place_order` idempotency key) so we can retry safely.
4. **Observability dashboard.** A pinned LangSmith view filtered by `layer=agent` with P50/P95 latency, token spend, and tool-failure rate.
5. **A/B prompt rollout.** `PROMPT_VERSION` is already a variable — wiring it to a feature flag would let us A/B v3 vs v4 against a held-out user cohort.
6. **End-to-end test against deployed URL.** `pytest tests/e2e/` that drives the live Chainlit URL through one full conversation per release.
