"""Match Intelligence: every question an agent may ask about a match, answered from the data.

This is the single source of numbers. The MCP server exposes these methods as tools, the
Analyst reads through them, and the Verifier uses `measure` to re-compute each claim from
scratch. Nothing here calls a model.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import Counter
from typing import Any

from backend.app.store import LoadedMatch
from backend.app.timeline import StatsItem
from backend.state.models import Moment
from engine.schema import EventType, MatchEvent

# What an agent may claim. The Analyst prompt lists these; `measure` rejects anything else.
STATE_METRICS = (
    "momentum",
    "pressure_index",
    "control_chaos",
    "events_per_min",
    "possession_5min",
    "possession_match",
    "score",
)
WINDOW_METRICS = (
    "passes",
    "pass_accuracy_pct",
    "shots",
    "xg_total",
    "ball_wins",
    "pressure_events",
    "fouls",
    "corners",
)
PLAYER_METRICS = (
    "top_speed_kmh",
    "distance_km",
    "pass_accuracy_pct",
    "xg",
    "hardest_pass",
    "sprints",
    "shots",
    "passes",
    "duels_won",
    "goals",
    "assists",
)
# Numbers about one action rather than a running total: the xG of the player's latest shot.
EVENT_METRICS = ("shot_xg",)
BALL_WIN_TYPES = {EventType.TACKLE, EventType.INTERCEPTION}


class UnknownMetricError(ValueError):
    """The metric name is not in the claimable list, or the arguments don't fit it."""


