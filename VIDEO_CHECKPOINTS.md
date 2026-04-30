# VIDEO_CHECKPOINTS.md — Your Recording Playbook

> Three videos. Each one earns or loses real points. The pattern that wins: **prove it works on screen before you talk about it**. Run the tests on camera, then explain.

---

## Universal rules for all three videos

1. **Run the test suite live, on camera, before you start talking about features.** Even 10 seconds of green dots does more for credibility than 5 minutes of explanation.
2. **Have your terminal, browser (LangSmith), code editor, and the deployed URL all open in tabs before you hit record.** Tab-fumbling reads as unprepared.
3. **Speak in claims-then-proof, not narration.** Bad: "So I'm clicking on the file…" Good: "My MCP client has zero hardcoded tool names — let me grep to prove it."
4. **Hit your time targets.** Long videos signal you couldn't edit your own thinking.
5. **One take is fine. Don't perfectionist yourself out of the time budget.**

---

## 🎥 VIDEO 1 — Approach & Architecture (~3–5 min)

**Record at:** ~30–45 minutes in, after scaffolding and one successful MCP tool call from a script.

### Verify before recording (run these, all must pass)

```bash
# 1. MCP discovery works — no hardcoded tool names
python -c "import asyncio; from app.mcp_client import get_mcp_tools; \
  tools, _ = asyncio.run(get_mcp_tools()); print([t.name for t in tools])"

# 2. Grep proves it
grep -rn "tool_name\|hardcoded" app/ || echo "clean"

# 3. The success criteria file exists and is filled in
cat docs/success_criteria.md   # or wherever you put it

# 4. prompts_log.md has at least v1
cat prompts_log.md
```

If all four show what you expect, hit record.

### What to say (this is your skeleton, not a script)

**Open with the problem (15 sec).**
> "I'm building a production-ready chatbot that consumes the [MCP server name] MCP server to handle [one-sentence business scenario]. I've got 3 hours. Here's how I'm thinking about it."

**Show the success criteria file (45 sec).**
> "First thing I did — before writing any code — was define measurable success criteria. Not 'the chatbot should work' but specific, testable claims. [Read 3–4 of them aloud.] Every test in my suite will map back to one of these."

**Show the architecture (90 sec).**
Open `docs/architecture.md` or sketch it inline.
> "Four layers, each independently testable. MCP client knows nothing about the LLM. Agent knows nothing about the UI. Guardrails are pure functions. This means I can swap the model for evaluation without touching MCP code, and I can write unit tests against any layer in isolation."

**Show the MCP integration is idiomatic (60 sec).**
Live demo: run the discovery script, show the tools list. Then grep your codebase to prove no tool names are hardcoded.
> "Tools are discovered dynamically at startup. The LLM picks which one to call based on descriptions from the server. Nothing in my code says 'if user says X call tool Y' — that's the LLM's job."

**Tradeoffs and what I'd cut (45 sec).**
> "I'm using LangGraph over a vanilla AgentExecutor because of multi-turn state. I'm using Chainlit over Streamlit because chat is its native form factor. If I run out of time, the first thing I'm cutting is the multi-model eval comparison — tests and deploy are non-negotiable."

**Close with the plan (15 sec).**
> "Next 45 minutes: agent + UI + happy path tests. After that: guardrails and adversarial suite. Deploy at the 2-hour mark. See you in Video 2."

### Common mistakes to avoid in Video 1
- Don't demo a half-working chatbot. Video 1 is about *thinking*, not *output*. A working tool-discovery script is enough.
- Don't read your README aloud. Show the artifacts that demonstrate the thinking.
- Don't skip the "what I'd cut" line — it's the engineering judgment moment graders score.

---

## 🎥 VIDEO 2 — Mid-Build Progress (~4–6 min)

**Record at:** ~1:50–2:00 in, after the agent works end-to-end with guardrails and most tests passing.

### Verify before recording (run these, all must pass)

```bash
# 1. Full test suite
pytest -q

# 2. Lint clean
ruff check app/

# 3. Chainlit app starts and a happy-path conversation works in the browser
chainlit run app/ui_chainlit.py -h    # then test one flow manually

# 4. LangSmith shows traces for that conversation
# Open LangSmith → your project → confirm runs are visible

# 5. prompts_log.md shows at least v1 → v2 with reasons
cat prompts_log.md

# 6. Adversarial test count
pytest tests/test_guardrails.py -v | tail
```

### What to say

**Open with what's working (30 sec).**
> "Halfway in. Here's what's working." Run `pytest -q` on camera. Show green dots.

**Demo a real conversation (90 sec).**
Open the Chainlit UI. Run a multi-turn flow that exercises 2–3 tools. Then deliberately throw in an edge case (ambiguous query, off-topic, or a prompt injection) and show the agent handling it gracefully.
> "Notice it asked a clarifying question instead of guessing. And here — [paste injection] — it stays in role. That's not the system prompt alone, it's defense in depth: input validation, prompt guardrails, output validation."

**Show LangSmith trace (60 sec).**
Open the trace for the conversation you just ran.
> "Full trace, user input through agent decision through MCP call back to response. Token count: X. Latency: Y. This is how I know my P95 is under my 8-second target."

**Show the prompts log (60 sec).**
> "I'm on prompt version 3. Started with a minimal scope statement, v1 failed two adversarial tests, v2 added explicit refusal patterns, v3 moved the refusal logic into guardrails for defense in depth. Each iteration is logged with the trace that triggered it."

