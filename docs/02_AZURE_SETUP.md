# Azure setup

Written for VJ (first time on Azure) and for Claude Code (which does most of the provisioning once the basics exist).

## How Azure is organised (read this once, it clears up 90% of the confusion)

- **One Microsoft account → one Azure subscription.** You do not sign up for each service separately. Foundry, Event Hubs, Cosmos DB, Container Apps, Translator, Speech: they're all just *resources* you create inside your one subscription. Billing for all of them comes out of the same free credit.
- **Resource group** = a folder for resources. We put everything in one: `rg-pitchside`. Deleting it deletes everything.
- **Two websites, same login:**
  - **portal.azure.com** (Azure portal): where *all* resources live. Event Hubs, Cosmos DB, Container Apps, Key Vault, billing, budgets. If you're looking for "resources", it's here.
  - **ai.azure.com** (Microsoft Foundry portal): only the AI side. Model deployments, agents, playground, tracing, evaluations. A Foundry **project** screen won't show your Event Hubs or databases, because those aren't AI resources. That's normal.
- The hackathon site (innovationstudio.microsoft.com) "project" is just your submission page. It has nothing to do with Azure.
- **Sentry** isn't a Microsoft product and isn't needed. For monitoring we use Azure Application Insights, which also counts as Azure tech for the judges.

## Step 1 — VJ: account and tools (about 30 minutes)

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

## Step 2 — VJ: Foundry project and models (about 20 minutes)

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
   - If a model shows **0 quota** on the free account, pick a different model or region and tell Claude Code which you used. Names change often; what matters is one fast model and one strong one.
4. From the project **Overview**, copy the **project endpoint** (looks like `https://<resource>.services.ai.azure.com/api/projects/pitchside`) into `.env` as `FOUNDRY_PROJECT_ENDPOINT`.
5. Tell Claude Code: "Foundry is set up, endpoint is in .env, deployments are chat-fast and chat-strong." From here, Claude Code provisions everything else as code.

## Step 3 — Claude Code: everything else as code (Bicep + azd)

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
| Foundry model usage | pay per token | agents | the main cost; budget ~$40–80 total with caching |

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

Cosmos DB free tier is one per subscription. If Sweden Central will not take a new Cosmos account, deploy it to another region with a `cosmosLocation` parameter. `API_MIN_REPLICAS=1` keeps the api warm for judging.

## Step 4 — keep it alive for judging (27 Oct – 10 Nov)

- `api` container: **min replicas 1** from 26 Oct until 11 Nov so judges never hit a cold start. Everything else scales to zero.
- The default judge experience is the **cached replay**, so judges clicking around don't burn tokens.
- Rate-limit the "go live" button (e.g. 5 fresh matches per hour globally).
- Add an Application Insights availability test on the frontend URL and the `/health` endpoint, with an email alert.
- After winners are announced, delete `rg-pitchside` so nothing keeps billing.

## What actually exists (updated 20 Oct)

- Subscription `Azure subscription 1`, upgraded to pay-as-you-go. Budget `pitchside-150`: $150 per month, email alerts at 50%, 80% and 100%.
- Resource group `pitchside` (not `rg-pitchside`), Sweden Central.
- Deployed 20 Oct: api at https://ca-api-uirzml34ufpge.salmonocean-c33a3a80.swedencentral.azurecontainerapps.io (`/health` ok). Static Web App is in westus2 (westeurope and Sweden Central refuse new SWA accounts); the web service is not deployed yet.
- Foundry resource and project `NovessaPitchside1`. Deployments: `chat-fast` (gpt-4.1-mini, 100K tokens/min) and `chat-strong` (gpt-5-mini, 500K tokens/min). Both work with Entra tokens through `https://novessapitchside1.cognitiveservices.azure.com/openai/deployments/<name>/chat/completions` (checked 20 Oct: `chat-fast` 1.3 s, `chat-strong` 1.7 s with `reasoning_effort: minimal`). The `openai.azure.com` host returned PermissionDenied for the same token, so use the cognitiveservices host. Subscription is PayAsYouGo with the spending limit off.

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
