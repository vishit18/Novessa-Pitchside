# 0010. No AI gateway in front of Foundry for now, and what production adds

Status: accepted

## Context

A deployment that serves a public audience and spends money per request needs to limit and observe that spend. The usual answer on Azure is API Management as an AI gateway in front of the model endpoint: token limits per caller, token metrics per caller, and one place to cut access.

We looked at it on 23 Oct. Two facts decided it. The per-caller token limit (`llm-token-limit`) is not available on the Consumption tier, so the pay-per-call tier would not have given us the feature that matters. The tiers that have it cost about $48 a month (Developer, no uptime guarantee) to about $197 a month (Basic v2). And it would sit on the path of every model call, when agent answers are already slower than our 4 s target.

## Decision

We do not put API Management in front of Foundry for the hackathon. We cover the same risks closer to the code:

- **Runaway spend from public traffic:** rate limits in the gateway (`backend/app/ratelimit.py`): fresh match runs per hour for the whole service, Ask and recaps per client per minute. A limited call gets a 429 with `Retry-After`. Replays answer from the cache and cost nothing, so the default judge experience is never limited.
- **Per-agent control and resilience:** every model call has a timeout, a retry, a circuit breaker and a fallback, and the Control Room can cut any agent off to show the recovery.
- **Observability:** an OpenTelemetry span per model call to Application Insights, an operations workbook, availability tests and alerts on failures.
- **Access:** keyless Entra ID everywhere (ADR 0003), so there is no key to leak or rotate.

## What production adds

These are the steps we would take before real broadcasters used this, in the order we would take them, with what each costs.

1. **API Management as the AI gateway** (a v2 tier or Developer to start). Token limits and token metrics per caller or per persona, request and completion logging for audit, and one switch to cut access. Its managed identity calls Foundry; the app no longer holds the role. Cost: a monthly fee and a few milliseconds per call. Worth it once there is more than one caller of the model endpoint.
2. **Private networking.** Container Apps in a virtual network, private endpoints for Foundry, Cosmos DB, Event Hubs and Key Vault, public access off. Cost: a larger Container Apps environment (workload profiles), private DNS, and a harder time for anyone to reach the demo, which is why it is off now.
3. **Counters shared across replicas.** Our limits are per replica. With APIM, or a shared store such as Redis, they hold across the whole service.
4. **Foundry guardrails on the deployment** as policy, beside the in-app checks (`backend/agents/guardrails.py`): content filters, prompt-shield and jailbreak detection set per deployment, so a new service cannot skip them.
5. **Defender for Cloud and Azure Policy** to keep every resource inside the rules: no public storage, TLS 1.2, tags, allowed regions. The footage container is public on purpose and would be the one documented exception.
6. **Two regions.** A second Container Apps environment and Cosmos DB multi-region writes, behind Front Door. The state engine is deterministic and the cache is shared, so a second region needs no data migration.
7. **Evaluation as a gate.** The Foundry evaluators and the red-team run (`docs/EVALUATION.md`, `docs/REDTEAM.md`) block a deploy when quality or safety drops, not only report it.

## Consequences

- Nothing stops a caller who gets past the rate limits from spending tokens, except the limits themselves and the Foundry quota on the deployment. For a public demo that is acceptable; for a customer it is not.
- The limits reset when a replica restarts, and each replica counts on its own, so the real ceiling is the per-replica limit times the replica count.
- If we put APIM in later, the gateway code does not change: the model endpoint is already a setting (`FOUNDRY_OPENAI_ENDPOINT`), so the gateway is a new address and a role assignment.
