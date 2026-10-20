"""Shared match context. Agents pass ids, not prompts; they read and write state here."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.agents.cache import AgentCache
from backend.agents.intel import MatchIntel
from backend.agents.llm import ResilientLLM
from backend.agents.models import Aired, ProducerItem
from backend.agents.safety import Safety
from backend.app.timeline import NameBook


@dataclass
class AirtimeEntry:
    moment_id: str
    slot: str
    start: float
    end: float


@dataclass
class MatchContext:
    """Everything the agents share for one match."""

    intel: MatchIntel
    names: NameBook
    llm: ResilientLLM
    cache: AgentCache
    safety: Safety
    fast_model: str = "chat-fast"
    strong_model: str = "chat-strong"
    decisions: dict[str, ProducerItem] = field(default_factory=dict)
    insights: dict[str, Aired] = field(default_factory=dict)
    airtime: list[AirtimeEntry] = field(default_factory=list)
    storylines: list[str] = field(default_factory=list)

    @property
    def seed(self) -> int:
        return self.intel.meta.seed

    @property
    def match_id(self) -> str:
        return self.intel.meta.match_id

    def team_name(self, code: str | None) -> str:
        return self.names.clubs.get(code or "", code or "")

    def on_screen(self, t: float, slot: str) -> list[AirtimeEntry]:
        """Entries still showing in `slot` at match time `t`."""
        return [a for a in self.airtime if a.slot == slot and a.start <= t < a.end]

    def log_airtime(self, item: ProducerItem, t: float) -> None:
        self.airtime.append(AirtimeEntry(item.moment_id, item.slot, t, t + item.duration_s))
