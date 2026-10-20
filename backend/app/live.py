"""Live ingest: the match engine publishes to the event bus, the gateway consumes it.

A producer task replays a finished match onto the bus at wall-clock pace. A consumer task reads
the bus and runs every event and frame through the same state engine and overlay builder the
replay uses, so the instant overlays here are identical to the ones in the timeline. The
consumer times each message from publish to overlay ready: that is the number behind the
"deterministic overlays in under 150 ms" claim, including the bus hop (docs/00, docs/01).
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from backend.app.overlay import Overlay
from backend.app.store import MatchStore
from backend.app.timeline import ENGINE_FRAME_HZ, TimelineBuilder
from backend.bus import Envelope, EventBus
from engine.clock import ReplayClock, merge_by_time, stream
from engine.schema import MatchEvent, TrackingFrame

log = logging.getLogger("pitchside.live")

BUDGET_MS = 150.0
FLUSH_S = 0.05


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    rank = max(1, round(pct / 100 * len(sorted_values)))
    return sorted_values[rank - 1]


@dataclass
class LiveStats:
    """Counters and latencies for one live match."""

    status: str = "idle"
    speed: float = 1.0
    published: int = 0
    consumed: int = 0
    overlays: int = 0
    # Milliseconds from publish to the overlay being ready, for messages that raised overlays.
    overlay_ms: list[float] = field(default_factory=list)
    # Milliseconds from publish to the consumer taking the message, for every message.
    bus_ms: list[float] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        o, b = sorted(self.overlay_ms), sorted(self.bus_ms)
        p95 = _percentile(o, 95)
        return {
            "status": self.status,
            "speed": self.speed,
            "published": self.published,
            "consumed": self.consumed,
            "overlays": self.overlays,
            "overlay_ms": {
                "p50": round(_percentile(o, 50), 1),
                "p95": round(p95, 1),
                "max": round(o[-1], 1) if o else 0.0,
                "budget": BUDGET_MS,
                "within_budget": bool(o) and p95 <= BUDGET_MS,
            },
            "bus_ms": {
                "p50": round(_percentile(b, 50), 1),
                "p95": round(_percentile(b, 95), 1),
            },
        }


class LiveIngest:
    """Runs the producer and consumer for each live match and keeps their numbers."""

    def __init__(self, store: MatchStore, bus: EventBus) -> None:
        self.store = store
        self.bus = bus
        self.stats: dict[str, LiveStats] = {}
        self.overlay_sinks: dict[str, list[Callable[[Overlay], None]]] = {}
        self._tasks: dict[str, list[asyncio.Task[None]]] = {}

    def start(self, match_id: str, speed: float = 4.0, until: float | None = None) -> LiveStats:
        """Begin streaming a match onto the bus and consuming it. One run per match.

        `until` stops the stream at that match second, for short runs and tests.
        """
        running = self._tasks.get(match_id)
        if running and not all(t.done() for t in running):
            return self.stats[match_id]
        stats = self.stats[match_id] = LiveStats(status="starting", speed=speed)
        ready = asyncio.Event()
        self._tasks[match_id] = [
            asyncio.create_task(self._consume(match_id, stats, ready)),
            asyncio.create_task(self._produce(match_id, stats, speed, ready, until)),
        ]
        return stats

    async def stop(self) -> None:
        for tasks in self._tasks.values():
            for t in tasks:
                t.cancel()
        await asyncio.gather(
            *(t for ts in self._tasks.values() for t in ts), return_exceptions=True
        )

    async def _produce(
        self,
        match_id: str,
        stats: LiveStats,
        speed: float,
        ready: asyncio.Event,
        until: float | None,
    ) -> None:
        try:
            loaded = await self.store.get(match_id)
            # A subscriber must be listening before the first kick, or it misses the start.
            await asyncio.wait_for(ready.wait(), timeout=30)
            frames = loaded.tracking.iter_frames(ENGINE_FRAME_HZ)
            clock = ReplayClock(speed=speed)
            clock.play()
            pending: list[Envelope] = []
            last_flush = time.monotonic()
            stats.status = "live"
            async for item in stream(merge_by_time(loaded.events, frames), clock):
                if until is not None and item.t_match > until:
                    break
                is_event = isinstance(item, MatchEvent)
                payload: dict[str, Any] = item.model_dump(mode="json")  # type: ignore[attr-defined]
                kind: Literal["event", "frame"] = "event" if is_event else "frame"
                pending.append(Envelope.wrap(match_id, kind, item.t_match, payload))
                # Events go out at once. Frames ride along, or go after FLUSH_S.
                if is_event or time.monotonic() - last_flush >= FLUSH_S:
                    await self.bus.publish(pending)
                    stats.published += len(pending)
                    pending, last_flush = [], time.monotonic()
            if pending:
                await self.bus.publish(pending)
                stats.published += len(pending)
            stats.status = "finished"
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("live producer failed for %s", match_id)
            stats.status = "failed"

    async def _consume(self, match_id: str, stats: LiveStats, ready: asyncio.Event) -> None:
        try:
            loaded = await self.store.get(match_id)
            builder = TimelineBuilder(loaded.meta, self.store.league)
            subscription = await self.bus.subscribe(match_id)
            ready.set()
            async for env in subscription:
                took = time.time()
                if env.kind == "event":
                    _, overlays = builder.feed_event(MatchEvent.model_validate(env.payload))
                else:
                    _, overlays = builder.feed_frame(TrackingFrame.model_validate(env.payload))
                done = time.time()
                stats.consumed += 1
                stats.bus_ms.append((took - env.published_at) * 1000)
                if overlays:
                    stats.overlays += len(overlays)
                    stats.overlay_ms.append((done - env.published_at) * 1000)
                    for sink in self.overlay_sinks.get(match_id, []):
                        for ov in overlays:
                            sink(ov)
                if stats.status == "finished" and stats.consumed >= stats.published:
                    break
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("live consumer failed for %s", match_id)
            stats.status = "failed"
