import itertools
from pathlib import Path

from engine.io import read_match_file, write_match
from engine.league import generate_league
from engine.schema import EventType, League
from engine.sim import Match, simulate_match


def test_same_seed_same_match(league: League, match: Match) -> None:
    again = simulate_match(league, "ASH", "KES", seed=7, match_id="t01")
    assert [e.model_dump() for e in again.events] == [e.model_dump() for e in match.events]
    assert again.score == match.score


def test_different_seed_differs(league: League, match: Match) -> None:
    other = simulate_match(league, "ASH", "KES", seed=8, match_id="t01")
    assert [e.t_match for e in other.events] != [e.t_match for e in match.events]


def test_events_are_ordered_and_numbered(match: Match) -> None:
    seqs = [e.seq for e in match.events]
    assert seqs == list(range(1, len(seqs) + 1))
    times = [e.t_match for e in match.events]
    assert all(b >= a - 1e-6 for a, b in itertools.pairwise(times))
    assert len({e.event_id for e in match.events}) == len(match.events)


def test_structure(match: Match) -> None:
    types = [e.type for e in match.events]
    assert types.count(EventType.PERIOD_START) == 2
    assert types.count(EventType.PERIOD_END) == 2
    assert types[0] == EventType.PERIOD_START
    assert types[-1] == EventType.PERIOD_END
    assert 5400 < match.events[-1].t_match < 6200
    assert {e.period for e in match.events} == {1, 2}


def test_goals_match_score(match: Match) -> None:
    goals = [e for e in match.events if e.type == EventType.GOAL]
    home = sum(1 for g in goals if g.team == "ASH")
    away = sum(1 for g in goals if g.team == "KES")
    assert (home, away) == match.score
    shot_goals = [e for e in match.events if e.type == EventType.SHOT and e.outcome == "goal"]
    assert len(shot_goals) == len(goals)


def test_pass_events_carry_difficulty_and_speed(match: Match) -> None:
    passes = [e for e in match.events if e.type == EventType.PASS]
    assert len(passes) > 600
    for p in passes:
        assert p.pass_difficulty is not None and 0 <= p.pass_difficulty <= 100
        assert p.ball_speed_kmh is not None and 20 <= p.ball_speed_kmh <= 100
        assert p.receiver_id and p.player_id and p.team
        assert p.player_id.startswith(p.team)
    done = sum(1 for p in passes if p.outcome == "complete") / len(passes)
    assert 0.65 < done < 0.92


def test_shots_have_xg_and_speed(match: Match) -> None:
    shots = [e for e in match.events if e.type == EventType.SHOT]
    assert 10 <= len(shots) <= 60
    for s in shots:
        assert s.xg is not None and 0 < s.xg < 1
        assert s.ball_speed_kmh is not None and 45 <= s.ball_speed_kmh <= 125


def test_coordinates_on_pitch(match: Match) -> None:
    for e in match.events:
        for v, hi in ((e.x, 105), (e.end_x, 105), (e.y, 68), (e.end_y, 68)):
            assert v is None or -0.01 <= v <= hi + 0.01


def test_clock_format(match: Match) -> None:
    assert match.events[0].clock == "00:00"
    late = [e for e in match.events if "+" in e.clock]
    assert late, "expected stoppage time"
    assert any(e.clock.startswith("45+") for e in late)
    assert any(e.clock.startswith("90+") for e in late)


def test_lineups_and_script(match: Match) -> None:
    for sheet in (match.meta.home, match.meta.away):
        assert len(sheet.starters) == 11
        assert sum(1 for s in sheet.starters if s.group == "GK") == 1
        assert sheet.captain in {s.player_id for s in sheet.starters}
    assert 2 <= len(match.script) <= 3
    assert any(e.type == EventType.SUBSTITUTION for e in match.events)


def test_tracking_frames(match: Match) -> None:
    f = match.tracking.frame_at(1000.0)
    assert len(f.players) == 22
    assert len({p.id for p in f.players}) == 22
    assert 0 <= f.ball.x <= 105 and 0 <= f.ball.y <= 68
    frames = list(match.tracking.iter_frames(10, start=500.0))[:50]
    assert all(b.t_match >= a.t_match for a, b in itertools.pairwise(frames))


def test_distance_is_plausible(match: Match) -> None:
    outfield = [
        d
        for pid, d in match.tracking.player_distances_km().items()
        if match.players[pid].position != "GK"
    ]
    assert 6.0 < sum(outfield) / len(outfield) < 13.0


def test_roundtrip_on_disk(match: Match, tmp_path: Path) -> None:
    path = write_match(match, tmp_path)
    meta, events = read_match_file(path)
    assert meta == match.meta
    assert events == match.events
    assert (tmp_path / "t01.script.json").exists()


def test_other_pairing_runs() -> None:
    m = simulate_match(generate_league(), "HAR", "SAL", seed=3, match_id="t02")
    assert m.events
