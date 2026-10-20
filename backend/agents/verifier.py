"""Verifier: proves every claim before it airs.

It does not trust the Analyst's numbers. Each claim is re-measured from the match data through
`MatchIntel.measure`, and every number in the prose must trace back to a verified claim or to the
moment's own evidence. No model is involved, so the check cannot be talked round.
"""

from __future__ import annotations

import re

from backend.agents.intel import MatchIntel, UnknownMetricError
from backend.agents.models import AnalystOutput, Claim, ClaimCheck, Verdict
from backend.state.models import Moment

ID_PATTERN = re.compile(r"\b[A-Z]{3}-\d{2}\b")
NUMBER = re.compile(r"\d+(?:\.\d+)?")
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
    return allowed


def verify(intel: MatchIntel, moment: Moment, analysis: AnalystOutput) -> Verdict:
    """Check every claim, then check the prose for numbers nobody proved."""
    checks = [_check_claim(intel, i, c) for i, c in enumerate(analysis.claims)]
    allowed = allowed_numbers(moment, analysis)
    text = f"{analysis.headline} {analysis.why} " + " ".join(c.text for c in analysis.claims)
    stray = [n for n in numbers_in(text) if not any(close(n, a) for a in allowed)]
    bad = [c for c in checks if c.status == "rejected"]
    if bad or stray:
        parts = [c.reason for c in bad]
        if stray:
            shown = ", ".join(f"{n:g}" for n in stray)
            parts.append(f"numbers with no claim behind them: {shown}")
        return Verdict(
            overall="rejected", checks=checks, stray_numbers=stray, reason="; ".join(parts)
        )
    return Verdict(overall="approved", checks=checks)
