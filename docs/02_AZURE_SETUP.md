# Azure setup

Written for someone new to Azure provisioning this repo (almost everything is code once the basics exist).

## How Azure is organised (read this once, it clears up 90% of the confusion)

- **One Microsoft account → one Azure subscription.** You do not sign up for each service separately. Foundry, Event Hubs, Cosmos DB, Container Apps, Translator, Speech: they're all just *resources* you create inside your one subscription. Billing for all of them comes out of the same free credit.
- **Resource group** = a folder for resources. We put everything in one: `rg-pitchside`. Deleting it deletes everything.
- **Two websites, same login:**
  - **portal.azure.com** (Azure portal): where *all* resources live. Event Hubs, Cosmos DB, Container Apps, Key Vault, billing, budgets. If you're looking for "resources", it's here.
  - **ai.azure.com** (Microsoft Foundry portal): only the AI side. Model deployments, agents, playground, tracing, evaluations. A Foundry **project** screen won't show your Event Hubs or databases, because those aren't AI resources. That's normal.
- The hackathon site (innovationstudio.microsoft.com) "project" is just your submission page. It has nothing to do with Azure.
- **Sentry** isn't a Microsoft product and isn't needed. For monitoring we use Azure Application Insights, which also counts as Azure tech for the judges.

## Step 1 — Account and tools (about 30 minutes)

1. Go to **azure.microsoft.com/free** → *Try Azure for free*. Sign in with your Microsoft account. It asks for a card for identity verification; you're not charged unless you manually upgrade. You get **$200 credit for 30 days**.
   - Sign up **today**. 30 days from 19–20 Oct covers the whole judging period (ends 10 Nov) with about a week spare.
2. In portal.azure.com: search **Cost Management → Budgets** → create a budget of **$150** with email alerts at 50%, 80%, 100%.
3. Install on your machine:
   - Azure CLI (`az`)
   - Azure Developer CLI (`azd`)
   - GitHub CLI (`gh`), then `gh auth login`
   - Docker Desktop, Node 22+, Python 3.12, `uv`
4. Log in from the terminal:
   ```bash
   az login
   azd auth login
   az account show   # note the subscription id
   ```
5. Register the providers we need (one-off, takes a few minutes):
   ```bash
   for p in Microsoft.CognitiveServices Microsoft.App Microsoft.OperationalInsights \
            Microsoft.EventHub Microsoft.DocumentDB Microsoft.Web Microsoft.KeyVault Microsoft.Insights; do
     az provider register --namespace $p
   done
   ```

## Step 2 — Foundry project and models (about 20 minutes)

Do this one by hand. It's quick, and it's how you'll check model quota.

1. Go to **ai.azure.com**, make sure the **New Foundry** toggle (top of the page) is on.
2. **Create new project** → name `pitchside` → *Advanced options*:
   - Resource group: create new `rg-pitchside`
   - Region: **Sweden Central** (broad model availability, EU, close to London). If it's unavailable to you, use East US 2. Use the same region for everything else.
   - This creates the Foundry resource and the project together.
3. In the project, go to **Models + endpoints** (or *Deploy model*) and deploy:
   - A small fast chat model for the high-volume agents, e.g. **gpt-4.1-mini** or the current equivalent mini model. Deployment name: `chat-fast`.
   - A stronger model for recaps and the Analyst, e.g. **gpt-4.1** or current equivalent. Deployment name: `chat-strong`.
   - Use *Global Standard* deployment type. Start with the default tokens-per-minute; raise it if you hit 429s.
   - If a model shows **0 quota** on the free account, pick a different model or region and note which you used. Names change often; what matters is one fast model and one strong one.
4. From the project **Overview**, copy the **project endpoint** (looks like `https://<resource>.services.ai.azure.com/api/projects/pitchside`) into `.env` as `FOUNDRY_PROJECT_ENDPOINT`.
5. Check that the endpoint is in `.env` and the deployments are named `chat-fast` and `chat-strong`. From here, everything else is provisioned as code.

## Step 3 — Everything else as code (Bicep + azd)

Create `infra/main.bicep` and modules, referencing the existing Foundry resource rather than creating a new one. Then `azd up`.

