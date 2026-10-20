# Novessa Pitchside

**Same match. Your story.**

Everyone watching a match gets the same broadcast. The analyst who wants pressing numbers and the mate who just wants to know why their team suddenly looks rattled see exactly the same thing. Novessa Pitchside gives each of them their own version of the game, live.

A match engine plays a full 90 minutes of football in an invented league. A stats layer turns it into momentum, pressure, control and chaos, pass difficulty, speeds and distances. A team of agents on Microsoft Foundry decides which moments matter, explains why in football terms, checks every claim against the numbers, then writes it up for each viewer: their persona, their language, their club or player. The whole thing is a timed overlay protocol, so any graphics engine could draw it.

Built for the "Inside the Game" developer hackathon. All match data is synthetic. No real clubs, players or marks anywhere.

![The broadcast view: a goal for Ashford Rovers, with the explanation the agents wrote](docs/img/broadcast.png)

The same goal for two viewers. An analyst gets the numbers in English, a casual fan gets the story in Spanish:

![Split view: one moment, two viewers](docs/img/split.png)

## Try it in 60 seconds

You need Python 3.12 with [`uv`](https://docs.astral.sh/uv/), and Node 22.

```bash
# terminal 1: the gateway
uv sync
AGENTS=off uv run uvicorn backend.app.main:app --port 8000

# terminal 2: the app
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and pick a match.

`AGENTS=off` runs without any Azure account: you get the pitch, the instant overlays, the stats and the recap numbers. Leave it off the command to turn the agents on. For that, run `az login`, copy `.env.example` to `.env` and fill in the Foundry endpoint (see [`docs/02_AZURE_SETUP.md`](docs/02_AZURE_SETUP.md)). Everything signs in with Entra ID, so there are no keys to paste.

Places worth a look:

| Screen | Link | What to try |
|---|---|---|
| Broadcast | `/watch?match=derby_01&speed=4` | Overlays land instantly, the "why" text a moment later. Move the mouse to bring up Companion, Recap and Commentary. |
| Split | `/split?match=derby_01&t=300&speed=4` | The same moment for an analyst in English and a casual fan in Spanish. |
| Companion | `/companion?match=derby_01&speed=10` | The phone view. Tap "What did I miss?" for a spoiler-safe catch-up. |
| Control Room | `/control?match=derby_01` | The agents at work, the Verifier rejecting a claim, and the chaos switch that kills an agent mid-match. |
| Recap | `/recap?match=derby_01&kind=full_time` | Half-time and full-time recaps in six languages. |
| Real footage | `/real` | The same overlays on a real amateur match, measured from video. |

## What it does

- **Synthetic league.** Eight invented clubs, 144 players, and a match engine with passes, carries, shots with xG, fouls, cards, penalties, corners, offsides, substitutions, fatigue and storylines that build over a match. Three demo matches ship in `data/matches/`, and `scripts/export_dataset.py` writes 200 matches as Parquet. See [`data/README.md`](data/README.md).
- **Deterministic stats.** Possession, momentum, pressure, control and chaos, rhythm, an explainable pass difficulty score, sprint speeds and distances. All of it is computed in code. No language model ever computes a number.
- **Instant overlays.** Name tags, speed bursts, pass difficulty, shot speed, cards, offsides and milestones come straight from the stats layer, with no model call.
- **Agents.** Eight agents and a safety gate, described below. They add the explanation, the commentary, the translation, the voice and the recap.
- **Personas.** Analyst, casual, first match and audio-described. Favourite club, favourite player (the camera follows them), or a single metric. English, Spanish and Arabic in the broadcast, plus French, Hindi and Portuguese in recaps.
- **Real footage.** A vision pipeline reads a real, openly licensed amateur match, tags players, follows the ball and measures speeds, then scores itself against the dataset's own labels.

## The agents

| Agent | Job |
|---|---|
| Producer | Decides which candidate moments go on screen and how |
| Tactical Analyst | Explains why a moment matters, in football terms, from the computed numbers |
| Verifier | Recomputes every claim through the same stats code. A claim that fails goes back once, then falls back to numbers only |
| Narrator | Writes the live commentary line for each persona |
| Story Keeper | Tracks the running storylines of the match |
| Localiser | Translates with Azure AI Translator, then a model polishes it. Numbers and names are protected |
| Voice | Turns the line into speech with Azure AI Speech |
| Recap Editor | Writes half-time and full-time recaps, reachable over A2A |

Everything an agent says passes a QA step with Azure AI Content Safety before it airs. If an agent is slow, wrong or switched off, the picture is never held up: the instant overlay is already on screen and the text attaches later. The chaos switch in the Control Room shows this live.

## How it is built

```
engine ──▶ Event Hubs ──▶ gateway ──▶ state engine ──▶ instant overlays ──┐
(synthetic)                  │                             │              ├─▶ WebSocket ──▶ React + PixiJS
                             └──▶ agents (Foundry + Agent Framework) ─────┘
                                  MCP server · A2A endpoint · Cosmos cache
real footage ──▶ vision pipeline ──▶ same event schema ──▶ same overlays
```

| Microsoft technology | Where it is used |
|---|---|
| Microsoft Foundry | Two chat models: a small one for the high-volume agents, a larger one for recaps only |
| Microsoft Agent Framework | The Producer, Analyst, Verifier, Narrator and Gate workflow (`backend/agents/workflow.py`) |
| Azure AI Translator, Speech, Content Safety | Localiser, Voice and the QA gate, all on the Foundry resource |
| Azure Event Hubs | The live feed from engine to gateway (`backend/bus/`) |
| Azure Cosmos DB | Shared cache of agent output per match, moment, persona and language |
| Azure Container Apps and Container Registry | The gateway and agents |
| Azure Static Web Apps | The frontend |
| Application Insights and OpenTelemetry | A span on every model call |
| Managed identity and Key Vault | Keyless access between services |
| Bicep and the Azure Developer CLI | Every resource is code (`infra/`, `azure.yaml`) |
| Azure MCP server | Used while building, to inspect and manage the resources |
| Our own MCP server and A2A endpoint | `backend/mcp_server/`, `backend/a2a/`. The match intelligence is a tool any agent can call |
| GitHub Actions and the GitHub CLI | CI and the repo |

Decisions and their costs are in [`docs/adr/`](docs/adr/README.md). A plain-language guide to each service, with an honest status for each, is in [`docs/AZURE_SERVICES.md`](docs/AZURE_SERVICES.md).

## Numbers

These are measured, not hoped for.

- **Tests:** 152 Python, 61 frontend unit, 8 browser end-to-end. Lint and types run in CI.
- **Cost:** running the agents over all three demo matches (94 moments) cost about $0.09 in model tokens. The results are cached per match, moment, persona and language, so a replay costs nothing.
- **Synthetic data:** 200 simulated matches (545,639 events) measured against typical top-flight ranges. Of 16 measures with a reference range, 14 are inside it and 2 (goals and red cards per match) are just outside by less than the sampling error. The engine was tuned until it got there. Chart and table: [`docs/CALIBRATION.md`](docs/CALIBRATION.md).
- **Live feed:** 2,190 messages sent through a real Event Hub and read back with none lost. Publish to overlay was 110 ms at the median and 177 ms at the 95th percentile from a laptop, against a 150 ms budget. In memory it is 65 ms at the 95th percentile. We have not yet measured it from inside Azure.
- **Agent text:** typically 3 to 5 seconds per step. It attaches after the instant overlay, so the picture never waits.
- **Real footage,** one 100 second window, scored against the dataset's labels (`data/real/117093_w1890/results.json`):

| Measure | Result |
|---|---|
| Players found | 71% of 11,000 labelled positions |
| Position error | median 1.0 m, 90th percentile 2.3 m |
| Player speed error | median 2.9 km/h, top speed within 3.2 km/h |
| Passes | 8 of 54 found, 67% precision |
| Shots | 0 of 1 found |
| Ball followed | in 50% of frames |

The ball is the weak spot, and we say so. A dedicated small-object ball detector would be the next step.

## Real footage and credits

![The real-footage screen: tagged players, passes found, and the scorecard against the dataset's labels](docs/img/real-footage.png)

Footage: **SoccerTrack v2 (CC BY 4.0)**, an openly licensed dataset of amateur matches on Hugging Face (`atomscott/soccertrack-v2`). It stays inside `vision/` and is used for exactly two things: showing that auto-eventing works on video, and scoring our output against its labels. It is never used to build or tune the synthetic engine. A university name and crest painted on the pitch are removed from the clip we show. The video file is not in this repo.

The detector is RT-DETR (Apache 2.0). We do not use Ultralytics YOLO because of its licence. Every asset is listed in [`docs/ASSET_LICENSES.md`](docs/ASSET_LICENSES.md).

## What is not finished

- Offside is a flag on through balls (one to four a match). The engine has no offside line, and no goal is ever disallowed.
- The Hindi recap can garble a clock and transliterate a surname. The Verifier checks the English draft, not the translation.
- Foundry tracing and evaluations, and the single-agent versus multi-agent comparison, are not done.
- The ball is found in only half the real-footage frames, and jersey numbers are not read.

## Repo map

| Path | What is in it |
|---|---|
| `engine/` | The synthetic match engine, league generator and replay clock |
| `backend/state/` | Deterministic stats and moment detection |
| `backend/agents/` | The agents, prompts, workflow and cache |
| `backend/app/` | FastAPI gateway, WebSocket, live ingest |
| `backend/bus/` | Event bus: in memory and Event Hubs |
| `backend/mcp_server/`, `backend/a2a/` | Our MCP server and A2A endpoint |
| `vision/` | Auto-eventing from real footage |
| `frontend/` | React, Vite and TypeScript |
| `infra/` | Bicep for every Azure resource |
| `data/` | The league, three demo matches and the dataset datasheet ([`data/README.md`](data/README.md)) |
| `docs/` | Design docs, Azure setup, calibration report, decisions (`adr/`), asset licences |

Run the checks with `uv run pytest`, `uv run ruff check .`, `uv run python -m mypy .`, and in `frontend/` with `npm test`, `npm run lint` and `npm run e2e` (start the gateway with `AGENTS=off` first).

## Who it is for

A broadcaster makes one feed for millions of different fans. A streaming platform wants a second screen that knows who is watching. A fan who is new to the game wants it explained, and a fan who lives for the numbers wants more of them. The overlay protocol is the same for all of them: only what each viewer sees changes.

## Licence

MIT. See [`LICENSE`](LICENSE).
