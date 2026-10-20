"""Fouls, cards, red cards, penalties, manager cards and corners (docs/03 "Discipline")."""

from __future__ import annotations

import pytest

from engine.league import generate_league, is_denied
from engine.schema import EventType, League, MatchEvent
from engine.sim import Match, simulate_match


@pytest.fixture(scope="module")
def drama(league: League) -> Match:
    """ASH v KES, seed 195: a penalty, a second yellow, a red and a manager booking."""
    return simulate_match(league, "ASH", "KES", seed=195, match_id="t195")


@pytest.fixture(scope="module")
def straight_red(league: League) -> Match:
    """ASH v KES, seed 5: contains a straight red card."""
    return simulate_match(league, "ASH", "KES", seed=5, match_id="t5")


def of_type(m: Match, t: EventType) -> list[MatchEvent]:
    return [e for e in m.events if e.type == t]


def test_managers_are_invented_and_unique(league: League) -> None:
    names = [c.manager for c in league.clubs]
    assert all(names) and len(set(names)) == 8
    assert not [n for n in names if is_denied(n)]
    players = {p.name for c in league.clubs for p in c.players}
    assert not set(names) & players


def test_adding_managers_did_not_change_the_squads() -> None:
    a = generate_league(2026)
    assert [p.name for p in a.clubs[0].players][:3] == [
        p.name for p in generate_league(2026).clubs[0].players
    ][:3]


def test_every_foul_is_followed_by_a_free_kick_or_penalty(drama: Match) -> None:
    ev = drama.events
    for i, e in enumerate(ev):
        if e.type != EventType.FOUL:
            continue
        nxt = next(
            n for n in ev[i + 1 : i + 8] if n.type == EventType.FREE_KICK and n.team != e.team
        )
        assert nxt.t_match >= e.t_match


def test_second_yellow_then_red_for_the_same_player(drama: Match) -> None:
    cards = [e for e in drama.events if e.type == EventType.CARD and "manager" not in e.tags]
    reds = [c for c in cards if c.outcome == "red"]
    assert reds
    r = reds[0]
    assert "second_yellow" in r.tags
    earlier = [c for c in cards if c.player_id == r.player_id and c.outcome == "yellow"]
    assert len(earlier) == 2  # the first yellow, then the second one issued with the red
    assert earlier[-1].t_match == r.t_match and "second_yellow" in earlier[-1].tags


def test_red_card_means_ten_men_and_he_is_gone(drama: Match) -> None:
    red = next(e for e in drama.events if e.type == EventType.CARD and e.outcome == "red")
    for dt in (0.0, 60.0, 600.0):
        f = drama.tracking.frame_at(red.t_match + dt + 5)
        team_n = sum(1 for p in f.players if p.id.startswith(red.team or "?"))
        other_n = sum(1 for p in f.players if not p.id.startswith(red.team or "?"))
        assert (team_n, other_n) == (10, 11), dt
        assert red.player_id not in {p.id for p in f.players}
    later = [e for e in drama.events if e.t_match > red.t_match and e.player_id == red.player_id]
    assert not later, "a sent-off player took part in later events"


def test_sent_off_player_does_not_run_in_the_distance_totals(drama: Match) -> None:
    red = next(e for e in drama.events if e.type == EventType.CARD and e.outcome == "red")
    totals = drama.tracking.player_distances_km()
    assert red.player_id in totals and totals[red.player_id] < 9.0


def test_straight_red_is_a_single_red_card(straight_red: Match) -> None:
    reds = [e for e in straight_red.events if e.type == EventType.CARD and e.outcome == "red"]
    straight = [r for r in reds if "straight_red" in r.tags]
    assert straight
    s = straight[0]
    yellows_same_time = [
        e
        for e in straight_red.events
        if e.type == EventType.CARD and e.outcome == "yellow" and e.t_match == s.t_match
    ]
    assert not yellows_same_time


def test_penalty_is_a_tagged_free_kick_then_a_tagged_shot(drama: Match) -> None:
    ev = drama.events
    i = next(k for k, e in enumerate(ev) if e.type == EventType.FREE_KICK and "penalty" in e.tags)
    kick = ev[i]
    shot = next(e for e in ev[i + 1 : i + 4] if e.type == EventType.SHOT)
    assert "penalty" in shot.tags and shot.xg == pytest.approx(0.76)
    assert shot.team == kick.team and shot.player_id == kick.player_id
    assert shot.outcome in ("goal", "saved", "off_target")
    # taken from the penalty spot, 11 m out
    assert kick.x is not None and min(kick.x, 105 - kick.x) == pytest.approx(11.0, abs=0.1)
    assert kick.y == pytest.approx(34.0)


def test_manager_card_has_no_player_and_a_team(drama: Match) -> None:
    mgr = [e for e in drama.events if e.type == EventType.CARD and "manager" in e.tags]
    assert mgr
    for c in mgr:
        assert c.player_id is None and c.team in ("ASH", "KES")
        assert c.outcome in ("yellow", "red")
    assert len({c.team for c in mgr}) == len(mgr)  # one card per manager


def test_corners_are_taken_from_the_corner_flag_then_delivered(drama: Match) -> None:
    ev = drama.events
    corners = [i for i, e in enumerate(ev) if e.type == EventType.CORNER]
    assert corners
    for i in corners:
        c = ev[i]
        assert c.x is not None and c.y is not None
        assert min(c.x, 105 - c.x) < 0.5 and min(c.y, 68 - c.y) < 0.5
        delivery = next(e for e in ev[i + 1 : i + 6] if e.type == EventType.PASS)
        assert "corner" in delivery.tags and delivery.team == c.team


def test_no_event_uses_a_sent_off_player_as_receiver(drama: Match) -> None:
    red = next(e for e in drama.events if e.type == EventType.CARD and e.outcome == "red")
    bad = [e for e in drama.events if e.t_match > red.t_match and e.receiver_id == red.player_id]
    assert not bad


def test_over_many_matches_the_rates_are_realistic() -> None:
    """A small batch. The 200-match report (scripts/calibrate.py) is the proper check."""
    lg = generate_league()
    fouls = yellows = corners = 0
    n = 4
    for seed in range(40, 40 + n):
        m = simulate_match(lg, "MIL", "THO", seed=seed, match_id=f"b{seed}")
        fouls += len(of_type(m, EventType.FOUL))
        yellows += sum(1 for e in of_type(m, EventType.CARD) if e.outcome == "yellow")
        corners += len(of_type(m, EventType.CORNER))
    assert 10 <= fouls / n <= 32
    assert 1 <= yellows / n <= 8
    assert 4 <= corners / n <= 18