| Resource | SKU / tier | Why | Approx cost |
|---|---|---|---|
| Log Analytics + Application Insights | Pay-as-you-go | OpenTelemetry traces, latency dashboard | ~free under 5 GB/month |
| Key Vault | Standard | secrets | pennies |
| User-assigned Managed Identity | — | keyless auth to everything | free |
| Container Apps environment (Consumption) | Consumption | `api`, `agents`, `mcp` apps | free monthly grant covers us if min replicas = 0 except during demos |
| Container Registry | Basic | images, pulled with managed identity (decided 20 Oct) | ~$5/month, about $6 until 10 Nov |
| Event Hubs namespace | Basic, 1 TU, hub `match-events` | event-driven backbone | ~$11/month |
| Cosmos DB for NoSQL | **Free tier** (1000 RU/s, 25 GB) | matches, moments, profiles, cache | free (enable free tier at create — only one per subscription) |
| Static Web Apps | **Free** | frontend | free |
| Azure AI Translator, Speech, Content Safety | **reuse the Foundry resource** `NovessaPitchside1` | same Azure AI Services, one endpoint, one role assignment, no free-tier cap to run out of during judging | pay per use, cents with caching (decided 20 Oct) |
| Container Apps `mcp`, `a2a` and Job `job-warm` | Consumption, scale to zero, same image as `api` | MCP server, A2A Recap Editor, manual cache-warming job (decided 23 Oct) | free monthly grant covers it |
| Storage account (Standard LRS, `footage` container) | Standard, anonymous blob read on one container | the real-footage clip, 31 MB (decided 23 Oct) | pence a month |
| Foundry model usage | pay per token | agents | the main cost; budget ~$40–80 total with caching |
| Azure AI Search (Person B, item 7, not provisioned yet) | **Free** (50 MB, keyless, API keys off) | league and glossary facts that ground Ask the Analyst | free; one free search service per subscription |

Rough total for the whole hackathon plus judging: **$60–120**, inside the $200 credit. Check actual spend daily in Cost Management.

Role assignments for the managed identity: `Cognitive Services OpenAI User` + `Azure AI User` on the Foundry resource, `Azure Event Hubs Data Owner` on the namespace, `Cosmos DB Built-in Data Contributor` (data-plane role), `Key Vault Secrets User`, `Cognitive Services User` on Translator/Speech/Content Safety.

### Deploying (infra is written, nothing deployed yet)

`infra/` holds the Bicep (`main.bicep` plus modules for monitoring, platform, data, roles and app). It targets the existing resource group and only references the Foundry resource. It creates Log Analytics, Application Insights, Key Vault, a user-assigned identity, Container Registry Basic, Event Hubs Basic, Cosmos DB (free tier, 1000 RU/s shared), a Container Apps environment with the `api` app, and a free Static Web App, plus the role assignments. `az bicep build` is clean and `az deployment group what-if` succeeded on 20 Oct.

```bash
azd env new pitchside
azd env set AZURE_RESOURCE_GROUP pitchside
azd env set AZURE_LOCATION swedencentral
azd env set FOUNDRY_PROJECT_ENDPOINT https://novessapitchside1.services.ai.azure.com/api/projects/NovessaPitchside1
azd provision          # creates the resources (this is the first spend)
azd deploy api         # builds the Dockerfile in ACR and rolls out the container
```

Cosmos DB free tier is one per subscription. If Sweden Central will not take a new Cosmos account, deploy it to another region with a `cosmosLocation` parameter. `API_MIN_REPLICAS=2` keeps two api replicas warm for judging (set on 23 Oct after the load test, see `docs/LOAD_TEST.md`).

## Step 4 — keep it alive for judging (27 Oct – 10 Nov)

- `api` container: **min replicas 1, max 3** until 11 Nov (changed from 2 on 26 Oct). One warm replica means judges never hit a cold start, and the Control Room's switch-off and agent counters, which live in memory inside a replica, read the same on every request. A sudden crowd still scales out to three, but the first minute lands on one replica (see `docs/LOAD_TEST.md`). `a2a` keeps one warm replica (a cold start took over 30 s and the agent card timed out). Everything else scales to zero.
- The default judge experience is the **cached replay**, so judges clicking around don't burn tokens.
- Rate-limit the "go live" button (e.g. 5 fresh matches per hour globally).
- Add an Application Insights availability test on the frontend URL and the `/health` endpoint, with an email alert.
- After winners are announced, delete `rg-pitchside` so nothing keeps billing.

## What actually exists (updated 20 Oct)

