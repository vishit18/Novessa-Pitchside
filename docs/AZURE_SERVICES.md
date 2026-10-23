# Azure services in Novessa Pitchside

A plain guide to every Azure service we use: what it is, why we picked it, where it lives in the code, and whether it has actually been checked end to end. The status column is the honest one. It gets updated as things are verified.

Everything signs in with **Entra ID (keyless)**. No service key sits in the repo or in `.env`. Locally the code uses your `az login`. In Azure it uses a managed identity.

## The AI side

| Service | What it is, in one line | What we use it for | Where | Status |
|---|---|---|---|---|
| **Microsoft Foundry** | Azure's home for models and agents. One resource, `NovessaPitchside1`, in Sweden Central. | Hosts two chat models: `chat-fast` (gpt-4.1-mini) for the high-volume agents, `chat-strong` (gpt-5-mini) for recaps only. | `backend/agents/llm.py`, `factory.py` | Verified live |
| **Microsoft Agent Framework** | A Python library (not a service) for building agents and wiring them into workflows. | Runs the Producer, Analyst, Verifier, Narrator, Gate workflow. | `backend/agents/workflow.py` | Verified live |
| **Azure AI Translator** | Machine translation. | First pass of each non-English language, before the model polishes it. | `backend/agents/services.py` | Verified live |
| **Azure AI Speech** | Neural text to speech. | The spoken commentary, per language. Audio is cached on disk, so a replay costs nothing. | `backend/agents/voice.py` | Verified 20 Oct |
| **Azure AI Content Safety** | Screens text for harmful content. | The Gate agent checks every line before it airs. | `backend/agents/safety.py` | In use when `CONTENT_SAFETY_ENDPOINT` is set |
| **Azure AI Search** | Managed search index, free tier, keyless (API keys off). | Grounds Ask the Analyst with league facts: clubs, managers, grounds, squads and what each metric means. No match results in it, so it cannot spoil. | `backend/agents/knowledge.py`, `scripts/index_knowledge.py`, `infra/modules/search.bicep` | Written and tested offline (mocked Search, plus a local keyword index that is also the fallback). Not provisioned yet. Behind `SEARCH_ENABLED`, off. |

Translator, Speech and Content Safety all live on the same Foundry resource, so there is one endpoint and one role assignment for all of them.

## Moving and storing data

| Service | What it is | What we use it for | Where | Status |
|---|---|---|---|---|
| **Event Hubs** | A high-throughput message stream. | The live feed: the engine publishes match events and tracking frames, the gateway consumes them. Partitioned by match id so order holds. | `backend/bus/eventhubs.py`, `backend/app/live.py` | Verified 20 Oct: 2,190 messages sent and received, none lost. Publish to overlay was p95 177 ms from a laptop, over the 150 ms budget. To be measured again from inside Azure. |
| **Blob Storage** | Cheap object storage. Standard LRS, one `footage` container with anonymous read (the clip is redacted and openly licensed). Shared keys are off. | Holds the real-footage clip. `/real/{clip}/video` on the gateway redirects to it, so the Container App image stays small. | `infra/modules/storage.bicep`, `backend/app/real.py` | Verified 23 Oct: the clip plays on the live `/real` page. |
| **Cosmos DB (NoSQL)** | A managed document database, free tier. | Shared cache of agent output keyed by match seed, moment, persona and language. | `backend/agents/cache.py` | Verified 20 Oct against the real account: a value written through `CosmosCache` was read back by a fresh instance. The warmed demo cache (54 entries) is loaded with `scripts/push_cache.py`. |

## Analytics

| Service | What it is | What we use it for | Where | Status |
|---|---|---|---|---|
| **Microsoft Fabric** (Eventstream, Eventhouse, Real-Time Dashboard, Lakehouse, Power BI) | Microsoft's analytics platform on OneLake. Trial capacity, free for 60 days. | The same Event Hubs feed lands in an Eventhouse for a live dashboard (score, xG race, tempo, shot map, publish-to-row latency); the 200 synthetic matches go to a Lakehouse for a Power BI league report. Eventstream signs in as the workspace identity, keyless. | `fabric/`, docs/FABRIC.md | KQL, notebook, upload and measures written and tested offline. Fabric items not created yet. |

## Running the app

| Service | What it is | What we use it for | Status |
|---|---|---|---|
| **Container Apps** | Runs containers, scales to zero. | The FastAPI gateway and agents (`ca-api-...`). | Deployed earlier. The live copy is an old build. |
| **Container Apps: `mcp`** | The Match Intelligence MCP server on its own address (`/mcp`, streamable HTTP). Same image, different start command. | Lets VS Code Copilot, Claude or a broadcaster tool read the state engine's numbers without going through the gateway. | `backend/mcp_server/server.py`, `infra/modules/services.bicep` | Verified 23 Oct: `initialize` answered from the live app. Scales to zero. |
| **Container Apps: `a2a`** | The Recap Editor as its own A2A agent (`backend/a2a/app.py`). The gateway still serves the same routes. | A second agent runs, scales and is discovered on its own URL: agent card at `/.well-known/agent-card.json`, JSON-RPC at `/a2a/jsonrpc`. | `backend/a2a/app.py`, `infra/modules/services.bicep` | Verified 23 Oct: a recap came back through `scripts/a2a_client` (the Verifier rejected two drafts and it fell back to the template, which is the recovery path working). |
| **Container Apps Job: `job-warm`** | A job you start by hand. Same image, runs `scripts.warm_overlay_text` with `STORE=cosmos`. | Rebuilds the instant-overlay translation tables into Cosmos from inside Azure. Costs model and Translator calls, so it is manual only. | `infra/modules/services.bicep` | Created 23 Oct. Not run yet. |
| **Container Registry** | Stores our Docker images. | `azd deploy api` pushes the image here. | In use |
| **Static Web Apps** | Free hosting for a built frontend. | The React app. | Created. Frontend not deployed yet. |
| **Managed Identity** | An identity an Azure resource can hold, so no passwords. | The Container App uses it to reach Foundry, Event Hubs, Cosmos and Key Vault. | In use |
| **Key Vault** | A safe for secrets. | Provisioned for secrets. Because everything is keyless it holds little. | Provisioned |

