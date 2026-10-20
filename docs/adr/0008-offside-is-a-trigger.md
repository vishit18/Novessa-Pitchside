# 0008. Offside flags are instant triggers, not moments

Status: accepted

## Context

The engine flags a few offsides a match, and the viewer should see them. Agents receive candidate moments, and each moment gets a sequential id that the agent cache is keyed on.

## Decision

An offside is a deterministic trigger that becomes an instant `milestone` overlay. It is not a moment. It never reaches the agents, and it does not take a moment id.

## Consequences

- Adding offsides did not shift any moment id, so cached agent output stayed valid.
- Offsides never get an explanation from an agent, only a lower third with the player and club.
- There is still no offside line in the engine and no goal is ever disallowed.