class MatchIntel:
    """Read-only queries over one loaded match."""

    def __init__(self, loaded: LoadedMatch) -> None:
        self.loaded = loaded
        self.meta = loaded.meta
        self.events: list[MatchEvent] = loaded.events
        self._times = [e.t_match for e in self.events]
        self.teams = (loaded.meta.home.code, loaded.meta.away.code)

    # ---- raw views ------------------------------------------------------------------------

    def get_state(self, t_match: float) -> dict[str, Any]:
        """The state snapshot at or before `t_match`."""
        state = self.loaded.timeline.state_at(t_match)
        if state is None:
            raise ValueError(f"no state at {t_match}")
        return state

    def _stats_rows(self, t_match: float) -> dict[str, dict[str, Any]]:
        item = self.loaded.timeline.latest("player_stats", t_match)
        if not isinstance(item, StatsItem):
            return {}
        return {p["player_id"]: p for p in item.json_data()["players"]}

    def get_player_stats(self, player_id: str, t_match: float) -> dict[str, Any]:
        """Running stats for one player at `t_match`."""
        rows = self._stats_rows(t_match)
        if player_id not in rows:
            raise ValueError(f"no stats for {player_id} at {t_match}")
        return rows[player_id]

    def top_players(self, field: str, t_match: float, n: int = 3) -> list[tuple[str, float]]:
        """The `n` players with the highest value of one player_stats field at `t_match`.

        `pass_accuracy_pct` reads `pass_accuracy` and needs at least ten passes to count.
        """
        src = "pass_accuracy" if field == "pass_accuracy_pct" else field
        rows = self._stats_rows(t_match).values()
        scored = [
            (r["player_id"], float(r[src]))
            for r in rows
            if r.get(src) is not None and (src != "pass_accuracy" or r.get("passes", 0) >= 10)
        ]
        return sorted(scored, key=lambda x: x[1], reverse=True)[:n]

    def _window(self, t_from: float, t_to: float) -> list[MatchEvent]:
        lo = bisect_left(self._times, t_from)
        hi = bisect_right(self._times, t_to)
        return self.events[lo:hi]

    def get_window_stats(self, team: str, t_from: float, t_to: float) -> dict[str, float]:
        """Counts for one team inside a window of match seconds."""
        return {m: self._window_metric(m, team, t_from, t_to) for m in WINDOW_METRICS}

    def compare_periods(
        self, team: str, metric: str, a: tuple[float, float], b: tuple[float, float]
    ) -> dict[str, float]:
        """The same window metric over two windows, plus the change."""
        va = self._window_metric(metric, team, *a)
        vb = self._window_metric(metric, team, *b)
        return {"a": va, "b": vb, "change": round(vb - va, 3)}

    def get_pass_network(self, team: str, t_from: float, t_to: float) -> list[dict[str, Any]]:
        """Completed passes between players, busiest links first."""
        links: Counter[tuple[str, str]] = Counter()
        for e in self._window(t_from, t_to):
            if (
                e.type == EventType.PASS
                and e.team == team
                and e.outcome == "complete"
                and e.player_id
                and e.receiver_id
            ):
                links[(e.player_id, e.receiver_id)] += 1
        return [{"from": a, "to": b, "passes": n} for (a, b), n in links.most_common(10)]

    def list_moments(
        self, t_from: float = 0.0, t_to: float = 1e9, min_significance: float = 0.0
    ) -> list[Moment]:
        """Candidate moments from the state engine, in match order."""
        return [
            m
            for m in self.loaded.timeline.moments
            if t_from <= m.t_match <= t_to and m.significance >= min_significance
        ]

    def get_moment(self, moment_id: str) -> Moment:
        for m in self.loaded.timeline.moments:
            if m.moment_id == moment_id:
                return m
        raise KeyError(moment_id)

    # ---- measuring ------------------------------------------------------------------------

    def measure(
        self,
        metric: str,
        *,
        team: str | None = None,
        player_id: str | None = None,
        t_from: float | None = None,
        t_to: float | None = None,
    ) -> float:
        """Compute one claimable number from scratch. Raises on an unknown metric."""
        if metric in EVENT_METRICS and player_id:
            return self._shot_xg(player_id, t_to)
        if metric in PLAYER_METRICS and player_id:
            return self._player_metric(metric, player_id, t_to)
        if metric in WINDOW_METRICS and team:
            if t_from is None or t_to is None:
                raise UnknownMetricError(f"{metric} needs a window")
            return self._window_metric(metric, team, t_from, t_to)
        if metric in STATE_METRICS:
            return self._state_metric(metric, team, t_to)
        raise UnknownMetricError(f"cannot measure {metric!r} for team={team} player={player_id}")

    def _state_metric(self, metric: str, team: str | None, t: float | None) -> float:
        if t is None:
            raise UnknownMetricError(f"{metric} needs a time")
        s = self.get_state(t)
        if metric == "momentum":
            return float(s["momentum"])
        if metric == "control_chaos":
            return float(s["control_chaos"]["value"])
        if metric == "events_per_min":
            return float(s["rhythm"]["events_per_min"])
        if team is None:
            raise UnknownMetricError(f"{metric} needs a team")
        if metric == "pressure_index":
            return float(s["pressure"][team])
        if metric == "possession_5min":
            return float(s["possession_5min"][team])
        if metric == "possession_match":
            return float(s["possession_match"][team])
        if metric == "score":
            return float(s["score"][team])
        raise UnknownMetricError(metric)

    def _window_metric(self, metric: str, team: str, t_from: float, t_to: float) -> float:
        evs = [e for e in self._window(t_from, t_to) if e.team == team]
        if metric == "passes":
            return float(sum(e.type == EventType.PASS for e in evs))
        if metric == "pass_accuracy_pct":
            passes = [e for e in evs if e.type == EventType.PASS]
            done = sum(e.outcome == "complete" for e in passes)
            return round(100.0 * done / len(passes), 1) if passes else 0.0
        if metric == "shots":
            return float(sum(e.type in (EventType.SHOT, EventType.GOAL) for e in evs))
        if metric == "xg_total":
            return round(sum(e.xg or 0.0 for e in evs), 3)
        if metric == "ball_wins":
            return float(sum(e.type in BALL_WIN_TYPES for e in evs))
        if metric == "pressure_events":
            return float(sum(e.type == EventType.PRESSURE for e in evs))
        if metric == "fouls":
            return float(sum(e.type == EventType.FOUL for e in evs))
        if metric == "corners":
            return float(sum(e.type == EventType.CORNER for e in evs))
        raise UnknownMetricError(metric)

    def latest_shot(self, player_id: str, t: float) -> MatchEvent | None:
        """The player's latest shot at or before `t`, goals included."""
        for e in reversed(self._window(0.0, t)):
            mine = e.player_id == player_id and e.type in (EventType.SHOT, EventType.GOAL)
            if mine and (e.type == EventType.SHOT or e.xg is not None):
                return e
        return None

    def _shot_xg(self, player_id: str, t: float | None) -> float:
        if t is None:
            raise UnknownMetricError("shot_xg needs a time")
        shot = self.latest_shot(player_id, t)
        if shot is None:
            raise ValueError(f"{player_id} has no shot by {t}")
        return round(shot.xg or 0.0, 3)

    def _player_metric(self, metric: str, player_id: str, t: float | None) -> float:
        if t is None:
            raise UnknownMetricError(f"{metric} needs a time")
        row = self.get_player_stats(player_id, t)
        key = "pass_accuracy" if metric == "pass_accuracy_pct" else metric
        value = row.get(key)
        if value is None:
            return 0.0
        return round(float(value) * 100.0, 1) if metric == "pass_accuracy_pct" else float(value)
