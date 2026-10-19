from __future__ import annotations

from backend.state.config import load_thresholds
from backend.state.models import Moment, Trigger
from backend.tests.conftest import StateRun, run_state
from engine.schema import EventType

NO_COOLDOWN = {"goal", "card", "big_chance", "standout_action"}


def moments(run: StateRun) -> list[Moment]:
    return [o for o in run.outputs if isinstance(o, Moment)]


def triggers(run: StateRun) -> list[Trigger]:
    return [o for o in run.outputs if isinstance(o, Trigger)]


def test_thresholds_load() -> None:
    cfg = load_thresholds()
    assert cfg.triggers.sprint_kmh > cfg.triggers.sprint_reset_kmh
    assert cfg.moments.cooldown_s > 0


def test_score_matches_simulator(state_run: StateRun) -> None:
    home, away = state_run.match.meta.home.code, state_run.match.meta.away.code
    assert (state_run.engine.score[home], state_run.engine.score[away]) == state_run.match.score


def test_snapshot_ranges(state_run: StateRun) -> None:
    s = state_run.engine.snapshot()
    assert -100 <= s.momentum <= 100
    assert 0 <= s.control_chaos.value <= 100
    assert abs(sum(s.possession_match.values()) - 100) < 0.5
    assert abs(sum(s.possession_5min.values()) - 100) < 0.5
    assert all(0 <= v <= 100 for v in s.pressure.values())
    assert 30 < max(s.possession_match.values()) < 70


def test_goals_become_top_moments(state_run: StateRun) -> None:
    goal_moments = [m for m in moments(state_run) if m.kind == "goal"]
    assert len(goal_moments) == sum(state_run.match.score)
    assert all(m.significance == 100 and m.player_ids for m in goal_moments)


def test_moment_ids_unique_and_snapshotted(state_run: StateRun) -> None:
    ms = moments(state_run)
    assert ms
    assert len({m.moment_id for m in ms}) == len(ms)
    assert all(m.snapshot.t_match == m.t_match for m in ms)
    assert all(0 <= m.significance <= 100 for m in ms)
    times = [m.t_match for m in ms]
    assert times == sorted(times)


def test_cooldown_between_repeated_moments(state_run: StateRun) -> None:
    cooldown = state_run.engine.cfg.moments.cooldown_s
    last: dict[tuple[str, str | None], float] = {}
    for m in moments(state_run):
        if m.kind in NO_COOLDOWN:
            continue
        key = (m.kind, m.team)
        if key in last:
            assert m.t_match - last[key] >= cooldown - 1e-6
        last[key] = m.t_match


def test_triggers_respect_thresholds(state_run: StateRun) -> None:
    cfg = state_run.engine.cfg.triggers
    ts = triggers(state_run)
    bursts = [t for t in ts if t.kind == "speed_burst"]
    assert bursts
    assert all(float(t.payload["speed_kmh"]) >= cfg.sprint_kmh for t in bursts)
    assert all(
        float(t.payload["difficulty"]) >= cfg.pass_difficulty
        for t in ts
        if t.kind == "pass_difficulty"
    )
    assert all(
        float(t.payload["speed_kmh"]) >= cfg.shot_speed_kmh for t in ts if t.kind == "shot_speed"
    )
    km = [float(t.payload["km"]) for t in ts if t.kind == "distance_milestone"]
    assert km and all(k % cfg.distance_step_km == 0 for k in km)


def test_player_stats_add_up(state_run: StateRun) -> None:
    passes = [e for e in state_run.match.events if e.type == EventType.PASS]
    total = sum(p.passes for p in state_run.engine.players.values())
    assert total == len(passes)
    done = sum(p.passes_complete for p in state_run.engine.players.values())
    assert done == sum(1 for e in passes if e.outcome == "complete")
    shots = [e for e in state_run.match.events if e.type == EventType.SHOT]
    assert sum(p.shots for p in state_run.engine.players.values()) == len(shots)
    for p in state_run.engine.players.values():
        if p.passes:
            assert p.pass_accuracy is not None and 0 <= p.pass_accuracy <= 1
            assert p.avg_difficulty is not None and 0 <= p.avg_difficulty <= 100
        assert (
            p.xa <= sum(q.xg for q in state_run.engine.players.values() if q.team == p.team) + 1e-9
        )


def test_distance_and_speed_from_frames(state_run: StateRun) -> None:
    outfield = [
        p
        for p in state_run.engine.players.values()
        if state_run.match.players[p.player_id].position != "GK"
    ]
    mean_km = sum(p.distance_km for p in outfield) / len(outfield)
    assert 6 < mean_km < 13
    assert all(p.top_speed_kmh < 45 for p in outfield)


def test_deterministic(state_run: StateRun) -> None:
    again = run_state(state_run.match)
    assert [o.model_dump() for o in again.outputs] == [o.model_dump() for o in state_run.outputs]
