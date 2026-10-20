"""Tracking data: sparse snapshots from the simulator, interpolated to 10 Hz on demand.

A full match at 10 Hz is about 60k frames of 23 objects. Holding that as models is wasteful,
so we keep one snapshot per simulator step and build `TrackingFrame`s lazily.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

import numpy as np

from engine.schema import BallState, PlayerFrame, TrackingFrame

BALL_RADIUS = 0.11


@dataclass
class TrackingData:
    """Snapshots of all 22 players and the ball.

    `hold[i]` means snapshot i is a jump (kick-off reset); frames before it stay on snapshot i-1
    instead of interpolating across the pitch.
    """

    match_id: str
    times: list[float] = field(default_factory=list)
    positions: list[np.ndarray] = field(default_factory=list)  # each (2, 11, 2)
    ids: list[tuple[tuple[str, ...], tuple[str, ...]]] = field(default_factory=list)
    ball: list[tuple[float, float]] = field(default_factory=list)
    peak: list[float] = field(default_factory=list)  # ball apex height over the segment ending here
    hold: list[bool] = field(default_factory=list)
    # (2, 11) bool per snapshot: False once a player has been sent off.
    active: list[np.ndarray] = field(default_factory=list)

    def add(
        self,
        t: float,
        pos: np.ndarray,
        ids: tuple[tuple[str, ...], tuple[str, ...]],
        ball: tuple[float, float],
        peak: float = 0.0,
        hold: bool = False,
        active: np.ndarray | None = None,
    ) -> None:
        self.times.append(t)
        self.positions.append(pos.copy())
        self.ids.append(ids)
        self.ball.append(ball)
        self.peak.append(peak)
        self.hold.append(hold)
        self.active.append(np.ones((2, 11), dtype=bool) if active is None else active.copy())

    @property
    def duration(self) -> float:
        return self.times[-1] if self.times else 0.0

    def frame_at(self, t: float) -> TrackingFrame:
        """Interpolated frame at match time `t`."""
        times = self.times
        i = int(np.searchsorted(times, t, side="right")) - 1
        i = max(0, min(i, len(times) - 1))
        if i >= len(times) - 1 or self.hold[i + 1]:
            pos = self.positions[i]
            vel_scale = 0.0
            bx, by = self.ball[i]
            z = BALL_RADIUS
            nxt = i
            shown = self.active[i]
        else:
            nxt = i + 1
            span = times[nxt] - times[i]
            f = (t - times[i]) / span if span > 0 else 1.0
            pos = self.positions[i] + (self.positions[nxt] - self.positions[i]) * f
            vel_scale = 3.6 / span if span > 0 else 0.0
            b0, b1 = self.ball[i], self.ball[nxt]
            bx = b0[0] + (b1[0] - b0[0]) * f
            by = b0[1] + (b1[1] - b0[1]) * f
            z = BALL_RADIUS + self.peak[nxt] * 4.0 * f * (1.0 - f)
            # A player sent off disappears as soon as the segment that removes him starts.
            shown = self.active[i] & self.active[nxt]
        if vel_scale:
            speed = np.linalg.norm(self.positions[nxt] - self.positions[i], axis=2) * vel_scale
        else:
            speed = np.zeros((2, 11))
        players = [
            PlayerFrame(
                id=self.ids[i][team][s],
                x=round(float(pos[team, s, 0]), 2),
                y=round(float(pos[team, s, 1]), 2),
                v_kmh=round(float(speed[team, s]), 1),
            )
            for team in (0, 1)
            for s in range(11)
            if shown[team, s]
        ]
        return TrackingFrame(
            match_id=self.match_id,
            t_match=round(t, 2),
            ball=BallState(x=round(bx, 2), y=round(by, 2), z=round(z, 2)),
            players=players,
        )

    def iter_frames(self, hz: float = 10.0, start: float = 0.0) -> Iterator[TrackingFrame]:
        """Yield frames at `hz` from `start` to the end of the match."""
        k = int(start * hz)
        while k / hz <= self.duration:
            yield self.frame_at(k / hz)
            k += 1

    def player_distances_km(self) -> dict[str, float]:
        """Total distance per player id, summed over snapshot segments (holds excluded)."""
        totals: dict[str, float] = {}
        for i in range(len(self.times) - 1):
            if self.hold[i + 1]:
                continue
            step = np.linalg.norm(self.positions[i + 1] - self.positions[i], axis=2)
            shown = self.active[i] & self.active[i + 1]
            for team in (0, 1):
                for s in range(11):
                    if not shown[team, s]:
                        continue
                    pid = self.ids[i][team][s]
                    totals[pid] = totals.get(pid, 0.0) + float(step[team, s])
        return {k: v / 1000.0 for k, v in totals.items()}
