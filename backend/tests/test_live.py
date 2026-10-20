"""Live ingest: the engine publishes to the bus and the consumer rebuilds the same overlays."""

from __future__ import annotations

import asyncio

from backend.app.live import BUDGET_MS, LiveIngest
from backend.app.store import MatchStore
from backend.bus import Envelope, InMemoryBus


async def test_bus_delivers_in_order_to_every_subscriber() -> None:
    bus = InMemoryBus()
    a, b = await bus.subscribe("m"), await bus.subscribe("m")
    other = await bus.subscribe("x")
    batch = [Envelope.wrap("m", "event", float(i), {"i": i}) for i in range(5)]
    await bus.publish(batch)
    await bus.close()
    assert [e.payload["i"] async for e in a] == [0, 1, 2, 3, 4]
    assert [e.payload["i"] async for e in b] == [0, 1, 2, 3, 4]
    assert [e async for e in other] == []


async def test_live_run_matches_the_replay_overlays_and_meets_the_budget() -> None:
    store = MatchStore()
    match = await store.get("derby_01")
    live = LiveIngest(store, InMemoryBus())
    stats = live.start("derby_01", speed=60, until=600)
    for _ in range(400):
        await asyncio.sleep(0.05)
        if stats.status == "finished" and stats.consumed >= stats.published:
            break
    summary = stats.summary()
    assert summary["status"] == "finished"
    assert summary["consumed"] == summary["published"] > 0
    # The live consumer must raise exactly the overlays the replay timeline has for those minutes.
    expected = [o for o in match.timeline.overlays if o.t_match <= 600]
    assert summary["overlays"] == len(expected) > 0
    assert summary["overlay_ms"]["p95"] < BUDGET_MS
    await live.stop()
