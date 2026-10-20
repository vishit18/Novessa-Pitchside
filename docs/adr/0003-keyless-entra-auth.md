# 0003. No service keys: Entra ID everywhere

Status: accepted

## Context

Keys in `.env` or the repo are the easiest way to leak access, and this repo will be public.

## Decision

Every Azure call uses `DefaultAzureCredential`: the signed-in `az login` locally, a user-assigned managed identity in Azure. Foundry, Translator, Speech, Content Safety, Event Hubs and Cosmos DB are all reached with role assignments, not keys.

## Consequences

- There is no secret to rotate, paste or leak.
- Running the agents needs `az login` and the right roles, which is more setup than pasting a key. `AGENTS=off` runs the whole app without any Azure account.
- Data-plane roles are separate from the Owner role, so Event Hubs and Cosmos each need an explicit assignment, even for the subscription owner.
