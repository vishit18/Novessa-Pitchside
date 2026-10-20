# 0002. Instant overlays first, agent text attaches later

Status: accepted

## Context

The brief asks for overlays in under 150 ms, and the agents take 3 to 5 seconds per step.

## Decision

The deterministic layer emits every overlay that needs no language (tags, speeds, pass difficulty, cards, offsides, milestones, the momentum bar) straight away. Agent text arrives later as an `update` overlay with the same `moment_id`, and the client attaches it to the card already on screen. An agent that is slow, wrong or switched off never holds the picture up.

## Consequences

- The picture never waits for a model.
- A card can change after it appears, so the client has to handle updates, and a viewer sees numbers first and the explanation second.
- The chaos switch in the Control Room can kill an agent mid-match and the broadcast carries on.
