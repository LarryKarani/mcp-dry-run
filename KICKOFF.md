# KICKOFF.md — How to drive Claude Code through this dry run

> Goal: end up with a complete, deployed, tested project that mirrors what you'll need on bootcamp day. Every choice and shortcut you take here is one less you have to figure out under pressure.

---

## Step 0 — One-time setup on your machine (5 min)

```bash
# 1. Get the bundle onto your machine and unzip it
cd ~/projects                              # or wherever you keep code
unzip ~/Downloads/mcp-bootcamp-dryrun.zip
cd mcp-bootcamp-dryrun

# 2. Init git so Claude Code can track its own changes
git init && git add -A && git commit -m "scaffold from bundle"

# 3. Create a venv
uv venv --python 3.11
source .venv/bin/activate                 # Windows: .venv\Scripts\activate

# 4. Copy the env template (you'll fill values in step 1)
cp .env.example .env 2>/dev/null || echo "OPENAI_API_KEY=
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=mcp-bootcamp-dryrun
MCP_SERVER_URL=http://127.0.0.1:8765/mcp
MCP_TRANSPORT=http
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LOG_LEVEL=INFO
APP_PORT=8000" > .env

# 5. Open it in your editor + open a terminal where Claude Code will run
code .                                     # or your editor of choice
```

