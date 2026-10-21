# Requirements checklist

Every line here comes from the official challenge brief, the official rules (github.com/microsoft/insidethegamehackathon, OFFICIAL RULES.md) or the judging rubric. Nothing is invented. Each item says **where we deliver it** and **where the judge sees it** (usually a timestamp in the demo video).

Tick a box only when the feature works end to end, not when the code exists.

Priority: **P0** = we fail or score badly without it. **P1** = needed to win. **P2** = extra edge if time allows.

---

## A. The five-stage pipeline (brief §(i)) — all P0

| ✓ | Requirement | How we deliver it | Seen in video |
|---|---|---|---|
| [x] | **Ingest** synthetic events *as they happen*: passes, shots, tackles, possession changes, pressure events, match metadata | Match engine streams events in real time onto the event bus (Event Hubs in Azure, in-memory locally). Gateway consumes them live. | 0:10 Verified 20 Oct: 2,190 messages through a real Event Hub, none lost (`backend/bus/`, `backend/app/live.py`, `POST /matches/{id}/live/start`). Viewers still stream from the precomputed timeline. |
| [x] | **Interpret** into statistics, patterns and context | `backend/state`: rolling possession, momentum, pressure index, pass networks, player load, rhythm, all deterministic | 0:20 |
| [x] | **Explain** why a moment matters, not just that it happened | Tactical Analyst agent writes the "why", Verifier agent checks it against the numbers. Lives in `backend/agents/` (analyst, verifier, workflow); text reaches viewers as an `update` overlay from `backend/app/agents_runtime.py` | 0:30 |
| [x] | **Render** insight that sits on screen alongside the match | Timed overlay protocol (`docs/05`) rendered over the 2D tactical feed and over real footage | throughout |
| [x] | **Personalise** so an analyst and a casual fan get two *genuinely different* experiences | Persona engine + split-screen "same moment, two viewers" view | 0:50 |

## B. Personalisation features named in the brief

| ✓ | Requirement | P | How |
|---|---|---|---|
| [x] | Customised viewing modes | P0 | Analyst, Casual, plus Kids/First-match and Accessibility (audio-described) |
| [x] | Favourite club(s) | P0 | Profile picks a club; tone and emphasis tilt toward it, notifications for its moments |
| [x] | Favourite player(s) | P0 | Their moments get priority and a "your player" badge |
| [x] | Player-focused mode, following one player throughout the match | P0 | Camera follow on the 2D pitch, live player card, every insight framed around them |
| [x] | Language preference | P0 | Narrative and voice in at least 5 languages (EN, ES, FR, AR, HI; plus PT if cheap) | 21 Oct: all six in every view (was EN/ES/AR live, six only in recaps). Interface strings `frontend/src/i18n/strings.more.ts`; instant overlays translated per match and language (`backend/app/overlay_text.py`, warmed by `scripts/warm_overlay_text.py`); Localiser now protects clocks, scores and short names and keeps units with their numbers (`backend/agents/localiser.py`). Fixed: Arabic recaps fell back to English, Hindi mangled clocks. |
| [x] | Single performance metric a viewer cares about | P0 | "One-number mode": viewer picks e.g. pressing intensity or sprint speed, the whole overlay layer reorganises around it Built 20 Oct: onboarding step "Just one number", a persistent leader readout, and the gateway filter. `e2e/one-number.spec.ts`. |
| [x] | "Welcome many more ideas" | P1 | Spoiler-safe catch-up ("I joined at 60', what did I miss?"), second-screen companion on mobile | Built: `/companion` (`frontend/src/screens/Companion.tsx`), catch-up from `GET /matches/{id}/catchup` (`backend/app/catchup.py`), spoiler test in `backend/tests/test_catchup.py`. Catch-up text is English only for now. 21 Oct: a timeline on Broadcast, Companion and Split (drag, skip, speed, spoiler-safe goal/card markers, `frontend/src/components/Timeline.tsx`, `GET /matches/{id}/moments`).

## C. Real-time match intelligence (brief §(ii))

