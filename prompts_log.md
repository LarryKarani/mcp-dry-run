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

**Observed (against initial happy-path probe):** TBD — will update once Phase B tests run.

**Decision:** Ship as v1; iterate to v2 once we see how the model handles the multi-turn auth scaffold under real LLM (gpt-4o-mini).
