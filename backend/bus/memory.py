"""In-process bus for local runs and tests: one asyncio queue per subscriber."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator

from backend.bus.base import Envelope


class InMemoryBus:
    name = "memory"

    def __init__(self) -> None:
        self._subs: dict[str, list[asyncio.Queue[Envelope | None]]] = defaultdict(list)

    async def publish(self, envelopes: list[Envelope]) -> None:
        for env in envelopes:
            for q in self._subs[env.match_id]:
                q.put_nowait(env)

    async def subscribe(self, match_id: str) -> AsyncIterator[Envelope]:
        q: asyncio.Queue[Envelope | None] = asyncio.Queue()
        self._subs[match_id].append(q)
        return self._read(match_id, q)

    async def _read(
        self, match_id: str, q: asyncio.Queue[Envelope | None]
    ) -> AsyncIterator[Envelope]:
        try:
            while (env := await q.get()) is not None:
                yield env
        finally:
            self._subs[match_id].remove(q)

    async def close(self) -> None:
        for queues in self._subs.values():
            for q in queues:
                q.put_nowait(None)
