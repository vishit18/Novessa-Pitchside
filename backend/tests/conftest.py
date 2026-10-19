from __future__ import annotations

from dataclasses import dataclass

import pytest

from backend.state.engine import Output, StateEngine
from engine.clock import merge_by_time
from engine.league import generate_league
from engine.schema import MatchEvent, TrackingFrame
from engine.sim import Match, simulate_match


@dataclass
class StateRun:
    match: Match
    engine: StateEngine
    outputs: list[Output]


def run_state(match: Match) -> StateRun:
    """Feed a whole match through a fresh engine (frames at 2 Hz to keep tests quick)."""
    engine = StateEngine(match.meta)
    outputs: list[Output] = []
    for item in merge_by_time(match.events, match.tracking.iter_frames(2.0)):
        if isinstance(item, MatchEvent):
            outputs.extend(engine.ingest_event(item))
        elif isinstance(item, TrackingFrame):
            outputs.extend(engine.ingest_frame(item))
    return StateRun(match, engine, outputs)


@pytest.fixture(scope="session")
def state_run() -> StateRun:
    match = simulate_match(generate_league(), "ASH", "KES", seed=7, match_id="s01")
    return run_state(match)
