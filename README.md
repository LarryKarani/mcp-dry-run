# Acme Coffee MCP Chatbot

A production-ready chatbot that consumes a Model Context Protocol (MCP) server to handle Acme Coffee Co's online catalogue, stock, and order flows. Built for the bootcamp dry-run challenge.

**Live URL:** `https://<your-app>.up.railway.app/` *(set after Phase E deploy — see `DEPLOYMENT.md`)*

---

## What it does

Customers can chat to:

- Browse the catalogue (*"any decaf options?"*)
- Get product details (*"tell me about AC-ESP-001"*)
- Check stock (*"is the Yirgacheffe in stock?"*)
- Place orders (SKU + quantity + email)
- Look up an existing order
- Cancel a pending order

The agent stays in scope (no brewing tutorials, no off-topic chat) and refuses prompt-injection / role-swap attempts.

---

## Quickstart (under 5 minutes)

```bash
git clone <this repo>
cd mcp-bootcamp-dryrun

python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env: at minimum set OPENROUTER_API_KEY and (optionally) LANGCHAIN_API_KEY

# Terminal 1 — local MCP server (Acme Coffee)
python -m mcp_server.server          # binds 127.0.0.1:8000/mcp

# Terminal 2 — Chainlit UI
PYTHONPATH=. chainlit run app/ui_chainlit.py --port 8001
# open http://127.0.0.1:8001
```

The MCP server's startup log says port 8765 — that's a stale log line in `mcp_server/server.py`. FastMCP actually binds 8000; `.env` is set up to match reality.

---

## How to test

```bash
# Full suite (76 tests, ~2s)
PYTHONPATH=. pytest -q

# Coverage on app/ (target: ≥70%; current: 91%)
PYTHONPATH=. pytest --cov=app --cov-report=term-missing

# Lint
ruff check app/ tests/ mcp_server/

# End-to-end smoke (requires MCP server running)
PYTHONPATH=. python -m app.smoke
```

The test suite runs hermetically — `tests/conftest.py` starts the MCP server in-thread on a free port via uvicorn, so you don't need to start anything externally for tests.

---

## Architecture (one paragraph)

Four independently-testable layers. **`mcp_client.py`** is the only module that imports MCP — tools are discovered dynamically (`tests/test_mcp_client.py` greps `app/` to enforce zero hardcoded tool names). **`agent.py`** wraps `langchain.agents.create_agent` with `InMemorySaver` for multi-turn state and applies guardrails around every turn. **`guardrails.py`** is three layers of defense: input validation, prompt-secrecy clauses (in `prompts/system_v3.md`), and output validation (catches prompt leaks, identity hijacks, secret-shaped strings, tracebacks). **`ui_chainlit.py`** is a thin Chainlit shell — open MCP on chat start, run the agent on each message, close on chat end. Full diagram in `docs/architecture.md`.

---

## Decisions summary

Detailed reasoning in `docs/decisions.md`.

1. **LangGraph (`langchain.agents.create_agent`)** over hand-rolled ReAct or `AgentExecutor` — the compiled state graph gives multi-turn anaphora (E8) for free.
2. **Three guardrail layers** — defense in depth; the prompt alone leaks ~3/22 adversarial cases, output validation catches the rest.
3. **LLM behind a factory** — `LLM_PROVIDER` env var; OpenRouter default; one-line swap to OpenAI direct or Anthropic Claude for Phase D eval.
4. **MCP via `langchain-mcp-adapters`** — idiomatic LangChain integration; tool descriptions and schemas come from the server.
5. **MCP server in-thread for tests** — `pytest -q` runs hermetically with real round-trips, no external process to manage.

### What I explicitly chose **not** to use

- ❌ Raw OpenAI function-calling SDK — would force hand-wired tool dispatch, defeating "idiomatic MCP usage."
- ❌ Streamlit — not chat-first, would force rebuilding chat primitives.
- ❌ Vercel — serverless model breaks long-lived MCP sessions.
- ❌ AWS / GCP / Azure raw — too much config for the time budget; Railway is a real production cloud.

---

## Repo map

| Path | Purpose |
|---|---|
| `app/config.py` | Pydantic settings, env loader, logging config |
| `app/llm.py` | LLM factory (OpenRouter / OpenAI / Anthropic) |
| `app/mcp_client.py` | MCP connection lifecycle + dynamic tool discovery |
| `app/agent.py` | LangGraph agent assembly, input/output guardrail wrapping |
| `app/guardrails.py` | Three-layer defense (input, prompt-secrecy detector, output) |
| `app/observability.py` | LangSmith env wiring + `traced` decorator |
| `app/ui_chainlit.py` | Chainlit chat UI (thin shell) |
| `app/smoke.py` | End-to-end health-check script |
| `app/prompts/` | System prompts v1, v2, v3; `current.py` selects active |
| `prompts_log.md` | Append-only iteration log (hypothesis → observation → decision) |
| `tests/` | pytest suite — 76 tests, 91% coverage on `app/` |
| `mcp_server/` | Local Acme MCP server (FastMCP, 6 tools) — for dev and tests |
| `docs/architecture.md` | Diagram + prose explanation of the layers |
| `docs/decisions.md` | ADR-lite for the 5 most significant choices |
| `docs/limitations.md` | Honest list of gaps + roadmap |
| `Dockerfile`, `railway.json` | Deploy config (see `DEPLOYMENT.md`) |

---

## Deployment

See `DEPLOYMENT.md` for the Railway setup walkthrough. Short version:

1. Push this repo to GitHub.
2. New Railway project from the GitHub repo.
3. Set env vars from `.env.example`.
4. Generate a public domain.
5. Smoke test: `curl -I https://<your-app>.up.railway.app/`.

Note: the deployed Chainlit container needs `MCP_SERVER_URL` to point at a publicly addressable MCP server — `127.0.0.1:8000` is unreachable from the container. Either (a) deploy `mcp_server` as a sibling Railway service, or (b) tunnel the local one via ngrok during the demo.
