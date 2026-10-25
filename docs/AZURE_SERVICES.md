# Azure services in Novessa Pitchside

A plain guide to every Azure service we use: what it is, why we picked it, where it lives in the code, and whether it has actually been checked end to end. The status column shows what has been checked end to end.

Everything signs in with **Entra ID (keyless)**. No service key sits in the repo or in `.env`. Locally the code uses your `az login`. In Azure it uses a managed identity.

## The AI side

| Service | What it is, in one line | What we use it for | Where | Status |
|---|---|---|---|---|
| **Microsoft Foundry** | Azure's home for models and agents. One resource, `NovessaPitchside1`, in Sweden Central. | Hosts two chat models: `chat-fast` (gpt-4.1-mini) for the high-volume agents, `chat-strong` (gpt-5-mini) for the Analyst, Ask the Analyst and recaps. | `backend/agents/llm.py`, `factory.py` | Verified live |
| **Microsoft Agent Framework** | A Python library (not a service) for building agents and wiring them into workflows. | Runs the Producer, Analyst, Verifier, Narrator, Gate workflow. | `backend/agents/workflow.py` | Verified live |
| **Azure AI Translator** | Machine translation. | First pass of each non-English language, before the model polishes it. | `backend/agents/services.py` | Verified live |
| **Azure AI Speech** | Neural text to speech. | The spoken commentary, per language. A replay costs nothing. | `backend/agents/voice.py` | Verified 20 Oct |
| **Azure AI Content Safety** | Screens text for harmful content. | The Gate agent checks every line before it airs. | `backend/agents/safety.py` | In use on the live gateway (`CONTENT_SAFETY_ENDPOINT` is set). A word list stands in as the fallback. |

Translator, Speech and Content Safety all live on the same Foundry resource, so there is one endpoint and one role assignment for all of them.

## Moving and storing data

| Service | What it is | What we use it for | Where | Status |
|---|---|---|---|---|
| **Event Hubs** | A high-throughput message stream. | The live feed: the engine publishes match events and tracking frames, the gateway consumes them. Partitioned by match id so order holds. | `backend/bus/eventhubs.py`, `backend/app/live.py` | Verified 20 Oct: 2,190 messages sent and received, none lost. Measured from inside Azure on 23 Oct (`scripts/measure_live.py`, in a job beside the API): overlay p95 140 ms at 4x replay and 115 ms at 30x, 19,830 messages, none lost. Details in `docs/LOAD_TEST.md`. |
| **Blob Storage** | Cheap object storage. Standard LRS, one `footage` container with anonymous read (the clip is redacted and openly licensed). Shared keys are off. | Holds the real-footage clip. `/real/{clip}/video` on the gateway redirects to it, so the Container App image stays small. | `infra/modules/storage.bicep`, `backend/app/real.py` | Verified 23 Oct: the clip plays on the live `/real` page. Scrubbing works. |
| **Cosmos DB (NoSQL)** | A managed document database, free tier. | Stores verified agent output keyed by match seed, moment, persona and language. | `backend/agents/cache.py` | Verified 20 Oct against the real account: a value written through `CosmosCache` was read back by a fresh instance. The prepared demo output (54 entries) is loaded with `scripts/push_cache.py`. |

## Running the app

| Service | What it is | What we use it for | Status |
|---|---|---|---|
| **Container Apps** | Runs containers, scales to zero. | The FastAPI gateway and agents (`ca-api-...`). | Deployed. Live at `ca-api-uirzml34ufpge`. |
| **Container Apps: `mcp`** | The Match Intelligence MCP server on its own address (`/mcp`, streamable HTTP). Same image, different start command. | Lets VS Code Copilot or a broadcaster tool read the state engine's numbers without going through the gateway. | `backend/mcp_server/server.py`, `infra/modules/services.bicep` | Verified 23 Oct: `initialize` answered from the live app. Scales to zero. |
| **Container Apps: `a2a`** | The Recap Editor as its own A2A agent (`backend/a2a/app.py`). The gateway still serves the same routes. | A second agent runs, scales and is discovered on its own URL: agent card at `/.well-known/agent-card.json`, JSON-RPC at `/a2a/jsonrpc`. | `backend/a2a/app.py`, `infra/modules/services.bicep` | Verified 23 Oct: a recap came back through `scripts/a2a_client`. |
| **Container Apps Job: `job-warm`** | A job you start by hand. Same image, runs `scripts.warm_overlay_text` with `STORE=cosmos`. | Rebuilds the instant-overlay translation tables into Cosmos from inside Azure. Costs model and Translator calls, so it is manual only. | `infra/modules/services.bicep` | Created 23 Oct. |
| **Container Registry** | Stores our Docker images. | `azd deploy api` pushes the image here. | In use |
| **Static Web Apps** | Free hosting for a built frontend. | The React app. | Deployed. Live at `ashy-pebble-0f5b51c1e.5.azurestaticapps.net`, built against the live gateway. |
| **Managed Identity** | An identity an Azure resource can hold, so no passwords. | The Container App uses it to reach Foundry, Event Hubs, Cosmos and Key Vault. | In use |
| **Key Vault** | A safe for secrets. | Provisioned for secrets. Because everything is keyless it holds little. | Provisioned |

