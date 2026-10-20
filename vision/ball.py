"""Find the one ball that is in play among the detector's candidates (docs/06 step 2).

A panorama has spare balls on the touchline and cones that the detector also calls balls. Two
filters handle that: candidates that sit in the same spot for much of the clip are dropped as
static, then a Viterbi search picks the trajectory that is both confident and physically
possible (a ball cannot jump further between frames than a hard shot would carry it).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import pairwise

import numpy as np
from numpy.typing import NDArray
from scipy.signal import savgol_filter

from vision.calibration import PitchCalibration
from vision.track import FPS, foot_points, on_pitch

STATIC_CELL_PX = 10
STATIC_FRACTION = 0.30  # in the same cell for this share of the clip: not the ball
MAX_STEP_M = 1.4  # 35 m/s between consecutive frames at 25 fps: a hard shot, not a jump
RESTART_COST = 4.5
NULL_COST = 1.6
NEAR_PEOPLE_M = 5.0  # the ball in play is within a few metres of someone
MAX_GAP_FRAMES = 20  # fill missing ball positions across gaps up to 0.8 s


@dataclass
class BallTrack:
    """Ball position for every frame of the clip; `valid` is False where it was not found."""

    xy: NDArray[np.float64]  # frames x 2, metres
    px: NDArray[np.float64]  # frames x 2, pixels on the original frame (for drawing)
    valid: NDArray[np.bool_]
    speed_ms: NDArray[np.float64]
    found_fraction: float


def _static_cells(
    frame: NDArray[np.int32], centres: NDArray[np.float64], n_frames: int
) -> set[tuple[int, int]]:
    cells: dict[tuple[int, int], set[int]] = {}
    for f, (x, y) in zip(frame, centres, strict=True):
        cells.setdefault((int(x // STATIC_CELL_PX), int(y // STATIC_CELL_PX)), set()).add(int(f))
    limit = STATIC_FRACTION * n_frames
    return {c for c, fs in cells.items() if len(fs) > limit}


def track_ball(
    n_frames: int,
    frame: NDArray[np.int32],
    boxes: NDArray[np.float32],
    scores: NDArray[np.float32],
    cal: PitchCalibration,
    people_xy: dict[int, NDArray[np.float64]] | None = None,
) -> BallTrack:
    """The in-play ball for every frame, from per-frame candidate detections.

    `people_xy` maps frame -> positions (metres) of the people on the pitch. When given, a
    candidate further than a few metres from all of them is not the ball: it is a mark on the
    turf, a cone, or a spare ball.
    """
    centres_px = np.c_[(boxes[:, 0] + boxes[:, 2]) / 2, (boxes[:, 1] + boxes[:, 3]) / 2]
    static = _static_cells(frame, centres_px, n_frames)
    xy_all = cal.to_pitch(foot_points(boxes))
    keep = on_pitch(xy_all, margin=1.0) & np.array(
        [(int(x // STATIC_CELL_PX), int(y // STATIC_CELL_PX)) not in static for x, y in centres_px]
    )
    if people_xy is not None:
        for i in np.flatnonzero(keep):
            others = people_xy.get(int(frame[i]))
            if (
                others is None
                or len(others) == 0
                or float(np.min(np.linalg.norm(others - xy_all[i], axis=1))) > NEAR_PEOPLE_M
            ):
                keep[i] = False
    cand: list[list[int]] = [[] for _ in range(n_frames)]
    for i in np.flatnonzero(keep):
        cand[int(frame[i])].append(int(i))

    # Viterbi. State j of frame k: candidate cand[k][j], or the "not seen" state at index -1.
    cost: list[np.ndarray] = []
    back: list[np.ndarray] = []
    prev_cost = np.array([-math.log(max(float(scores[i]), 1e-3)) for i in cand[0]] + [NULL_COST])
    cost.append(prev_cost)
    back.append(np.zeros(len(prev_cost), dtype=int))
    for k in range(1, n_frames):
        cur = cand[k]
        last = cand[k - 1]
        cur_cost = np.full(len(cur) + 1, np.inf)
        cur_back = np.zeros(len(cur) + 1, dtype=int)
        # Previous states: candidates of k-1, then null at the end.
        for j in range(len(cur) + 1):
            unary = NULL_COST if j == len(cur) else -math.log(max(float(scores[cur[j]]), 1e-3))
            best, arg = np.inf, 0
            for pj in range(len(last) + 1):
                base = prev_cost[pj]
                if pj == len(last) or j == len(cur):
                    step = 0.0 if j == len(cur) else RESTART_COST
                else:
                    d = float(np.linalg.norm(xy_all[cur[j]] - xy_all[last[pj]]))
                    if d > MAX_STEP_M:
                        continue
                    step = 0.35 * d
                if base + step < best:
                    best, arg = base + step, pj
            if np.isfinite(best):
                cur_cost[j], cur_back[j] = best + unary, arg
            else:  # nothing reachable: start again here
                cur_cost[j], cur_back[j] = (
                    float(np.min(prev_cost)) + RESTART_COST + unary,
                    int(np.argmin(prev_cost)),
                )
        cost.append(cur_cost)
        back.append(cur_back)
        prev_cost = cur_cost

    xy = np.full((n_frames, 2), np.nan)
    px = np.full((n_frames, 2), np.nan)
    state = int(np.argmin(prev_cost))
    for k in range(n_frames - 1, -1, -1):
        c = cand[k]
        if state < len(c):
            xy[k] = xy_all[c[state]]
            px[k] = centres_px[c[state]]
        state = int(back[k][state]) if k > 0 else state
    return _finish(xy, px)


def _finish(xy: NDArray[np.float64], px: NDArray[np.float64]) -> BallTrack:
    """Fill short gaps, smooth, and derive speed."""
    n = len(xy)
    seen = ~np.isnan(xy[:, 0])
    valid = np.zeros(n, bool)
    out = xy.copy()
    idx = np.flatnonzero(seen)
    if len(idx) >= 2:
        for a, b in pairwise(idx):
            if 1 < b - a <= MAX_GAP_FRAMES:
                for c in (0, 1):
                    out[a : b + 1, c] = np.linspace(xy[a, c], xy[b, c], b - a + 1)
                    px[a : b + 1, c] = np.linspace(px[a, c], px[b, c], b - a + 1)
        valid = ~np.isnan(out[:, 0])
    speed = np.zeros(n)
    # Smooth each uninterrupted run separately.
    run_start = None
    for k in range(n + 1):
        ok = k < n and valid[k]
        if ok and run_start is None:
            run_start = k
        if not ok and run_start is not None:
            seg = slice(run_start, k)
            m = k - run_start
            win = min(7, m - (1 - m % 2))
            if win >= 5:
                out[seg, 0] = savgol_filter(out[seg, 0], win, 2)
                out[seg, 1] = savgol_filter(out[seg, 1], win, 2)
                vx = savgol_filter(out[seg, 0], win, 2, deriv=1) * FPS
                vy = savgol_filter(out[seg, 1], win, 2, deriv=1) * FPS
                speed[seg] = np.hypot(vx, vy)
            run_start = None
    return BallTrack(out, px, valid, np.minimum(speed, 45.0), float(valid.mean()))
