"""Runs the newsroom for matches in the background and hands finished text to the sockets.

The gateway never waits for a model. The instant overlay goes out first; this runtime attaches the
agents' text later as an `op: "update"` overlay with the same `moment_id` (docs/05).
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

from backend.agents.cache import AgentCache, default_cache
from backend.agents.context import MatchContext
from backend.agents.intel import MatchIntel
from backend.agents.llm import FoundryTransport, ResilientLLM, Transport
from backend.agents.models import Aired
from backend.agents.safety import default_safety
from backend.agents.workflow import run_batch
from backend.app.overlay import ALL_PERSONAS, Persona
from backend.app.store import MatchStore

log = logging.getLogger("pitchside.agents")
BATCH_SIZE = 5
MIN_SIGNIFICANCE = 50.0
PERSONA_FALLBACK: dict[Persona, list[Persona]] = {
    "analyst": ["analyst", "casual"],
    "casual": ["casual", "analyst"],
    "kids": ["kids", "casual", "analyst"],
    "accessibility": ["accessibility", "casual", "analyst"],
}


def agents_enabled() -> bool:
    """On when a model endpoint is configured, unless AGENTS=off."""
    return os.environ.get("AGENTS", "on") != "off" and bool(
        os.environ.get("FOUNDRY_OPENAI_ENDPOINT")
    )


class AgentRuntime:
    """One shared model client (so the chaos switch and health are global) and a task per match."""

    def __init__(
        self,
        store: MatchStore,
        transport: Transport | None = None,
        enabled: bool | None = None,
        cache: AgentCache | None = None,
    ) -> None:
        self.store = store
        self.enabled = agents_enabled() if enabled is None else enabled
        self.llm = ResilientLLM(transport or FoundryTransport()) if self.enabled else None
        self.cache = cache or default_cache()
        self.safety = default_safety()
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._results: dict[str, dict[str, Aired]] = {}
        self._changed: dict[str, asyncio.Condition] = {}
        self.progress: dict[str, dict[str, Any]] = {}

    def start(self, match_id: str) -> None:
        """Begin processing a match once. Safe to call on every connection."""
        if not self.enabled or match_id in self._tasks:
            return
        self._results[match_id] = {}
        self._changed[match_id] = asyncio.Condition()
        self._tasks[match_id] = asyncio.create_task(self._run(match_id))

    async def _context(self, match_id: str) -> MatchContext:
        assert self.llm is not None
        loaded = await self.store.get(match_id)
        return MatchContext(
            intel=MatchIntel(loaded),
            names=self.store.names,
            llm=self.llm,
            cache=self.cache,
            safety=self.safety,
            fast_model=os.environ.get("FOUNDRY_DEPLOYMENT_FAST", "chat-fast"),
            strong_model=os.environ.get("FOUNDRY_DEPLOYMENT_STRONG", "chat-strong"),
        )

    async def _run(self, match_id: str) -> None:
        started = time.perf_counter()
        info = self.progress.setdefault(match_id, {"batches": 0, "done": 0, "total": 0})
        try:
            ctx = await self._context(match_id)
            moments = ctx.intel.list_moments(min_significance=MIN_SIGNIFICANCE)
            info["total"] = len(moments)
            for i in range(0, len(moments), BATCH_SIZE):
                batch = moments[i : i + BATCH_SIZE]
                out = await run_batch(ctx, [m.moment_id for m in batch])
                async with self._changed[match_id]:
                    for a in out:
                        self._results[match_id][a.moment_id] = a
                    self._changed[match_id].notify_all()
                info["batches"] += 1
                info["done"] += len(batch)
        except Exception:
            log.exception("agent run for %s stopped", match_id)
            info["error"] = True
        finally:
            info["seconds"] = round(time.perf_counter() - started, 1)
            info["finished"] = True

    def results(self, match_id: str) -> dict[str, Aired]:
        return self._results.get(match_id, {})

    async def wait_for(self, match_id: str, moment_id: str, timeout: float) -> Aired | None:
        """The finished text for a moment, waiting up to `timeout` seconds for it."""
        if not self.enabled or match_id not in self._changed:
            return None
        cond = self._changed[match_id]

        async def ready() -> Aired:
            async with cond:
                await cond.wait_for(lambda: moment_id in self._results[match_id])
            return self._results[match_id][moment_id]

        got = self._results[match_id].get(moment_id)
        if got is None:
            try:
                got = await asyncio.wait_for(ready(), timeout)
            except TimeoutError:
                return None
        return got if got.status != "dropped" else None

    def health(self) -> dict[str, Any]:
        agents = {}
        if self.llm is not None:
            for name, h in self.llm.health.items():
                lat = h.latencies_ms
                agents[name] = {
                    "calls": h.calls,
                    "failures": h.failures,
                    "fallbacks": h.fallbacks,
                    "last_latency_ms": round(h.last_latency_ms),
                    "avg_latency_ms": round(sum(lat) / len(lat)) if lat else 0,
                    "breaker_open": h.breaker_open,
                    "killed": h.killed,
                }
        return {"enabled": self.enabled, "agents": agents, "matches": self.progress}

    def kill(self, agent: str, seconds: float) -> None:
        """Chaos switch."""
        if self.llm is not None:
            self.llm.kill(agent, seconds)

    def update_overlay(
        self, base: dict[str, Any], aired: Aired, persona: Persona
    ) -> dict[str, Any]:
        """Build the `op: "update"` overlay that adds agent text to an earlier instant overlay."""
        variant = None
        for p in PERSONA_FALLBACK.get(persona, ALL_PERSONAS):
            variant = aired.variants.get(p)
            if variant:
                break
        if variant is None:
            return {}
        verified = aired.status == "verified"
        evidence = (
            [{"metric": c.metric, "value": c.value, "window": None} for c in aired.analysis.claims]
            if aired.analysis
            else base["provenance"]["evidence"]
        )
        out = dict(base)
        out["op"] = "update"
        out["msg_id"] = f"{base['msg_id']}-text"
        out["payload"] = {
            "headline": variant.headline,
            "body": variant.body,
            "commentary": variant.commentary,
            "agent_status": aired.status,
        }
        out["provenance"] = {
            "source": "agent:analyst" if verified else "state_engine",
            "verified": True,
            "evidence": evidence,
        }
        return out