## Seeing what happened

| Service | What it is | What we use it for | Status |
|---|---|---|---|
| **Application Insights + Log Analytics** | Traces, logs and metrics. | Every model call has an OpenTelemetry span, so latency and failures show up here. | Verified 20 Oct: a span from a real model call arrived in Application Insights with the agent name, model, latency and outcome (`backend/app/telemetry.py`). |
| **Foundry evaluations** | Foundry's built-in evaluators (groundedness, relevance, fluency), run through the `azure-ai-evaluation` package, keyless. | Scores the newsroom's text against a single prompt (`scripts/eval_single_vs_multi.py`, result in `docs/EVALUATION.md`). | Run 25 Oct. |
| **Red team and guardrails** | An offline red team that assumes the model is hijacked, plus the Foundry AI Red Teaming Agent (`azure-ai-evaluation[redteam]`) for the live scan. | 14 attacks on Ask the Analyst (injection, spoilers, links, markup, prompt extraction, harmful, off-topic), each run with the guardrails off and on (`scripts/eval_redteam.py`, `data/evals/redteam.json`, result in `docs/REDTEAM.md`). In CI on every agent change (`.github/workflows/evals.yml`). | Offline run: 14 of 14 held with guardrails on. Ask's Verifier checks scorelines as pairs and does not count numbers the viewer typed or numbers inside row labels. `GUARDRAILS=true` on the live API. |

### Availability, alerts and the operations workbook (23 Oct)

`infra/modules/alerts.bicep`. All of it is Azure Monitor, no extra service to run.

| What | Detail | Status |
|---|---|---|
| **Availability tests** | Three standard tests every 15 minutes from three regions: the web app, the API `/health`, and a real read (`/matches`). | Verified 23 Oct: results arriving in `AppAvailabilityResults`. |
| **Alerts** | A test failing from two or more locations; more than 5 API 5xx in 5 minutes; more than 10 failed model calls in 15 minutes (the chaos switch is not counted). All go to one action group by email. | Created 23 Oct. |
| **Workbook "Pitchside operations"** | Availability, API p50 and p95, status codes, agent calls by outcome, calls per model deployment, requests turned away by the rate limit. | Every query run against the live workspace 23 Oct. |

### Load test (23 Oct)

| What | Detail | Status |
|---|---|---|
| **Azure Load Testing** | A Locust test of viewers reading match state, pulse, catch-up and moments, run from the same region as the API. Billed by virtual-user hour. | Run 23 Oct: 150 viewers, 5 minutes, 32,120 requests, 0 errors, p95 11 ms, API scaled 1 to 3 replicas and back to 0. Details in `docs/LOAD_TEST.md`. |

### Rate limits (23 Oct)

`backend/app/ratelimit.py`, on in Azure (`RATE_LIMIT=on`), off locally and in tests. Fresh match runs: 5 an hour for the whole service. Ask the Analyst (typed or spoken): 12 a minute per client. Recaps: 20 a minute per client. Chaos switch: 10 a minute per client. Replays are never limited. A limited call gets a 429 with `Retry-After`. Verified on the live API: 12 requests allowed, the 13th and 14th refused.

## Tools, not services

- **Azure MCP server:** lets us inspect and manage Azure resources from the editor. It's one of the judges' named hero technologies.
- **Microsoft Learn MCP:** current Microsoft docs, used before writing any Azure code.
- **`az` and `azd`:** the Azure CLI, and the Developer CLI that provisions (`azd provision`) and deploys (`azd deploy api`, `azd deploy web`) from the Bicep in `infra/`.
- **Bicep:** the language `infra/` is written in. Every resource above is code, not clicks.

## Costs, roughly

Foundry tokens are the biggest variable spend, and a replay costs nothing (the three demo matches cost about $0.09 to prepare). The always-on parts are the two API replicas, Event Hubs Basic (about $11 a month) and Container Registry Basic (about $5). Cosmos and Static Web Apps are free tier, and Load Testing is billed only while a test runs. There is a budget alert at $150 (`pitchside-150`). Rate limits on everything that calls a model or Speech stop a runaway.
