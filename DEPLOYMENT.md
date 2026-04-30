# DEPLOYMENT.md — Get to a Public URL in <30 Minutes

> Goal: a public, HTTPS URL that runs your Chainlit app, connects to the MCP server, and survives a smoke test. Everything else is a bonus.

---

## Why Railway (primary recommendation)

- **Production cloud**: real container infra, not a sandbox.
- **Python + Chainlit work out of the box** with a Dockerfile or Nixpacks.
- **Persistent connections** to MCP work (Vercel kills these).
- **Free trial → $5/mo Hobby plan**, fast deploy, env vars in UI.
- **Public HTTPS URL** auto-provisioned (`*.up.railway.app`).

Fallback: **HuggingFace Spaces** — also free, Docker-based, slightly slower cold start, fine if Railway fights you.

---

## Pre-deployment checklist (do this BEFORE pushing)

```bash
# 1. App runs locally
chainlit run app/ui_chainlit.py

# 2. Tests green
pytest -q

# 3. .env.example is complete and committed
cat .env.example

# 4. .env is git-ignored (NEVER commit secrets)
grep -E "^\.env$" .gitignore

# 5. requirements.txt is pinned and current
pip freeze > requirements.txt   # only if your venv is clean

# 6. Smoke test script exists
python -m app.smoke
```

`.env.example` should include (no values):

```
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
LANGCHAIN_API_KEY=
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=mcp-bootcamp
MCP_SERVER_URL=
MCP_TRANSPORT=http
LOG_LEVEL=INFO
APP_PORT=8000
```

---

## Files needed for deployment

### `Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install build deps (kept minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Chainlit listens on PORT (Railway sets this) — fall back to 8000 locally
ENV PORT=8000
EXPOSE 8000

# -h = headless (no browser auto-open). --host 0.0.0.0 for container networking.
CMD ["sh", "-c", "chainlit run app/ui_chainlit.py --host 0.0.0.0 --port ${PORT} -h"]
```

### `railway.json` (optional but explicit)

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": { "builder": "DOCKERFILE", "dockerfilePath": "Dockerfile" },
  "deploy": {
    "startCommand": "chainlit run app/ui_chainlit.py --host 0.0.0.0 --port $PORT -h",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3,
    "healthcheckPath": "/",
    "healthcheckTimeout": 30
  }
}
```

### `.dockerignore`

```
.git
.venv
__pycache__/
*.pyc
.env
.env.*
!.env.example
.pytest_cache
htmlcov
node_modules
.DS_Store
*.log
```

---

## Path A — Railway (recommended, ~10 min)

### One-time setup
1. Create a Railway account (GitHub login is fastest).
2. Install the CLI **only if** you want to test the build locally; the dashboard is enough for deploying.
   ```bash
   npm i -g @railway/cli
   railway login
   ```

### Deploy
1. Push your repo to GitHub (private is fine).
2. In Railway dashboard: **New Project → Deploy from GitHub repo → select your repo**.
3. Railway detects the Dockerfile and starts building. Watch the build logs.
4. Once built and *before it crashes on startup*, go to **Variables** tab and add **every** env var from `.env.example` (with real values). The most commonly missed:
   - `OPENAI_API_KEY`
   - `MCP_SERVER_URL`
   - `LANGCHAIN_API_KEY` and `LANGCHAIN_TRACING_V2=true`
5. Trigger redeploy (it auto-redeploys on env var change usually).
6. Once "Deployed" is green, click **Settings → Networking → Generate Domain**. You now have `https://yourapp.up.railway.app`.

### Smoke test the live URL
```bash
# 1. Page loads
curl -I https://yourapp.up.railway.app/

# 2. Open in browser, run one full conversation, confirm:
#    - It connects (no MCP error in UI)
#    - One tool is called successfully
#    - LangSmith shows a trace from prod
```

### Common Railway gotchas
- **Port not respected:** Make sure your start command uses `${PORT}`, not a hardcoded number. Railway injects `PORT` at runtime.
- **Build OOM:** Slim base image and `--no-cache-dir` already help. If it still OOMs, upgrade to Hobby plan or trim deps.
- **MCP connection refused from container:** If your MCP server is on `localhost`, Railway can't reach it. The MCP server must be publicly addressable.
- **Build cache stale:** "Redeploy" button in Railway, or push an empty commit.

---

## Path B — HuggingFace Spaces (fallback, ~10 min)

Use this if Railway gives you trouble or your bootcamp prefers HF.

### Deploy
1. Go to https://huggingface.co/new-space.
2. Name it. SDK: **Docker**. Visibility: Public (free) or Private (Pro).
3. Create. You now have a Space repo.
4. Push your code:
   ```bash
   git remote add space https://huggingface.co/spaces/YOUR_USERNAME/your-space
   git push space main
   ```
5. **Settings → Variables and secrets** → add every env var from `.env.example`. Mark API keys as **Secret**, not **Variable**.
6. Watch the build. Public URL is `https://YOUR_USERNAME-your-space.hf.space`.

### HF Spaces gotchas
- **Port must be 7860** for Spaces' default proxy. Override your start command:
  ```
  chainlit run app/ui_chainlit.py --host 0.0.0.0 --port 7860 -h
  ```
- **First load is slow** (cold container). Hit the URL once before recording Video 3.
- **No persistent disk on free tier** — fine for this project, just don't expect file uploads to survive restarts.

---

## Path C — Render (alternative)

Similar to Railway. Free web services sleep after 15 min of inactivity, which can ruin a demo. If you use Render, **ping the URL right before recording Video 3** to warm it up.

---

## What to put in your README about deployment

```markdown
## Deployment

Live URL: https://yourapp.up.railway.app

### Reproduce the deployment
1. Fork this repo.
2. Create a Railway project from your fork.
3. Set env vars from `.env.example` (you'll need an OpenAI key, a LangSmith key, and the MCP server URL).
4. Railway builds the Dockerfile and provisions an HTTPS domain automatically.

### Architectural choice
Railway over Vercel: this app holds a long-lived MCP connection per session;
Vercel's serverless model would force a reconnect per request. Railway over
AWS/GCP raw: 3-hour budget made a managed PaaS the right tradeoff. Render
was the close runner-up — picked Railway for faster cold starts.
```

That paragraph alone earns the "Tech Choice" justification points.

---

## Production-readiness checklist (last-mile)

Before submitting:

- [ ] Public HTTPS URL works in an incognito window.
- [ ] Env vars in deploy platform match `.env.example` (no missing keys).
- [ ] `.env` is in `.gitignore`. Run `git log -p -- .env` to confirm it was never committed.
- [ ] `requirements.txt` versions are pinned (no `package` without `==x.y.z`).
- [ ] Logs in Railway/HF show clean startup, no tracebacks.
- [ ] One full conversation works end-to-end on the deployed URL.
- [ ] LangSmith shows traces tagged with the project name from production.
- [ ] README has the live URL at the top.

If all eight are true, you've cleared the deployment bar.
