# CLAUDE.md — Novessa Pitchside

You're building **Novessa Pitchside** with VJ for the Microsoft x Premier League "Inside the Game" Developer Hackathon.
Tagline: *Same match. Your story.*

**Hard deadline: 27 Oct 2026, 11:59pm Pacific = Wed 28 Oct, 06:59 London.** Aim to be feature-complete by 25 Oct, then polish, record and submit with a day spare. Never let "nice to have" eat the buffer.

Read these before writing any code, in this order:

1. `docs/00_REQUIREMENTS_CHECKLIST.md` — every single thing the judges asked for, mapped to where we deliver it. This is the source of truth. If something isn't traceable to it, ask why we're building it.
2. `docs/01_ARCHITECTURE.md` — system design, repo layout, data flow.
3. `docs/02_AZURE_SETUP.md` — every Azure resource, how it's created, what it costs.
4. `docs/03_SYNTHETIC_DATA.md` — the match engine and event schema.
5. `docs/04_AGENTS.md` — the multi-agent system (this is where we win or lose).
6. `docs/05_OVERLAY_PROTOCOL.md` — the timed, machine-readable overlay format.
7. `docs/06_VISION_AUTO_EVENTING.md` — real-footage auto-eventing.
8. `docs/07_FRONTEND_DESIGN.md` — design direction, screens, the frontend tooling you must use.
9. `docs/08_BUILD_PLAN.md` — day-by-day plan with priorities.
10. `docs/09_DEMO_AND_SUBMISSION.md` — 2-minute video script and submission copy.
11. `docs/10_COMPETITION_NOTES.md` — what the other 336 entries are doing and how we stand apart.

---

## What we're building, in one paragraph

A synthetic match engine streams a full 90 minutes of football-realistic events from a fictional league. A deterministic stats engine turns them into match state (possession, momentum, pressure, pass difficulty, speeds, distances). A team of specialised agents on **Microsoft Foundry + Microsoft Agent Framework** decides which moments matter, explains *why* in football terms, verifies every claim against the numbers, and produces timed overlay instructions, live narrative, voice commentary and recaps. Each viewer gets their own version of the same match: analyst vs casual fan, favourite club, favourite player, player-focus mode, single-metric mode, any language. A separate vision pipeline proves the same system works on real footage (an openly licensed amateur match), tagging players and measuring ball and shot speed automatically, and we score it against the dataset's ground truth.

---

## Non-negotiable rules

### Data and IP
- **Synthetic data only** for the match intelligence. No real Premier League data, ever.
- **Keep real and synthetic strictly apart.** SoccerTrack v2 is real footage of real (amateur) matches. It lives only in `vision/` and is used for exactly two things: showing auto-eventing works on video, and scoring our vision output against its labels. Never use it to build, train, tune or calibrate the synthetic engine, never mix its events into synthetic matches, and never feed it to the agents as if it were synthetic. Everything it produces is tagged `source: "vision"` and shown only in Real footage mode with the dataset credit visible.
- **No real clubs, players, crests, kits, league names, sponsors or PL branding anywhere** in the UI, code, seed data, README or video. Our league, clubs and players are invented (see `docs/03_SYNTHETIC_DATA.md`). The rules say the demo must not include third-party trademarks.
- Real footage comes only from the openly licensed SoccerTrack v2 dataset (CC BY 4.0) or another source listed in `docs/06`. Never download professional or lower-league match clips, highlights or YouTube videos. Credit every asset in `docs/ASSET_LICENSES.md`.
- No copyrighted music. No stock assets unless the licence is explicitly free for commercial use and is recorded in `docs/ASSET_LICENSES.md`.
- Open-source dependencies must be licence-compatible with our MIT repo. **Do not use Ultralytics YOLO** (AGPL). Use permissively-licensed models only (see `docs/06`).

### Git — VJ is the only author
- Do all the git work: init, branch, commit often with clear messages, push, open PRs if asked.
- **Never add AI attribution to anything.** No `Co-Authored-By:` trailers, no "Generated with Claude Code", no `Claude-Session:` trailers, no AI mentions in commit messages, PR descriptions, code comments, README or docs.
- Commits are made with VJ's own git identity (`git config user.name` / `user.email` already set on his machine). Never change the git identity. Never pass `--author`.
- `.claude/settings.json` disables attribution and `.githooks/commit-msg` strips any trailer that slips through. On first setup run:
  ```bash
  git config core.hooksPath .githooks
  chmod +x .githooks/commit-msg
  ```
  Verify with `git log -1 --format=%B` after the first commit. If a trailer ever appears, amend it out before pushing.
- Never `git push --force` to `main`. Never commit secrets, `.env`, keys, or footage files.
- Commit message style: short imperative subject, plain English, e.g. `add pressure index to state engine`. Write like a human engineer, not a changelog generator.

### Writing style (README, docs, UI copy, agent prompts' output tone)
- Sound like a person who loves football and builds things, not a press release. Short sentences. No buzzword soup ("revolutionary", "seamless", "cutting-edge", "unlock", "leverage", "empower", "delve").
- No emojis in the README headings. No walls of badges.

