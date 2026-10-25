# Azure work split: two people, two Claudes

> **Status, 25 Oct:** this is the plan as written on 23 Oct, kept for the record. Done: Blob footage, the `api`, `mcp` and `a2a` Container Apps and the warm job, load test, AI Search and Agent Service code (flags off). Fabric was dropped and its code removed on 25 Oct, red team and guardrails. Not done on purpose: the KEDA `agents` worker and API Management (see ADR 0010). What is deployed is listed in `docs/AZURE_SERVICES.md`.

Goal: add the extra Azure services in parallel without anyone breaking `main` or the live site. Written 23 Oct. Deadline is 28 Oct 06:59 London, so feature-complete by 25 Oct.

The split is by folder, not by feature size. Each person owns a set of files, so two Claudes rarely edit the same one.

## Who does what

**Person A (VJ): platform and delivery**

| Item | What | Files A owns |
|---|---|---|
| Real footage online | Put the clip in Azure Blob, serve it from `/real/{clip}/video` | `infra/modules/storage.bicep`, `backend/app/real.py`, `scripts/upload_footage.py` |
| 1. Container Apps split | `api`, `agents` worker (KEDA on Event Hubs lag), `mcp`, `a2a-recap`; vision and cache warming as Jobs | `infra/modules/app.bicep`, `infra/modules/jobs.bicep`, `azure.yaml`, `Dockerfile*`, `backend/mcp_server/`, `backend/a2a/` |
| 6. API Management | AI gateway in front of Foundry: token limits per persona, logging, kill switch | `infra/modules/apim.bicep`, `backend/agents/llm.py` (base URL from env only) |
| 8. Load test | One Azure Load Testing run against the live gateway, numbers into the docs | `loadtest/`, `docs/LOAD_TEST.md` |
| Deploys | Only A runs `azd provision` and `azd deploy` | |

**Person B (teammate): data and AI depth**

| Item | What | Files B owns |
|---|---|---|
| 2. Fabric | Event Hubs, Eventstream, Eventhouse (KQL), real-time dashboard, Power BI over the 200-match dataset in OneLake | `fabric/` (KQL, notebooks, setup notes), `docs/FABRIC.md` |
| 5. Foundry depth | Register agents in Foundry Agent Service, connect Tracing to App Insights, evals and a red-team scan in CI, guardrails | `backend/app/telemetry.py`, `backend/agents/factory.py`, `scripts/eval_*`, `.github/workflows/evals.yml`, `docs/EVALUATION.md` |
| 7. AI Search | Free-tier index of league and club facts and the glossary, used to ground Ask the Analyst | `infra/modules/search.bicep`, `scripts/index_knowledge.py`, `backend/agents/ask.py` (retrieval step only), `data/knowledge/` |

B writes the Bicep for what B needs (Search) but does not provision it. B hands A the module and A runs it, or A gives B Contributor on the `pitchside` resource group so B can run it. Fabric is portal work and needs its own trial capacity, which B can start in the Fabric portal.

## Shared files (the usual conflict spots)

| File | Rule |
|---|---|
| `infra/main.bicep` | Add your module as one new block at the end, nothing else. Pull first. |
| `.env.example` | Append your variables under a heading with your item name. Never reorder. |
| `docs/02_AZURE_SETUP.md`, `docs/AZURE_SERVICES.md` | Add or edit only your own rows. Say honestly whether it is verified. |
| `docs/00_REQUIREMENTS_CHECKLIST.md`, `docs/08_BUILD_PLAN.md` | Tick your own boxes. Status goes in a new dated bullet, never edit someone else's. |
| `pyproject.toml` / `uv.lock` | Rebase, then re-run `uv lock`. Do not hand-merge the lock file. |

## Rules so nothing breaks

1. **Everything new is behind a flag, default off.** Example: `APIM_ENABLED=false`, `SEARCH_ENABLED=false`, `FOUNDRY_AGENT_SERVICE=false`. With the flags off the app behaves exactly as it does today. Flip a flag only after you have run it live.
2. **Before every push:** `uv run pytest`, `uv run ruff check .`, `uv run python -m mypy .`, and in `frontend/`: `npm test`, `npm run lint`. If one fails, fix it first.
3. **Pull and rebase before you push**, push small commits, never force-push `main`. Commit style and the no-AI-attribution rule in `CLAUDE.md` apply to both of you. Run `git config core.hooksPath .githooks` on your machine.
4. **Infra changes:** run `az bicep build` and `az deployment group what-if` first. Only A applies it. Never delete or recreate the existing resources (Foundry, Cosmos, Event Hubs, the `api` app).
5. **One deployer.** Two people running `azd deploy` can overwrite each other's build. B asks A to deploy, or both agree in the chat first.
6. **Cost check.** Before creating a billable resource, say what it costs and wait for A. The budget alert is `pitchside-150`. Trial and free tiers first.
7. **Keyless.** Managed identity and Entra only. No keys in the repo, `.env` or the chat.
8. **Cut line.** If an item will not be done by 25 Oct, say so and cut it. Do not leave it half-wired.

## Access B needs (A does these once)

- Reader or Contributor on resource group `pitchside` for B's Microsoft account.
- Data-plane roles on B's own identity for local runs: Cosmos DB Built-in Data Contributor, Azure Event Hubs Data Receiver, Cognitive Services OpenAI User and Azure AI User on `NovessaPitchside1`.
- Added as a collaborator on the GitHub repo.
- A copy of the non-secret `.env` values (endpoints). Send over a private channel, not the repo.

## Order of work

| When | A | B |
|---|---|---|
| 23 Oct (today) | Real footage in Blob and redeploy. Container Apps split. | Start Fabric trial, Eventstream from Event Hubs. Foundry tracing connected. |
| 24 Oct | APIM in front of Foundry (flag off, then on). | Evals and red-team in CI. AI Search index and Ask retrieval. |
| 25 Oct | Load test, docs, redeploy with flags on. | Fabric dashboard and Power BI, docs. Feature-complete line. |
| 26 Oct | Record the video, README. Both: bug fixes only. | Same. |

## Starter prompt for each Claude

Person A: *Read CLAUDE.md and docs/11_TEAM_SPLIT.md. I am Person A. Do my items in the order in the table, stay inside my files, put everything behind a flag, run the checks before each push, and ask me before creating any billable resource.*

Person B: *Read CLAUDE.md and docs/11_TEAM_SPLIT.md. I am Person B. Do my items in the order in the table, stay inside my files, put everything behind a flag, run the checks before each push, and ask me before creating any billable resource. Do not run azd deploy.*
