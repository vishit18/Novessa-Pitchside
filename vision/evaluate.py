"""Score our vision output against SoccerTrack v2 labels (docs/06, validation section).

Labels are used only here, never by detection, tracking or events. Positions are compared on the
pitch in metres. Matching is optimal per frame (Hungarian) with a gate, so one wrong player does
not hide behind a right one.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import linear_sum_assignment

from vision.calibration import from_dataset_centre
from vision.track import Track

GATE_M = 3.0
PLAYER_ROLES = ("player", "goalkeeper")


@dataclass
class PositionScore:
    frames_scored: int
    gt_players: int
    matched: int
    detections: int
    recall: float
    precision: float
    median_error_m: float
    p90_error_m: float
    # our track id -> labelled player id it matched most often (for speed and pass checks)
    track_to_gt: dict[int, int]


def position_metrics(
    tracks: list[Track],
    gt: dict[int, list[dict[str, Any]]],
    first_frame: int,
    step: int = 5,
) -> PositionScore:
    """Per-frame optimal matching of tracked players to labelled players, every `step` frames."""
    by_frame: dict[int, list[tuple[int, NDArray[np.float64]]]] = {}
    for t in tracks:
        if t.team == "OTH":
            continue
        for f, p in zip(t.frames, t.xy, strict=True):
            by_frame.setdefault(int(f), []).append((t.track_id, p))
    errors: list[float] = []
    votes: dict[int, Counter[int]] = {}
    n_gt = n_match = n_det = scored = 0
    for k in range(0, max(by_frame) + 1, step):
        people = list(gt.get(first_frame + k, []))  # referees are on the pitch and detected too
        ours = by_frame.get(k, [])
        if not people:
            continue
        scored += 1
        gt_xy = from_dataset_centre(np.array([p["pitch"] for p in people]))
        n_gt += sum(p["role"] in PLAYER_ROLES for p in people)
        n_det += len(ours)
        if not ours:
            continue
        cost = np.linalg.norm(np.array([o[1] for o in ours])[:, None, :] - gt_xy[None], axis=2)
        rows, cols = linear_sum_assignment(cost)
        for r, c in zip(rows, cols, strict=True):
            if cost[r, c] <= GATE_M:
                if people[c]["role"] not in PLAYER_ROLES:
                    n_det -= 1  # a referee is a correct detection, but not a player to score
                    continue
                n_match += 1
                errors.append(float(cost[r, c]))
                pid = people[c]["player_id"]
                if pid is not None:
                    votes.setdefault(ours[r][0], Counter())[int(pid)] += 1
    err = np.array(errors) if errors else np.zeros(1)
    return PositionScore(
        frames_scored=scored,
        gt_players=n_gt,
        matched=n_match,
        detections=n_det,
        recall=n_match / max(n_gt, 1),
        precision=n_match / max(n_det, 1),
        median_error_m=float(np.median(err)),
        p90_error_m=float(np.percentile(err, 90)),
        track_to_gt={t: c.most_common(1)[0][0] for t, c in votes.items()},
    )


PASS_LABELS = {"PASS", "HIGH PASS", "CROSS"}
SHOT_LABELS = {"SHOT", "GOAL"}


@dataclass
class EventScore:
    gt: int
    ours: int
    matched: int
    precision: float
    recall: float
    f1: float
    passer_agreement: float | None = None


def _team_map(
    tracks: list[Track], track_to_gt: dict[int, int], gt: dict[int, list[dict[str, Any]]]
) -> tuple[dict[str, str], dict[int, int]]:
    """Which labelled side ("left"/"right") each of our team names corresponds to."""
    side_of_player: dict[int, str] = {}
    for people in gt.values():
        for p in people:
            if p["player_id"] is not None and p["team"]:
                side_of_player[int(p["player_id"])] = p["team"]
    votes: dict[str, Counter[str]] = {}
    for t in tracks:
        gid = track_to_gt.get(t.track_id)
        if gid is not None and gid in side_of_player:
            votes.setdefault(t.team, Counter())[side_of_player[gid]] += 1
    return {team: c.most_common(1)[0][0] for team, c in votes.items()}, {
        k: v for k, v in track_to_gt.items()
    }


def event_metrics(
    ours: list[Any],
    gt_events: list[dict[str, Any]],
    team_side: dict[str, str],
    track_to_gt: dict[int, int],
    labels: set[str],
    types: set[str],
    tolerance_frames: int = 15,
    complete_only: bool = True,
) -> EventScore:
    """Match our events to labelled ones one-to-one by time and team."""
    truth = [e for e in gt_events if e["label"] in labels]
    mine = [
        e
        for e in ours
        if e.type.value in types and (not complete_only or e.outcome in ("complete", "unknown"))
    ]
    used: set[int] = set()
    matched = agree = 0
    for e in mine:
        frame = round(e.t_match * 25)
        best, bj = tolerance_frames + 1, -1
        for j, g in enumerate(truth):
            if j in used or g["team"] != team_side.get(e.team or ""):
                continue
            d = abs(g["frame"] - frame)
            if d < best:
                best, bj = d, j
        if bj >= 0:
            used.add(bj)
            matched += 1
            if e.player_id and e.player_id.split("-T")[-1].isdigit():
                gid = track_to_gt.get(int(e.player_id.split("-T")[-1]))
                agree += int(gid is not None and str(gid) == str(truth[bj]["player_id"]))
    p = matched / max(len(mine), 1)
    r = matched / max(len(truth), 1)
    return EventScore(
        gt=len(truth),
        ours=len(mine),
        matched=matched,
        precision=p,
        recall=r,
        f1=2 * p * r / (p + r) if p + r else 0.0,
        passer_agreement=agree / matched if matched else None,
    )


@dataclass
class SpeedScore:
    tracks_compared: int
    samples: int
    median_abs_error_kmh: float
    p90_abs_error_kmh: float
    top_speed_error_kmh: float  # median over players of (our top speed - labelled top speed)


def speed_metrics(
    tracks: list[Track],
    gt: dict[int, list[dict[str, Any]]],
    first_frame: int,
    track_to_gt: dict[int, int],
) -> SpeedScore:
    """Our per-player speed against speed derived from the labelled positions.

    Both are smoothed the same way (Savitzky-Golay over 0.44 s). Only tracks that matched a
    labelled player are compared, and only on frames where the label exists.
    """
    from scipy.signal import savgol_filter

    from vision.track import FPS, MAX_SPEED_MS

    by_player: dict[int, dict[int, tuple[float, float]]] = {}
    for f, people in gt.items():
        for p in people:
            if p["player_id"] is not None and p["role"] in PLAYER_ROLES:
                xy = from_dataset_centre(np.array(p["pitch"]))
                by_player.setdefault(int(p["player_id"]), {})[f - first_frame] = (xy[0], xy[1])
    errs: list[float] = []
    tops: list[float] = []
    compared = 0
    for t in tracks:
        gid = track_to_gt.get(t.track_id)
        if gid is None or gid not in by_player or len(by_player[gid]) < 25:
            continue
        frames = np.array(sorted(by_player[gid]))
        pts = np.array([by_player[gid][int(f)] for f in frames])
        win = 11
        v = np.hypot(
            savgol_filter(pts[:, 0], win, 2, deriv=1) * FPS,
            savgol_filter(pts[:, 1], win, 2, deriv=1) * FPS,
        )
        v = np.minimum(v, MAX_SPEED_MS)
        gt_speed = dict(zip(frames.tolist(), v.tolist(), strict=True))
        common = [(i, gt_speed[int(f)]) for i, f in enumerate(t.frames) if int(f) in gt_speed]
        if len(common) < 25:
            continue
        compared += 1
        ours = np.array([t.speed_ms[i] for i, _ in common]) * 3.6
        theirs = np.array([g for _, g in common]) * 3.6
        errs += np.abs(ours - theirs).tolist()
        tops.append(float(ours.max() - theirs.max()))
    e = np.array(errs) if errs else np.zeros(1)
    return SpeedScore(
        tracks_compared=compared,
        samples=len(errs),
        median_abs_error_kmh=float(np.median(e)),
        p90_abs_error_kmh=float(np.percentile(e, 90)),
        top_speed_error_kmh=float(np.median(tops)) if tops else 0.0,
    )
