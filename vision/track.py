"""Tracking, team assignment and speeds from cached detections (docs/06 steps 2, 3, 6)."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray
from scipy.cluster.vq import kmeans2
from scipy.optimize import linear_sum_assignment
from scipy.signal import savgol_filter

from vision.calibration import PITCH_LENGTH, PITCH_WIDTH, PitchCalibration

FPS = 25
MARGIN_M = 2.5  # people further outside the lines than this are staff, subs or spectators
MIN_TRACK_FRAMES = 25
MAX_SPEED_MS = 11.5  # faster than this on foot is noise
SPEED_WINDOW = 25  # frames (1 s) for the speed estimate


@dataclass
class Track:
    """One tracked person, sampled on the frames where they were seen."""

    track_id: int
    frames: NDArray[np.int32]
    xy: NDArray[np.float64]  # metres, origin bottom-left, smoothed
    box: NDArray[np.float32]  # pixels on the original frame, x1 y1 x2 y2
    colour: NDArray[np.float32]  # median shirt colour, Lab
    speed_ms: NDArray[np.float64] = field(default_factory=lambda: np.zeros(0))
    team: str = "OTH"


def foot_points(boxes: NDArray[np.float32]) -> NDArray[np.float64]:
    """Where a person touches the ground: bottom middle of the box."""
    return np.c_[(boxes[:, 0] + boxes[:, 2]) / 2, boxes[:, 3]].astype(np.float64)


def on_pitch(xy: NDArray[np.float64], margin: float = MARGIN_M) -> NDArray[np.bool_]:
    return (
        (xy[:, 0] > -margin)
        & (xy[:, 0] < PITCH_LENGTH + margin)
        & (xy[:, 1] > -margin)
        & (xy[:, 1] < PITCH_WIDTH + margin)
    )


HIGH_SCORE = 0.5
MAX_LOST_FRAMES = 40
BASE_GATE_M = 1.3  # how far a person can plausibly move between two frames, plus slack
GROW_GATE_M = 0.45  # extra reach for each frame a track has been unseen
MAX_GATE_M = 7.0
COLOUR_WEIGHT = 0.04  # metres of cost per unit of Lab colour difference


@dataclass
class _Live:
    id: int
    xy: NDArray[np.float64]
    vel: NDArray[np.float64]
    last: int
    colour: NDArray[np.float32]
    rows: list[int] = field(default_factory=list)


def associate(
    frame_idx: NDArray[np.int32],
    xy: NDArray[np.float64],
    scores: NDArray[np.float32],
    colours: NDArray[np.float32],
    idx: NDArray[np.int64],
) -> dict[int, list[int]]:
    """ByteTrack-style tracking in pitch space. Returns track id -> detection rows.

    Stage one matches confident detections to tracks, stage two lets weaker detections rescue the
    tracks that are still unmatched. Cost is distance in metres from where a constant-velocity
    guess puts the person, plus a small penalty for a different shirt colour.
    """
    live: list[_Live] = []
    done: list[_Live] = []
    next_id = 1
    by_frame: dict[int, list[int]] = {}
    for i in idx:
        by_frame.setdefault(int(frame_idx[i]), []).append(int(i))

    def match(
        tracks: list[_Live], dets: list[int], k: int, gate_scale: float
    ) -> list[tuple[int, int]]:
        if not tracks or not dets:
            return []
        pred = np.array([t.xy + t.vel * (k - t.last) for t in tracks])
        pos = xy[dets]
        dist = np.linalg.norm(pred[:, None, :] - pos[None], axis=2)
        col = np.linalg.norm(
            np.array([t.colour for t in tracks])[:, None, :] - colours[dets][None], axis=2
        )
        cost = dist + COLOUR_WEIGHT * col
        gates = np.array(
            [
                min(MAX_GATE_M, BASE_GATE_M + GROW_GATE_M * (k - t.last - 1)) * gate_scale
                for t in tracks
            ]
        )
        cost[dist > gates[:, None]] = 1e6
        rows, cols = linear_sum_assignment(cost)
        return [(int(r), int(c)) for r, c in zip(rows, cols, strict=True) if cost[r, c] < 1e5]

    for k in range(int(frame_idx.max()) + 1):
        dets = by_frame.get(k, [])
        high = [d for d in dets if scores[d] >= HIGH_SCORE]
        low = [d for d in dets if scores[d] < HIGH_SCORE]
        matched_tracks: set[int] = set()
        used: set[int] = set()
        for stage_dets, scale in ((high, 1.0), (low, 0.7)):
            free = [t for j, t in enumerate(live) if j not in matched_tracks]
            free_ids = [j for j in range(len(live)) if j not in matched_tracks]
            avail = [d for d in stage_dets if d not in used]
            for r, c in match(free, avail, k, scale):
                t, d = live[free_ids[r]], avail[c]
                dt = max(k - t.last, 1)
                t.vel = 0.7 * t.vel + 0.3 * (xy[d] - t.xy) / dt
                t.xy, t.last = xy[d], k
                t.colour = 0.9 * t.colour + 0.1 * colours[d]
                t.rows.append(d)
                matched_tracks.add(free_ids[r])
                used.add(d)
        for d in high:
            if d not in used:
                live.append(_Live(next_id, xy[d], np.zeros(2), k, colours[d].copy(), [d]))
                next_id += 1
        still: list[_Live] = []
        for t in live:
            (still if k - t.last <= MAX_LOST_FRAMES else done).append(t)
        live = still
    return {t.id: t.rows for t in done + live}


def track_people(
    frame_idx: NDArray[np.int32],
    boxes: NDArray[np.float32],
    scores: NDArray[np.float32],
    colours: NDArray[np.float32],
    cal: PitchCalibration,
) -> list[Track]:
    """Track people standing on or beside the pitch, then smooth and label them."""
    xy_all = cal.to_pitch(foot_points(boxes))
    keep = on_pitch(xy_all) & ((boxes[:, 3] - boxes[:, 1]) >= 14)
    per_track = associate(frame_idx, xy_all, scores, colours, np.flatnonzero(keep))
    tracks = []
    for tid, rows in per_track.items():
        if len(rows) < MIN_TRACK_FRAMES:
            continue
        rows_a = np.array(sorted(rows, key=lambda i: frame_idx[i]))
        tracks.append(
            Track(
                track_id=tid,
                frames=frame_idx[rows_a],
                xy=xy_all[rows_a],
                box=boxes[rows_a],
                colour=np.median(colours[rows_a], axis=0),
            )
        )
    for t in tracks:
        _smooth(t)
    assign_teams(tracks)
    return sorted(tracks, key=lambda t: t.track_id)


def _smooth(t: Track) -> None:
    """Fill short gaps, smooth positions with Savitzky-Golay, and derive speed."""
    f = t.frames
    full = np.arange(f[0], f[-1] + 1)
    x = np.interp(full, f, t.xy[:, 0])
    y = np.interp(full, f, t.xy[:, 1])
    win = min(SPEED_WINDOW, len(full) - (1 - len(full) % 2))
    if win >= 5:
        # Differentiating amplifies jitter, so speed uses a longer window than position does.
        x, y = savgol_filter(x, min(win, 11), 2), savgol_filter(y, min(win, 11), 2)
        vx, vy = savgol_filter(x, win, 2, deriv=1) * FPS, savgol_filter(y, win, 2, deriv=1) * FPS
    else:
        vx = vy = np.zeros_like(x)
    speed = np.minimum(np.hypot(vx, vy), MAX_SPEED_MS)
    pos = np.searchsorted(full, f)
    t.xy = np.c_[x, y][pos]
    t.speed_ms = speed[pos]


def assign_teams(tracks: list[Track]) -> None:
    """Cluster shirt colours into two teams and an "other" group (referees, keepers, staff).

    Features are brightness and saturation of the shirt. This footage has a strong blue cast, so a
    white kit renders pale blue and "how blue" cannot tell the kits apart, but a white shirt is
    clearly brighter and less saturated than a royal-blue one. The two largest clusters are the
    teams; the brighter kit is called White and the darker Blue.
    """
    if len(tracks) < 6:
        return
    rgb = np.array([t.colour for t in tracks], dtype=np.float64)
    lum = rgb.mean(axis=1)
    sat = (rgb.max(axis=1) - rgb.min(axis=1)) / np.maximum(rgb.max(axis=1), 1.0)
    feats = np.c_[lum, sat]
    feats = (feats - feats.mean(axis=0)) / (feats.std(axis=0) + 1e-6)
    _, labels = kmeans2(feats, 3, minit="++", seed=7)
    sizes = np.bincount(labels, minlength=3)
    teams = [int(c) for c in np.argsort(sizes)[::-1][:2]]
    teams.sort(key=lambda c: float(np.median(lum[labels == c])))  # darker first
    names = {teams[0]: "BLU", teams[1]: "WHT"}
    for t, lab in zip(tracks, labels, strict=True):
        t.team = names.get(int(lab), "OTH")