Get an **OpenAI API key** (https://platform.openai.com/api-keys) and a **LangSmith API key** (https://smith.langchain.com → Settings → API keys, free tier is enough). Paste both into `.env`.

Install the Claude Code CLI if you haven't: `npm i -g @anthropic-ai/claude-code` then `claude` in your project dir.

---

## Step 1 — The kickoff prompt (paste this verbatim into Claude Code)

```
We're doing a 3-hour bootcamp simulation. The goal is a production-ready chatbot that consumes an MCP server, deployable to a public URL.

Read these files in order before writing any code:
  1. CLAUDE.md            — the rubric and architecture (your contract)
  2. DRY_RUN_SCENARIO.md  — the business domain (Acme Coffee) and concrete success criteria
  3. VIDEO_CHECKPOINTS.md — when I'll record videos and what each must prove
  4. DEPLOYMENT.md        — how we ship to Railway

Also read what's already scaffolded:
  - mcp_server/server.py and mcp_server/data.py (the MCP server is DONE — runs with `python -m mcp_server.server`)
  - app/config.py, app/llm.py, app/mcp_client.py (skeletons of the boundary layers)
  - app/prompts/ (v1, v2, v3 + current.py — DONE, demonstrates iteration pattern)
  - prompts_log.md (DONE — extend if you iterate further)

Your job: build everything else per CLAUDE.md, in this order. Stop after each phase and tell me what you did before moving on. I will run tests between phases.

Phase A — make it run end-to-end (target: 30 min)
  - app/guardrails.py: 3 layers (input validation, system-prompt secrecy, output validation)
  - app/observability.py: LangSmith env wiring + a @traceable helper
  - app/agent.py: use langchain.agents.create_agent with tools from MCPClientHolder; wrap input/output with guardrails
  - app/ui_chainlit.py: @cl.on_chat_start opens MCP, @cl.on_message runs the agent with checkpointed memory, @cl.on_chat_end closes
  - app/smoke.py: connects to MCP, lists tools, runs one canned query, prints result
  - requirements.txt: pinned versions
  - .env.example: complete

Verify before moving on: I should be able to run `python -m mcp_server.server` in one terminal and `chainlit run app/ui_chainlit.py` in another, and have a working conversation about coffee.

Phase B — tests (target: 30 min)
  - tests/conftest.py: fixtures including a fake LLM (langchain_core.language_models.fake.FakeListChatModel) so tests run without API calls, and a fixture that resets mcp_server data between tests
  - tests/test_mcp_client.py: tool discovery, tool count, no hardcoded names (grep test)
  - tests/test_guardrails.py: input validation cases, output-leak detector, ≥22 adversarial cases
  - tests/test_agent_happy.py: H1–H6 from DRY_RUN_SCENARIO.md (use FakeListChatModel scripted to call the right tool)
  - tests/test_agent_edges.py: E1–E8 from DRY_RUN_SCENARIO.md
  - pytest.ini configured for asyncio mode

Verify: `pytest -q` is fully green.

Phase C — production polish (target: 30 min)
  - Dockerfile + railway.json + .dockerignore (use DEPLOYMENT.md as reference)
  - .gitignore covering .venv, .env, __pycache__, .pytest_cache, etc.
  - chainlit.md (the landing page content)
  - docs/architecture.md (one diagram + one page of prose)
  - docs/decisions.md (ADR-lite for the 5 most significant choices)
  - docs/limitations.md (honest list)
  - README.md (live URL placeholder, setup, how to test, decisions summary)

Verify: `pytest -q` still green; lint clean (ruff check app/ tests/ mcp_server/).

Phase D — eval comparison (target: 15 min, cut first if behind)
  - tests/test_eval.py: parameterise tests across two LLM_MODEL values (e.g. gpt-4o-mini vs gpt-4o), record pass rate + mean latency per model, write a markdown table to docs/decisions.md

Phase E — deploy (target: 15 min)
  - Walk me through Railway setup (you can't do it for me; give me the exact clicks and env vars to set)
  - Provide a curl command I run to smoke-test the deployed URL

When you're done with Phase A, stop and ping me. Don't run ahead.

Rules:
- No tool name string literals anywhere in app/ (the LLM picks tools via discovery).
- Every prompt change goes in prompts_log.md with hypothesis/observation/decision.
- Every except clause logs the error with a reason.
- No print() for app logs — use logging.
- Type hints everywhere.
- Keep functions under ~40 lines.
```

---

## Step 2 — While Claude Code works, you do these (in parallel)

These don't need code, just your attention:

1. **Read `VIDEO_CHECKPOINTS.md` end to end.** The structure is more important than the words.
2. **Decide your recording tool now.** OBS, Loom, QuickTime — pick one, do the audio test described in VIDEO_CHECKPOINTS.md.
3. **Open the four tabs you'll use during videos:** terminal, browser pointed at LangSmith (after you create the project there), code editor, browser tab where Chainlit will run.
4. **Skim `DEPLOYMENT.md` Path A (Railway).** Create a Railway account now if you don't have one — the email verification can take a few minutes and you don't want it blocking you at the deploy phase.

---

## Step 3 — Recording the videos for the dry run

Even though this is practice, **record the videos**. Reasons:
- You'll see your own filler words and pacing problems while there's still time to fix them.
- The VIDEO_CHECKPOINTS.md structure feels different when you actually do it vs. when you read about it.
- You'll discover which terminal commands you fumble — those are the ones to alias before bootcamp day.

Don't share these. They're rehearsals. Treat them as such — under 5 min each, one take.

---

## Step 4 — When the dry run is done

Spend 15 min writing yourself a "lessons learned" note:
- What took longer than expected?
- What command did you reach for and have to look up?
- What part of `CLAUDE.md` would you change if you wrote it again?
- What single thing would have saved you the most time?

Update `CLAUDE.md` with the answer to that last question. The version you take into bootcamp day will be sharper than the one you started with — that's the entire point of doing the dry run.

---

## If Claude Code goes off the rails

- "You're not following Phase order — stop, return to CLAUDE.md."
- "You added a hardcoded tool name in `app/agent.py` line N — remove it. Tool discovery is dynamic."
- "Run `pytest -q` and paste the output before claiming Phase B is done."
- "Don't add features I didn't ask for. Stay scoped to DRY_RUN_SCENARIO.md."

The most common Claude Code failure mode in projects like this is **scope creep** — it'll want to add features (auth, payments, fancy UI) that aren't in the brief. Steer it back ruthlessly. You have 3 hours.
