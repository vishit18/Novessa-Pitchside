"""Match simulator v1.

Simulates football decisions on top of light kinematics (docs/03 section 3). One step is one
on-ball action by the player with the ball. Between actions everyone drifts toward a formation
slot that shifts with the ball. Everything is driven by one seeded numpy generator, so a seed
always gives the same match.

Not in v1: red cards, penalties, offsides beyond a rare flag on through balls, injuries that
change the squad.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from engine.difficulty import PassContext, pass_difficulty
from engine.schema import (
    PITCH_LENGTH,
    PITCH_WIDTH,
    Club,
    EventType,
    League,
    LineupSlot,
    MatchEvent,
    MatchMeta,
    Player,
    Position,
    TeamSheet,
)
from engine.tracking import TrackingData

HALF = 2700.0
Vec = np.ndarray

Slot = tuple[Position, float, float]


def _line(group: Position, u: float, ys: tuple[float, ...]) -> list[Slot]:
    return [(group, u, y) for y in ys]


# Formation slots, own goal on the left: (group, u as a fraction of pitch length, y in metres).
FORMATIONS: dict[str, list[Slot]] = {
    "4-3-3": _line("GK", 0.04, (34,))
    + _line("DEF", 0.22, (10, 26, 42, 58))
    + _line("MID", 0.45, (18, 34, 50))
    + _line("FWD", 0.73, (10, 34, 58)),
    "5-4-1": _line("GK", 0.04, (34,))
    + _line("DEF", 0.2, (7, 20, 34, 48, 61))
    + _line("MID", 0.42, (12, 26, 42, 56))
    + _line("FWD", 0.65, (34,)),
    "4-2-3-1": _line("GK", 0.04, (34,))
    + _line("DEF", 0.22, (10, 26, 42, 58))
    + _line("MID", 0.38, (26, 42))
    + _line("MID", 0.58, (14, 34, 54))
    + _line("FWD", 0.72, (34,)),
    "4-4-2": _line("GK", 0.04, (34,))
    + _line("DEF", 0.22, (10, 26, 42, 58))
    + _line("MID", 0.45, (12, 26, 42, 56))
    + _line("FWD", 0.68, (26, 42)),
}

ARC_KINDS = ("dominate_no_score", "sub_changes_game", "late_collapse", "star_quiet_then_moment")


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))


@dataclass
class Mods:
    bias: float = 0.0
    finish: float = 1.0
    press: float = 1.0
    drain: float = 1.0


@dataclass
class Arc:
    """A storyline the engine nudges toward. Hidden from the agents on purpose."""

    kind: str
    team: int
    start: float
    end: float
    player_id: str | None = None


@dataclass
class Match:
    meta: MatchMeta
    events: list[MatchEvent]
    tracking: TrackingData
    score: tuple[int, int]
    script: list[dict[str, float | str | None]]
    players: dict[str, Player] = field(default_factory=dict)


def _overall(p: Player) -> float:
    a = p.attributes
    return (
        a.pace
        + a.passing
        + a.vision
        + a.first_touch
        + a.finishing
        + a.tackling
        + a.positioning
        + a.composure
    ) / 8


class MatchSimulator:
    """Simulate one match. Use `simulate_match` rather than constructing this directly."""

    def __init__(
        self, league: League, home: str, away: str, seed: int, match_id: str, matchday: int = 1
    ) -> None:
        self.league = league
        self.seed = seed
        self.match_id = match_id
        self.matchday = matchday
        self.r = np.random.default_rng(seed)
        self.clubs: list[Club] = [league.club(home), league.club(away)]
        self.dir = [1, -1]
        self.t = 0.0
        self.period = 1
        self.p2_start = HALF
        self.seq = 0
        self.events: list[MatchEvent] = []
        self.score = [0, 0]
        self.tracking = TrackingData(match_id)

        self.on_pitch: list[list[Player]] = []
        self.group: list[list[Position]] = []
        self.base: list[np.ndarray] = []
        self.bench: list[list[Player]] = []
        self.entered = [[0.0] * 11, [0.0] * 11]
        self.sheets: list[TeamSheet] = []
        for club in self.clubs:
            self._pick_lineup(club)

        self.pos = np.zeros((2, 11, 2))
        self.vel = np.zeros((2, 11, 2))
        self.wander = np.zeros((2, 11, 2))
        self.ball = np.array([52.5, 34.0])
        self.carrier = (0, 0)
        self.just_received = False
        self.aerial = False
        self.last_pass: tuple[int, str | None, float] | None = None  # (event index, receiver, t)
        self.yellows: set[str] = set()
        self.pending_subs: list[list[float]] = [
            sorted(self.r.uniform(3300, 4900, size=int(self.r.integers(2, 4)))) for _ in (0, 1)
        ]
        self.arcs = self._pick_arcs()
        self.injury_done = False

    # ---- setup ---------------------------------------------------------------------------

    def _pick_lineup(self, club: Club) -> None:
        slots = FORMATIONS[club.identity.formation]
        by_group: dict[Position, list[Player]] = {"GK": [], "DEF": [], "MID": [], "FWD": []}
        for p in club.players:
            by_group[p.position].append(p)
        for g in by_group:
            by_group[g].sort(key=lambda p: -_overall(p))
        counts = {g: sum(1 for s in slots if s[0] == g) for g in by_group}
        starters: list[Player] = []
        used: set[str] = set()
        for g, n in counts.items():
            chosen = sorted(by_group[g][:n], key=lambda p: p.shirt)
            starters.extend(chosen)
            used.update(p.id for p in chosen)
        # `slots` is ordered GK, DEF.., MID.., FWD.. like `counts`, so zip lines up.
        order = {g: [p for p in starters if p.position == g] for g in by_group}
        line: list[Player] = []
        for g, _, _ in slots:
            line.append(order[g].pop(0))
        self.on_pitch.append(line)
        self.group.append([s[0] for s in slots])
        self.base.append(np.array([[s[1], s[2]] for s in slots]))
        self.bench.append([p for p in club.players if p.id not in used])
        captain = max(
            (p for p in line if p.position != "GK"), key=lambda p: p.attributes.composure + p.age
        )
        self.sheets.append(
            TeamSheet(
                code=club.code,
                formation=club.identity.formation,
                captain=captain.id,
                starters=[
                    LineupSlot(player_id=p.id, group=self.group[-1][i], slot=i)
                    for i, p in enumerate(line)
                ],
                bench=[p.id for p in self.bench[-1]],
            )
        )

    def _pick_arcs(self) -> list[Arc]:
        kinds = [
            str(k) for k in self.r.choice(ARC_KINDS, size=int(self.r.integers(2, 4)), replace=False)
        ]
        arcs: list[Arc] = []
        for k in kinds:
            team = int(self.r.integers(0, 2))
            if k == "dominate_no_score":
                arcs.append(Arc(k, team, 0.0, HALF))
            elif k == "sub_changes_game":
                arcs.append(Arc(k, team, float(self.r.uniform(3700, 4300)), 6000.0))
            elif k == "late_collapse":
                arcs.append(Arc(k, team, float(self.r.uniform(4000, 4500)), 6000.0))
            else:
                fwd = [p for p in self.on_pitch[team] if p.position in ("FWD", "MID")]
                star = max(fwd, key=lambda p: p.attributes.finishing + p.attributes.pace)
                arcs.append(Arc(k, team, 3600.0, 6000.0, star.id))
        return arcs

    def _mods(self, team: int) -> Mods:
        m = Mods()
        for a in self.arcs:
            if a.team != team:
                continue
            if a.kind == "dominate_no_score" and self.t < a.end:
                m.bias += 0.10
                m.finish *= 0.45
            elif a.kind == "sub_changes_game" and self.t >= a.start:
                m.bias += 0.12
                m.finish *= 1.25
            elif a.kind == "late_collapse" and self.t >= a.start:
                m.drain *= 2.2
                m.press *= 0.6
                m.bias -= 0.12
        return m

    def _star_factor(self, pid: str) -> tuple[float, float]:
        """(involvement multiplier, finishing multiplier) for the arc's star player."""
        for a in self.arcs:
            if a.kind == "star_quiet_then_moment" and a.player_id == pid:
                return (0.4, 1.0) if self.t < a.start else (1.2, 1.8)
        return 1.0, 1.0

    # ---- coordinate helpers --------------------------------------------------------------

    def _u(self, team: int, x: float) -> float:
        return x if self.dir[team] == 1 else PITCH_LENGTH - x

    def _x(self, team: int, u: float) -> float:
        return u if self.dir[team] == 1 else PITCH_LENGTH - u

    def _yr(self, team: int, y: float) -> float:
        return y if self.dir[team] == 1 else PITCH_WIDTH - y

    def _clip(self, p: Vec) -> Vec:
        return np.array([min(max(p[0], 0.0), PITCH_LENGTH), min(max(p[1], 0.0), PITCH_WIDTH)])

    # ---- attribute helpers ---------------------------------------------------------------

    def _fatigue(self, team: int, slot: int) -> float:
        p = self.on_pitch[team][slot]
        played = max(self.t - self.entered[team][slot], 0.0) / 5400.0
        drain = self._mods(team).drain
        return max(0.72, 1.0 - 0.20 * played * (1.5 - p.attributes.stamina / 99.0) * drain)

    def _attr(self, team: int, slot: int, name: str) -> float:
        p = self.on_pitch[team][slot]
        return float(getattr(p.attributes, name)) * (0.85 + 0.15 * self._fatigue(team, slot))

    def _pid(self, team: int, slot: int) -> str:
        return self.on_pitch[team][slot].id

    # ---- events --------------------------------------------------------------------------

    def _clock(self) -> str:
        if self.period == 1:
            t, base, cap = self.t, 0.0, HALF
        else:
            t, base, cap = self.t - self.p2_start, HALF, HALF
        if t <= cap:
            tt = base + t
            return f"{int(tt // 60):02d}:{int(tt % 60):02d}"
        extra = t - cap
        return f"{int((base + cap) // 60)}+{int(extra // 60)}:{int(extra % 60):02d}"

    def _emit(
        self,
        etype: EventType,
        team: int | None = None,
        slot: int | None = None,
        t: float | None = None,
        **kw: object,
    ) -> int:
        """Append an event and return its index."""
        t_ev = self.t if t is None else t
        saved = self.t
        self.t = t_ev
        clock = self._clock()
        self.t = saved
        self.seq += 1
        ev = MatchEvent(
            event_id=f"{self.match_id}-{self.seq:06d}",
            match_id=self.match_id,
            seq=self.seq,
            t_match=round(t_ev, 2),
            period=self.period,
            clock=clock,
            type=etype,
            team=None if team is None else self.clubs[team].code,
            player_id=None if team is None or slot is None else self._pid(team, slot),
            **kw,
        )
        self.events.append(ev)
        return len(self.events) - 1

    # ---- movement ------------------------------------------------------------------------

    def _targets(self) -> np.ndarray:
        tgt = np.zeros((2, 11, 2))
        poss = self.carrier[0]
        for team in (0, 1):
            ident = self.clubs[team].identity
            mods = self._mods(team)
            ball_u = self._u(team, self.ball[0])
            ball_y = self._yr(team, self.ball[1])
            shift = float(
                np.clip((ball_u - 52.5) * 0.55 + ident.line_height + mods.bias * 15, -18, 22)
            )
            width = 1.1 if team == poss else 0.8
            for s in range(11):
                bu, by = self.base[team][s]
                if self.group[team][s] == "GK":
                    tu, ty = 3.5 + 0.04 * ball_u, 34 + 0.12 * (ball_y - 34)
                else:
                    w = 0.7 if self.group[team][s] == "DEF" else 1.0
                    tu = float(np.clip(bu * PITCH_LENGTH + shift * w, 4, 101))
                    ty = 34 + (by - 34) * width + 0.18 * (ball_y - 34)
                ty = float(np.clip(ty, 2, PITCH_WIDTH - 2))
                yy = ty if self.dir[team] == 1 else PITCH_WIDTH - ty
                tgt[team, s] = (self._x(team, tu), yy)
        # Defending side: two nearest outfield players close the ball down.
        opp = 1 - poss
        d_ball = np.linalg.norm(self.pos[opp] - self.ball, axis=1)
        chance = self.clubs[opp].identity.press * self._mods(opp).press
        for rank, s in enumerate(np.argsort(d_ball)[:2]):
            if self.group[opp][int(s)] != "GK" and self.r.random() < chance * (0.6, 0.3)[rank]:
                toward_own_goal = np.array([-self.dir[opp] * 3.0, 0.0])
                tgt[opp, int(s)] = self.ball + toward_own_goal
        # Attacking side: two nearest teammates offer an option near the carrier.
        c_slot = self.carrier[1]
        d_c = np.linalg.norm(self.pos[poss] - self.ball, axis=1)
        offered = 0
        for s in np.argsort(d_c):
            s = int(s)
            if s == c_slot or self.group[poss][s] == "GK":
                continue
            side = 1 if offered == 0 else -1
            tgt[poss, s] = self._clip(self.ball + np.array([self.dir[poss] * 5.0, side * 9.0]))
            offered += 1
            if offered == 2:
                break
        return tgt

    def _advance(self, dt: float, exclude: set[tuple[int, int]]) -> None:
        tgt = self._targets()
        for team in (0, 1):
            for s in range(11):
                if (team, s) in exclude:
                    continue
                cur = self.pos[team, s]
                delta = tgt[team, s] - cur
                dist = float(np.linalg.norm(delta))
                vmax = (7.0 + 0.03 * self._attr(team, s, "pace")) * self._fatigue(team, s)
                step = np.zeros(2)
                if dist > 1e-6:
                    speed = min(vmax, dist / 2.2)
                    step = delta / dist * min(speed * dt, dist)
                self.wander[team, s] = 0.75 * self.wander[team, s] + self.r.normal(0, 0.45, 2)
                new = self._clip(cur + step + self.wander[team, s] * dt)
                self.vel[team, s] = (new - cur) / max(dt, 1e-6)
                self.pos[team, s] = new

    def _ids(self) -> tuple[tuple[str, ...], tuple[str, ...]]:
        return (tuple(p.id for p in self.on_pitch[0]), tuple(p.id for p in self.on_pitch[1]))

    def _snapshot(self, peak: float = 0.0, hold: bool = False) -> None:
        self.tracking.add(
            self.t, self.pos, self._ids(), (float(self.ball[0]), float(self.ball[1])), peak, hold
        )

    def _finish(self, dt: float, involved: set[tuple[int, int]], peak: float = 0.0) -> None:
        """Let the world move for `dt` seconds, then record a snapshot."""
        dt = self._scaled(dt)
        self._advance(dt, involved)
        self.t += dt
        self._snapshot(peak)

    def _scaled(self, dt: float) -> float:
        """Action duration after the possessing team's tempo is applied."""
        c = self.clubs[self.carrier[0]].identity
        return max(dt * (1.3 - 0.6 * c.tempo) * 1.7, 0.4)

    def _reach(self, team: int, slot: int, target: Vec, dt: float) -> Vec:
        """Move a player toward `target`, no faster than they can run in `dt` raw seconds."""
        cur = self.pos[team, slot]
        delta = target - cur
        dist = float(np.linalg.norm(delta))
        vmax = (7.0 + 0.03 * self._attr(team, slot, "pace")) * self._fatigue(team, slot)
        reach = vmax * self._scaled(dt) * 0.9
        new = target.copy() if dist <= reach else cur + delta / dist * reach
        self.pos[team, slot] = new
        return new

    def _walk_delay(self, team: int, slot: int, spot: Vec, base: float) -> float:
        """Dead-ball delay, stretched if the taker has a long walk to the spot."""
        dist = float(np.linalg.norm(self.pos[team, slot] - spot))
        return max(base, dist / 5.0 / (self._scaled(1.0)))

    def _idle(self, seconds: float) -> None:
        left = seconds
        while left > 0:
            chunk = min(3.0, left)
            self._advance(chunk, {self.carrier})
            self.t += chunk
            self._snapshot()
            left -= chunk

    def _reset_positions(self, kick_team: int) -> None:
        for team in (0, 1):
            for s in range(11):
                bu, by = self.base[team][s]
                u = min(bu * PITCH_LENGTH, 50.0)
                yy = by if self.dir[team] == 1 else PITCH_WIDTH - by
                self.pos[team, s] = (self._x(team, u), yy)
        fwd = [s for s in range(11) if self.group[kick_team][s] == "FWD"]
        kicker = fwd[len(fwd) // 2]
        self.pos[kick_team, kicker] = (52.5, 34.0)
        self.ball = np.array([52.5, 34.0])
        self.carrier = (kick_team, kicker)
        self.vel[:] = 0
        self.t += 0.1
        self._snapshot(hold=True)

    # ---- possession ----------------------------------------------------------------------

    def _change_possession(self, team: int, slot: int, cause: str) -> None:
        self._emit(
            EventType.POSSESSION_CHANGE,
            team,
            slot,
            x=_r(self.ball[0]),
            y=_r(self.ball[1]),
            outcome="won",
            tags=[cause],
        )
        self.carrier = (team, slot)
        self.just_received = False
        self.aerial = False

    def _nearest(self, team: int, point: Vec, skip_gk: bool = True) -> tuple[int, float]:
        d = np.linalg.norm(self.pos[team] - point, axis=1)
        if skip_gk:
            for s in range(11):
                if self.group[team][s] == "GK":
                    d[s] = 1e9
        s = int(np.argmin(d))
        return s, float(d[s])

    def _maybe_subs(self) -> None:
        for team in (0, 1):
            while self.pending_subs[team] and self.t >= self.pending_subs[team][0]:
                self.pending_subs[team].pop(0)
                cands = [s for s in range(11) if self.group[team][s] != "GK"]
                off = max(
                    cands, key=lambda s: (1 - self._fatigue(team, s)) + self.r.random() * 0.05
                )
                grp = self.group[team][off]
                bench = [p for p in self.bench[team] if p.position == grp] or [
                    p for p in self.bench[team] if p.position != "GK"
                ]
                if not bench:
                    continue
                new = bench[0]
                old = self.on_pitch[team][off]
                self._emit(
                    EventType.SUBSTITUTION,
                    team,
                    off,
                    receiver_id=new.id,
                    x=_r(self.pos[team, off, 0]),
                    y=_r(self.pos[team, off, 1]),
                )
                self.bench[team].remove(new)
                self.bench[team].append(old)
                self.on_pitch[team][off] = new
                self.entered[team][off] = self.t

    def _restart(
        self,
        team: int,
        spot: Vec,
        etype: EventType | None,
        delay: float,
        goalkeeper: bool = False,
        cause: str | None = None,
    ) -> None:
        """Dead-ball restart: the nearest suitable player puts the ball back in play."""
        spot = self._clip(spot)
        slot = 0 if goalkeeper else self._nearest(team, spot)[0]
        delay = self._walk_delay(team, slot, spot, delay)
        self.pos[team, slot] = spot
        self.ball = spot.copy()
        self.carrier = (team, slot)
        self.just_received = False
        self.aerial = False
        if etype is not None:
            self._emit(etype, team, slot, x=_r(spot[0]), y=_r(spot[1]))
        if cause:
            self._emit(
                EventType.POSSESSION_CHANGE,
                team,
                slot,
                x=_r(spot[0]),
                y=_r(spot[1]),
                outcome="won",
                tags=[cause],
            )
        self._maybe_subs()
        self._finish(delay, {self.carrier})

    # ---- action selection ----------------------------------------------------------------

    def _step(self) -> None:
        team, slot = self.carrier
        opp = 1 - team
        cpos = self.pos[team, slot].copy()
        self.ball = cpos.copy()
        u = self._u(team, cpos[0])
        d_opp = np.linalg.norm(self.pos[opp] - cpos, axis=1)
        order = np.argsort(d_opp)
        dmin = float(d_opp[order[0]])
        pres = float(np.clip((5.0 - dmin) / 5.0, 0.0, 1.0))
        pressers = [int(s) for s in order if d_opp[s] < 4.0]
        if dmin < 4.5 and self.r.random() < 0.65:
            self._emit(
                EventType.PRESSURE,
                opp,
                int(order[0]),
                x=_r(cpos[0]),
                y=_r(cpos[1]),
                outcome="applied",
                tags=[f"on:{self._pid(team, slot)}"],
            )

        is_gk = self.group[team][slot] == "GK"
        w = {"pass": 1.0 + 0.5 * pres, "carry": 0.0, "dribble": 0.0, "shot": 0.0, "clear": 0.0}
        if is_gk:
            w["clear"] = 0.1 * pres
        else:
            ft = self._attr(team, slot, "first_touch")
            pace = self._attr(team, slot, "pace")
            w["carry"] = 0.32 * (1 - 0.5 * pres)
            w["dribble"] = (0.03 + 0.16 * pres) * (0.5 + (ft + pace) / 200) if u > 35 else 0.02
            if u < 25:
                w["clear"] = 0.9 * pres + 0.03
            if u > 66:
                ang = 1 - 0.8 * float(np.clip((abs(cpos[1] - 34) - 12) / 22, 0, 1))
                sf = self._attr(team, slot, "finishing") / 70
                inv, _ = self._star_factor(self._pid(team, slot))
                w["shot"] = ((u - 66) / 39) ** 1.8 * 0.24 * ang * sf * (inv if inv > 1 else 1.0)
                if self.aerial and u > 85:
                    w["shot"] *= 3.0
        keys = list(w)
        probs = np.array([w[k] for k in keys])
        action = keys[int(self.r.choice(len(keys), p=probs / probs.sum()))]
        under = dmin < 3.0
        by = [self._pid(opp, s) for s in pressers]
        if action == "pass":
            self._do_pass(team, slot, cpos, u, pres, under, by)
        elif action == "carry":
            self._do_carry(team, slot, cpos, pres, under, by, dribble=False)
        elif action == "dribble":
            self._do_carry(team, slot, cpos, pres, under, by, dribble=True)
        elif action == "shot":
            self._do_shot(team, slot, cpos, pres, under, by)
        else:
            self._do_clearance(team, slot, cpos, under, by)

    # ---- passing -------------------------------------------------------------------------

    def _pass_context(
        self, team: int, slot: int, start: Vec, end: Vec, height: str, recv: int | None
    ) -> PassContext:
        opp = 1 - team
        d = float(np.linalg.norm(end - start))
        lane_gaps: list[float] = []
        if d > 0.1:
            unit = (end - start) / d
            for s in range(11):
                rel = self.pos[opp, s] - start
                along = float(rel @ unit)
                if 1.0 < along < d - 1.0:
                    gap = abs(float(rel[0] * unit[1] - rel[1] * unit[0]))
                    if gap < 8.0:
                        lane_gaps.append(gap)
        pressers: list[tuple[float, float]] = []
        for s in range(11):
            dist = float(np.linalg.norm(self.pos[opp, s] - start))
            if dist < 3.0:
                toward = (start - self.pos[opp, s]) / max(dist, 1e-6)
                pressers.append((dist, float(self.vel[opp, s] @ toward)))
        marker = float(np.min(np.linalg.norm(self.pos[opp] - end, axis=1)))
        u0, u1 = self._u(team, start[0]), self._u(team, end[0])
        fwd = (u1 - u0) / d if d > 0.1 else 0.0
        lat = abs(end[1] - start[1]) / d if d > 0.1 else 0.0
        first_time = self.just_received and self.r.random() < 0.35
        return PassContext(
            distance=d,
            lane_gaps=lane_gaps,
            pressers=pressers,
            receiver_marker_dist=marker,
            forward_component=fwd,
            lateral_component=lat,
            height=height,
            weak_foot=bool(self.r.random() < 0.12),
            first_time=first_time,
        )

    def _choose_receiver(self, team: int, slot: int, cpos: Vec, u: float, corner: bool) -> int:
        ident = self.clubs[team].identity
        opp = 1 - team
        cands: list[int] = []
        weights: list[float] = []
        gk_carry = self.group[team][slot] == "GK"
        pref = 8 + 14 * ident.directness + (16 if gk_carry and ident.directness > 0.5 else 0)
        fw = 0.3 + 0.6 * ident.directness
        for s in range(11):
            if s == slot:
                continue
            rp = self.pos[team, s]
            d = float(np.linalg.norm(rp - cpos))
            ru = self._u(team, rp[0])
            if corner:
                if self.group[team][s] == "GK" or ru < 80:
                    continue
                cands.append(s)
                weights.append(1.0 + 0.01 * self._attr(team, s, "finishing"))
                continue
            if d < 4.0:
                continue
            openness = float(
                np.clip(np.min(np.linalg.norm(self.pos[opp] - rp, axis=1)) / 8.0, 0.1, 1.5)
            )
            wgt = math.exp(-(((d - pref) / 12.0) ** 2)) * math.exp(fw * (ru - u) / 15.0)
            wgt *= 0.3 + openness
            if self.group[team][s] == "GK":
                wgt *= 0.25
            inv, _ = self._star_factor(self._pid(team, s))
            wgt *= inv
            cands.append(s)
            weights.append(wgt)
        if not cands:
            return (slot + 1) % 11
        p = np.array(weights)
        return cands[int(self.r.choice(len(cands), p=p / p.sum()))]

    def _do_pass(
        self,
        team: int,
        slot: int,
        cpos: Vec,
        u: float,
        pres: float,
        under: bool,
        by: list[str],
        corner: bool = False,
        tags: list[str] | None = None,
    ) -> None:
        opp = 1 - team
        recv = self._choose_receiver(team, slot, cpos, u, corner)
        rpos = self.pos[team, recv]
        lead = (
            0.0 if corner else float(self.r.uniform(0, 3.0)) * self.clubs[team].identity.directness
        )
        end = self._clip(rpos + np.array([self.dir[team] * lead, 0.0]))
        d = float(np.linalg.norm(end - cpos))
        if corner:
            height = "high"
        else:
            height = (
                "high"
                if d > 28 and self.r.random() < 0.6
                else "low"
                if d > 18 and self.r.random() < 0.25
                else "ground"
            )
        ctx = self._pass_context(team, slot, cpos, end, height, recv)
        diff, factors = pass_difficulty(ctx)
        mods = self._mods(team)
        z = (
            3.05
            - 0.045 * diff
            + (self._attr(team, slot, "passing") - 68) / 50
            + mods.bias * 0.8
            - self._mods(opp).bias * 0.8
        )
        complete = self.r.random() < _sigmoid(z)
        speed = float(np.clip(22 + 1.35 * d + self.r.normal(0, 4), 20, 100))
        flight = d / (speed / 3.6)
        u_end = self._u(team, end[0])
        ptags = list(tags or [])
        if u_end - u >= 10:
            ptags.append("progressive")
        if u_end - u > 20 and ctx.lane_gaps and min(ctx.lane_gaps) < 6:
            ptags.append("through_ball")
        if d > 32:
            ptags.append("long_ball")
        if ctx.lateral_component > 0.85 and d > 28:
            ptags.append("switch")
        player = self.on_pitch[team][slot]
        foot = "right_foot" if player.foot == "right" else "left_foot"
        offside = "through_ball" in ptags and self.r.random() < 0.05
        outcome = "complete" if complete and not offside else "incomplete"
        idx = self._emit(
            EventType.PASS,
            team,
            slot,
            x=_r(cpos[0]),
            y=_r(cpos[1]),
            end_x=_r(end[0]),
            end_y=_r(end[1]),
            outcome=outcome,
            receiver_id=self._pid(team, recv),
            under_pressure=under,
            pressure_by=by,
            ball_speed_kmh=round(speed, 1),
            height=height,
            body_part=foot,
            tags=ptags,
            pass_difficulty=diff,
            difficulty_factors=factors,
        )
        dt = flight + 0.8
        peak = {"ground": 0.0, "low": 1.0, "high": 0.18 * d}[height]
        if outcome == "complete":
            self.pos[team, recv] = end
            self.ball = end.copy()
            self.carrier = (team, recv)
            self.just_received = True
            self.aerial = corner
            self.last_pass = (idx, self._pid(team, recv), self.t)
            self._finish(dt, {(team, slot), (team, recv)}, peak)
            return
        self.just_received = False
        self.last_pass = None
        if offside:
            self._emit(EventType.OFFSIDE, team, recv, t=self.t + flight, x=_r(end[0]), y=_r(end[1]))
            self.ball = end.copy()
            self._finish(dt, {(team, slot)}, peak)
            self._free_kick(opp, end)
            return
        if not corner and self.r.random() < 0.12:
            spot = end.copy()
            spot[1] = 0.0 if end[1] < 34 else PITCH_WIDTH
            self.ball = spot
            self._finish(dt, {(team, slot)}, peak)
            self._restart(opp, spot, EventType.THROW_IN, 4.0)
            return
        # Loose ball: the defender nearest the pass line gets there.
        icept = self._interceptor(team, cpos, end)
        target = self._closest_on_segment(self.pos[opp, icept], cpos, end)
        spot = self._reach(opp, icept, target, dt * 0.8)
        self.ball = spot.copy()
        etype = EventType.CLEARANCE if corner else EventType.INTERCEPTION
        self._emit(
            etype, opp, icept, t=self.t + flight * 0.8, x=_r(spot[0]), y=_r(spot[1]), outcome="won"
        )
        self._finish(dt * 0.8, {(team, slot), (opp, icept)}, peak)
        self._change_possession(opp, icept, "clearance" if corner else "interception")

    def _interceptor(self, team: int, start: Vec, end: Vec) -> int:
        opp = 1 - team
        best, best_d = 0, 1e9
        for s in range(11):
            if self.group[opp][s] == "GK" and self._u(team, end[0]) < 90:
                continue
            q = self._closest_on_segment(self.pos[opp, s], start, end)
            d = float(np.linalg.norm(self.pos[opp, s] - q))
            if d < best_d:
                best, best_d = s, d
        return best

    @staticmethod
    def _closest_on_segment(p: Vec, a: Vec, b: Vec) -> Vec:
        ab = b - a
        denom = float(ab @ ab)
        if denom < 1e-9:
            return a.copy()
        f = float(np.clip(((p - a) @ ab) / denom, 0.05, 0.95))
        return np.asarray(a + ab * f)

    # ---- carries, dribbles, tackles ------------------------------------------------------

    def _do_carry(
        self,
        team: int,
        slot: int,
        cpos: Vec,
        pres: float,
        under: bool,
        by: list[str],
        dribble: bool,
    ) -> None:
        opp = 1 - team
        mods = self._mods(team)
        dist = float(self.r.uniform(3, 12) * (0.6 + 0.4 * (1 - pres)))
        if dribble:
            dist = float(self.r.uniform(4, 9))
        ang = float(self.r.normal(0, 0.6)) - 0.004 * (cpos[1] - 34) * self.dir[team]
        end = self._clip(cpos + dist * np.array([self.dir[team] * math.cos(ang), math.sin(ang)]))
        etype = EventType.DRIBBLE if dribble else EventType.CARRY
        d_slot, d_dist = self._nearest(opp, cpos)
        lose = 0.03 + 0.30 * pres
        if dribble:
            lose = (
                0.55
                - 0.15
                + 0.45 * pres
                - (self._attr(team, slot, "first_touch") + self._attr(team, slot, "pace") - 135)
                / 400
            )
            lose = float(np.clip(lose, 0.1, 0.85)) * 0.8
        lose *= (
            self._attr(opp, d_slot, "tackling") / max(self._attr(team, slot, "first_touch"), 1)
        ) ** 0.7
        lose = float(np.clip(lose - mods.bias * 0.3 + self._mods(opp).bias * 0.3, 0.01, 0.9))
        if d_dist < 5.0 and self.r.random() < lose:
            self._emit(
                etype,
                team,
                slot,
                x=_r(cpos[0]),
                y=_r(cpos[1]),
                end_x=_r(cpos[0]),
                end_y=_r(cpos[1]),
                outcome="lost",
                under_pressure=under,
                pressure_by=by,
            )
            self._emit(EventType.TACKLE, opp, d_slot, x=_r(cpos[0]), y=_r(cpos[1]), outcome="won")
            self._reach(opp, d_slot, cpos, 1.0)
            if self.r.random() < 0.11:
                self._foul(opp, d_slot, team, cpos)
                return
            self._finish(1.0, {(team, slot), (opp, d_slot)})
            self._change_possession(opp, d_slot, "tackle")
            return
        self._emit(
            etype,
            team,
            slot,
            x=_r(cpos[0]),
            y=_r(cpos[1]),
            end_x=_r(end[0]),
            end_y=_r(end[1]),
            outcome="complete",
            under_pressure=under,
            pressure_by=by,
            tags=["progressive"] if abs(end[0] - cpos[0]) >= 10 else [],
        )
        self.pos[team, slot] = end
        self.ball = end.copy()
        self.just_received = False
        self.aerial = False
        self._finish(dist / float(self.r.uniform(3.2, 5.0)) + 0.5, {(team, slot)})

    def _foul(self, fouler_team: int, fouler: int, victim_team: int, spot: Vec) -> None:
        self._emit(
            EventType.FOUL, fouler_team, fouler, x=_r(spot[0]), y=_r(spot[1]), outcome="foul"
        )
        pid = self._pid(fouler_team, fouler)
        if self.r.random() < 0.18 and pid not in self.yellows:
            self.yellows.add(pid)
            self._emit(EventType.CARD, fouler_team, fouler, outcome="yellow")
        self._free_kick(victim_team, spot)

    def _free_kick(self, team: int, spot: Vec) -> None:
        spot = self._clip(spot)
        slot, _ = self._nearest(team, spot)
        delay = self._walk_delay(team, slot, spot, 4.0)
        self.pos[team, slot] = spot
        self.ball = spot.copy()
        self.carrier = (team, slot)
        self.just_received = False
        self.aerial = False
        self._emit(EventType.FREE_KICK, team, slot, x=_r(spot[0]), y=_r(spot[1]))
        self._maybe_subs()
        u = self._u(team, spot[0])
        if u > 78 and abs(spot[1] - 34) < 18 and self.r.random() < 0.3:
            self._finish(delay, {self.carrier})
            self._do_shot(team, slot, spot, 0.2, False, [], free_kick=True)
        else:
            self._finish(delay, {self.carrier})

    def _do_clearance(self, team: int, slot: int, cpos: Vec, under: bool, by: list[str]) -> None:
        opp = 1 - team
        u = self._u(team, cpos[0])
        land_u = min(u + float(self.r.uniform(25, 45)), 100.0)
        land = self._clip(np.array([self._x(team, land_u), cpos[1] + self.r.normal(0, 10)]))
        self._emit(
            EventType.CLEARANCE,
            team,
            slot,
            x=_r(cpos[0]),
            y=_r(cpos[1]),
            end_x=_r(land[0]),
            end_y=_r(land[1]),
            outcome="complete",
            under_pressure=under,
            pressure_by=by,
            ball_speed_kmh=round(float(self.r.uniform(60, 95)), 1),
            height="high",
            body_part="right_foot",
        )
        roll = self.r.random()
        self.ball = land
        flight = float(np.linalg.norm(land - cpos)) / 18.0
        if roll < 0.15:
            spot = land.copy()
            spot[1] = 0.0 if land[1] < 34 else PITCH_WIDTH
            self._finish(flight, {(team, slot)}, 8.0)
            self._restart(opp, spot, EventType.THROW_IN, 4.0)
            return
        who = opp if roll < 0.70 else team
        s, _ = self._nearest(who, land)
        self.ball = self._reach(who, s, land, flight + 0.5)
        self._finish(flight + 0.5, {(team, slot), (who, s)}, 8.0)
        if who == opp:
            self._change_possession(opp, s, "clearance")
        else:
            self.carrier = (team, s)
            self.just_received = False

    # ---- shooting ------------------------------------------------------------------------

    def _do_shot(
        self,
        team: int,
        slot: int,
        cpos: Vec,
        pres: float,
        under: bool,
        by: list[str],
        free_kick: bool = False,
    ) -> None:
        opp = 1 - team
        gx = PITCH_LENGTH if self.dir[team] == 1 else 0.0
        gy = 34.0
        dist = float(math.hypot(gx - cpos[0], gy - cpos[1]))
        v1 = np.array([gx - cpos[0], gy - 3.66 - cpos[1]])
        v2 = np.array([gx - cpos[0], gy + 3.66 - cpos[1]])
        theta = abs(math.atan2(v1[0] * v2[1] - v1[1] * v2[0], float(v1 @ v2)))
        head = self.aerial and self.r.random() < 0.7
        z = -0.85 - 0.14 * dist + 1.4 * theta - 0.6 * pres - (0.7 if head else 0.0)
        if free_kick:
            z -= 0.5
        xg = _sigmoid(z)
        pid = self._pid(team, slot)
        _, fin_star = self._star_factor(pid)
        fin = self._attr(team, slot, "finishing") / 70 * self._mods(team).finish * fin_star
        p_goal = float(np.clip(xg * fin, 0.0, 0.9))
        on_pitch_gk = 0
        speed = float(
            np.clip(
                40 + 0.7 * self._attr(team, slot, "shot_power") - 0.25 * dist + self.r.normal(0, 7),
                45,
                125,
            )
        )
        flight = dist / (speed / 3.6)
        roll = self.r.random()
        p_block = 0.22 + 0.15 * pres
        p_off = float(
            np.clip(0.45 - 0.2 * (self._attr(team, slot, "finishing") - 60) / 40, 0.2, 0.6)
        )
        rest = 1 - p_goal
        if roll < p_goal:
            outcome = "goal"
        elif roll < p_goal + rest * p_block:
            outcome = "blocked"
        elif roll < p_goal + rest * (p_block + p_off * (1 - p_block)):
            outcome = "off_target"
        else:
            outcome = "saved"
        player = self.on_pitch[team][slot]
        foot = "right_foot" if player.foot == "right" else "left_foot"
        tags = ["free_kick"] if free_kick else ["header"] if head else []
        if self.last_pass and self.last_pass[1] == pid and self.t - self.last_pass[2] < 8:
            self.events[self.last_pass[0]].tags.append("key_pass")
        end_y = (
            gy + float(self.r.uniform(-3.0, 3.0))
            if outcome in ("goal", "saved")
            else gy + float(self.r.choice([-1, 1])) * float(self.r.uniform(4.0, 9.0))
        )
        end = np.array([gx, end_y])
        if outcome == "blocked":
            b_slot, _ = self._nearest(opp, cpos)
            end = self._closest_on_segment(self.pos[opp, b_slot], cpos, np.array([gx, gy]))
        self._emit(
            EventType.SHOT,
            team,
            slot,
            x=_r(cpos[0]),
            y=_r(cpos[1]),
            end_x=_r(end[0]),
            end_y=_r(end[1]),
            outcome=outcome,
            under_pressure=under,
            pressure_by=by,
            ball_speed_kmh=round(speed, 1),
            height="ground",
            body_part="head" if head else foot,
            tags=tags,
            xg=round(xg, 3),
        )
        self.aerial = False
        self.just_received = False
        self.last_pass = None
        self.ball = end.copy()
        t_hit = self.t + flight
        if outcome == "goal":
            self.score[team] += 1
            assist = None
            for e in reversed(self.events[-6:]):
                if e.type == EventType.PASS and "key_pass" in e.tags and e.receiver_id == pid:
                    e.tags.append("assist")
                    assist = e.player_id
                    break
            self._emit(
                EventType.GOAL,
                team,
                slot,
                t=t_hit,
                x=_r(gx),
                y=_r(end_y),
                outcome="goal",
                tags=[f"score:{self.score[0]}-{self.score[1]}"]
                + ([f"assist:{assist}"] if assist else []),
            )
            self._finish(flight + 0.6, {(team, slot)})
            self._idle(20.0)
            self._reset_positions(opp)
            self._emit(EventType.KICK_OFF, opp, self.carrier[1], x=52.5, y=34.0)
            self._maybe_subs()
            self._finish(2.0, {self.carrier})
            return
        if outcome == "saved":
            self._emit(
                EventType.SAVE, opp, on_pitch_gk, t=t_hit, x=_r(gx), y=_r(end_y), outcome="saved"
            )
            self._finish(flight + 0.4, {(team, slot)})
            if self.r.random() < 0.28:
                self._corner(team)
            else:
                self.ball = self._reach(opp, 0, np.array([self._x(opp, 4.0), 34.0]), 2.5)
                self._change_possession(opp, 0, "save")
                self._finish(2.5, {self.carrier})
            return
        if outcome == "blocked":
            b_slot, _ = self._nearest(opp, end)
            end = self._reach(opp, b_slot, end, flight + 0.3)
            self.ball = end.copy()
            self._emit(
                EventType.BLOCK, opp, b_slot, t=t_hit, x=_r(end[0]), y=_r(end[1]), outcome="blocked"
            )
            self._finish(flight + 0.3, {(team, slot), (opp, b_slot)})
            if self.r.random() < 0.3:
                self._corner(team)
            else:
                self._change_possession(opp, b_slot, "block")
            return
        self._finish(flight + 0.8, {(team, slot)})
        self._restart(
            opp, np.array([self._x(opp, 5.0), 34.0]), None, 6.0, goalkeeper=True, cause="goal_kick"
        )

    def _corner(self, team: int) -> None:
        gx = PITCH_LENGTH if self.dir[team] == 1 else 0.0
        side = 0.0 if self.r.random() < 0.5 else PITCH_WIDTH
        spot = np.array([gx, side])
        slot, _ = self._nearest(team, spot)
        delay = self._walk_delay(team, slot, spot, 8.0)
        self.pos[team, slot] = spot
        self.ball = spot.copy()
        self.carrier = (team, slot)
        self._emit(EventType.CORNER, team, slot, x=_r(spot[0]), y=_r(spot[1]))
        # Attackers and defenders crowd the box.
        opp = 1 - team
        movers = sorted(
            (s for s in range(11) if s != slot and self.group[team][s] != "GK"),
            key=lambda s: -self._u(team, self.pos[team, s, 0]),
        )[:4]
        for k, s in enumerate(movers):
            self.pos[team, s] = self._clip(
                np.array([gx - self.dir[team] * float(self.r.uniform(5, 14)), 34 + (k - 1.5) * 4.5])
            )
        defenders = sorted(
            (s for s in range(11) if self.group[opp][s] != "GK"),
            key=lambda s: abs(self.pos[opp, s, 0] - gx),
        )[:5]
        for k, s in enumerate(defenders):
            self.pos[opp, s] = self._clip(
                np.array([gx - self.dir[team] * float(self.r.uniform(3, 11)), 34 + (k - 2) * 4.0])
            )
        self._maybe_subs()
        self._finish(delay, {self.carrier})
        self._do_pass(
            team,
            slot,
            spot,
            self._u(team, spot[0]),
            0.0,
            False,
            [],
            corner=True,
            tags=["corner", "cross"],
        )

    def run(self) -> Match:
        """Play both halves and return the finished match."""
        r = self.r
        kick_team = int(r.integers(0, 2))
        for period in (1, 2):
            self.period = period
            if period == 2:
                self.dir = [-1, 1]
                self.p2_start = self.t
                kick_team = 1 - kick_team
            end_at = (
                self.t + HALF + float(r.integers(60, 150) if period == 1 else r.integers(120, 270))
            )
            inj_at = self.t + float(r.uniform(300, 2400))
            injury_done = bool(r.random() > 0.35)
            self._emit(EventType.PERIOD_START, outcome=f"period_{period}")
            self._reset_positions(kick_team)
            self._emit(EventType.KICK_OFF, kick_team, self.carrier[1], x=52.5, y=34.0)
            self._finish(1.5, {self.carrier})
            while self.t < end_at:
                if not injury_done and self.t >= inj_at:
                    injury_done = True
                    team = int(r.integers(0, 2))
                    slot = int(r.integers(1, 11))
                    self._emit(EventType.INJURY_STOPPAGE, team, slot)
                    self._idle(45.0)
                    end_at += 45.0
                self._step()
            self._emit(EventType.PERIOD_END, outcome=f"period_{period}")
        self.tracking.add(
            self.t + 0.1, self.pos, self._ids(), (float(self.ball[0]), float(self.ball[1]))
        )
        home, away = self.sheets
        meta = MatchMeta(
            match_id=self.match_id,
            seed=self.seed,
            competition=self.league.name,
            matchday=self.matchday,
            venue=self.clubs[0].ground,
            kickoff_time="2026-11-07T15:00:00Z",
            weather=str(r.choice(["clear", "overcast", "light rain", "windy", "cold and dry"])),
            referee=str(r.choice(["A. Thornley", "M. Quade", "S. Pellew", "R. Dunmore"])),
            home=home,
            away=away,
        )
        script = [
            {
                "kind": a.kind,
                "team": self.clubs[a.team].code,
                "from_s": a.start,
                "to_s": a.end,
                "player_id": a.player_id,
            }
            for a in self.arcs
        ]
        players = {p.id: p for c in self.clubs for p in c.players}
        return Match(
            meta=meta,
            events=self.events,
            tracking=self.tracking,
            score=(self.score[0], self.score[1]),
            script=script,
            players=players,
        )


def _r(v: float) -> float:
    return round(float(v), 2)


def simulate_match(
    league: League, home: str, away: str, seed: int, match_id: str, matchday: int = 1
) -> Match:
    """Run a full 90 minutes (plus stoppage) and return events and tracking."""
    sim = MatchSimulator(league, home, away, seed, match_id, matchday)
    return sim.run()