- Subscription `Azure subscription 1`, upgraded to pay-as-you-go. Budget `pitchside-150`: $150 per month, email alerts at 50%, 80% and 100%.
- Resource group `pitchside` (not `rg-pitchside`), Sweden Central.
- Deployed 20 Oct: api at https://ca-api-uirzml34ufpge.salmonocean-c33a3a80.swedencentral.azurecontainerapps.io (`/health` ok). Static Web App is in westus2 (westeurope and Sweden Central refuse new SWA accounts); the web service is not deployed yet.
- Foundry resource and project `NovessaPitchside1`. Deployments: `chat-fast` (gpt-4.1-mini, 100K tokens/min) and `chat-strong` (gpt-5-mini, 500K tokens/min). Both work with Entra tokens through `https://novessapitchside1.cognitiveservices.azure.com/openai/deployments/<name>/chat/completions` (checked 20 Oct: `chat-fast` 1.3 s, `chat-strong` 1.7 s with `reasoning_effort: minimal`). The `openai.azure.com` host returned PermissionDenied for the same token, so use the cognitiveservices host. Subscription is PayAsYouGo with the spending limit off.

- 23 Oct: both apps redeployed. Storage account `stuirzml34ufpge` created with only `infra/modules/storage.bicep` (a full `azd provision` would put the API image back to the placeholder). The clip is at `https://stuirzml34ufpge.blob.core.windows.net/footage/117093_w1890/clip.mp4` and the API has `REAL_VIDEO_BASE_URL` set. Upload with `az storage blob upload --auth-mode login` (needs Storage Blob Data Contributor; shared keys are off).

- 23 Oct: `mcp`, `a2a` and `job-warm` created with only `infra/modules/services.bicep` (parameters taken from the live `api` app so nothing there changed). `main.parameters.json` now passes `SERVICE_*_IMAGE_NAME`, so a later `azd provision` keeps the deployed images instead of resetting them to the placeholder. `azure.yaml` lists `mcp` and `a2a` as services, so `azd deploy` builds them too.
  - MCP: `https://ca-mcp-uirzml34ufpge.salmonocean-c33a3a80.swedencentral.azurecontainerapps.io/mcp`
  - A2A: `https://ca-a2a-uirzml34ufpge.salmonocean-c33a3a80.swedencentral.azurecontainerapps.io`
  - Warm the cache from Azure: `az containerapp job start -g pitchside -n job-warm-uirzml34ufpge`

- 23 Oct: monitoring added with `infra/modules/alerts.bicep` (three availability tests, five alert rules, one action group, one workbook; emails go to the budget-alert address). Azure Load Testing resource `lt-uirzml34ufpge` added with `infra/modules/loadtest.bicep` (billed by virtual-user hour, nothing while idle). `RATE_LIMIT=on` is set on the api. `azd env set ALERT_EMAIL <address>` makes `azd provision` keep the alert module.

## Environment variables (`.env.example`)

```
FOUNDRY_PROJECT_ENDPOINT=
FOUNDRY_DEPLOYMENT_FAST=chat-fast
FOUNDRY_DEPLOYMENT_STRONG=chat-strong
EVENTHUB_FQDN=                    # <ns>.servicebus.windows.net
EVENTHUB_NAME=match-events
COSMOS_ENDPOINT=
COSMOS_DATABASE=pitchside
TRANSLATOR_ENDPOINT=
TRANSLATOR_REGION=
SPEECH_REGION=
SPEECH_RESOURCE_ID=
CONTENT_SAFETY_ENDPOINT=
APPLICATIONINSIGHTS_CONNECTION_STRING=
EVENT_BUS=memory                  # memory | eventhubs
STORE=local                       # local | cosmos
AGENT_CACHE=on
```

## Person B items: how to switch them on (added 23 Oct)

Everything here is behind a flag that is off by default. With the flags off the app is exactly as it was. Nothing below has been provisioned yet. Person B wrote it, Person A applies it.

### AI Search (item 7)

1. Get your own object id: `az ad signed-in-user show --query id -o tsv`.
2. Turn the module on and provision:
   ```bash
   azd env set SEARCH_ENABLED true          # read by main.parameters.json, see below
   azd env set SEARCH_DEVELOPER_PRINCIPAL_ID <object id from step 1>
   azd provision
   ```
   This adds `srch-<token>` (free tier, API keys disabled), gives the app's managed identity **Search Index Data Reader**, and gives you **Search Service Contributor** and **Search Index Data Contributor** so you can build the index. If provisioning says a free service already exists in the subscription, delete the old free one or ask before choosing Basic (about $75 a month, not worth it here).
3. Wait a few minutes for the roles, then build the index from your machine:
   ```bash
   SEARCH_ENDPOINT=$(azd env get-value SEARCH_ENDPOINT) uv run python -m scripts.index_knowledge
   ```
   Expect `177 documents`, `uploaded 177 documents` and `check query 'pressure index' -> term-pressure-index`.
