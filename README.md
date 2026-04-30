# Meridian Electronics — Customer Support Chatbot

A production-ready prototype that consumes Meridian's hosted Model Context Protocol (MCP) server to handle catalogue browsing, customer authentication, order placement, and order history lookup. Built for the AI Engineer assessment.

**Live URL:** https://mcp-dry-run-production.up.railway.app/
**MCP server:** `https://order-mcp-74afyau24q-uc.a.run.app/mcp`

---

## What it does

Customers can chat to:
- **Browse the catalogue** — by category (*"show me your monitors"*), free text (*"do you sell mechanical keyboards?"*), or SKU (*"tell me about MON-0067"*).
- **Authenticate** — email + 4-digit PIN. Required before any account-touching action.
- **See order history** — *"what orders do I have?"*.
- **Place a multi-line order** — *"order 1 of MON-0054 and 2 of KEY-0010"*.
- **Look up an order by ID** — *"what's the status of order 9d3b…?"*.

Out of scope by design: returns, refunds, shipping ETAs, account changes, brewing tutorials, weather, anything else outside the catalogue + orders surface.

---

## Quickstart (under 5 minutes)

```bash
git clone https://github.com/LarryKarani/mcp-dry-run.git
cd mcp-dry-run

python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env: set OPENROUTER_API_KEY (and optionally LANGCHAIN_API_KEY).

PYTHONPATH=. chainlit run app/ui_chainlit.py --port 8001
# open http://127.0.0.1:8001
```

The MCP server is hosted on Cloud Run; no local server to start.

---

## How to test

```bash
# Full hermetic suite (76 tests, ~2s, no API calls)
PYTHONPATH=. pytest -q

# Coverage on app/ (target: ≥70%; current: 91%)
PYTHONPATH=. pytest --cov=app --cov-report=term-missing

# Lint
ruff check app/ tests/

# Live smoke against the hosted MCP (one LLM call)
PYTHONPATH=. python -m app.smoke

# Eval comparison across two cost-effective models (real LLM calls; opt-in)
PYTHONPATH=. pytest -m eval
```

`tests/conftest.py` discovers tools from the hosted MCP for tool-discovery tests, and uses in-process stubs for everything else — agent tests never create real orders against the hosted server.

---

## Architecture (one paragraph)

Four independently-testable layers. **`mcp_client.py`** is the only module that imports MCP — tools are discovered dynamically (`tests/test_mcp_client.py` greps `app/` to enforce zero hardcoded tool names). **`agent.py`** wraps `langchain.agents.create_agent` with `InMemorySaver` for multi-turn state and applies guardrails around every turn. **`guardrails.py`** is three layers of defence: input validation, prompt-secrecy clauses (in `prompts/system_v1.md`), and output validation (catches prompt leaks, identity hijacks, secret-shaped strings, tracebacks). **`ui_chainlit.py`** is a thin Chainlit shell — open MCP on chat start, run the agent on each message, close on chat end. Full diagram and prose in `docs/architecture.md`.

The architecturally interesting part of this domain is the auth flow: the LLM walks it, holding the customer UUID in checkpointed message history rather than in our own session-state code. See ADR-5 in `docs/decisions.md`.

---

## Decisions summary

Detailed reasoning in `docs/decisions.md`.

1. **LangGraph (`langchain.agents.create_agent`)** over hand-rolled ReAct or `AgentExecutor` — multi-turn anaphora for free.
2. **Three guardrail layers** — defence in depth; the prompt alone leaks on translate / repeat / persuasion attacks.
3. **LLM behind a factory** — `LLM_PROVIDER` env var; OpenRouter default; one-line swap to OpenAI direct or Anthropic Claude for eval.
4. **MCP via `langchain-mcp-adapters`** — idiomatic LangChain integration; tool descriptions and schemas come from the server.
5. **LLM walks the auth flow** — no custom session-state code; the checkpointer + system prompt do the work.

### What I explicitly chose **not** to use

- ❌ Raw OpenAI function-calling SDK — would force hand-wired tool dispatch, defeating the brief's *"discover and use"* spirit.
- ❌ Streamlit / Gradio — Chainlit is purpose-built for chat with streaming, history, and session lifecycle as native primitives.
- ❌ HuggingFace Spaces — Railway gives a faster cold-start and a real container; the brief lists Vercel/GCP/AWS/Azure as bonus tier and Railway is in the same class.

---

## Repo map

| Path | Purpose |
|---|---|
| `app/config.py` | Pydantic settings, env loader, logging config |
| `app/llm.py` | LLM factory (OpenRouter / OpenAI / Anthropic) |
| `app/mcp_client.py` | MCP connection lifecycle + dynamic tool discovery |
| `app/agent.py` | LangGraph agent assembly, input/output guardrail wrapping |
| `app/guardrails.py` | Three-layer defence (input, prompt-secrecy detector, output) |
| `app/observability.py` | LangSmith env wiring + `traced` decorator |
| `app/ui_chainlit.py` | Chainlit chat UI (thin shell) |
| `app/smoke.py` | End-to-end health-check script |
| `app/prompts/` | System prompt versions; `current.py` selects active |
| `prompts_log.md` | Append-only iteration log (hypothesis → observation → decision) |
| `tests/` | pytest suite — 76 tests, 91% coverage on `app/` |
| `docs/architecture.md` | Diagram + prose explanation of the layers |
| `docs/decisions.md` | ADR-lite for the 5 most significant choices |
| `docs/limitations.md` | Honest list of gaps + roadmap |
| `Dockerfile`, `railway.json` | Deploy config (Railway, Dockerfile builder) |

---

## Deployment

Hosted on Railway via Dockerfile builder (`builder=DOCKERFILE` in `railway.json`). Auto-redeploys on push to `main`.

```bash
# Smoke test the live URL
curl -I https://mcp-dry-run-production.up.railway.app/
```

Required Railway env vars (mirror `.env.example`):
- `OPENROUTER_API_KEY`
- `LLM_PROVIDER=openrouter`
- `LLM_MODEL=openai/gpt-4o-mini`
- `MCP_SERVER_URL=https://order-mcp-74afyau24q-uc.a.run.app/mcp`
- `MCP_TRANSPORT=http`
- `LANGCHAIN_TRACING_V2=true`
- `LANGCHAIN_API_KEY`
- `LANGCHAIN_PROJECT=meridian-prod`
