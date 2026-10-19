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
- **Rough calibration (3 to 36 match samples, not the 200-match report yet):** pass completion about 80%, pass difficulty median about 27, about 9 km per outfield player, about 28 shots per match, about 3.3 goals per match (a bit high, tune before Sunday), top speeds 36 to 39 km/h (a bit high, caused by snap moves; tune).
- **Broken / risky:** no red cards or penalties yet. Passes per match about 1,200 (real is nearer 900 to 1,000). `az` and `azd` are not installed yet. Plugins (`frontend-design`, `microsoft-docs`) not installed. The repo is not pushed anywhere yet.
- **Next (Wed 21):** state engine (`backend/state`): all metrics in `docs/03` section 6, thresholds, milestones, candidate moments. Gateway (REST + WS). Broadcast view v1. Bicep and the first `azd up`.
- **Needs VJ:** Azure free account and budget alert, Foundry project with `chat-fast` and `chat-strong`, public GitHub repo, SoccerTrack v2 conditions (Tuesday task in the plan), plugins.
- **Azure spend so far:** $0
