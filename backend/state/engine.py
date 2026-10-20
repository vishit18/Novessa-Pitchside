"""Deterministic state engine: events and tracking frames in, numbers and candidate moments out.

No language and no model calls in here. Everything the agents say about the match traces back
to a number computed by this module (docs/03 section 6). Works the same for synthetic events and
for vision events, since both use the same schema.
"""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Iterable
from typing import Literal

from backend.state.config import Thresholds, load_thresholds
from backend.state.models import (
    ControlChaos,
    Evidence,
    Moment,
    MomentKind,
    PlayerStats,
    Rhythm,
    StateSnapshot,
    TeamStats,
    Trigger,
)
from engine.schema import EventType, MatchEvent, MatchMeta, TrackingFrame

Output = Trigger | Moment

# Events that give the ball to ev.team. A failed pass or carry does not: the event that takes
# the ball (interception, tackle, possession_change, throw_in) does.
OWNERSHIP = {
    EventType.PASS,
    EventType.CARRY,
    EventType.DRIBBLE,
    EventType.SHOT,
    EventType.CLEARANCE,
    EventType.FREE_KICK,
    EventType.THROW_IN,
    EventType.CORNER,
    EventType.KICK_OFF,
    EventType.SAVE,
    EventType.BLOCK,
    EventType.INTERCEPTION,
    EventType.TACKLE,
    EventType.POSSESSION_CHANGE,
}
ON_BALL = {EventType.PASS, EventType.CARRY, EventType.DRIBBLE, EventType.SHOT}
PITCH_L = 105.0


