# Prompts Log — Meridian Electronics

Append-only. One entry per system prompt version. Format: hypothesis, observation, decision.

---

## v1 — initial baseline (2026-04-30)
**File:** `app/prompts/system_v1.md`

**Hypothesis:** A scope-limited prompt that explicitly describes the auth flow (email + PIN → UUID → reuse UUID across turns) is enough for the LLM to drive a verify→list-orders→place-order workflow without re-asking for credentials.

**Key clauses introduced:**
- Scope whitelist (browse / verify / order history / create order).
- Out-of-scope refusal block.
- Auth flow as a 4-step sequence with "do not re-ask, do not invent UUID, do not proceed without one".
- "Never reveal customer UUID or PIN" — UUIDs are returned by the tool but should not be echoed back to the user verbatim.
- Standard identity persistence + prompt-secrecy clauses (carried from dry-run experience).

**Observed (against `pytest -m eval`, 2026-04-30):**
- `openai/gpt-4o-mini` — happy 5/5, adversarial 5/5. **Mean turn latency 7.96s; max 33.6s.** The max-latency outlier was the auth + list-orders chain (two tool calls + a verbose summary).
- `anthropic/claude-3.5-haiku` — happy 4/5, adversarial 5/5. Mean 5.86s, max 16.1s. Failed one happy-path scenario; faster overall.
- Live manual test confirmed the auth flow walks correctly end-to-end (customer types credentials → agent verifies → agent lists orders without re-prompting).

**Decision:** Quality is solid; latency is the issue. Mini's 33.6s outlier is right at SC-6's 8s P95 budget — would feel slow to a customer. Hypothesis: verbose response generation is the dominant cost. Iterate to v2 with explicit brevity rules.

---

## v2 — brevity directive for tool-result summaries (CURRENT)
**File:** `app/prompts/system_v2.md`
**Diff vs v1:** added a "Reply length and shape" block:
- Cap replies at ~4 sentences unless asked for more detail.
- When summarising lists (products, orders), show at most 5 items + offer to expand.
- For order create/cancel confirmations, surface only status + ID.
- Numbers and IDs from tool output verbatim.

**Hypothesis:** The brevity directive cuts emitted-token count on tool-result summaries, which dominated the v1 latency outlier. Should not regress quality — both models scored 5/5 happy on v1 (modulo the one haiku miss), and the new clause does not change tool-selection behaviour.

**Observed (against `pytest -m eval`, 2026-04-30):**
- `openai/gpt-4o-mini` — happy 5/5, adversarial 5/5. **Mean 4.31s, max 11.50s.** Down from 7.96s/33.6s on v1 — 46% mean reduction, 66% max reduction.
- `anthropic/claude-3.5-haiku` — happy 4/5, adversarial 5/5. Mean 5.81s, max 13.8s — flat vs haiku v1.
- Quality unchanged on both models.

**Decision:** Ship v2. Mini-on-v2 is now both faster and higher quality than haiku-on-v2; the brevity directive paid off without any tool-selection regressions. **Not iterating to v3** — further changes would be improvements without a measured failure to fix; the marginal value is below the cost of testing another iteration in the time we have.
