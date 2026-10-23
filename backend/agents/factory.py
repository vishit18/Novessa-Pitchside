"""Build a ready-to-run `MatchContext` from environment settings."""

from __future__ import annotations

import os

from backend.agents.cache import default_cache
from backend.agents.context import MatchContext
from backend.agents.foundry_agents import AgentServiceTransport, agent_service_enabled
from backend.agents.intel import MatchIntel
from backend.agents.llm import FoundryTransport, ResilientLLM, Transport
from backend.agents.safety import default_safety
from backend.app.store import MatchStore


def default_transport() -> Transport:
    """Direct model calls, or the registered Foundry agents when FOUNDRY_AGENT_SERVICE=true."""
    direct = FoundryTransport()
    return AgentServiceTransport(direct) if agent_service_enabled() else direct


async def build_context(
    store: MatchStore, match_id: str, transport: Transport | None = None
) -> MatchContext:
    """Load a match and wire the model client, cache and content gate around it."""
    loaded = await store.get(match_id)
    return MatchContext(
        intel=MatchIntel(loaded),
        names=store.names,
        llm=ResilientLLM(transport or default_transport()),
        cache=default_cache(),
        safety=default_safety(),
        fast_model=os.environ.get("FOUNDRY_DEPLOYMENT_FAST", "chat-fast"),
        strong_model=os.environ.get("FOUNDRY_DEPLOYMENT_STRONG", "chat-strong"),
    )