4. Try it locally: put `SEARCH_ENABLED=true` and `SEARCH_ENDPOINT=...` in `.env`, run `make dev`, ask "who manages Kestrel Bay?" or "what does the pressure index mean?". The answer's trail says `Knowledge: 2 league facts from Azure AI Search`. If it says `local index`, the call to Search failed (usually the role has not landed yet); the logs say why.
5. On the api app, add `SEARCH_ENABLED=true` and `SEARCH_ENDPOINT=<value>` to the `env` block that `main.bicep` passes to `app.bicep`, then `azd provision` and `azd deploy api`.

`infra/main.parameters.json` maps `SEARCH_ENABLED` and `SEARCH_DEVELOPER_PRINCIPAL_ID` from the azd environment; both default to off and empty.

### Foundry tracing (item 5)

Every model call is already a span in Application Insights. The spans now also carry the GenAI attributes (`gen_ai.agent.name`, `gen_ai.request.model`, ...) that the Foundry portal reads. To see them in Foundry:

1. Open [ai.azure.com](https://ai.azure.com) with the **New Foundry** toggle on, and open the project `NovessaPitchside1`.
2. Left menu **Agents**, then **Traces** at the top, then **Connect** on the right.
3. Pick the existing Application Insights resource `appi-<token>` in `pitchside` (the one in `APPLICATIONINSIGHTS_CONNECTION_STRING`) and **Connect**.
4. Run a match with agents on, wait 2 to 5 minutes, refresh Traces. Spans are named `agent.producer`, `agent.analyst` and so on, with the workflow spans from Agent Framework around them.

No code change and no new resource. Prompts and answers are not recorded.

### Foundry Agent Service (item 5)

1. Your identity needs **Azure AI User** on the Foundry resource (the subscription owner has it; the app's managed identity already has it from `roles.bicep`).
2. Publish the agents. Safe to re-run; only changed prompts get a new version:
   ```bash
   uv run python -m scripts.register_agents --dry-run
   uv run python -m scripts.register_agents
   ```
   Expect seven agents, `pitchside-producer` to `pitchside-ask`, each `published version 1`. They then show under **Agents** in the portal with their instructions and model.
3. Try it locally with `FOUNDRY_AGENT_SERVICE=true` in `.env` and `make dev`. The log says `calling pitchside-producer version 1 through Foundry Agent Service` once per agent. A line saying an agent `is not registered for this prompt and model` means step 2 was not run after a prompt edit; that agent is called directly, nothing breaks.
4. For the deployed app, add `FOUNDRY_AGENT_SERVICE=true` to the api app's `env` in `main.bicep`, then `azd provision` and `azd deploy api`. Re-run step 2 after every prompt change before deploying.

### Guardrails (item 5)

`GUARDRAILS=true` puts deterministic rules ahead of Content Safety: no links, emails, markup or system prompt read back, in viewer questions or in anything that airs. No Azure resource. `backend/tests/test_guardrails.py` checks they pass every one of the 7,000-odd lines in the demo cache. Turn it on locally, watch a match, then add it to the api app's `env`.

### Evals and red team in CI (item 5)

`.github/workflows/evals.yml` runs the offline red team (`scripts/eval_redteam.py`, hijacked model, no Azure) on every change to `backend/agents/`. Results land in the run summary and in `docs/REDTEAM.md` when run locally.

The live job (real models, Content Safety, optionally the Foundry AI Red Teaming Agent) only runs by hand and needs a keyless GitHub login to Azure. Person A, once:

1. Portal, **Microsoft Entra ID** > **App registrations** > **New registration**, name `pitchside-github`, register. Note the **Application (client) ID** and **Directory (tenant) ID**.
2. In that app: **Certificates & secrets** > **Federated credentials** > **Add credential** > **GitHub Actions deploying Azure resources**. Organization `vishit18`, repository `Novessa-Pitchside`, entity **Branch**, branch `main`. Save. No secret is created.
3. Resource group `pitchside` > **Access control (IAM)** > add **Cognitive Services OpenAI User** and **Azure AI User** on `NovessaPitchside1` for `pitchside-github` (and **Cognitive Services User** for Content Safety).
4. GitHub repo **Settings** > **Secrets and variables** > **Actions** > **Variables** (not secrets): `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `FOUNDRY_PROJECT_ENDPOINT`, `FOUNDRY_OPENAI_ENDPOINT`, `CONTENT_SAFETY_ENDPOINT`.
5. **Actions** > **evals** > **Run workflow** on `main`, tick **live**. The table appears in the run summary and as an artifact. A live run is 14 questions through the real models, well under a cent.

Without step 4 the live job is skipped, and the offline job still runs.
