# BOOTCAMP_DAY.md — Real-day migration playbook

> Read this BEFORE the bootcamp starts. Print it. Keep it open in a tab during the run. Every minute spent figuring out something you already figured out in the dry run is a minute lost.

---

## Pre-bootcamp (do the night before)

- [ ] Confirm OpenRouter key has credit (≥$5 — eval phase costs ~$0.50, headroom for retries).
- [ ] Confirm LangSmith key works — visit https://smith.langchain.com → see your projects.
- [ ] Confirm Railway account works — log in, see the dry-run project.
- [ ] **Decide: reuse the dry-run Railway project (faster) or create a fresh one (cleaner demo URL).** Recommend: reuse, just rename the service after pointing it at the new MCP.
- [ ] `git clone <your-handle>/mcp-dry-run mcp-bootcamp-final && cd mcp-bootcamp-final && git remote set-url origin <new-repo>` so the dry-run history isn't lost.
- [ ] Open Railway, OpenRouter dashboard, LangSmith, code editor, terminal, browser tabs in advance.

---

## Step 1 — When they hand you the MCP server brief (0:00–0:10)

1. **Read the entire brief once, then again.** Underline the business domain in one sentence.
2. **Edit `.env`:**
   ```
   MCP_SERVER_URL=<bootcamp-provided>
   MCP_TRANSPORT=http   # or sse, whichever they say
   ```
3. **Confirm tool discovery works:**
   ```fish
   PYTHONPATH=. .venv/bin/python -c "import asyncio; from app.mcp_client import MCPClientHolder; tools = asyncio.run(MCPClientHolder().connect()); [print(t.name, '—', (t.description or '')[:80]) for t in tools]"
   ```
   You should see the full tool list. **If this fails, fix it before doing anything else.** Common causes: wrong transport (http vs sse), auth header missing, URL typo.
4. **Skim the tool descriptions.** Note the *intents* they cover (browse / mutate / lookup / cancel / etc.) — these become your H/E test scenarios.

---

## Step 2 — Reset the domain-specific files (0:10–0:15)

Run these commands verbatim:

```fish
# Wipe domain-specific content; keep file structure for the iteration story.
rm -rf mcp_server/
rm -rf docs/
rm -f DRY_RUN_SCENARIO.md KICKOFF.md
mkdir -p docs

# Reset prompts to v1 only.
echo "v1" > /tmp/_pv && \
sed -i '' 's/PROMPT_VERSION = "v3"/PROMPT_VERSION = "v1"/' app/prompts/current.py && \
rm -f app/prompts/system_v2.md app/prompts/system_v3.md
# Then write a fresh app/prompts/system_v1.md based on the brief.

# Reset prompts log.
> prompts_log.md
echo "# Prompts Log\n\nAppend-only. One entry per system prompt version.\n" >> prompts_log.md

# Reset agent test files (keep test_guardrails.py, test_eval.py, test_mcp_client.py — they're mostly reusable).
> tests/test_agent_happy.py
> tests/test_agent_edges.py
```

---

## Step 3 — Hand off to Claude Code (0:15)

**Paste this prompt verbatim:**

```
We're at bootcamp day. We're reusing the dry-run scaffolding (CLAUDE.md §0).
Read these files in order before writing any code:
  1. CLAUDE.md            — the rubric (especially §0 reuse strategy and §12 video stops)
  2. <bootcamp brief>     — the business domain + tools they gave us
  3. VIDEO_CHECKPOINTS.md — when I'll record videos and what each must prove
  4. DEPLOYMENT.md        — Railway path

The MCP_SERVER_URL is set in .env. Confirm tool discovery works first thing
(commands in BOOTCAMP_DAY.md step 1) and paste the tool list back to me.

Your job: drive the same five phases from the dry run (A → E in CLAUDE.md
§12), but adapt the domain layer:

Phase A — write app/prompts/system_v1.md (scope, identity, tool-use rules,
refusal phrasing) based on the discovered tool list. Verify chainlit run
works end-to-end with one happy-path query.

Phase B — rewrite tests/test_agent_happy.py and tests/test_agent_edges.py
for the new domain. The conftest fixture that started a local MCP server
in-thread won't apply — use the hosted MCP for tests, or mock at the LLM
layer with FakeAgentModel only. Update guardrails._PROMPT_LEAK_FRAGMENTS.

Phase C — regenerate docs/architecture.md, docs/decisions.md, docs/limitations.md,
chainlit.md, and the README intro for the new domain. Pre-existing structure
applies; just swap the content.

Phase D — re-run tests/test_eval.py against two models. The asserter
heuristics may need broadening for the new domain (we hit this in dry run).

Phase E — point the existing Railway service at the new MCP_SERVER_URL.
The dry-run service URL stays the same; only env vars change.

🎥 RULE: Stop at every video checkpoint per CLAUDE.md §12. Run the pre-record
verification commands. Prompt me to record. Wait for me to say 'recorded'
before moving on.

Rules from the dry run still apply:
- No tool name string literals anywhere in app/.
- Every prompt change goes in prompts_log.md.
- Type hints, ≤40-line functions, logging not print.
```

---

## Common pitfalls we hit in the dry run (don't repeat them)

1. **Eval asserter heuristics are too narrow.** The first eval run failed because *"I'm here to assist with X"* didn't match my refusal-marker list. Broaden upfront.
2. **`os.environ.setdefault` in conftest masks real `.env` values.** If the eval needs the real OpenRouter key, read it from `.env` directly (we have a helper in `tests/test_eval.py`).
3. **Railway healthcheck on `/` will fail for the MCP service.** Our `railway.json` no longer sets `healthcheckPath` — leave it that way.
4. **Chainlit's loader doesn't add the project root to `sys.path`.** `app/ui_chainlit.py` self-bootstraps via `sys.path.insert(0, project_root)` — leave that block.
5. **`PORT` env-var expansion is shell-dependent.** Our Dockerfile uses `sh -c "exec chainlit … --port ${PORT:-8000} -h"`. Do not switch the builder to Nixpacks.
6. **MCP tool errors must be `handle_tool_error=True`.** `app/agent.py::_with_error_handling` does this — without it, `place_order` errors abort the turn instead of being paraphrased.
7. **Don't push real API keys to git.** `.env` is git-ignored; double-check `git log -p -- .env` returns nothing before pushing publicly.

---

## What to remove from the prompts before submission

If your bootcamp evaluator looks at the repo, they shouldn't see Acme-specific dry-run artifacts. After Step 2 above, `git grep -i acme` should return nothing in `app/`, `tests/`, `docs/`, `chainlit.md`, `README.md`, or `prompts_log.md`. The only mention should be in git history.
