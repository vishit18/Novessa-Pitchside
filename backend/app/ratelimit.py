"""Rate limits for the endpoints that spend money (docs/02, "keep it alive for judging").

A model call, a Speech call or a fresh match run costs real money, and the judges' link is public.
Replays answer from the cache and cost nothing, so they are not limited. What is limited:

- fresh agent and live runs: 5 an hour for the whole service (`RATE_START_PER_HOUR`)
- Ask the Analyst, typed or spoken: 12 a minute per client (`RATE_ASK_PER_MIN`)
- recaps, which call the model on a cache miss: 20 a minute per client (`RATE_RECAP_PER_MIN`)
- the chaos switch: 10 a minute per client (`RATE_KILL_PER_MIN`)

Off unless `RATE_LIMIT=on`, so local runs and the tests are never throttled. Counters live in
memory, so with more than one replica each keeps its own count; the limits are a guard against
runaway spend, not a billing meter.
"""

from __future__ import annotations

import os
import time
from collections import deque
from collections.abc import Callable
from math import ceil

from fastapi import HTTPException, Request

Clock = Callable[[], float]
MAX_KEYS = 5000


class SlidingWindow:
    """At most `limit` hits per `window_s` seconds for each key."""

    def __init__(self, limit: int, window_s: float, clock: Clock = time.monotonic) -> None:
        self.limit, self.window_s, self._clock = limit, window_s, clock
        self._hits: dict[str, deque[float]] = {}

    def hit(self, key: str) -> float:
        """Record a hit. Returns 0 if allowed, else the seconds until it would be."""
        now = self._clock()
        q = self._hits.setdefault(key, deque())
        while q and now - q[0] >= self.window_s:
            q.popleft()
        if len(q) >= self.limit:
            return self.window_s - (now - q[0])
        q.append(now)
        if len(self._hits) > MAX_KEYS:
            self._drop_idle(now)
        return 0.0

    def _drop_idle(self, now: float) -> None:
        for key in [k for k, q in self._hits.items() if not q or now - q[-1] >= self.window_s]:
            del self._hits[key]


def client_key(request: Request) -> str:
    """The caller's address. Behind the Container Apps ingress the last X-Forwarded-For entry
    is the one the proxy added; earlier ones can be set by the caller."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        last = forwarded.split(",")[-1].strip()
        if last:
            return last.rsplit(":", 1)[0] if last.count(":") == 1 else last
    return request.client.host if request.client else "unknown"


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


class RateLimits:
    """The service's limits, read from the environment when the app is built."""

    def __init__(self, clock: Clock = time.monotonic) -> None:
        self.enabled = os.environ.get("RATE_LIMIT", "off") == "on"
        self._start = SlidingWindow(_env_int("RATE_START_PER_HOUR", 5), 3600, clock)
        self._ask = SlidingWindow(_env_int("RATE_ASK_PER_MIN", 12), 60, clock)
        self._recap = SlidingWindow(_env_int("RATE_RECAP_PER_MIN", 20), 60, clock)
        self._kill = SlidingWindow(_env_int("RATE_KILL_PER_MIN", 10), 60, clock)

    def _check(self, window: SlidingWindow, key: str, what: str) -> None:
        if not self.enabled:
            return
        wait = window.hit(key)
        if wait > 0:
            seconds = max(1, ceil(wait))
            raise HTTPException(
                429,
                f"too many {what} right now, try again in {seconds} s",
                headers={"Retry-After": str(seconds)},
            )

    def fresh_start(self) -> None:
        """Call before starting a run that is not already going. Shared by everyone."""
        self._check(self._start, "all", "new match runs")

    def ask(self, request: Request) -> None:
        self._check(self._ask, client_key(request), "questions")

    def recap(self, request: Request) -> None:
        self._check(self._recap, client_key(request), "recap requests")

    def kill(self, request: Request) -> None:
        self._check(self._kill, client_key(request), "switch-offs")