## Seeing what happened

| Service | What it is | What we use it for | Status |
|---|---|---|---|
| **Application Insights + Log Analytics** | Traces, logs and metrics. | Every model call has an OpenTelemetry span, so latency and failures show up here. | Verified 20 Oct: a span from a real model call arrived in Application Insights with the agent name, model, latency and outcome (`backend/app/telemetry.py`). Not yet connected to the Foundry project's Tracing tab. |
| **Foundry evaluations** | Foundry's built-in evaluators (groundedness, relevance, fluency), run through the `azure-ai-evaluation` package, keyless. | Scores the newsroom's text against a single prompt (`scripts/eval_single_vs_multi.py`, result in `docs/EVALUATION.md`). | Done. The single prompt scored higher on quality. |
| **Red team and guardrails** | An offline red team that assumes the model is hijacked, plus the Foundry AI Red Teaming Agent (`azure-ai-evaluation[redteam]`) for the live scan. | 14 attacks on Ask the Analyst (injection, spoilers, links, markup, prompt extraction, harmful, off-topic), each run with the guardrails off and on (`scripts/eval_redteam.py`, `data/evals/redteam.json`, result in `docs/REDTEAM.md`). In CI on every agent change (`.github/workflows/evals.yml`). | Offline run done: 11 of 14 held with guardrails on, 6 of 14 off; the other 3 are known gaps, listed with fixes. Live run and Foundry scan written, not run yet (need the OIDC setup in docs/02). Guardrails behind `GUARDRAILS`, off. |
| **Foundry tracing tab** | Foundry's view of agent runs, fed by the same Application Insights resource. | Every model span carries the GenAI semantic-convention attributes Foundry reads (`backend/app/telemetry.py`). The portal connection is one click (docs/02). | Code done and tested offline. Portal connection not made yet. |
| **Foundry Agent Service** | Hosts versioned prompt agents: instructions, model and settings live in Foundry. | Our seven prompts published as `pitchside-*` agents (`scripts/register_agents.py`). With `FOUNDRY_AGENT_SERVICE=true` the app calls them by reference through the Responses API, after checking each one matches the prompt in the checkout (`backend/agents/foundry_agents.py`). | Written and tested against a mocked endpoint. Not registered or run live yet. Off by default. |

### Availability, alerts and the operations workbook (23 Oct)

`infra/modules/alerts.bicep`. All of it is Azure Monitor, no extra service to run.

| What | Detail | Status |
|---|---|---|
| **Availability tests** | Three standard tests every 15 minutes from three regions: the web app, the API `/health`, and a real read (`/matches`). | Verified 23 Oct: results arriving in `AppAvailabilityResults`. |
| **Alerts** | A test failing from two or more locations; more than 5 API 5xx in 5 minutes; more than 10 failed model calls in 15 minutes (the chaos switch is not counted). All go to one action group by email. | Created 23 Oct. Not fired yet. |
| **Workbook "Pitchside operations"** | Availability, API p50 and p95, status codes, agent calls by outcome, calls per model deployment, requests turned away by the rate limit. | Every query run against the live workspace 23 Oct. |

### Rate limits (23 Oct)

`backend/app/ratelimit.py`, on in Azure (`RATE_LIMIT=on`), off locally and in tests. Fresh match runs: 5 an hour for the whole service. Ask the Analyst (typed or spoken): 12 a minute per client. Recaps: 20 a minute per client. Chaos switch: 10 a minute per client. Replays answer from the cache and are never limited. A limited call gets a 429 with `Retry-After`. Verified on the live API: 12 requests allowed, the 13th and 14th refused. Counters are per replica, so this is a guard against runaway spend, not a billing meter.

## Tools, not services

- **Azure MCP server:** lets Claude Code inspect and manage Azure resources from the editor. It's one of the judges' named hero technologies.
- **Microsoft Learn MCP:** current Microsoft docs, used before writing any Azure code.
- **`az` and `azd`:** the Azure CLI, and the Developer CLI that provisions (`azd provision`) and deploys (`azd deploy api`, `azd deploy web`) from the Bicep in `infra/`.
- **Bicep:** the language `infra/` is written in. Every resource above is code, not clicks.

## Costs, roughly

Foundry tokens are the only real spend, and caching keeps that to pennies for a replay. Event Hubs Basic is about $11 a month and Container Registry Basic about $5. Cosmos and Static Web Apps are free tier. There is a budget alert set at $150 (`pitchside-150`).
