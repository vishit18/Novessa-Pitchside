"""Replay clock: turns a finished match into a live stream in match time.

The clock maps wall time to match time at a chosen speed (1x, 4x, 10x, 30x), and supports
pause and seek. Time and sleep are injected so tests run instantly.
"""

from __future__ import annotations

import asyncio
import heapq
import time
from collections.abc import AsyncIterator, Callable, Iterable, Iterator
from typing import Protocol, TypeVar


class Timed(Protocol):
    t_match: float


T = TypeVar("T", bound=Timed)

SPEEDS = (1.0, 4.0, 10.0, 30.0)


class ReplayClock:
    """Match time as a function of wall time. Not tied to any event loop."""

    def __init__(
        self, speed: float = 1.0, start: float = 0.0, now: Callable[[], float] = time.monotonic
    ) -> None:
        if speed <= 0:
            raise ValueError("speed must be positive")
        self._now = now
        self._speed = speed
        self._anchor_wall = now()
        self._anchor_match = start
        self._paused = True

    @property
    def speed(self) -> float:
        return self._speed

    @property
    def paused(self) -> bool:
        return self._paused

    def match_time(self) -> float:
        if self._paused:
            return self._anchor_match
        return self._anchor_match + (self._now() - self._anchor_wall) * self._speed

    def _rebase(self) -> None:
        self._anchor_match = self.match_time()
        self._anchor_wall = self._now()

    def play(self) -> None:
        if self._paused:
            self._anchor_wall = self._now()
            self._paused = False

    def pause(self) -> None:
        self._rebase()
        self._paused = True

    def set_speed(self, speed: float) -> None:
        if speed <= 0:
            raise ValueError("speed must be positive")
        self._rebase()
        self._speed = speed

    def seek(self, t_match: float) -> None:
        self._anchor_match = t_match
        self._anchor_wall = self._now()

    def wall_delay(self, t_match: float) -> float:
        """Wall seconds until the clock reaches `t_match` (0 if already past)."""
        if self._paused:
            return float("inf")
        return max(0.0, (t_match - self.match_time()) / self._speed)


def merge_by_time[T: Timed](*streams: Iterable[T]) -> Iterator[T]:
    """Merge already-sorted streams (events, tracking frames) into one time-ordered stream."""
    return heapq.merge(*streams, key=lambda item: item.t_match)


async def stream[T: Timed](
    items: Iterable[T],
    clock: ReplayClock,
    sleep: Callable[[float], object] = asyncio.sleep,
    poll: float = 0.05,
) -> AsyncIterator[T]:
    """Yield each item when the clock reaches its `t_match`.

    Items already behind the clock (after a seek forward) are skipped. Items are not replayed
    after a seek backward; start a new stream for that.
    """
    for item in items:
        if item.t_match < clock.match_time() - 1e-9:
            continue
        while True:
            delay = clock.wall_delay(item.t_match)
            if delay <= 0:
                break
            wait = poll if delay == float("inf") else min(delay, poll if poll else delay)
            result = sleep(wait)
            if asyncio.iscoroutine(result):
                await result
        yield item
