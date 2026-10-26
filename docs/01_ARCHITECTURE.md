# Architecture

## The shape of it

```
                ┌──────────────────────┐        ┌───────────────────────┐
                │  Synthetic Match      │        │  Vision Auto-Eventing │
                │  Engine (engine/)     │        │  (vision/) real video │
                └──────────┬───────────┘        └──────────┬────────────┘
                           │  MatchEvent (same schema)      │
                           ▼                                ▼
                ┌──────────────────────────────────────────────────────┐
                │  Event bus: Azure Event Hubs  (in-memory locally)    │
                └──────────────────────────┬───────────────────────────┘
                                           ▼
                ┌──────────────────────────────────────────────────────┐
  STAGE 1–2     │  State Engine (deterministic, backend/state)          │
  ingest +      │  possession · momentum · pressure · control/chaos ·  │
  interpret     │  rhythm · pass difficulty · speeds · distances ·     │
                │  thresholds · milestones · candidate moments         │
                └───────┬──────────────────────────────┬───────────────┘
                        │ instant overlays (<150ms)     │ candidate moments + state snapshot
                        │                               ▼
                        │      ┌────────────────────────────────────────────┐
  STAGE 3               │      │  Agent workflow (Microsoft Agent Framework) │
  explain               │      │  Producer → Analyst ⇄ Verifier → Narrator   │
                        │      │  → Localiser → Voice   |  Recap (A2A)       │
                        │      │  models + tracing + evals in Foundry        │
                        │      └───────────────┬────────────────────────────┘
                        ▼                      ▼
                ┌──────────────────────────────────────────────────────┐
  STAGE 4–5     │  Overlay Gateway (FastAPI + WebSocket)               │
  render +      │  per-viewer Persona Renderer: filters, ranks, words  │
  personalise   │  every overlay message for that viewer's profile     │
                └───────┬───────────────┬──────────────────┬───────────┘
                        ▼               ▼                  ▼
                 Broadcast view    Companion (mobile)   Control Room
                 (studio / TV)     (streaming fan)      (producer, agent traces)

  Side services: Cosmos DB (matches, moments, profiles, cache) · Key Vault ·
  App Insights (OpenTelemetry) · Content Safety · Match Intelligence MCP server
```

## Key design decisions (write each as an ADR in `docs/adr/`)

1. **Numbers in code, words in models.** The state engine computes everything numeric and deterministic. Agents only explain, rank and phrase. This keeps it fast, cheap, testable and stops hallucinated stats.
2. **Two speeds.** Instant overlays (name tags, speed, pass difficulty, momentum bar) go straight from the state engine to the gateway. Language overlays arrive 1–4s later and attach to the same `moment_id`. Live TV graphics work like this anyway: the stat lands first, the analysis follows.
3. **One schema for synthetic and real.** The vision pipeline emits the exact same `MatchEvent` schema as the engine. That's the proof the system would work in production on real tracking data.
4. **Personalisation at the edge.** Agents generate a small set of variants per moment (by persona × language). The gateway picks and filters per viewer. We don't run a full agent pipeline per viewer, which wouldn't scale. Show this cost logic in the README.
5. **Replay mode.** Every match is seeded and deterministic. With the agent cache warm, replay costs zero tokens. The demo video and judges' default view use a cached replay; a "go live" button runs the full pipeline fresh.
6. **Event-driven and stateless services** so Container Apps can scale out and back to zero.

## Components

| Component | Tech | Runs on (Azure) |
|---|---|---|
| Match engine | Python package, numpy | Container Apps job (or inside API container on a trigger) |
| Event bus | Azure Event Hubs (Basic/Standard) with an `EventBus` interface; `InMemoryBus` locally | Event Hubs namespace |
| State engine | Python, pure functions + rolling windows | Container App `api` |
| Agent workflow | Microsoft Agent Framework (Python), Foundry models | Container App `agents` |
| Overlay gateway | FastAPI, WebSocket | Container App `api` |
| Match Intelligence MCP server | Python MCP SDK, streamable HTTP | Container App `mcp` (or route on `api`) |
| A2A endpoint (Recap agent) | `agent-framework` A2A hosting | Container App `agents` |
| Storage | Cosmos DB for NoSQL (free tier) | Cosmos DB account |
| Frontend | React + Vite + TS | Azure Static Web Apps (free) |
| Vision | Python, RF-DETR/RT-DETR + supervision ByteTrack | Offline job; outputs uploaded as events |
| Observability | OpenTelemetry → Application Insights; Foundry tracing for agents | App Insights + Foundry |
| Secrets | Key Vault + Managed Identity | Key Vault |
| IaC | Bicep + `azd` | — |
| CI/CD | GitHub Actions, `gh` CLI | GitHub |

## Latency budget (measure these, show them in the Control Room)

| Path | Target |
|---|---|
| Event → instant overlay built | < 150 ms (met in memory and in a one-off Event Hubs job at 4x; about 250 ms p95 on the deployed API replicas, see `docs/LOAD_TEST.md`) |
| Candidate moment → verified explanation on screen | < 4 s (p95) |
| Explanation → 5 languages ready | < 6 s |
| Full-time → recap ready | < 20 s |

## Cosmos DB containers

| Container | Partition key | Contents |
|---|---|---|
| `matches` | `/match_id` | metadata, seed, teams, final stats |
| `events` | `/match_id` | raw events (also dataset export source) |
| `moments` | `/match_id` | detected moments + verified explanations + variants |
| `profiles` | `/viewer_id` | persona, club, players, language, metric |
| `agent_cache` | `/cache_key` | LLM outputs keyed by seed + moment + persona + language |

## API surface (gateway)

- `POST /matches` — start a match (seed, teams, speed) → `match_id`
- `GET /matches/{id}` — metadata + current state
- `WS /ws/matches/{id}?viewer=...` — overlay stream for this viewer
- `PUT /viewers/{id}/profile` — persona, club, players, language, metric
- `GET /matches/{id}/recap?persona=&lang=` — recap
- `POST /matches/{id}/ask` — "what did I miss?" / free question, answered by agents using MCP tools
- `GET /health`, `GET /metrics/latency`

## Local dev

`docker compose up` brings up api, agents, frontend and a Cosmos emulator (or use a local JSON store behind the same repository interface to keep it light). Event bus in-memory. Foundry models are called for real (there's no good local substitute), but the cache means re-runs are free.
