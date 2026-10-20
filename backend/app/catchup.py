"""Spoiler-safe catch-up: what has happened in a match up to one moment, and nothing after it.

Everything here is computed from the state engine's moments and snapshots, so it costs no model
calls and cannot mention anything past `t_match`. A viewer who joins at 60' asks for this and
gets the score, who has had the ball, and the handful of moments that mattered so far.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

from backend.app.store import LoadedMatch
from backend.app.timeline import HEADLINES, NameBook
from backend.state.models import Moment

# Moments below this significance are not worth a viewer's catch-up time.
MIN_SIGNIFICANCE = 65.0
MAX_MOMENTS = 6
# Kinds that read as a story beat. Pressure and rhythm shifts are left for the live view.
STORY_KINDS = {"goal", "card", "penalty", "big_chance", "standout_action", "momentum_swing"}


class CatchUpMoment(BaseModel):
    moment_id: str
    clock: str
    kind: str
    headline: str
    body: str
    team: str | None = None


class CatchUp(BaseModel):
    match_id: str
    t_match: float
    clock: str
    period: int
    score: dict[str, int]
    summary: str
    moments: list[CatchUpMoment]
    note: str


CODE_PATTERN = re.compile(r"\b[A-Z]{3}\b")


def _clubs_by_name(text: str, names: NameBook) -> str:
    """Swap a bare club code such as ASH for the club name."""
    return CODE_PATTERN.sub(lambda m: names.clubs.get(m.group(0), m.group(0)), text)


def _headline(m: Moment) -> str:
    if m.kind == "card" and m.card:
        return (
            "Manager sent off"
            if m.staff and m.card == "red"
            else (
                "Manager booked" if m.staff else ("Red card" if m.card == "red" else "Yellow card")
            )
        )
    return HEADLINES.get(m.kind, (m.kind.replace("_", " ").capitalize(), ""))[0]


def _summary(state: dict[str, Any], home: str, away: str, names: NameBook) -> str:
    """Two plain sentences from the numbers: the score and who has had the ball."""
    h, a = state["score"].get(home, 0), state["score"].get(away, 0)
    hn, an = names.clubs.get(home, home), names.clubs.get(away, away)
    if h == a:
        score = f"{hn} and {an} are level at {h}-{a}."
    elif h > a:
        score = f"{hn} lead {an} {h}-{a}."
    else:
        score = f"{an} lead {hn} {a}-{h}."
    poss = state["possession_match"]
    top = home if poss.get(home, 0) >= poss.get(away, 0) else away
    share = round(poss.get(top, 0))
    stats = state.get("team_stats", {})
    hs, as_ = stats.get(home, {}).get("shots", 0), stats.get(away, {}).get("shots", 0)
    ball = (
        f"{names.clubs.get(top, top)} have had {share}% of the ball. Shots: {hn} {hs}, {an} {as_}."
    )
    return f"{score} {ball}"


def build_catchup(match_id: str, loaded: LoadedMatch, names: NameBook, t_match: float) -> CatchUp:
    """Catch-up for a viewer who is at `t_match` seconds. Only moments at or before it appear."""
    state = loaded.timeline.state_at(t_match)
    if state is None:
        raise ValueError(f"no state at {t_match}")
    home, away = loaded.meta.home.code, loaded.meta.away.code
    seen = [
        m
        for m in loaded.timeline.moments
        if m.t_match <= t_match and m.kind in STORY_KINDS and m.significance >= MIN_SIGNIFICANCE
    ]
    # Keep the most significant, then put them back in match order.
    top = sorted(seen, key=lambda m: m.significance, reverse=True)[:MAX_MOMENTS]
    moments = [
        CatchUpMoment(
            moment_id=m.moment_id,
            clock=m.clock,
            kind=m.kind,
            headline=_headline(m),
            body=_clubs_by_name(names.humanise(m.summary), names),
            team=m.team,
        )
        for m in sorted(top, key=lambda m: m.t_match)
    ]
    return CatchUp(
        match_id=match_id,
        t_match=state["t_match"],
        clock=state["clock"],
        period=state["period"],
        score=state["score"],
        summary=_summary(state, home, away, names),
        moments=moments,
        note=f"This covers the match up to {state['clock']} and nothing after it.",
    )
