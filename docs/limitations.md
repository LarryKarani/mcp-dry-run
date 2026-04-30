# Limitations

What this prototype does not do today, why, and what I'd improve next.

---

## Out of scope by design

These are deliberate per the brief; calling them out explicitly so a security review doesn't surface them as gaps:

- **No password / multi-factor auth.** Identity verification is a 4-digit PIN over email — that's the only handle Meridian's MCP exposes. Prod would want OTP or session tokens.
- **No payment processing.** `create_order` returns a `submitted` order; nothing is actually charged. The MCP-side workflow seems to expect a separate fulfilment step.
- **No persistent conversation storage on our side.** `InMemorySaver` is per-process; restart drops in-progress chats. Fine for a single-instance prototype.
- **No returns / refunds / shipping ETAs.** No tools for these in the MCP; the system prompt explicitly refuses them.

---

## Real gaps caught during the build

- **Tool-call timeout (E6) is not exercised by tests.** Hosted MCP, no way to inject a >10s stall. Marked `xfail` in `tests/test_agent_edges.py`. The agent code still has a broad-except branch that surfaces a friendly error if a tool stalls — uncovered by tests.
- **No content moderation API.** Layer-3 output validation is regex-based and catches obvious leaks (prompt fragments, identity hijacks, key shapes, tracebacks). It does not detect culturally inappropriate paraphrasing or PII echoing. With another day I'd add an OpenAI / Anthropic moderation pass as a fourth layer.
- **No retry-with-backoff on MCP calls.** A transient 5xx from Cloud Run fails the turn outright; the user retries by re-asking. With another day: idempotent retries on read-only tools (`list_*`, `get_*`, `search_*`) with jitter; idempotency keys on `create_order` so retries don't double-place.
- **`smoke.py` and `ui_chainlit.py` are excluded from coverage** (`.coveragerc`). They're entry-point shells exercised by running them or by the deployed URL. With another day: an httpx-driven test that walks one full conversation against the live URL.
- **No persistent checkpointer.** A Railway redeploy wipes every active conversation. With another day: `SqliteSaver` (cheapest) or `PostgresSaver` (proper) so multi-turn flows survive a restart.
- **Customer UUID leakage risk.** The system prompt forbids the model from echoing the UUID; Layer 3 doesn't currently detect leaked UUIDs (only secret-shaped patterns). If the model echoed it once, Layer 3 wouldn't block. Mitigation: the verify tool already gates this; a UUID echo would have to come from a hijacked turn. Improvement: add a UUID-shape regex to Layer 3.
- **Single-instance deployment.** Railway runs one container; no horizontal scaling. Fine for prototype demo; not for production traffic.

---

## Roadmap (priority order, with the user-value rationale)

1. **Persistent checkpointer (SqliteSaver, then PostgresSaver).** Conversations survive redeploy; auth handoff to a different instance becomes trivial. Highest user-value because nothing else fixes the "I logged in 5 minutes ago and it asked me again" failure mode.
2. **Moderation as Layer-4 guardrail.** OpenAI / Anthropic moderation endpoint on every output, in parallel with the existing Layer-3 regex. Cheap, high-leverage; closes the *"my regex didn't catch the new attack class"* gap.
3. **Retry-with-backoff for read-only MCP tools.** Idempotency keys on `create_order` so we can retry safely. Covers transient Cloud Run 5xx without surfacing them to the user.
4. **Observability dashboard.** A pinned LangSmith view filtered by `layer=agent` showing P50 / P95 latency, token spend per conversation, and tool-failure rate. Makes the cost case to the VP.
5. **A/B prompt rollout.** `PROMPT_VERSION` is already a variable; wire it to a feature flag to A/B v1 vs v2 against a held-out user cohort. Closes the loop on prompt iteration.
6. **End-to-end test against the deployed URL.** `pytest tests/e2e/` that drives the live Chainlit URL through one full conversation per release. Catches the *"works locally, broken in prod"* class of bugs.
