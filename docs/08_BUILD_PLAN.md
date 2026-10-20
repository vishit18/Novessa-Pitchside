# Build plan (solo, 8 days)

Deadline: Tue 27 Oct 11:59pm PT = **Wed 28 Oct 06:59 London**. We submit by **Tue 27 Oct evening London**. No late-night submissions.

Rule: **deploy to Azure on day 3, not day 7.** Every day after that, the deployed version should work.

| Day | Claude Code builds | VJ does |
|---|---|---|
| **Mon 19 (tonight)** | Read all docs. Init repo, `.githooks`, settings, MCP config. Scaffold folders, Makefile, CI skeleton, `.env.example`. | Azure free account + budget alert, install CLIs, Foundry project + 2 model deployments (`docs/02`). Create public GitHub repo `novessa-pitchside`. Install plugins. |
| **Tue 20** | Event schema + Pydantic models. Fictional league generator. Match engine v1 (possession state machine, positions, passes, shots, tackles, pressure). Replay clock with speed control. Tests. | Get SoccerTrack v2 access on Hugging Face, read the conditions, pick a 60–120 s segment with no readable logos. Check engine output looks like football. |
| **Wed 21** | State engine: all metrics in `docs/03` §6, thresholds, milestones, candidate moments. Gateway (REST + WS). Broadcast view v1 with pitch + instant overlays. **Bicep + `azd up`: first deploy.** | Sanity-check numbers vs real football feel. |
| **Thu 22** | MCP server. Agent Framework workflow: Producer, Analyst, Verifier, Narrator. Agent cache. Content Safety gate. OpenTelemetry → App Insights + Foundry tracing. | Download only match 117093 1st half (~6 GB, command in `docs/06`), run `prepare_footage.py`, delete originals. Try the detector on 10 seconds. |
| **Fri 23** | Story Keeper, Localiser (Translator), Voice (Speech), Recap Editor + A2A endpoint + demo client. Persona renderer. Split view, player focus, one-number mode. | Try every persona; note what feels off. |
| **Sat 24** | Frontend polish across all screens with frontend-design + Playwright screenshots. Control Room with agent graph, latency, chaos switch. Companion mobile view. Failure recovery paths. | Watch the clip with overlays; flag anything that looks wrong. |
| **Sun 25** | Vision pipeline end to end, real footage mode. `eval_single_vs_multi.py` + Foundry evaluations. `calibrate.py` realism report. Dataset export + datasheet. **Feature freeze at midnight.** | Review `vision/evaluate.py` numbers vs ground truth; decide what we show. |
| **Mon 26** | Hardening only: tests green, lint, error states, cold starts, min replicas = 1, uptime test, cache warm for demo matches. README with architecture diagram, screenshots, results tables, "Try it in 60 seconds". | Record video takes (script in `docs/09`). |
| **Tue 27** | Last fixes from the recording. Final deploy. Tag `v1.0`. | Edit video to < 2:00, upload to YouTube (public), fill the submission form, **submit by 20:00 London**. Verify everything from a logged-out browser. |

## If we're behind

Cut in this order (and tell VJ before cutting anything):
1. Kids persona (keep Analyst, Casual, Accessibility)
2. Portuguese
3. Companion mobile view (keep broadcast + split + control room)
4. Vision event detection beyond passes and speed (keep tags + speed + passes)
5. A2A endpoint (keep MCP)

Never cut: the five pipeline stages, Verifier, failure recovery demo, split-view personalisation, multi-language, deployed URL, video quality.

## Status

_Claude Code updates this at the end of every working day._

