# 0009. Agent output cache: files locally, Cosmos DB in Azure, layered

Status: accepted

## Context

Agent output is cached per match seed, moment, persona and language, so replays and the demo cost nothing. The cache has to work offline and in Azure.

## Decision

`FileCache` is the default. When `STORE=cosmos`, `CosmosCache` sits in front of it: reads try the local layer first and only go to Cosmos on a miss, and writes land locally at once and go to Cosmos on a worker thread. A database that is slow or down never holds up a broadcast.

## Consequences

- The deployed API shares one cache across replicas, and a cold container still starts warm.
- A write to Cosmos can be lost if the process dies in the instant after the local write. The local layer still has it.
- The cache is only as good as its keys, and a change to a prompt needs the cache cleared by hand.
