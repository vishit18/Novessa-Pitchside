# 0004. An event bus interface with an in-memory and an Event Hubs version

Status: accepted

## Context

The live feed from engine to gateway should be a real message stream in Azure, and it should still run on a laptop with nothing installed.

## Decision

`backend/bus/` defines one `EventBus` interface and two versions. `InMemoryBus` is the default. `EventHubsBus` is used when `EVENT_BUS=eventhubs`. Messages are wrapped in one envelope with the publish time, and are partitioned by match id so one match stays in order. The Event Hubs consumer starts from the latest position, since a live feed has no use for old messages, and uses the `$Default` group because the Basic tier has no others. `subscribe` returns only once the listener is attached, so the producer cannot start before anyone is listening.

## Consequences

- The same tests run against both versions of the feed.
- Publish-to-overlay latency is measured per message, and through a real hub from a laptop it came to p95 177 ms against a 150 ms budget. It still needs measuring from inside Azure.
- No checkpoint store, so a restarted consumer misses what it was not listening to. That is acceptable for a live feed.
