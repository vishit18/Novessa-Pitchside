"""Pass difficulty, 0-100, with the factors that produced it (docs/03 section 5).

A fixed-weight logit over eight factors. Each factor's `points` is how much it added to the
final score, found by switching that factor off and re-scoring. Weights are commented so they
can be tuned against the calibration report.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

from engine.schema import DifficultyFactor

BASE_LOGIT = -2.7


@dataclass(frozen=True)
class PassContext:
    """Everything the model needs to know about one pass. Coordinates are metres."""

    distance: float
    # Perpendicular distance from each defender to the pass line, for defenders alongside the lane.
    lane_gaps: list[float] = field(default_factory=list)
    # (distance to passer, closing speed m/s) for each defender within 3 m of the passer.
    pressers: list[tuple[float, float]] = field(default_factory=list)
    receiver_marker_dist: float = 10.0
    forward_component: float = 0.0  # -1 (backwards) to +1 (straight at goal)
    lateral_component: float = 0.0  # 0 to 1, 1 = pure switch of play
    height: str = "ground"
    weak_foot: bool = False
    first_time: bool = False


def _logit_terms(c: PassContext) -> dict[str, float]:
    d = c.distance
    return {
        # Longer is harder, and it bends upward past ~25 m.
        "distance": 0.028 * d + 0.0005 * d * d,
        # The tightest defender on the lane dominates. Under ~2 m the lane is basically shut.
        "lane_obstruction": 1.7 * max((math.exp(-g / 2.2) for g in c.lane_gaps), default=0.0),
        # Each presser adds a base cost plus more if closing fast.
        "pressure_on_passer": sum(
            0.55 * math.exp(-(dist - 1.0) / 3.0) + 0.05 * max(closing, 0.0)
            for dist, closing in c.pressers
        ),
        "receiver_marking": 1.3 * math.exp(-c.receiver_marker_dist / 3.0),
        # Forward and switching passes are harder than sideways and back passes.
        "direction": 0.6 * c.forward_component + 0.4 * c.lateral_component,
        "height": {"ground": 0.0, "low": 0.3, "high": 0.9}[c.height],
        "weak_foot": 0.5 if c.weak_foot else 0.0,
        "tempo": 0.4 if c.first_time else 0.0,
    }


def _score(terms: dict[str, float], skip: str | None = None) -> float:
    logit = BASE_LOGIT + sum(v for k, v in terms.items() if k != skip)
    return 100.0 / (1.0 + math.exp(-logit))


def pass_difficulty(c: PassContext) -> tuple[float, list[DifficultyFactor]]:
    """Return (score 0-100, factors sorted by points descending, zero-point factors dropped)."""
    terms = _logit_terms(c)
    score = _score(terms)
    factors = [
        DifficultyFactor(name=k, points=round(score - _score(terms, skip=k), 1)) for k in terms
    ]
    factors = [f for f in factors if abs(f.points) >= 0.5]
    factors.sort(key=lambda f: -f.points)
    return round(score, 1), factors


def with_changes(c: PassContext, **changes: object) -> PassContext:
    """Copy a context with some fields changed. Handy in tests."""
    return replace(c, **changes)  # type: ignore[arg-type]