**Obstacles — be honest (60 sec).**
> "Here's what hasn't gone smoothly. [One concrete thing.] I tried [approach A], it [failed/was slow], so I [pivoted to B]. Trade-off is [honest tradeoff]."
Examples that work: MCP server's tool descriptions are vague so I added a tool-disambiguation step / Chainlit session state collided with LangGraph's checkpointer so I keyed checkpoints by session ID / first model I tried hallucinated tool args so I switched to one with stricter schema adherence.

**Close with the plan (30 sec).**
> "Next: deploy to Railway, run the eval comparison, then Video 3."

### Common mistakes to avoid in Video 2
- Don't fake a smooth demo. If something flakes, acknowledge it and move on. "That's flaky, here's why" is better than re-recording 3 times.
- Don't claim metrics you can't show. If you say "P95 is 6 seconds," LangSmith should be open.
- Don't skip the obstacles section. Pretending nothing went wrong reads as either dishonest or shallow.

---

## 🎥 VIDEO 3 — Final Pitch to Leadership (~5–8 min)

**Record at:** Last 15 min. This is the most important deliverable. Treat it as a pitch, not a tour.

### Verify before recording (run all of this)

```bash
# 1. Full suite green
pytest -v

# 2. Coverage
pytest --cov=app --cov-report=term-missing

# 3. Adversarial pass rate calculated
pytest tests/test_guardrails.py -v | grep -E "passed|failed"

# 4. Deployed URL responds
curl -I https://your-app.up.railway.app/   # or your URL

# 5. Open the deployed URL in a browser, run one full conversation, confirm it works
# 6. Open LangSmith — pin or bookmark one good trace to show
# 7. Eval results table written up in docs/decisions.md
cat docs/decisions.md
```

### Structure (pitch, not tour)

#### 1. Hook — what you built and why it matters (30 sec)
> "I built [X], a [Y] chatbot deployed at [URL]. It handles [the actual business scenario] end to end — [one specific user journey], [another]. Here's it working in production."
Click the deployed URL. Run one impressive flow.

#### 2. Live demo — 3 flows (90–120 sec)
- **Happy path:** the most representative business scenario.
- **Edge case:** ambiguous request that triggers a clarifying question.
- **Adversarial:** prompt injection that the agent refuses cleanly.

> "Three flows: the core happy path, an edge case my tests caught, and an adversarial prompt my guardrails handled."

#### 3. Architecture walkthrough (60–90 sec)
Show `docs/architecture.md`. Pan through the file tree.
> "Four layers, each independently testable. The MCP client doesn't know what model it's talking to — that's how I ran the eval comparison without code changes. The UI doesn't know what's behind it — I could swap Chainlit for FastAPI in an afternoon."

#### 4. Code walkthrough — pick THREE files (60 sec)
- `mcp_client.py` — show no hardcoded tool names.
- `guardrails.py` — show the three layers of defense.
- `tests/test_guardrails.py` — show the adversarial corpus.

> "The whole codebase is [N] files, but if you read three to understand the engineering, read these. Notice no hardcoded tool names. Notice three independent guardrail layers. Notice 22 adversarial test cases."

#### 5. Evaluation — drive a decision with data (60 sec)
> "I ran the suite against gpt-4o-mini and gpt-4o. Mini hit 11/12 happy path, 18/22 adversarial, P95 latency 4.1s. Full hit 12/12, 21/22, P95 7.8s. I'm shipping mini because the one happy-path case full got right was a corner case I can fix in the prompt, and the latency difference matters more for UX than that single case."

This single paragraph — data → conclusion → decision — is what separates strong candidates.

#### 6. Limitations and roadmap (45 sec)
Open `docs/limitations.md`.
> "What it doesn't do today: [thing 1], [thing 2]. With another day I'd add [highest-value improvement] because [reason tied to user value]. With a week I'd add [bigger thing]."

Specifically include any of: rate limiting, persistent user auth, content moderation API, retry-with-backoff for MCP, observability dashboard, A/B test framework for prompts.

#### 7. Close (15 sec)
> "Production URL is [link]. Code is [repo]. README has setup. Thanks."

### Common mistakes to avoid in Video 3
- Don't tour every file. Three files, three claims each.
- Don't be over-modest. State your wins. "I have 22 adversarial tests passing" is not bragging, it's reporting.
- Don't skip the data → decision moment in section 5. That's the single highest-leverage minute of the video.
- Don't end with "I would have liked to do X." End with what's there. Limitations are a separate section, deliberately.

---

## Recording setup checklist (do once, before Video 1)

- [ ] OBS / QuickTime / Loom configured, mic tested.
- [ ] Terminal font size **bumped** so it's readable in the recording.
- [ ] Browser zoom on Chainlit and LangSmith set so text is readable.
- [ ] Notification silencer on (Slack, Mail, etc.).
- [ ] All tabs you'll use are pre-opened in order.
- [ ] One dry run: hit record, say one sentence, stop, play it back. Confirm audio + video.

---

## If you're running late

- **Behind by 15 min before Video 2:** Skip the second prompt iteration write-up; you can mention it verbally.
- **Behind by 30 min before Video 2:** Cut the multi-model eval. Run one model only.
- **Behind by 15 min before Video 3:** Skip the eval section in Video 3; replace with a deeper limitations + roadmap section. The pitch still works.
- **Deploy is broken at the 2:45 mark:** Show localhost in Video 3, but be explicit: "Deployed URL is [X], it's up but I'm demoing locally for stability." Then submit with the deployed URL working — graders will check it after.

**Late penalty math:** Submitting on time with one rough video beats submitting 25 min late with three perfect videos. The scoreboard rewards delivery.
