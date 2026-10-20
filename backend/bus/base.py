"""The event bus interface and the envelope every message travels in.

Locally the bus is in memory. In Azure it is Event Hubs. Both carry the same envelope, so the
consumer cannot tell them apart.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any, Literal, Protocol

from pydantic import BaseModel


class Envelope(BaseModel):
    """One match event or tracking frame on its way from the engine to the gateway."""

    match_id: str
    kind: Literal["event", "frame"]
    t_match: float
    # Wall clock at publish, from time.time(), so the consumer can measure bus latency.
    published_at: float
    payload: dict[str, Any]

    @classmethod
    def wrap(
        cls, match_id: str, kind: Literal["event", "frame"], t_match: float, payload: dict[str, Any]
    ) -> Envelope:
        return cls(
            match_id=match_id,
            kind=kind,
            t_match=t_match,
            published_at=time.time(),
            payload=payload,
        )


class EventBus(Protocol):
    """Publish envelopes for a match; read them back in the order they were published."""

    name: str

    async def publish(self, envelopes: list[Envelope]) -> None:
        """Send a batch. Envelopes for one match keep their order."""
        ...

    async def subscribe(self, match_id: str) -> AsyncIterator[Envelope]:
        """Start listening and return the stream of envelopes for one match.

        Returns only once the listener is attached, so anything published afterwards is seen.
        The stream runs until the bus closes or the caller calls `aclose()` on it.
        """
        ...

    async def close(self) -> None: ...