def _clip(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


class StateEngine:
    """Feed it events and frames in match-time order; read snapshots and moments out."""

    def __init__(
        self, meta: MatchMeta, thresholds: Thresholds | None = None, check_every_s: float = 15.0
    ) -> None:
        self.meta = meta
        self.cfg = thresholds or load_thresholds()
        self.home, self.away = meta.home.code, meta.away.code
        self.teams = (self.home, self.away)
        self.check_every_s = check_every_s

        self.t = 0.0
        self.clock = "00:00"
        self.period = 1
        self.score = {self.home: 0, self.away: 0}

        self.poss_team: str | None = None
        self.poss_time = {t: 0.0 for t in self.teams}
        self._poss_window: deque[tuple[float, str, float]] = deque()
        self._spell_len = 0
        self._spells: deque[tuple[float, int]] = deque()
        self._flips: deque[float] = deque()
        self._fouls: deque[float] = deque()
        self._passes: deque[tuple[float, bool]] = deque()
        self._tempo: deque[float] = deque()
        self._tempo_baseline: float | None = None

        self._momentum = {t: 0.0 for t in self.teams}
        self._mom_hist: deque[tuple[float, float]] = deque()
        self._press_actions: dict[str, deque[float]] = {t: deque() for t in self.teams}
        self._own_half_passes: dict[str, deque[float]] = {t: deque() for t in self.teams}
        self._press_hist: deque[tuple[float, float]] = deque()

        self.players: dict[str, PlayerStats] = {}
        self.team_passes = {t: 0 for t in self.teams}
        self.team_stats = {t: TeamStats() for t in self.teams}
        self.sent_off = {t: 0 for t in self.teams}
        self._goals_by: dict[str, int] = {}
        self._pending_key: dict[str, str] = {}
        self._longest_pass = 0.0
        self._fastest = 0.0
        self._sprinting: dict[str, bool] = {}
        self._dist_marks: dict[str, int] = {}
        self._last_frame_t: float | None = None

        self._moment_n = 0
        self._last_moment: dict[tuple[str, str | None], float] = {}
        self._next_check = check_every_s
        self._last_extreme: str | None = None
        self._first_goal_done = False

    # ---- geometry ------------------------------------------------------------------------

    def _u(self, team: str, x: float) -> float:
        """Distance from the team's own goal line along the pitch, 0 to 105."""
        attacks_right = (team == self.home) == (self.period == 1)
        return x if attacks_right else PITCH_L - x

    def _other(self, team: str) -> str:
        return self.away if team == self.home else self.home

    def player(self, pid: str) -> PlayerStats:
        if pid not in self.players:
            self.players[pid] = PlayerStats(player_id=pid, team=pid.split("-")[0])
        return self.players[pid]

    # ---- snapshot ------------------------------------------------------------------------

    def _prune(self, dq: deque[float], window: float) -> None:
        while dq and dq[0] < self.t - window:
            dq.popleft()

    def momentum(self) -> float:
        return math.tanh((self._momentum[self.home] - self._momentum[self.away]) / 20.0) * 100.0

    def pressure(self) -> dict[str, float]:
        w = self.cfg.windows.pressure_s
        out = {}
        for team in self.teams:
            self._prune(self._press_actions[team], w)
            opp = self._other(team)
            self._prune(self._own_half_passes[opp], w)
            ratio = len(self._press_actions[team]) / max(len(self._own_half_passes[opp]), 1)
            out[team] = round(_clip(ratio / 6.0) * 100.0, 1)
        return out

    def possession_5min(self) -> dict[str, float]:
        w = self.cfg.windows.possession_s
        while self._poss_window and self._poss_window[0][0] < self.t - w:
            self._poss_window.popleft()
        tot = {t: 0.0 for t in self.teams}
        for _, team, dt in self._poss_window:
            tot[team] += dt
        s = sum(tot.values())
        return {t: round(100.0 * tot[t] / s, 1) if s else 50.0 for t in self.teams}

    def possession_match(self) -> dict[str, float]:
        s = sum(self.poss_time.values())
        return {t: round(100.0 * self.poss_time[t] / s, 1) if s else 50.0 for t in self.teams}

    def control_chaos(self) -> ControlChaos:
        w = self.cfg.windows.control_s
        elapsed = max(min(w, self.t), 30.0)
        self._prune(self._flips, w)
        self._prune(self._fouls, w)
        while self._spells and self._spells[0][0] < self.t - w:
            self._spells.popleft()
        while self._passes and self._passes[0][0] < self.t - w:
            self._passes.popleft()
        avg_len = sum(n for _, n in self._spells) / len(self._spells) if self._spells else 4.0
        flips_pm = (len(self._flips) + len(self._fouls)) / (elapsed / 60.0)
        comp = sum(1 for _, ok in self._passes if ok) / len(self._passes) if self._passes else 0.8
        value = 100.0 * (
            0.45 * _clip(avg_len / 10.0)
            + 0.35 * (1.0 - _clip(flips_pm / 8.0))
            + 0.20 * _clip((comp - 0.5) / 0.4)
        )
        label = "controlled" if value >= 60 else "chaotic" if value <= 40 else "balanced"
        return ControlChaos(value=round(value, 1), label=label)

    def rhythm(self) -> Rhythm:
        w = self.cfg.windows.rhythm_s
        self._prune(self._tempo, w)
        elapsed = max(min(w, self.t), 30.0)
        epm = len(self._tempo) / (elapsed / 60.0)
        base = self._tempo_baseline
        broken = (
            base is not None
            and self.t >= self.cfg.moments.min_time_s
            and abs(epm - base) / base > self.cfg.moments.rhythm_break_ratio
        )
        recent = [n for _, n in self._spells]
        avg_len = sum(recent) / len(recent) if recent else 0.0
        return Rhythm(
            events_per_min=round(epm, 1), avg_possession_len=round(avg_len, 1), broken=broken
        )

    def snapshot(self) -> StateSnapshot:
        return StateSnapshot(
            t_match=round(self.t, 2),
            clock=self.clock,
            period=self.period,
            score=dict(self.score),
            possession_match=self.possession_match(),
            possession_5min=self.possession_5min(),
            momentum=round(self.momentum(), 1),
            pressure=self.pressure(),
            control_chaos=self.control_chaos(),
            rhythm=self.rhythm(),
            team_stats={t: s.model_copy() for t, s in self.team_stats.items()},
        )

    # ---- moments -------------------------------------------------------------------------

    def _moment(
        self,
        kind: MomentKind,
        significance: float,
        summary: str,
        team: str | None = None,
        players: list[str] | None = None,
        evidence: list[Evidence] | None = None,
        cooldown: bool = True,
        card: Literal["yellow", "red"] | None = None,
        staff: bool = False,
    ) -> Moment | None:
        key = (kind, team)
        last = self._last_moment.get(key)
        if cooldown and last is not None and self.t - last < self.cfg.moments.cooldown_s:
            return None
        self._last_moment[key] = self.t
        self._moment_n += 1
        return Moment(
            moment_id=f"mom-{self.meta.match_id}-{self._moment_n:04d}",
            kind=kind,
            t_match=round(self.t, 2),
            clock=self.clock,
            significance=round(_clip(significance / 100.0) * 100.0, 1),
            team=team,
            player_ids=players or [],
            summary=summary,
            evidence=evidence or [],
            card=card,
            staff=staff,
            snapshot=self.snapshot(),
        )

    def _periodic_checks(self) -> list[Output]:
        out: list[Output] = []
        m = self.cfg.moments
        mom = self.momentum()
        self._mom_hist.append((self.t, mom))
        while self._mom_hist and self._mom_hist[0][0] < self.t - m.momentum_swing_window_s:
            self._mom_hist.popleft()
        press = self.pressure()
        diff = press[self.home] - press[self.away]
        self._press_hist.append((self.t, diff))
        while self._press_hist and self._press_hist[0][0] < self.t - 120:
            self._press_hist.popleft()
        cc = self.control_chaos()
        rh = self.rhythm()
        base = self._tempo_baseline
        if base is None and self.t >= self.cfg.windows.rhythm_s:
            self._tempo_baseline = rh.events_per_min
        elif base is not None:
            self._tempo_baseline = 0.97 * base + 0.03 * rh.events_per_min
        if self.t < m.min_time_s:
            return out

        start_mom = self._mom_hist[0][1]
        delta = mom - start_mom
        if abs(delta) >= m.momentum_swing:
            team = self.home if delta > 0 else self.away
            mo = self._moment(
                "momentum_swing",
                50 + 40 * _clip((abs(delta) - m.momentum_swing) / (100 - m.momentum_swing)),
                f"Momentum moved {abs(delta):.0f} points toward {team} in about "
                f"{self.cfg.moments.momentum_swing_window_s / 60:.0f} minutes.",
                team=team,
                evidence=[
                    Evidence(metric="momentum", value=round(mom, 1)),
                    Evidence(metric="momentum_change", value=round(delta, 1), window="2min"),
                ],
            )
            if mo:
                out.append(mo)

        d_press = diff - self._press_hist[0][1]
        if abs(d_press) >= m.pressure_shift:
            team = self.home if d_press > 0 else self.away
            mo = self._moment(
                "pressure_shift",
                45 + 40 * _clip((abs(d_press) - m.pressure_shift) / 50),
                f"{team} are pressing noticeably harder than two minutes ago "
                f"(pressure index {press[team]:.0f}).",
                team=team,
                evidence=[
                    Evidence(metric="pressure_index", value=press[team], window="5min"),
                    Evidence(metric="pressure_gap_change", value=round(d_press, 1), window="2min"),
                ],
            )
            if mo:
                out.append(mo)

        if cc.label != "balanced" and cc.label != self._last_extreme:
            first = self._last_extreme is None
            self._last_extreme = cc.label
            if not first:
                mo = self._moment(
                    "control_chaos_flip",
                    45,
                    f"The match has turned {cc.label}.",
                    evidence=[Evidence(metric="control_chaos", value=cc.value, window="3min")],
                )
                if mo:
                    out.append(mo)

        if rh.broken and base:
            ratio = abs(rh.events_per_min - base) / base
            mo = self._moment(
                "rhythm_break",
                35 + 30 * _clip(ratio - m.rhythm_break_ratio),
                f"Tempo is {'up' if rh.events_per_min > base else 'down'} on the match norm "
                f"({rh.events_per_min:.0f} on-ball actions a minute against about {base:.0f}).",
                evidence=[
                    Evidence(metric="events_per_min", value=rh.events_per_min, window="2min")
                ],
            )
            if mo:
                out.append(mo)
        return out

    # ---- ingest: events ------------------------------------------------------------------

    def ingest(self, events: Iterable[MatchEvent]) -> list[Output]:
        out: list[Output] = []
        for ev in events:
            out.extend(self.ingest_event(ev))
        return out

    def ingest_event(self, ev: MatchEvent) -> list[Output]:
        """Process one event and return the triggers and moments it produced."""
        out: list[Output] = []
        dt = max(ev.t_match - self.t, 0.0)
        self._momentum = {
            t: v * 0.5 ** (dt / self.cfg.windows.momentum_half_life_s)
            for t, v in self._momentum.items()
        }
        if self.poss_team and dt > 0:
            self.poss_time[self.poss_team] += dt
            self._poss_window.append((ev.t_match, self.poss_team, dt))
        self.t, self.clock, self.period = ev.t_match, ev.clock, ev.period

        handler = {
            EventType.PASS: self._on_pass,
            EventType.CARRY: self._on_carry,
            EventType.DRIBBLE: self._on_carry,
            EventType.SHOT: self._on_shot,
            EventType.GOAL: self._on_goal,
            EventType.TACKLE: self._on_win_ball,
            EventType.INTERCEPTION: self._on_win_ball,
            EventType.PRESSURE: self._on_pressure,
            EventType.CORNER: self._on_corner,
            EventType.FREE_KICK: self._on_free_kick,
            EventType.FOUL: self._on_foul,
            EventType.CARD: self._on_card,
            EventType.OFFSIDE: self._on_offside,
        }.get(ev.type)
        if handler:
            out.extend(handler(ev))

        if ev.type in ON_BALL:
            self._tempo.append(ev.t_match)
            if self.poss_team:
                self._spell_len += 1
        if ev.type in OWNERSHIP and ev.team and not self._failed(ev):
            if self.poss_team and ev.team != self.poss_team:
                self._flips.append(ev.t_match)
                self._spells.append((ev.t_match, self._spell_len))
                self._spell_len = 0
            self.poss_team = ev.team

        if self.t >= self._next_check:
            self._next_check = self.t + self.check_every_s
            out.extend(self._periodic_checks())
        return out

    @staticmethod
    def _failed(ev: MatchEvent) -> bool:
        return ev.outcome in ("incomplete", "lost") and ev.type in (
            EventType.PASS,
            EventType.CARRY,
            EventType.DRIBBLE,
        )

    def _on_pass(self, ev: MatchEvent) -> list[Output]:
        out: list[Output] = []
        if not ev.player_id or not ev.team:
            return out
        p = self.player(ev.player_id)
        ok = ev.outcome == "complete"
        p.passes += 1
        p.passes_complete += int(ok)
        diff = ev.pass_difficulty or 0.0
        p.difficulty_sum += diff
        self.team_passes[ev.team] += 1
        self._passes.append((ev.t_match, ok))
        length = _dist(ev)
        p.longest_pass_m = max(p.longest_pass_m, length)
        if ok:
            p.hardest_pass = max(p.hardest_pass, diff)

        x0 = ev.x if ev.x is not None else 52.5
        if self._u(ev.team, x0) <= PITCH_L / 2:
            self._own_half_passes[ev.team].append(ev.t_match)
        if (
            ok
            and ev.end_x is not None
            and ev.x is not None
            and self._u(ev.team, ev.end_x) > 70 >= self._u(ev.team, ev.x)
        ):
            self._momentum[ev.team] += 1.0
        if "progressive" in ev.tags and ok:
            self._momentum[ev.team] += 0.3
        if "key_pass" in ev.tags and ev.receiver_id:
            self._pending_key[ev.receiver_id] = ev.player_id

        tr = self.cfg.triggers
        if diff >= tr.pass_difficulty:
            out.append(
                Trigger(
                    kind="pass_difficulty",
                    t_match=ev.t_match,
                    team=ev.team,
                    player_id=ev.player_id,
                    payload={
                        "difficulty": diff,
                        "distance_m": round(length, 1),
                        "ball_speed_kmh": ev.ball_speed_kmh or 0.0,
                        "outcome": ev.outcome or "",
                    },
                )
            )
        if ok and diff >= self.cfg.moments.standout_pass_difficulty:
            mo = self._moment(
                "standout_action",
                55 + 30 * _clip((diff - 85) / 15),
                f"{ev.player_id} completed a pass rated {diff:.0f} for difficulty.",
                team=ev.team,
                players=[ev.player_id],
                evidence=[Evidence(metric="pass_difficulty", value=diff)],
                cooldown=False,
            )
            if mo:
                out.append(mo)
        if length > tr.long_pass_m and length > self._longest_pass:
            if self._longest_pass > 0:
                out.append(self._milestone(ev, "longest_pass", length))
            self._longest_pass = length
        elif length > self._longest_pass:
            self._longest_pass = length
        for n in self.cfg.milestones.team_pass_counts:
            if self.team_passes[ev.team] == n:
                out.append(self._milestone(ev, "team_passes", n, player=False))
        for n in self.cfg.milestones.player_pass_counts:
            if p.passes == n:
                out.append(self._milestone(ev, "player_passes", n))
        return out

    def _milestone(self, ev: MatchEvent, name: str, value: float, player: bool = True) -> Trigger:
        return Trigger(
            kind="milestone",
            t_match=ev.t_match,
            team=ev.team,
            player_id=ev.player_id if player else None,
            payload={"milestone": name, "value": round(value, 1)},
        )

    def _on_carry(self, ev: MatchEvent) -> list[Output]:
        if not ev.player_id or not ev.team:
            return []
        won = ev.outcome == "complete"
        if ev.type == EventType.DRIBBLE:
            p = self.player(ev.player_id)
            p.duels_won += int(won)
            p.duels_lost += int(not won)
        if (
            won
            and ev.x is not None
            and ev.end_x is not None
            and self._u(ev.team, ev.end_x) > 70 >= self._u(ev.team, ev.x)
        ):
            self._momentum[ev.team] += 1.0
        return []

    def _on_win_ball(self, ev: MatchEvent) -> list[Output]:
        if not ev.team:
            return []
        self._press_actions[ev.team].append(ev.t_match)
        if ev.type == EventType.TACKLE and ev.player_id:
            self.player(ev.player_id).duels_won += 1
        if ev.x is not None and self._u(ev.team, ev.x) > PITCH_L / 2:
            self._momentum[ev.team] += 0.8
        return []

    def _on_pressure(self, ev: MatchEvent) -> list[Output]:
        if ev.team:
            self._press_actions[ev.team].append(ev.t_match)
        return []

    def _on_offside(self, ev: MatchEvent) -> list[Output]:
        """Count it against the team that was caught offside."""
        if ev.team:
            self.team_stats[ev.team].offsides += 1
        return []

    def _on_corner(self, ev: MatchEvent) -> list[Output]:
        if ev.team:
            self._momentum[ev.team] += 1.5
            self.team_stats[ev.team].corners += 1
        return []

    def _on_free_kick(self, ev: MatchEvent) -> list[Output]:
        if not ev.team:
            return []
        if "penalty" not in ev.tags:
            self.team_stats[ev.team].free_kicks += 1
            return []
        self.team_stats[ev.team].penalties += 1
        self._momentum[ev.team] += 6.0
        mo = self._moment(
            "penalty",
            75,
            f"{ev.player_id} steps up to take a penalty for {ev.team}.",
            team=ev.team,
            players=[ev.player_id] if ev.player_id else [],
            evidence=[Evidence(metric="penalties", value=self.team_stats[ev.team].penalties)],
            cooldown=False,
        )
        return [mo] if mo else []

    def _on_foul(self, ev: MatchEvent) -> list[Output]:
        self._fouls.append(ev.t_match)
        if ev.team:
            self.team_stats[ev.team].fouls += 1
        if ev.player_id:
            self.player(ev.player_id).fouls += 1
        return []

    def _on_card(self, ev: MatchEvent) -> list[Output]:
        if not ev.team:
            return []
        card: Literal["yellow", "red"] = "red" if ev.outcome == "red" else "yellow"
        staff = "manager" in ev.tags
        second_yellow = "second_yellow" in ev.tags
        if not staff:
            stats = self.team_stats[ev.team]
            if card == "yellow":
                stats.yellows += 1
            else:
                stats.reds += 1
                self.sent_off[ev.team] += 1
            if ev.player_id:
                p = self.player(ev.player_id)
                if card == "yellow":
                    p.yellows += 1
                else:
                    p.reds += 1
        if second_yellow and card == "yellow":
            return []  # the red that follows is the moment
        if staff:
            summary = f"{ev.team} manager was shown a {card} card."
            significance = 45.0 if card == "yellow" else 70.0
        elif card == "red":
            men = 11 - self.sent_off[ev.team]
            how = "a second yellow" if second_yellow else "a straight red"
            summary = f"{ev.player_id} was sent off for {how}. {ev.team} are down to {men} men."
            significance = 85.0
        else:
            summary = f"{ev.player_id} was shown a yellow card."
            significance = 50.0
        mo = self._moment(
            "card",
            significance,
            summary,
            team=ev.team,
            players=[ev.player_id] if ev.player_id else [],
            evidence=[Evidence(metric="men_on_pitch", value=11 - self.sent_off[ev.team])],
            cooldown=False,
            card=card,
            staff=staff,
        )
        return [mo] if mo else []

    def _on_shot(self, ev: MatchEvent) -> list[Output]:
        out: list[Output] = []
        if not ev.player_id or not ev.team:
            return out
        p = self.player(ev.player_id)
        xg = ev.xg or 0.0
        p.shots += 1
        p.xg += xg
        self.team_stats[ev.team].shots += 1
        passer = self._pending_key.pop(ev.player_id, None)
        if passer:
            self.player(passer).xa += xg
        self._momentum[ev.team] += 2.0 + 12.0 * xg
        speed = ev.ball_speed_kmh or 0.0
        p.top_shot_kmh = max(p.top_shot_kmh, speed)
        if speed >= self.cfg.triggers.shot_speed_kmh:
            out.append(
                Trigger(
                    kind="shot_speed",
                    t_match=ev.t_match,
                    team=ev.team,
                    player_id=ev.player_id,
                    payload={"speed_kmh": speed, "xg": round(xg, 3), "outcome": ev.outcome or ""},
                )
            )
        if ev.outcome != "goal" and xg >= self.cfg.moments.big_chance_xg:
            mo = self._moment(
                "big_chance",
                40 + 60 * xg,
                f"{ev.player_id} had a chance worth {xg:.2f} xG ({ev.outcome}).",
                team=ev.team,
                players=[ev.player_id],
                evidence=[Evidence(metric="xg", value=round(xg, 3))],
                cooldown=False,
            )
            if mo:
                out.append(mo)
        return out

    def _on_goal(self, ev: MatchEvent) -> list[Output]:
        out: list[Output] = []
        if not ev.team or not ev.player_id:
            return out
        self.score[ev.team] += 1
        self._momentum[ev.team] += 10.0
        n = self._goals_by.get(ev.player_id, 0) + 1
        self._goals_by[ev.player_id] = n
        if not self._first_goal_done:
            self._first_goal_done = True
            out.append(self._milestone(ev, "first_goal", 1))
        if n >= 2:
            out.append(self._milestone(ev, "brace" if n == 2 else "hat_trick", n))
        mo = self._moment(
            "goal",
            100,
            f"{ev.player_id} scored for {ev.team}. It is {self.score[self.home]}-"
            f"{self.score[self.away]}.",
            team=ev.team,
            players=[ev.player_id],
            evidence=[
                Evidence(metric="score_home", value=self.score[self.home]),
                Evidence(metric="score_away", value=self.score[self.away]),
            ],
            cooldown=False,
        )
        if mo:
            out.append(mo)
        return out

    # ---- ingest: tracking frames ---------------------------------------------------------

    def ingest_frame(self, frame: TrackingFrame) -> list[Output]:
        """Update distance and speed per player, and fire sprint and distance triggers."""
        out: list[Output] = []
        dt = 0.0 if self._last_frame_t is None else max(frame.t_match - self._last_frame_t, 0.0)
        self._last_frame_t = frame.t_match
        tr = self.cfg.triggers
        for pf in frame.players:
            p = self.player(pf.id)
            p.distance_km += pf.v_kmh / 3.6 * dt / 1000.0
            if pf.v_kmh > p.top_speed_kmh:
                p.top_speed_kmh = pf.v_kmh
            if pf.v_kmh >= tr.sprint_kmh and not self._sprinting.get(pf.id, False):
                self._sprinting[pf.id] = True
                p.sprints += 1
                rank = 1 + sum(1 for q in self.players.values() if q.top_speed_kmh > pf.v_kmh)
                out.append(
                    Trigger(
                        kind="speed_burst",
                        t_match=frame.t_match,
                        team=p.team,
                        player_id=pf.id,
                        payload={"speed_kmh": pf.v_kmh, "rank_in_match": rank},
                    )
                )
                if pf.v_kmh > self._fastest:
                    if self._fastest > 0 and frame.t_match >= 600:
                        out.append(
                            Trigger(
                                kind="milestone",
                                t_match=frame.t_match,
                                team=p.team,
                                player_id=pf.id,
                                payload={"milestone": "fastest_sprint", "value": pf.v_kmh},
                            )
                        )
                    self._fastest = pf.v_kmh
            elif pf.v_kmh < tr.sprint_reset_kmh:
                self._sprinting[pf.id] = False
            marks = int(p.distance_km // tr.distance_step_km)
            if marks > self._dist_marks.get(pf.id, 0):
                self._dist_marks[pf.id] = marks
                out.append(
                    Trigger(
                        kind="distance_milestone",
                        t_match=frame.t_match,
                        team=p.team,
                        player_id=pf.id,
                        payload={"km": round(marks * tr.distance_step_km, 1)},
                    )
                )
        return out


def _dist(ev: MatchEvent) -> float:
    if None in (ev.x, ev.y, ev.end_x, ev.end_y):
        return 0.0
    assert ev.x is not None and ev.y is not None
    assert ev.end_x is not None and ev.end_y is not None
    return math.hypot(ev.end_x - ev.x, ev.end_y - ev.y)
