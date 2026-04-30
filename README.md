# MCP Bootcamp Dry Run — starter bundle

A scaffolded starter for practising the bootcamp challenge before the real day. The MCP server (Acme Coffee Co e-commerce) is included so you can run the whole stack locally.

## Files at a glance

| File | What it is | Status |
|---|---|---|
| `KICKOFF.md` | **Start here.** How to use this bundle with Claude Code. | — |
| `CLAUDE.md` | Project contract / rubric — Claude Code reads this. | Done |
| `DRY_RUN_SCENARIO.md` | Acme Coffee business brief + concrete success criteria. | Done |
| `VIDEO_CHECKPOINTS.md` | Recording playbook for all 3 videos. | Done |
| `DEPLOYMENT.md` | Railway + HF Spaces deploy guides. | Done |
| `prompts_log.md` | Iteration log v1 → v2 → v3. | Done — extend if you iterate |
| `mcp_server/` | The MCP server (FastMCP, 6 tools). Stand-in for the real bootcamp server. | Done |
| `app/config.py` | Pydantic settings, env-var loader. | Done |
| `app/llm.py` | LLM factory (OpenAI / Anthropic). | Done |
| `app/mcp_client.py` | MCP connection + tool discovery. | Done |
| `app/prompts/` | v1, v2, v3 system prompts + loader. | Done |
| `app/agent.py` | LangGraph/LangChain agent assembly. | **Claude Code builds this** |
| `app/guardrails.py` | 3-layer defense. | **Claude Code builds this** |
| `app/observability.py` | LangSmith wiring. | **Claude Code builds this** |
| `app/ui_chainlit.py` | Chainlit chat UI. | **Claude Code builds this** |
| `app/smoke.py` | Health check script. | **Claude Code builds this** |
| `tests/` | pytest suite. | **Claude Code builds this** |
| `docs/` | architecture, decisions, limitations. | **Claude Code builds this** |
| `Dockerfile`, `railway.json` | Deploy config. | **Claude Code builds this** |

## Quickstart

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in OPENAI_API_KEY and LANGCHAIN_API_KEY

# Terminal 1 — the MCP server
python -m mcp_server.server

# Terminal 2 — verify the MCP server is up and tools are discoverable
python -c "import asyncio; from app.mcp_client import MCPClientHolder; \
  h = MCPClientHolder(); \
  tools = asyncio.run(h.connect()); \
  print('Discovered:', [t.name for t in tools])"
```

You should see all 6 Acme Coffee tools listed. That confirms the scaffolding works. From here, follow `KICKOFF.md` step 1 to drive Claude Code through the rest.

## Why the MCP server is included

On bootcamp day you won't get the MCP server source — you'll get a URL. So why is it here?

1. **You can practice without depending on a remote service.** No flaky internet, no rate limits.
2. **Seeing the server side once makes the client side make sense** — particularly tool descriptions, schema validation, and error shapes.
3. **You can deliberately break it** to test edge cases (kill it mid-conversation, return malformed responses, add latency).

On real bootcamp day, delete `mcp_server/`, point `MCP_SERVER_URL` at their URL, and your `app/` code shouldn't change at all. That's the architectural test.
