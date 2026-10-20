# 0006. Translator, Speech and Content Safety share the Foundry resource

Status: accepted

## Context

Each Azure AI service can be created as its own resource, with its own endpoint, role assignment and free tier cap.

## Decision

Translator, Speech and Content Safety are reached through the one Azure AI Services resource that already hosts the models (`NovessaPitchside1`). One endpoint, one set of role assignments, and no free-tier cap to run out of while judges are testing.

## Consequences

- Fewer resources to create, secure and explain.
- Pay-per-use rather than free tier, which is cents with caching.
- One resource is a single point of failure for every AI call, so each service has a fallback: no translation means English text, no speech means text only, and a Content Safety outage falls back to a local check.
