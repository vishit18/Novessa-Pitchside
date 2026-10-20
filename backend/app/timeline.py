"""Build the shared match timeline: events, 1 Hz state, and instant overlays.

Runs the deterministic state engine once per match. Every viewer shares the result; the
persona filter (personas.py) trims it per connection. Overlays here are the instant,
language-free layer (docs/01 decision 2). Agent text attaches later by `moment_id`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from backend.app.overlay import (
    ALL_PERSONAS,
    Anchor,
    EvidenceRef,
    Overlay,
    Persona,
    Provenance,
)
from backend.state.engine import Output, StateEngine
from backend.state.models import Moment, Trigger
from engine.clock import display_clock, merge_by_time
from engine.schema import EventType, League, MatchEvent, MatchMeta, TrackingFrame
from engine.tracking import TrackingData

INSTANT_DELAY_S = 0.2
STATE_EVERY_S = 1.0
ENGINE_FRAME_HZ = 5.0
ID_PATTERN = re.compile(r"\b[A-Z]{3}-\d{2}\b")

HEADLINES = {
    "goal": ("Goal", "goal"),
    "big_chance": ("Big chance", "chance"),
    "momentum_swing": ("Momentum swing", "swing"),
    "pressure_shift": ("Pressure shift", "swing"),
    "control_chaos_flip": ("Match turns", "info"),
    "rhythm_break": ("Tempo change", "info"),
    "card": ("Booking", "info"),
    "penalty": ("Penalty", "chance"),
    "standout_action": ("Standout pass", "chance"),
}
MILESTONE_HEADLINES = {
    "first_goal": "First goal",
    "brace": "Brace",
    "hat_trick": "Hat-trick",
    "longest_pass": "Longest pass of the match",
    "fastest_sprint": "Fastest sprint of the match",
}


# Columns kept per player per second. Stored as a float32 array rather than dicts: a match has
# about 5,700 ticks and 25 players, and dicts for all of that would cost hundreds of MB.
STAT_COLUMNS = (
    "passes", "passes_complete", "difficulty_sum", "longest_pass_m", "hardest_pass", "shots",
    "xg", "xa", "duels_won", "duels_lost", "fouls", "yellows", "reds", "distance_km",
    "top_speed_kmh", "top_shot_kmh", "sprints",
)  # fmt: skip
INT_COLUMNS = {
    "passes",
    "passes_complete",
    "shots",
    "duels_won",
    "duels_lost",
    "fouls",
    "yellows",
    "reds",
    "sprints",
}
HIDDEN_COLUMNS = {"difficulty_sum"}
# One-number mode metric id -> the column whose maximum is the match leader.
LEADER_COLUMNS = {
    "sprint_speed": "top_speed_kmh",
    "shot_speed": "top_shot_kmh",
    "pass_difficulty": "hardest_pass",
    "distance": "distance_km",
}


@dataclass
class TimelineItem:
    """One thing to send at `t_match`. `type` is the WebSocket message type."""

    t_match: float
    type: str
    data: dict[str, Any]

    def json_data(self) -> dict[str, Any]:
        """The message body, ready for JSON. Subclasses build it lazily."""
        return self.data


@dataclass
class StatsItem(TimelineItem):
    """The `player_stats` message, held as an array and expanded only when sent."""

    ids: tuple[str, ...] = ()
    rows: np.ndarray = field(default_factory=lambda: np.zeros((0, len(STAT_COLUMNS))))
    on_pitch: tuple[bool, ...] = ()

    def json_data(self) -> dict[str, Any]:
        cols = {c: i for i, c in enumerate(STAT_COLUMNS)}
        players = []
        for i, pid in enumerate(self.ids):
            row = self.rows[i]
            entry: dict[str, Any] = {
                "player_id": pid,
                "team": pid.split("-")[0],
                "on_pitch": self.on_pitch[i],
            }
            for c, j in cols.items():
                if c in HIDDEN_COLUMNS:
                    continue
                entry[c] = int(row[j]) if c in INT_COLUMNS else round(float(row[j]), 3)
            passes = entry["passes"]
            entry["pass_accuracy"] = round(entry["passes_complete"] / passes, 4) if passes else None
            entry["avg_difficulty"] = (
                round(float(row[cols["difficulty_sum"]]) / passes, 2) if passes else None
            )
            players.append(entry)
        return {"t_match": self.t_match, "players": players, "leaders": self.data["leaders"]}


@dataclass
class Timeline:
    items: list[TimelineItem] = field(default_factory=list)
    overlays: list[Overlay] = field(default_factory=list)
    moments: list[Moment] = field(default_factory=list)

    def latest(self, kind: str, t: float) -> TimelineItem | None:
        """The latest item of a type at or before `t`."""
        best: TimelineItem | None = None
        for it in self.items:
            if it.t_match > t:
                break
            if it.type == kind:
                best = it
        return best

    def state_at(self, t: float) -> dict[str, Any] | None:
        """The latest state message at or before `t`."""
        item = self.latest("state", t)
        return item.json_data() if item else None


class NameBook:
    """Player and club names for overlay text."""

    def __init__(self, league: League) -> None:
        self.players = {p.id: p.name for c in league.clubs for p in c.players}
        self.clubs = {c.code: c.name for c in league.clubs}
        self.managers = {c.code: c.manager for c in league.clubs}

    def humanise(self, text: str) -> str:
        """Swap player ids in a fact sentence for names."""
        return ID_PATTERN.sub(lambda m: self.players.get(m.group(0), m.group(0)), text)

    def player(self, pid: str | None) -> str:
        return self.players.get(pid or "", pid or "")


class TimelineBuilder:
    def __init__(self, meta: MatchMeta, league: League) -> None:
        self.meta = meta
        self.names = NameBook(league)
        self.engine = StateEngine(meta)
        self._n = 0
        self._order: list[str] = []
        self._ids: tuple[str, ...] = ()
        self._on_pitch: set[str] = set()
        # Match second where the first half ends; the clock shown to viewers depends on it.
        self._period_break = 0.0

    def _overlay(self, **kw: Any) -> Overlay:
        self._n += 1
        t = float(kw["t_match"])
        return Overlay(
            msg_id=f"ovl-{self.meta.match_id}-{self._n:05d}",
            match_id=self.meta.match_id,
            show_at=round(t + INSTANT_DELAY_S, 2),
            **kw,
        )

    def build(self, events: list[MatchEvent], tracking: TrackingData) -> Timeline:
        tl = Timeline()
        next_tick = 0.0
        period_break = next(
            (e.t_match for e in events if e.type == EventType.PERIOD_END and e.period == 1),
            events[-1].t_match,
        )
        self._period_break = period_break
        frames = tracking.iter_frames(ENGINE_FRAME_HZ)
        for item in merge_by_time(events, frames):
            while item.t_match >= next_tick:
                snap = self.engine.snapshot().model_dump(mode="json")
                snap["t_match"] = round(next_tick, 2)
                # The clock ticks every second, even when no event has happened for a while.
                snap["period"], snap["clock"] = display_clock(next_tick, period_break)
                tl.items.append(TimelineItem(round(next_tick, 2), "state", snap))
                tl.items.append(self._stats_item(round(next_tick, 2)))
                next_tick += STATE_EVERY_S
            if isinstance(item, MatchEvent):
                tl.items.append(TimelineItem(item.t_match, "event", item.model_dump(mode="json")))
                outs = self.engine.ingest_event(item)
                for o in outs:
                    if isinstance(o, Moment):
                        tl.moments.append(o)
                    tl.overlays.extend(self._to_overlays(o, item))
            elif isinstance(item, TrackingFrame):
                self._on_pitch = {p.id for p in item.players}
                for o in self.engine.ingest_frame(item):
                    if isinstance(o, Moment):
                        tl.moments.append(o)
                    tl.overlays.extend(self._to_overlays(o, None))
        for ov in tl.overlays:
            tl.items.append(TimelineItem(ov.t_match, "overlay", ov.model_dump(mode="json")))
        tl.items.sort(key=lambda i: i.t_match)
        return tl

    def _stats_item(self, t: float) -> StatsItem:
        """Snapshot every player's stats at tick `t`, plus the leader for each metric."""
        for pid in self.engine.players:
            if pid not in self._order:
                self._order.append(pid)
                self._ids = tuple(self._order)
        rows = np.zeros((len(self._ids), len(STAT_COLUMNS)), dtype=np.float32)
        for i, pid in enumerate(self._ids):
            st = self.engine.players[pid]
            rows[i] = [getattr(st, c) for c in STAT_COLUMNS]
        leaders: dict[str, dict[str, Any]] = {}
        for metric, col in LEADER_COLUMNS.items():
            if not len(rows):
                break
            j = STAT_COLUMNS.index(col)
            best = int(np.argmax(rows[:, j]))
            if rows[best, j] > 0:
                leaders[metric] = {
                    "player_id": self._ids[best],
                    "value": round(float(rows[best, j]), 3),
                }
        on_pitch = tuple(pid in self._on_pitch for pid in self._ids)
        return StatsItem(t, "player_stats", {"leaders": leaders}, self._ids, rows, on_pitch)

    # ---- mapping -------------------------------------------------------------------------

    def _to_overlays(self, out: Output, ev: MatchEvent | None) -> list[Overlay]:
        if isinstance(out, Moment):
            return [self._insight(out)]
        return self._from_trigger(out, ev)

    def _from_trigger(self, tr: Trigger, ev: MatchEvent | None) -> list[Overlay]:
        prov = Provenance(source="state_engine", verified=True)
        anchor = Anchor(type="player", id=tr.player_id) if tr.player_id else None
        p = tr.payload
        if tr.kind == "speed_burst":
            rank = int(p["rank_in_match"])
            personas: list[Persona] = ["analyst", "casual"] if rank <= 3 else ["analyst"]
            return [
                self._overlay(
                    slot="player_tag",
                    kind="speed_burst",
                    priority=40,
                    t_match=tr.t_match,
                    duration_s=3.5,
                    anchor=anchor,
                    persona=personas,
                    provenance=prov,
                    payload={
                        "player_id": tr.player_id,
                        "speed_kmh": p["speed_kmh"],
                        "rank_in_match": rank,
                    },
                )
            ]
        if tr.kind == "distance_milestone":
            return [
                self._overlay(
                    slot="player_tag",
                    kind="distance_milestone",
                    priority=30,
                    t_match=tr.t_match,
                    duration_s=4.0,
                    anchor=anchor,
                    persona=["analyst"],
                    provenance=prov,
                    payload={"player_id": tr.player_id, "km": p["km"]},
                )
            ]
        if tr.kind == "pass_difficulty" and ev is not None:
            return [self._pass_overlay(tr, ev)]
        if tr.kind == "shot_speed":
            return [
                self._overlay(
                    slot="lower_third",
                    kind="shot_speed",
                    priority=60,
                    t_match=tr.t_match,
                    duration_s=5.0,
                    anchor=anchor,
                    provenance=prov,
                    payload={
                        "player_id": tr.player_id,
                        "speed_kmh": p["speed_kmh"],
                        "xg": p["xg"],
                        "outcome": p["outcome"],
                    },
                )
            ]
        if tr.kind == "milestone":
            return [self._milestone(tr, anchor, prov)]
        return []

    def _pass_overlay(self, tr: Trigger, ev: MatchEvent) -> Overlay:
        factors = [f.model_dump() for f in ev.difficulty_factors or []]
        return self._overlay(
            slot="pitch_annotation",
            kind="pass_difficulty",
            priority=50 + int(min(float(tr.payload["difficulty"]) - 75, 25)),
            t_match=tr.t_match,
            duration_s=5.0,
            anchor=Anchor(type="pitch", x=ev.x, y=ev.y),
            persona=["analyst"],
            provenance=Provenance(
                source="state_engine",
                verified=True,
                evidence=[
                    EvidenceRef(metric="pass_difficulty", value=float(tr.payload["difficulty"]))
                ],
            ),
            payload={
                "player_id": ev.player_id,
                "team": ev.team,
                "difficulty": tr.payload["difficulty"],
                "distance_m": tr.payload["distance_m"],
                "ball_speed_kmh": tr.payload["ball_speed_kmh"],
                "end_x": ev.end_x,
                "end_y": ev.end_y,
                "complete": ev.outcome == "complete",
                "factors": factors,
            },
        )

    def _milestone(self, tr: Trigger, anchor: Anchor | None, prov: Provenance) -> Overlay:
        name = str(tr.payload["milestone"])
        value = float(tr.payload["value"])
        who = self.names.player(tr.player_id)
        club = self.names.clubs.get(tr.team or "", tr.team or "")
        if name == "team_passes":
            headline, body = f"{value:.0f} passes", club
        elif name == "player_passes":
            headline, body = f"{value:.0f} passes", who
        elif name == "longest_pass":
            headline, body = MILESTONE_HEADLINES[name], f"{who}, {value:.0f} m"
        elif name == "fastest_sprint":
            headline, body = MILESTONE_HEADLINES[name], f"{who}, {value:.1f} km/h"
        else:
            headline, body = MILESTONE_HEADLINES.get(name, name), who
        return self._overlay(
            slot="lower_third",
            kind="milestone",
            priority=55,
            t_match=tr.t_match,
            duration_s=6.0,
            anchor=anchor,
            provenance=prov,
            payload={
                "headline": headline,
                "body": body,
                "team": tr.team,
                "tone": "milestone",
                "milestone": name,
                "value": value,
                "clock": display_clock(tr.t_match, self._period_break)[1],
            },
        )

    def _insight_payload(self, m: Moment, headline: str, tone: str) -> dict[str, Any]:
        body = self.names.humanise(m.summary)
        if m.kind == "card" and m.staff and m.team and m.card:
            who = self.names.managers.get(m.team) or "The manager"
            club = self.names.clubs.get(m.team, m.team)
            body = f"{who}, {club} manager, was shown a {m.card} card."
        payload: dict[str, Any] = {
            "headline": headline,
            "body": body,
            "team": m.team,
            "tone": tone,
            "moment_kind": m.kind,
            "clock": m.clock,
            "significance": m.significance,
        }
        if m.card:
            payload["card"] = m.card
            payload["staff"] = m.staff
        return payload

    def _insight(self, m: Moment) -> Overlay:
        headline, tone = HEADLINES[m.kind]
        if m.kind == "control_chaos_flip":
            headline = f"Match turns {m.snapshot.control_chaos.label}"
        elif m.kind == "card" and m.card:
            if m.staff:
                headline = "Manager sent off" if m.card == "red" else "Manager booked"
            else:
                headline = "Red card" if m.card == "red" else "Yellow card"
        anchor = Anchor(type="player", id=m.player_ids[0]) if m.player_ids else None
        return self._overlay(
            slot="lower_third",
            kind="insight",
            priority=int(m.significance),
            t_match=m.t_match,
            duration_s=9.0 if m.kind == "goal" else 7.0,
            anchor=anchor,
            moment_id=m.moment_id,
            provenance=Provenance(
                source="state_engine",
                verified=True,
                evidence=[EvidenceRef(**e.model_dump()) for e in m.evidence],
            ),
            payload=self._insight_payload(m, headline, tone),
        )


def build_timeline(
    meta: MatchMeta, events: list[MatchEvent], tracking: TrackingData, league: League
) -> Timeline:
    """Convenience wrapper: build the shared timeline for one match."""
    return TimelineBuilder(meta, league).build(events, tracking)


__all__ = ["ALL_PERSONAS", "NameBook", "Timeline", "TimelineItem", "build_timeline"]
