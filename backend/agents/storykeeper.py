"""Story Keeper: the running storylines of a match.

Rule-based on purpose. Storylines come from state the engine already computed (score, possession,
pressure, discipline), so they carry no invented numbers; the text deliberately has no digits.
The Narrator can call back to them and the Recap Editor reads them.
"""

from __future__ import annotations

from pydantic import BaseModel

from backend.agents.context import MatchContext
from backend.agents.intel import MatchIntel

DOMINANT_POSSESSION = 62.0
HIGH_PRESSURE = 70.0
WINDOW_S = 600.0


class Storyline(BaseModel):
    key: str
    team: str | None
    text: str


def storylines_at(intel: MatchIntel, names: dict[str, str], t_match: float) -> list[Storyline]:
    """The storylines active at `t_match`, most important first."""
    s = intel.get_state(t_match)
    home, away = intel.teams
    out: list[Storyline] = []
    score = s["score"]
    gap = score[home] - score[away]
    if t_match > 120:
        if gap == 0 and score[home] > 0:
            out.append(
                Storyline(key="level", team=None, text="The sides are level and nothing is settled")
            )
        elif gap != 0:
            lead, trail = (home, away) if gap > 0 else (away, home)
            word = "a goal" if abs(gap) == 1 else "a clear margin"
            out.append(
                Storyline(
                    key="lead",
                    team=lead,
                    text=f"{names[lead]} lead and {names[trail]} are chasing, {word} between them",
                )
            )
    for team in (home, away):
        poss = s["possession_5min"][team]
        other = away if team == home else home
        if poss >= DOMINANT_POSSESSION:
            out.append(
                Storyline(
                    key="dominant",
                    team=team,
                    text=(
                        f"{names[team]} have had most of the ball lately "
                        f"and {names[other]} cannot get out"
                    ),
                )
            )
        if s["pressure"][team] >= HIGH_PRESSURE:
            out.append(
                Storyline(
                    key="pressing",
                    team=team,
                    text=f"{names[team]} are pressing high and forcing mistakes",
                )
            )
        stats = s["team_stats"][team]
        if stats["reds"]:
            out.append(
                Storyline(key="ten_men", team=team, text=f"{names[team]} are down to ten men")
            )
        elif stats["yellows"] >= 2:
            out.append(
                Storyline(
                    key="bookings",
                    team=team,
                    text=f"{names[team]} are collecting bookings and the referee is watching",
                )
            )
    if s["control_chaos"]["label"] == "chaotic":
        out.append(
            Storyline(key="chaos", team=None, text="It has turned scrappy and nobody has control")
        )
    return out


def update(ctx: MatchContext, t_match: float) -> list[Storyline]:
    """Refresh the shared storylines. Call every few match minutes and after big moments."""
    names = {c: ctx.team_name(c) for c in ctx.intel.teams}
    found = storylines_at(ctx.intel, names, t_match)
    ctx.storylines = [s.text for s in found]
    return found
