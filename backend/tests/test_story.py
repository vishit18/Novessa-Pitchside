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
