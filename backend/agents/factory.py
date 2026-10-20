"""Build a ready-to-run `MatchContext` from environment settings."""

from __future__ import annotations

import os

from backend.agents.cache import default_cache
from backend.agents.context import MatchContext
from backend.agents.intel import MatchIntel
from backend.agents.llm import FoundryTransport, ResilientLLM, Transport
from backend.agents.safety import default_safety
from backend.app.store import MatchStore


async def build_context(
    store: MatchStore, match_id: str, transport: Transport | None = None
) -> MatchContext:
    """Load a match and wire the model client, cache and content gate around it."""
    loaded = await store.get(match_id)
    return MatchContext(
        intel=MatchIntel(loaded),
        names=store.names,
        llm=ResilientLLM(transport or FoundryTransport()),
        cache=default_cache(),
        safety=default_safety(),
        fast_model=os.environ.get("FOUNDRY_DEPLOYMENT_FAST", "chat-fast"),
        strong_model=os.environ.get("FOUNDRY_DEPLOYMENT_STRONG", "chat-strong"),
    )
