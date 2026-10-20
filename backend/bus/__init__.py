"""Event bus: in memory locally, Azure Event Hubs in the cloud (`EVENT_BUS`)."""

from __future__ import annotations

import os

from backend.bus.base import Envelope, EventBus
from backend.bus.memory import InMemoryBus


def default_bus() -> EventBus:
    """The bus named by `EVENT_BUS`. Falls back to memory when Event Hubs is not configured."""
    fqdn, hub = os.environ.get("EVENTHUB_FQDN"), os.environ.get("EVENTHUB_NAME")
    if os.environ.get("EVENT_BUS", "memory") == "eventhubs" and fqdn and hub:
        from backend.bus.eventhubs import EventHubsBus

        return EventHubsBus(fqdn, hub)
    return InMemoryBus()


__all__ = ["Envelope", "EventBus", "InMemoryBus", "default_bus"]