| ✓ | Requirement | P | How |
|---|---|---|---|
| [x] | Aggregate events into meaningful football states and statistics | P0 | State engine |
| [x] | **Player identification**: real-time name tagging | P0 | Name-tag overlay attached to player position, 2D feed and real footage |
| [x] | Speed and distance indicators **triggered when predefined thresholds are reached** | P0 | Configurable thresholds (e.g. sprint > 30 km/h, distance milestones every 1 km) fire overlays |
| [x] | **Pass quality**: pass distance | P0 | Computed per pass |
| [x] | **Pass quality**: pass accuracy | P0 | Per pass (completed/not) and per player rolling % |
| [x] | **Pass quality**: pass difficulty rating | P0 | Our own explainable model (`docs/03` §5), 0–100 with factors shown |
| [x] | **Speed metrics**: ball speed | P0 | Per pass and shot |
| [x] | **Speed metrics**: shot speed | P0 | Per shot, with overlay |
| [x] | **Auto-eventing**: a model over an incoming video feed generates the pass and speed metrics automatically | P1 | `vision/` pipeline on SoccerTrack v2 footage (CC BY 4.0, `docs/06`) emits the same event schema, scored against ground truth Works on one 100 s window; the ball is the weak spot (found in 50% of frames). Scores in `data/real/117093_w1890/results.json`. |
| [ ] | Responsive enough for live play | P0 | Deterministic overlays < 150ms, LLM explanations < 4s, measured and shown in Control Room Control Room (`/control`) shows LLM p50/p95 per agent against 4 s. Not met yet: agent p95 is 4 to 6 s on Foundry, and instant-overlay latency is not measured. **Still open:** publish-to-overlay p95 was 177 ms through a real Event Hub from a laptop (budget 150 ms; 65 ms in memory), not yet measured inside Azure. |

## D. Narrative, explainability, data, language (brief §(iii)–(vi))

| ✓ | Requirement | P | How |
|---|---|---|---|
| [x] | Key narratives | P0 | Narrator agent keeps running storylines ("Ashford can't get out of their own half") |
| [x] | Player-performance context | P0 | Player cards with context vs their own baseline and the match | 21 Oct: every number on the player-focus card says where the player ranks among the same position on the pitch ("#1 of 4 forwards"), computed in code (`frontend/src/core/context.ts`). Against the match, not a season baseline: the league has no history yet. |
| [x] | Notable milestones | P0 | Milestone detector (first goal, 50th pass, fastest sprint of the match, etc.) |
| [x] | Match recaps, automated | P0 | Half-time and full-time recaps per persona and language, plus a short "60-second highlights" script | Built: `/recap` (`frontend/src/screens/Recap.tsx`) over `GET /matches/{id}/recap`; six languages, four personas, highlights script, numbers panel, key moments, share. Falls back to computed numbers when the agents are off.
| [x] | Explain **control vs chaos** | P0 | Control/Chaos index from possession stability, turnover rate, shape spread |
| [x] | Explain **tactical pressure changes** | P0 | Pressure index + shift detector, explained by Tactical Analyst |
| [x] | Explain **game rhythm patterns** | P0 | Rhythm from event tempo and possession length, momentum swings |
| [x] | **Data innovation**: create or extend a synthetic football-realistic dataset (passes, shots, tackles, possession changes, pressure events, metadata) | P0 | Our engine + published dataset of generated matches with a datasheet (`data/README.md`) `data/README.md` datasheet, `scripts/export_dataset.py`, `docs/CALIBRATION.md`. |
| [x] | **Multi-language storytelling** for global studio/streaming | P0 | Localiser agent + Azure AI Translator + Azure AI Speech voices |
| [x] | Suitable for studio, broadcast **and** streaming | P0 | Broadcast view (studio), Companion view (streaming/second screen), Control Room (producer) | All three exist: `/watch`, `/companion`, `/control`.

## E. Submission requirements (rules §4.4) — all P0

| ✓ | Requirement | Notes |
|---|---|---|
| [x] | Newly built project, created after 29 Sep 2026 | Fresh repo, first commit this week |
| [ ] | Elevator pitch naming the Microsoft/Azure tech used, what it does, what problem it solves | `docs/09` has the draft |
| [ ] | Demo video **under 2:00** | Aim for 1:55. Judges won't watch past 2:00 |
| [ ] | Video shows the project actually running on its platform | Screen recording of the deployed Azure URL, not localhost |
| [ ] | Video on YouTube / Vimeo, public URL on the project page | YouTube, unlisted is risky, use **public** |
| [ ] | No third-party trademarks, copyrighted music or material in the video | Fictional league only, royalty-free or no music |
| [ ] | Public GitHub repo URL | MIT licence, clean history, VJ as sole author |
| [ ] | Working project link for judges, free and unrestricted until judging ends (10 Nov 2026) | Deployed URL, no login wall, or test credentials in the testing instructions |
| [x] | Testing instructions | README section "Try it in 60 seconds" |
| [x] | All materials in English | Multi-language output is fine, submission text is English |
| [x] | Project linked to the challenge on the hackathon site | Already created: "Novessa Pitchside" |
| [x] | Only open-source with compatible licences, and we build on top of it | No AGPL deps |

## F. Judging rubric (rules §6.2) — five criteria, 20% each

**Stage One is pass/fail**: fits the theme and "reasonably applies the required technologies". Stage Two uses the rubric below.

