"""Match store: loads saved matches, regenerates tracking from the seed, caches timelines."""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path

from backend.app.timeline import NameBook, Timeline, build_timeline
from engine.io import read_match_file
from engine.league import load_league
from engine.schema import League, MatchEvent, MatchMeta
from engine.sim import simulate_match
from engine.tracking import TrackingData

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


class UnknownMatchError(KeyError):
    """No saved match with that id."""


class StaleDataError(RuntimeError):
    """The saved events no longer match what the engine generates for that seed."""


@dataclass
class LoadedMatch:
    meta: MatchMeta
    events: list[MatchEvent]
    tracking: TrackingData
    timeline: Timeline


class MatchStore:
    """Loads each match once, on first request, and keeps it in memory."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or Path(os.environ.get("DATA_DIR", DEFAULT_DATA_DIR))
        self.league: League = load_league(self.data_dir / "league")
        self.names = NameBook(self.league)
        self._cache: dict[str, LoadedMatch] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def match_ids(self) -> list[str]:
        return sorted(p.stem for p in (self.data_dir / "matches").glob("*.jsonl"))

    def read_meta(self, match_id: str) -> MatchMeta:
        path = self.data_dir / "matches" / f"{match_id}.jsonl"
        if not path.exists():
            raise UnknownMatchError(match_id)
        with path.open(encoding="utf-8") as fh:
            first = json.loads(fh.readline())
        first.pop("record", None)
        return MatchMeta.model_validate(first)

    def _load(self, match_id: str) -> LoadedMatch:
        path = self.data_dir / "matches" / f"{match_id}.jsonl"
        if not path.exists():
            raise UnknownMatchError(match_id)
        meta, events = read_match_file(path)
        sim = simulate_match(
            self.league, meta.home.code, meta.away.code, meta.seed, meta.match_id, meta.matchday
        )
        if len(sim.events) != len(events) or sim.events[-1].t_match != events[-1].t_match:
            raise StaleDataError(
                f"{match_id}: saved events differ from the engine; run `make seed`"
            )
        timeline = build_timeline(meta, events, sim.tracking, self.league)
        return LoadedMatch(meta, events, sim.tracking, timeline)

    async def get(self, match_id: str) -> LoadedMatch:
        """The loaded match, building it in a worker thread the first time."""
        if match_id in self._cache:
            return self._cache[match_id]
        lock = self._locks.setdefault(match_id, asyncio.Lock())
        async with lock:
            if match_id not in self._cache:
                self._cache[match_id] = await asyncio.to_thread(self._load, match_id)
        return self._cache[match_id]
