"""Story check: right club, right time. The Verifier proves numbers; this proves who and when."""

from __future__ import annotations

from backend.agents.intel import MatchIntel
from backend.agents.story import (
    clock_minute,
    goal_time_problems,
    story_problems,
    team_problems,
    time_problems,
)
from backend.app.timeline import NameBook
from backend.tests.test_agents import intel as intel
from backend.tests.test_agents import names as names


def test_clock_minutes() -> None:
    assert clock_minute("26:47") == 26
    assert clock_minute("45+3:07") == 48
    assert clock_minute("90+2:02") == 92


def test_headline_must_not_credit_the_other_club(intel: MatchIntel, names: NameBook) -> None:
    m = next(m for m in intel.loaded.timeline.moments if m.kind in ("goal", "penalty") and m.team)
    assert m.team is not None
    own = names.clubs[m.team]
    other = names.clubs[next(t for t in intel.teams if t != m.team)]
    short_other = other.replace(" FC", "")
    assert team_problems(names, m, intel.teams, f"{short_other} has a clear chance")
    assert not team_problems(names, m, intel.teams, f"{own} strike first")
    assert not team_problems(names, m, intel.teams, f"{own} punish {other}")
    assert not team_problems(names, m, intel.teams, "What a finish")


def test_time_phrases_must_fit_the_clock() -> None:
    assert time_problems("He scored just before half-time", "26:47")
    assert not time_problems("He scored just before half-time", "44:10")
    assert time_problems("striking first just before half\N{NON-BREAKING HYPHEN}time", "26:47")
    assert time_problems("A goal in stoppage time", "88:00")
    assert not time_problems("A goal in stoppage time", "90+2:02")
    assert time_problems("An early goal settles nerves", "61:00")
    assert not time_problems("A late winner", "84:01")


def test_recap_goal_times(names: NameBook) -> None:
    goals = [{"clock": "26:47", "scorer": "Tobias Wragg", "team": "Ashford Rovers"}]
    bad = "Wragg opened the scoring just before half-time. Kestrel pressed after."
    good = "Wragg opened the scoring midway through the first half."
    assert goal_time_problems(bad, goals)
    assert not goal_time_problems(good, goals)


def test_story_combines_both(intel: MatchIntel, names: NameBook) -> None:
    m = next(m for m in intel.loaded.timeline.moments if m.kind == "goal" and m.team)
    other = names.clubs[next(t for t in intel.teams if t != m.team)]
    problems = story_problems(names, m, intel.teams, f"{other} hit back", "a late winner")
    assert any("credits" in p for p in problems)


def test_a_running_total_is_not_one_shots_number() -> None:
    from backend.agents.models import AnalystOutput, Claim
    from backend.agents.verifier import scope_problems

    total = Claim(text="his xG so far", metric="xg", value=0.002, player_id="ASH-17", t_to=1593)
    bad = AnalystOutput(headline="Penalty", why="Wragg's penalty xG is 0.002.", claims=[total])
    assert scope_problems(bad)
    fine = AnalystOutput(
        headline="Penalty won",
        why="Ashford won a penalty, and Wragg has 0.002 xG so far.",
        claims=[total],
    )
    assert not scope_problems(fine)
    one = Claim(text="this penalty", metric="shot_xg", value=0.76, player_id="ASH-17", t_to=1607)
    said = "His penalty was worth 0.76 xG."
    shot = AnalystOutput(headline="Wragg scores", why=said, claims=[one])
    assert not scope_problems(shot)


def test_a_booking_does_not_change_a_teams_tactics(intel: MatchIntel, names: NameBook) -> None:
    card = next(m for m in intel.loaded.timeline.moments if m.kind == "card" and not m.staff)
    said = "The yellow card triggers a shift to defensive containment"
    assert story_problems(names, card, intel.teams, "Yellow card", said)
    assert not story_problems(names, card, intel.teams, "Yellow card", "He must be careful now")


def test_shot_xg_is_the_latest_shot(intel: MatchIntel) -> None:
    from engine.schema import EventType

    shot = next(e for e in intel.events if e.type == EventType.SHOT and e.player_id and e.xg)
    assert shot.player_id is not None
    got = intel.measure("shot_xg", player_id=shot.player_id, t_to=shot.t_match)
    assert got == round(shot.xg or 0.0, 3)


def test_a_two_goal_scorer_can_be_early_and_late() -> None:
    goals = [
        {"scorer": "Hugo Brocard", "clock": "32:52"},
        {"scorer": "Hugo Brocard", "clock": "89:26"},
    ]
    assert not goal_time_problems("Brocard scored in the first half and again late on.", goals)
    assert goal_time_problems("Brocard scored in stoppage time.", goals)


def test_wording_checks(intel: MatchIntel, names: NameBook) -> None:
    pen = next(m for m in intel.loaded.timeline.moments if m.kind == "penalty")
    fouler = names.player(pen.summary.split()[0])
    said = f"Ashford got a penalty because {fouler.split()[0]} was fouled."
    assert any(
        "committed the foul" in p for p in story_problems(names, pen, intel.teams, "Pen", said)
    )
    assert story_problems(names, pen, intel.teams, "Pen", "The pressure_index hit 100.")
    shift = next(m for m in intel.loaded.timeline.moments if m.kind == "pressure_shift" and m.team)
    other = names.clubs[next(t for t in intel.teams if t != shift.team)]
    own = names.clubs[shift.team or ""]
    bad = f"{own} press harder while {other}'s pressure index increased."
    assert story_problems(names, shift, intel.teams, "Pressing", bad)
    fine = f"{own}'s pressure is rising, disrupting {other}'s rhythm."
    assert not story_problems(names, shift, intel.teams, "Pressing", fine)