### F1. Technological Implementation (20%)
- [x] Creative and **optimised synthetic data creation** (explicitly scored) → engine realism, calibration report, dataset card
- [x] Quality software practices → tests, CI, typed code, linting, IaC, ADRs in `docs/adr/`
- [ ] Effective use of **hero technologies**. Their list: Microsoft Foundry, Agent Framework, Azure MCP, GitHub Copilot Agent Mode, Fabric, GitHub SDK, GitHub CLI, Azure Apps and AI Services, Azure databases. We use:
  - [ ] Microsoft Foundry (models, agents, tracing, evaluations, content safety)
  - [x] Microsoft Agent Framework (workflow orchestration): `backend/agents/workflow.py`
  - [ ] Azure MCP (dev tooling) **and** our own MCP server
  - [ ] GitHub CLI (`gh`) + GitHub Actions for CI/CD
  - [ ] Azure Container Apps, Static Web Apps (Azure Apps)
  - [x] Azure AI Translator, Azure AI Speech, Azure AI Content Safety (AI Services)
  - [x] Azure Cosmos DB (Azure databases) Verified against the real account; `scripts/push_cache.py`
  - [x] Azure Event Hubs (event-driven backbone) Verified against the deployed hub.
  - [ ] GitHub Copilot Agent Mode → P2: if VJ uses it for any part (e.g. writing tests), note it honestly in the README
  - [ ] Fabric → P2/skip. Costly and not needed. Don't fake it
- [x] Well-structured, documented, maintainable code

### F2. Agentic Design & Innovation (20%)
- [x] Creative agentic patterns → Producer/orchestrator, verifier loop, debate between Analyst and Verifier
- [x] Sophisticated orchestration / **MCP integration** / multi-agent collaboration → Agent Framework workflow + our MCP server + A2A endpoint
- [ ] Novel, or meaningfully better than existing approaches → "every claim is proven before it airs". 21 Oct: Ask the Analyst (Scout picks tools, code runs them up to the viewer's clock, Verifier checks the answer: `backend/agents/ask.py`), and a story check for who and when (`backend/agents/story.py`). + persona-aware rendering + same agents on synthetic and real footage

### F3. Real-World Impact & Applicability (20%)
- [ ] Significant problem → broadcasters make one feed for millions of different fans
- [ ] Could deploy in production → IaC, scale-to-zero, observability, content safety, failure recovery, cost per match measured
- [ ] Impact on businesses / users → broadcaster, streaming platform and fan stories in README

### F4. User Experience & Presentation (20%)
- [ ] Well-designed, intuitive UX → `docs/07`. 21 Oct walk-through fixes: home page that states the problem (`frontend/src/screens/Home.tsx`), one nav on every page (`frontend/src/components/AppNav.tsx`), scrub timeline, split view explains itself and shows each viewer's record, real footage full screen keeps its tracking.
- [ ] Demo video clearly communicates the value → `docs/09`
- [ ] Balanced frontend and backend → both visible in the video (Control Room shows the backend working) (screen built: `frontend/src/screens/ControlRoom.tsx`; tick once recorded)

### F5. Adherence to Hackathon Category (20%)
- [ ] Fits the challenge brief → this whole checklist
- [ ] Fits our target category prize (below)

## G. Category prizes (rules §4.2) — we can win one Grand Prize + one Category Prize

Primary target: **Best Multi-Agent System**. Judges check:
- [x] Specialised agents with **distinct roles**
- [x] They coordinate through **shared state** and **effective handoffs**
- [ ] They **recover from failures** (and we show it happening in the demo)
- [ ] The end-to-end outcome is better than a single agent could achieve (we show the comparison)  **Still open, and the evidence is mixed:** `docs/EVALUATION.md` shows one prompt scoring higher on Foundry's quality evaluators; the newsroom's case is verified numbers, an audit trail and resilience.
- [x] Uses Microsoft Agent Framework and/or A2A → we use both

Secondary fit (judges can reassign us): **Best Use of Microsoft Foundry** and **Best Azure Cloud Native Integration** — the architecture already covers both, so call them out in the README.

## H. Things that would quietly sink us

- [ ] Any real club, player, crest or PL mark anywhere
- [ ] Any footage we don't hold a commercial-use licence for (pro or lower-league clips, YouTube, CC BY-NC datasets)
- [ ] Video over 2:00
- [ ] Repo private, or missing README/run instructions
- [ ] Demo link dead during judging (27 Oct – 10 Nov) → uptime check + budget alert
- [ ] Azure free credit running out before 10 Nov → see `docs/02` cost plan
- [ ] AI co-author showing on GitHub commits
- [ ] LLM hallucinating a stat on screen in the video → Verifier agent + recorded replay with cached, verified outputs