- **Done (Mon 19):** read CLAUDE.md and all docs. Repo initialised on `main`, hooks enabled, folder scaffold, `pyproject.toml` (uv, Python 3.12, ruff, mypy strict, pytest), Makefile, `.env.example`, CI skeleton, MIT licence, stub README.
- **Done (Tue 20):** event schema and Pydantic models (`engine/schema.py`), league generator with 8 invented clubs and 144 players (`engine/league.py`, saved to `data/league/`), explainable pass difficulty model (`engine/difficulty.py`), match engine v1 (`engine/sim.py`: possession loop, formation shifting, passes, carries, dribbles, tackles, shots with xG, corners, free kicks, fouls, yellow cards, subs, fatigue, hidden storyline arcs), lazy 10 Hz tracking (`engine/tracking.py`), replay clock with speed/pause/seek (`engine/clock.py`), JSONL writer (`engine/io.py`), `make seed` and `make replay`. Three demo matches in `data/matches/` (about 1 MB each). 31 tests, ruff and mypy clean. `docs/03` updated first for `t_match`, `pass_difficulty`, `difficulty_factors`, `xg`.
- **Done (Wed 21, so far):** doc sync with the updated pack (real/synthetic separation rule, no-calibrating-on-SoccerTrack rule). Audit fixes: real-name denylist is now hashed so no real names sit in source; README no longer names the league. Commit hook is executable in git and tested. State engine v1 (`backend/state/`): possession (match and rolling 5 min), momentum, pressure index, control/chaos, rhythm, per-player stats (passes, accuracy, difficulty, xG, xA, duels, distance, top speed, sprints), thresholds from `config/thresholds.yaml`, instant triggers (speed burst, distance milestone, pass difficulty, shot speed, milestones), candidate moments with significance and a state snapshot. Runs a full match in about 1 s. 42 tests, ruff and mypy clean. Demo matches regenerated after a simulator speed-cap change.
- **Done (Wed 21, frontend):** Broadcast view v1 in `frontend/` (Vite, React 18, TypeScript, Tailwind, Zustand, PixiJS). 2D pitch with 22 players and ball, score bug, momentum bar, lower thirds, player tags, speed burst, pass difficulty line and shot speed overlays, floodlight styling, portrait layout for 390 wide. WebSocket client with reconnect, buffers keyed to `t_match`, adjustable stream delay. Runs on a mock source built from `data/matches/*.jsonl` behind one `MatchSource` interface; switch to the gateway with `VITE_GATEWAY_URL` or `?source=ws`. 22 vitest tests, eslint, prettier and tsc clean. Not done: Playwright e2e (waits for the gateway), other screens.
- **Done (gateway, backend session):** overlay gateway (`backend/app/`): REST (`/health`, `/league`, `/matches`, `/matches/{id}`, `/matches/{id}/state`, overlay export as JSONL and CSV cue sheet) and `WS /ws/matches/{id}` with play, pause, speed and seek. Streams frames at 10 Hz, events, 1 Hz state and instant overlays; shared timeline built once per match, per-viewer persona filter (`personas.py`: analyst, casual, kids, accessibility, favourite club, player focus, one-number mode). Overlay model and generated JSON Schema (`backend/app/schemas/overlay.schema.json`). `docs/05` updated first with transport and payload shapes. Run: `uv run uvicorn backend.app.main:app --port 8000` (`PRELOAD=1` warms all matches, first load about 7 s). 55 Python tests.
- **Done (discipline and set pieces):** the simulator now has fouls (about 20 a match), yellow and red cards (second yellow then red, straight reds), ten men after a red (the player leaves the tracking frames), penalties, manager cards and more corners (about 11). Club managers are invented names (separate generator, squads unchanged). The state engine counts fouls, cards, corners, free kicks, penalties and shots per team (`state.team_stats`) and per player, and raises card and penalty moments. Gateway overlays for cards (`payload.card`, `payload.staff`) and penalties. Demo matches regenerated to show them. A new test caught sent-off players being moved by the corner routine; fixed. 86 Python tests. Rough rates from 40 matches: fouls 20, yellows 3.2, reds 0.2, corners 11, penalties 0.5 (a bit high), goals 3.0.
- **Azure:** `az` and `azd` installed and logged in. Foundry resource `NovessaPitchside1` (Sweden Central, resource group `pitchside`) has `chat-fast` (gpt-4.1-mini) and `chat-strong` (gpt-5-mini). Model calls still return PermissionDenied for the signed-in user even with the OpenAI User, Cognitive Services User and Azure AI User roles assigned; needs a retry or a portal check.
- **Rough calibration (small samples, not the 200-match report yet):** pass completion about 80%, difficulty median about 27, about 9 km per outfield player, about 28 shots per match, goals a bit high at about 3.3 per match, sprints over 30 km/h still too frequent (about 175 bursts per match), passes per match about 1,200 (real is nearer 900 to 1,000). All to tune before the Sunday `calibrate.py` run.
- **Broken / risky:** no red cards or penalties. Model calls blocked (above). Repo not pushed. Plugins not installed. Checklist boxes not ticked yet: none works end to end until the gateway and a view exist.
- **Next:** gateway (REST + WebSocket, overlay protocol schema), Broadcast view v1 with pitch and instant overlays, Bicep and the first `azd up`.
- **Needs VJ:** public GitHub repo, plugins, SoccerTrack v2 conditions check, pay-as-you-go upgrade decision, portal check of model access.
- **Azure spend so far:** about $0
