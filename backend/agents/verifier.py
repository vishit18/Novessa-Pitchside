"""Verifier: proves every claim before it airs.

It does not trust the Analyst's numbers. Each claim is re-measured from the match data through
`MatchIntel.measure`, and every number in the prose must trace back to a verified claim or to the
moment's own evidence. No model is involved, so the check cannot be talked round.
"""

from __future__ import annotations

import re

from backend.agents.intel import MatchIntel, UnknownMetricError
from backend.agents.models import AnalystOutput, Claim, ClaimCheck, Verdict
from backend.agents.story import story_problems
from backend.app.timeline import NameBook
from backend.state.models import Moment

ID_PATTERN = re.compile(r"\b[A-Z]{3}-\d{2}\b")
NUMBER = re.compile(r"\d+(?:\.\d+)?")
# Running totals: correct as numbers, wrong if the prose says they belong to one action.
TOTAL_METRICS = {"xg", "xg_total", "shots", "passes", "distance_km", "sprints"}
ONE_ACTION = re.compile(
    r"\b(penalty|spot[- ]kick|from the spot|(this|that|the|his|her|their) "
    r"(shot|chance|effort|strike|finish|attempt)|shot's|chance's)\b",
    re.I,
)
# How far before a number to look for the words that say what it is, never past its own clause.
SCOPE_LOOKBACK = 45
CLAUSE_BREAK = re.compile(r"[;:.,!?]|\b(?:and|but|while|after|whereas)\b", re.I)
ABS_TOL = 0.51
REL_TOL = 0.02


def close(a: float, b: float) -> bool:
    """Equal once rounding is allowed for: within half a unit or two percent."""
    return abs(a - b) <= max(ABS_TOL, REL_TOL * abs(b))


def numbers_in(text: str) -> list[float]:
    """Numbers written in digits, ignoring player ids like ASH-07."""
    return [float(n) for n in NUMBER.findall(ID_PATTERN.sub("", text))]


def _check_claim(intel: MatchIntel, i: int, claim: Claim) -> ClaimCheck:
    try:
        measured = intel.measure(
            claim.metric,
            team=claim.team,
            player_id=claim.player_id,
            t_from=claim.t_from,
            t_to=claim.t_to,
        )
    except (UnknownMetricError, ValueError, KeyError) as exc:
        return ClaimCheck(
            claim_index=i, status="rejected", claimed=claim.value, reason=f"cannot measure: {exc}"
        )
    if close(claim.value, measured):
        return ClaimCheck(claim_index=i, status="approved", claimed=claim.value, measured=measured)
    return ClaimCheck(
        claim_index=i,
        status="rejected",
        claimed=claim.value,
        measured=measured,
        reason=f"{claim.metric} is {measured:g}, not {claim.value:g}",
    )


def _spellings(value: float) -> set[str]:
    """How a number may be written in prose: 0.002, 0.00, 22, 22.0."""
    out = {f"{value:g}", f"{value:.2f}", f"{value:.1f}", f"{value:.3f}"}
    if float(value).is_integer():
        out.add(str(int(value)))
    return out


def scope_problems(analysis: AnalystOutput) -> list[str]:
    """A running total described as one action ("his penalty xG is 0.002").

    The number check cannot see this: the total is real, it is just not what the sentence says it
    is. Looks at the words just before each place a total's number is written.
    """
    out: list[str] = []
    prose = f"{analysis.headline} {analysis.why}"
    for c in analysis.claims:
        if c.metric not in TOTAL_METRICS:
            continue
        for text in (prose, c.text):
            for spelling in _spellings(c.value):
                for hit in re.finditer(rf"(?<![\d.]){re.escape(spelling)}(?!\d)", text):
                    before = text[max(0, hit.start() - SCOPE_LOOKBACK) : hit.start()]
                    before = CLAUSE_BREAK.split(before)[-1]
                    words = ONE_ACTION.search(before)
                    if words:
                        hint = "; use shot_xg for one shot" if c.metric.startswith("xg") else ""
                        out.append(
                            f'"{words.group(0)} ... {spelling}": {c.metric} {spelling} is a '
                            f"total so far, not one action's{hint}"
                        )
    return list(dict.fromkeys(out))


def allowed_numbers(moment: Moment, analysis: AnalystOutput) -> list[float]:
    allowed = [c.value for c in analysis.claims]
    allowed += [e.value for e in moment.evidence]
    allowed += [float(v) for v in moment.snapshot.score.values()]
    allowed += [float(n) for n in numbers_in(moment.clock)]
    allowed += numbers_in(moment.summary)
    allowed += [n for e in moment.evidence for n in numbers_in(e.window or "")]
    if any(c.metric.endswith("5min") for c in analysis.claims):
        allowed.append(5.0)
    for c in analysis.claims:
        if c.t_from is not None and c.t_to is not None:
            allowed.append(round((c.t_to - c.t_from) / 60.0))
        # A claim's own time window is true by construction (it was the question), so the
        # edges, and the same times in minutes, may appear in the prose.
        for t in (c.t_from, c.t_to):
            if t is not None:
                allowed += [t, round(t / 60.0)]
    return allowed


def verify(
    intel: MatchIntel, moment: Moment, analysis: AnalystOutput, book: NameBook | None = None
) -> Verdict:
    """Check every claim, then the prose for numbers nobody proved, then that no running total is
    passed off as one action's number, then (given the names) that the headline credits the right
    club and its time phrases fit the clock."""
    checks = [_check_claim(intel, i, c) for i, c in enumerate(analysis.claims)]
    allowed = allowed_numbers(moment, analysis)
    text = f"{analysis.headline} {analysis.why} " + " ".join(c.text for c in analysis.claims)
    stray = [n for n in numbers_in(text) if not any(close(n, a) for a in allowed)]
    bad = [c for c in checks if c.status == "rejected"]
    story = (
        story_problems(book, moment, intel.teams, analysis.headline, analysis.why) if book else []
    )
    story += scope_problems(analysis)
    if bad or stray or story:
        parts = [c.reason for c in bad]
        if stray:
            shown = ", ".join(f"{n:g}" for n in stray)
            parts.append(f"numbers with no claim behind them: {shown}")
        parts.extend(story)
        return Verdict(
            overall="rejected", checks=checks, stray_numbers=stray, reason="; ".join(parts)
        )
    return Verdict(overall="approved", checks=checks)
