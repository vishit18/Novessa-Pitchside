"""Football events from tracks and the ball, by rules (docs/06 step 7). Output is the shared schema.

Possession is the nearest tracked player to the ball. A pass is possession moving between two
players of one team. A turnover is possession moving to the other team. A shot is a fast ball
heading for a goal. Every pass is scored by the same explainable difficulty model as the
synthetic engine (engine/difficulty.py).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import pairwise

import numpy as np
from numpy.typing import NDArray

from engine.difficulty import PassContext, pass_difficulty
from engine.schema import EventType, MatchEvent
from vision.ball import BallTrack
from vision.calibration import PITCH_LENGTH, PITCH_WIDTH
from vision.track import FPS, Track

POSSESSION_RADIUS_M = 2.6
MIN_SEGMENT_FRAMES = 3
GAP_FRAMES = 8  # a short loss of the ball does not end possession
MAX_PASS_GAP_FRAMES = 75  # more than 3 s between touches: ball was out or lost
MIN_PASS_M = 2.0
SHOT_SPEED_MS = 20.0  # 72 km/h
GOAL_HALF_WIDTH_M = 6.0  # a shot is on its way if it would cross the line this close to the posts
MS_TO_KMH = 3.6
MAX_PASS_SPEED_MS = 32.0  # 115 km/h: faster between two touches means a tracking jump
MAX_REPORTED_KMH = 115.0


@dataclass
class Segment:
    track: int
    team: str
    start: int
    end: int


def _positions(tracks: list[Track]) -> dict[int, list[tuple[Track, int]]]:
    """frame -> [(track, index into that track's arrays)] for tracked team players."""
    by_frame: dict[int, list[tuple[Track, int]]] = {}
    for t in tracks:
        if t.team == "OTH":
            continue
        for i, f in enumerate(t.frames):
            by_frame.setdefault(int(f), []).append((t, i))
    return by_frame


def possession_segments(
    tracks: list[Track], ball: BallTrack, by_frame: dict[int, list[tuple[Track, int]]]
) -> list[Segment]:
    """Runs of frames where one player is the nearest to the ball and close enough to play it."""
    owner: list[int | None] = []
    for k in range(len(ball.xy)):
        best: tuple[float, int] | None = None
        if ball.valid[k]:
            for t, i in by_frame.get(k, []):
                d = float(np.hypot(*(t.xy[i] - ball.xy[k])))
                if d <= POSSESSION_RADIUS_M and (best is None or d < best[0]):
                    best = (d, t.track_id)
        owner.append(best[1] if best else None)
    team = {t.track_id: t.team for t in tracks}
    segs: list[Segment] = []
    k = 0
    while k < len(owner):
        if owner[k] is None:
            k += 1
            continue
        tid, start, last = owner[k], k, k
        j = k + 1
        while j < len(owner) and j - last <= GAP_FRAMES:
            if owner[j] == tid:
                last = j
            elif owner[j] is not None:
                break
            j += 1
        if last - start + 1 >= MIN_SEGMENT_FRAMES and tid is not None:
            segs.append(Segment(tid, team[tid], start, last))
        k = max(last + 1, k + 1)
    return segs


def attacking_direction(tracks: list[Track]) -> dict[str, float]:
    """+1 if a team attacks towards x = 105, -1 towards x = 0. A team defends where it spends time
    without the ball; over a clip its average position sits in its own half."""
    out: dict[str, float] = {}
    for team in {t.team for t in tracks if t.team != "OTH"}:
        xs = np.concatenate([t.xy[:, 0] for t in tracks if t.team == team])
        out[team] = 1.0 if float(np.mean(xs)) < PITCH_LENGTH / 2 else -1.0
    return out


def _lane_gap(
    p: NDArray[np.float64], a: NDArray[np.float64], b: NDArray[np.float64]
) -> float | None:
    """Distance from p to segment ab, or None if p is not alongside the lane."""
    ab = b - a
    n = float(ab @ ab)
    if n < 1e-6:
        return None
    u = float((p - a) @ ab) / n
    if not 0.05 <= u <= 0.95:
        return None
    return float(np.linalg.norm(p - (a + u * ab)))


def build_events(
    tracks: list[Track], ball: BallTrack, match_id: str, start_s: float
) -> list[MatchEvent]:
    """Passes, turnovers and shots for the clip, as MatchEvent with source "vision"."""
    by_frame = _positions(tracks)
    segs = possession_segments(tracks, ball, by_frame)
    direction = attacking_direction(tracks)
    pos_at = {
        t.track_id: dict(zip(t.frames.tolist(), range(len(t.frames)), strict=True)) for t in tracks
    }
    by_id = {t.track_id: t for t in tracks}
    events: list[MatchEvent] = []

    def clock(frame: int) -> str:
        s = int(start_s + frame / FPS)
        return f"{s // 60:02d}:{s % 60:02d}"

    def pid(t: Track) -> str:
        return f"{t.team}-T{t.track_id:03d}"

    def add(frame: int, etype: EventType, **kw: object) -> None:
        events.append(
            MatchEvent(
                event_id=f"vis-{match_id}-{len(events) + 1:04d}",
                match_id=match_id,
                seq=len(events) + 1,
                t_match=round(frame / FPS, 2),
                period=1,
                clock=clock(frame),
                type=etype,
                source="vision",
                tags=["vision"],
                **kw,  # type: ignore[arg-type]
            )
        )

    for a, b in pairwise(segs):
        if a.track == b.track or b.start - a.end > MAX_PASS_GAP_FRAMES:
            continue
        ta, tb = by_id[a.track], by_id[b.track]
        start, end = ball.xy[a.end], ball.xy[b.start]
        dist = float(np.hypot(*(end - start)))
        if dist / (max(b.start - a.end, 1) / FPS) > MAX_PASS_SPEED_MS:
            continue  # the ball cannot have covered this distance in this time: a tracking jump
        window = slice(a.end, b.start + 1)
        flight = ball.speed_ms[window][ball.valid[window]]
        speed = float(np.percentile(flight, 85)) * MS_TO_KMH if len(flight) else None
        if speed is not None and speed > MAX_REPORTED_KMH:
            speed = None  # not believable as a pass; better to show nothing than a wrong number
        if a.team != b.team:
            if dist >= 4.0:
                add(
                    a.end,
                    EventType.PASS,
                    team=a.team,
                    player_id=pid(ta),
                    x=round(start[0], 2),
                    y=round(start[1], 2),
                    end_x=round(end[0], 2),
                    end_y=round(end[1], 2),
                    outcome="incomplete",
                    ball_speed_kmh=speed,
                )
            add(
                b.start,
                EventType.POSSESSION_CHANGE,
                team=b.team,
                player_id=pid(tb),
                x=round(end[0], 2),
                y=round(end[1], 2),
            )
            continue
        if dist < MIN_PASS_M:
            continue
        ia, ib = pos_at[a.track].get(a.end), pos_at[b.track].get(b.start)
        gaps: list[float] = []
        pressers: list[tuple[float, float]] = []
        marker = 10.0
        for t, i in by_frame.get(a.end, []):
            if t.team == a.team:
                continue
            g = _lane_gap(t.xy[i], start, end)
            if g is not None and g < 8.0:
                gaps.append(g)
            d = float(np.hypot(*(t.xy[i] - start)))
            if d < 3.0:
                pressers.append((d, 0.0))
        for t, i in by_frame.get(b.start, []):
            if t.team != a.team:
                marker = min(marker, float(np.hypot(*(t.xy[i] - end))))
        fwd = direction.get(a.team, 1.0) * (end[0] - start[0]) / dist
        ctx = PassContext(
            distance=dist,
            lane_gaps=gaps,
            pressers=pressers,
            receiver_marker_dist=marker,
            forward_component=max(-1.0, min(1.0, fwd)),
            lateral_component=min(1.0, abs(end[1] - start[1]) / dist),
        )
        score, factors = pass_difficulty(ctx)
        add(
            a.end,
            EventType.PASS,
            team=a.team,
            player_id=pid(ta),
            receiver_id=pid(tb),
            x=round(start[0], 2),
            y=round(start[1], 2),
            end_x=round(end[0], 2),
            end_y=round(end[1], 2),
            outcome="complete",
            ball_speed_kmh=speed,
            under_pressure=bool(pressers),
            pass_difficulty=round(score, 1),
            difficulty_factors=factors,
        )
        del ia, ib

    # Shots: a fast ball heading at a goal from within range, one per burst.
    last_shot = -10 * FPS
    for k in range(2, len(ball.xy) - 2):
        if not ball.valid[k] or ball.speed_ms[k] < SHOT_SPEED_MS or k - last_shot < 2 * FPS:
            continue
        v = (ball.xy[k + 2] - ball.xy[k - 2]) / (4 / FPS)
        if abs(v[0]) < 1.0:
            continue
        goal_x = PITCH_LENGTH if v[0] > 0 else 0.0
        t_hit = (goal_x - ball.xy[k, 0]) / v[0]
        y_hit = ball.xy[k, 1] + v[1] * t_hit
        near = abs(goal_x - ball.xy[k, 0]) < 38.0
        if 0 < t_hit < 3.0 and near and abs(y_hit - PITCH_WIDTH / 2) < GOAL_HALF_WIDTH_M + 2.0:
            shooter = next((s for s in reversed(segs) if s.end <= k), None)
            tr = by_id.get(shooter.track) if shooter else None
            add(
                k,
                EventType.SHOT,
                team=tr.team if tr else None,
                player_id=pid(tr) if tr else None,
                x=round(float(ball.xy[k, 0]), 2),
                y=round(float(ball.xy[k, 1]), 2),
                ball_speed_kmh=round(float(ball.speed_ms[k]) * MS_TO_KMH, 1),
                outcome="unknown",
            )
            last_shot = k
    events.sort(key=lambda e: e.t_match)
    for n, e in enumerate(events, 1):
        e.seq = n
        e.event_id = f"vis-{match_id}-{n:04d}"
    return events


def speed_bursts(tracks: list[Track], threshold_kmh: float = 24.0) -> list[dict[str, object]]:
    """Peak of each sprint above the threshold, for the "speed burst" overlay."""
    out: list[dict[str, object]] = []
    for t in tracks:
        if t.team == "OTH":
            continue
        kmh = t.speed_ms * MS_TO_KMH
        i = 0
        while i < len(kmh):
            if kmh[i] >= threshold_kmh:
                j = i
                while j < len(kmh) and kmh[j] >= threshold_kmh - 3:
                    j += 1
                peak = i + int(np.argmax(kmh[i:j]))
                if j - i >= int(0.6 * FPS):
                    out.append(
                        {
                            "frame": int(t.frames[peak]),
                            "track": t.track_id,
                            "team": t.team,
                            "kmh": round(float(kmh[peak]), 1),
                        }
                    )
                i = j
            else:
                i += 1
    return sorted(out, key=lambda b: int(b["frame"]))  # type: ignore[call-overload]


__all__ = ["build_events", "math", "possession_segments", "speed_bursts"]