### Engineering
- **Python 3.12** backend (FastAPI, asyncio), **TypeScript + React + Vite** frontend.
- Type everything. Pydantic v2 models for every event, state and overlay message. The schemas in `docs/03` and `docs/05` are contracts — change them only by updating the doc first.
- Deterministic maths in code, language in LLMs. **Never ask an LLM to compute a number.** Agents receive computed numbers and explain them.
- Every LLM call has: a timeout, a retry with backoff, a fallback output, structured output (JSON schema), and an OpenTelemetry span.
- Overlays that don't need language (name tags, speed, pass difficulty, momentum bar) are emitted by the deterministic layer in under 150ms. LLM text arrives asynchronously and attaches to the moment by `moment_id`.
- Config through environment variables only. `.env.example` lists every variable with a comment. Secrets live in Key Vault in Azure, `.env` locally. Prefer Managed Identity / `DefaultAzureCredential` over keys wherever the service supports it.
- Tests: `pytest` for engine, stats and agent contracts (mock LLM). `vitest` for overlay rendering logic. One Playwright end-to-end smoke test that loads the broadcast view and sees an overlay appear.
- Lint/format: `ruff` + `mypy` (Python), `eslint` + `prettier` (TS). CI runs all of it.
- Small modules, clear names, docstrings on public functions. The judges score "well-structured, documented, maintainable code".

### Cost discipline (VJ is on a free Azure account)
- Before creating any Azure resource, check `docs/02_AZURE_SETUP.md`. Don't create anything not listed there without asking VJ.
- Use the cheapest SKU that works. Scale-to-zero where possible.
- Cache LLM outputs per `(match_seed, moment_id, persona, language)` so replays and the demo cost nothing.
- Use the small chat model for high-volume agents and the bigger one only for recaps.

---

## Tools you must set up and use

### MCP servers (configured in `.mcp.json`)
| Server | Why |
|---|---|
| **Playwright MCP** | Open the running frontend, take screenshots, check layouts at 1920×1080 and 390×844, fix what you see. Use it after every meaningful UI change. Don't call a screen done until you've looked at it. |
| **Microsoft Learn MCP** | Official, current Microsoft docs. Use it before writing any Azure, Foundry or Agent Framework code — these SDKs move fast and your training data is probably stale. |
| **Azure MCP** | Inspect and manage VJ's Azure resources (resource groups, Container Apps, Cosmos DB, Key Vault, monitor logs). It's also one of the judges' named "hero technologies", so mention it in the README's "how we built it". |
| **Context7** (optional) | Up-to-date library docs for React, Vite, Framer Motion, PixiJS, FastAPI. |

If an MCP server fails to start, tell VJ the exact error. Don't silently skip it.

### Claude Code plugins / skills
Install these at the start of the first session (VJ runs these slash commands, or you prompt him to):
```
/plugin install frontend-design@claude-plugins-official
/plugin install microsoft-docs@claude-plugins-official
```
If the marketplace isn't registered yet: `/plugin marketplace add anthropics/claude-plugins-official` first.

**Always use the frontend-design skill for any UI work.** Read `docs/07_FRONTEND_DESIGN.md` alongside it — that doc is our specific art direction and overrides generic defaults.

Extra design skills are installed in `~/.claude/skills` and are part of this project's UI workflow: `emil-design-eng` (and its animation review skills: `review-animations`, `improve-animations`, `animation-performance`, `animation-vocabulary`), `impeccable` (critique, polish, audit) and `taste-skill`. Use them on every meaningful UI change: build with `frontend-design` + `taste-skill`, tune motion with `emil-design-eng`, then run `impeccable` critique/audit before calling a screen done. `docs/07` still wins where they disagree. Keep overlay motion under 300ms and respect `prefers-reduced-motion`.

### CLIs VJ will have installed (see docs/02)
`az` (Azure CLI), `azd` (Azure Developer CLI), `gh` (GitHub CLI), `docker`, `node` 22+, `python` 3.12, `uv`.

---

## Repo layout (target)

```
novessa-pitchside/
├── CLAUDE.md
├── README.md
├── LICENSE                      # MIT
├── azure.yaml                   # azd project
├── infra/                       # Bicep: every Azure resource as code
├── docs/
├── engine/                      # synthetic match engine (python package)
├── backend/
│   ├── app/                     # FastAPI: REST + WebSocket gateway
│   ├── state/                   # deterministic stats + moment detection
│   ├── agents/                  # Agent Framework agents + workflow
│   ├── mcp_server/              # our Match Intelligence MCP server
│   ├── a2a/                     # A2A endpoint for the Recap agent
│   └── tests/
├── vision/                      # auto-eventing from real footage
├── frontend/                    # React + Vite + TS
├── data/
│   ├── league/                  # fictional clubs, players (JSON)
│   └── matches/                 # generated match files (JSONL), small samples only in git
├── scripts/                     # seed, replay, cache-warm, demo helpers
└── .github/workflows/           # CI + deploy
```

## Commands (keep this section updated as you build)

```bash
make dev          # engine + backend + frontend locally, in-memory bus
make test         # all tests
make lint
make seed         # generate the league + 3 demo matches
make replay MATCH=derby_01 SPEED=4
azd up            # provision + deploy everything to Azure
```

---

## How to work with VJ

- He's a mid-senior AI/ML engineer. Don't explain Python, APIs or ML basics. He hasn't used Azure before, so do explain Azure-specific steps clearly.
- When you need him to do something in a browser or portal (sign-ups, approvals, quotas), stop and give him exact numbered steps, then wait.
- Treat first versions as drafts. He'll iterate.
- When you finish a task, tick the matching box in `docs/00_REQUIREMENTS_CHECKLIST.md` and note where it lives (file path or screen).
- At the end of each day of work, update the "Status" section at the bottom of `docs/08_BUILD_PLAN.md`: what's done, what's broken, what's next.
- If you're about to cut something from the checklist for time, say so explicitly and get his OK first.
