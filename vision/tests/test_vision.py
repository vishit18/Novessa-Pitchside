"""Vision logic on synthetic data: no footage, no GPU. Skipped if OpenCV or SciPy are missing."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("cv2")
pytest.importorskip("scipy")

from vision.ball import BallTrack
from vision.calibration import from_dataset_centre
from vision.evaluate import event_metrics
from vision.events import build_events
from vision.redact import MARK_REGION, redact
from vision.track import Track, associate

N = 120


def _track(tid: int, team: str, xy: tuple[float, float]) -> Track:
    frames = np.arange(N, dtype=np.int32)
    return Track(
        track_id=tid,
        frames=frames,
        xy=np.tile(np.array(xy, dtype=np.float64), (N, 1)),
        box=np.zeros((N, 4), np.float32),
        colour=np.zeros(3, np.float32),
        speed_ms=np.zeros(N),
        team=team,
    )


def _ball(path: list[tuple[float, float]]) -> BallTrack:
    xy = np.array(path, dtype=np.float64)
    speed = np.r_[0.0, np.hypot(*np.diff(xy, axis=0).T) * 25]
    return BallTrack(xy, np.zeros_like(xy), np.ones(len(xy), bool), speed, 1.0)


def _pass_ball() -> BallTrack:
    """At A's feet for 20 frames, travels to B over 40 frames, then at B's feet."""
    a, b = np.array([20.0, 30.0]), np.array([35.0, 30.0])
    path = [tuple(a)] * 20 + [tuple(a + (b - a) * i / 40) for i in range(1, 40)] + [tuple(b)] * 61
    return _ball(path)


def test_dataset_centre_origin_becomes_bottom_left() -> None:
    assert from_dataset_centre(np.array([0.0, 0.0])).tolist() == [52.5, 34.0]
    # Near touchline (positive y in the dataset) is the bottom of the pitch for us.
    assert from_dataset_centre(np.array([-52.5, 34.0])).tolist() == [0.0, 0.0]


def test_a_pass_between_teammates_is_found_and_scored() -> None:
    tracks = [
        _track(1, "BLU", (20.0, 30.0)),
        _track(2, "BLU", (35.0, 30.0)),
        _track(3, "WHT", (28, 40)),
    ]
    events = build_events(tracks, _pass_ball(), "t", 0.0)
    passes = [e for e in events if e.type.value == "pass"]
    assert len(passes) == 1
    p = passes[0]
    assert (p.player_id, p.receiver_id, p.outcome, p.source) == (
        "BLU-T001",
        "BLU-T002",
        "complete",
        "vision",
    )
    # Recorded as the ball leaves the passer's possession radius: near the feet, not on them.
    assert p.x == pytest.approx(20.0, abs=3.0) and p.end_x == pytest.approx(35.0, abs=3.0)
    assert 0 < (p.pass_difficulty or 0) < 100 and p.difficulty_factors


def test_the_ball_going_to_the_other_team_is_a_turnover() -> None:
    tracks = [_track(1, "BLU", (20.0, 30.0)), _track(2, "WHT", (35.0, 30.0))]
    events = build_events(tracks, _pass_ball(), "t", 0.0)
    assert [e.type.value for e in events] == ["pass", "possession_change"]
    assert events[0].outcome == "incomplete" and events[1].team == "WHT"


def test_a_slow_ball_heading_nowhere_is_not_a_shot() -> None:
    tracks = [_track(1, "BLU", (20.0, 30.0))]
    assert not [e for e in build_events(tracks, _pass_ball(), "t", 0.0) if e.type.value == "shot"]


def test_associate_keeps_two_walkers_apart() -> None:
    frames, boxes, xy, scores, cols = [], [], [], [], []
    for k in range(40):
        for i, (x0, y0, vx) in enumerate([(10.0, 20.0, 0.1), (11.5, 20.0, -0.1)]):
            frames.append(k)
            boxes.append([0, 0, 1, 1])
            xy.append([x0 + vx * k, y0])
            scores.append(0.9)
            cols.append([30.0 + 100 * i, 80, 90])
    tracks = associate(
        np.array(frames, np.int32), np.array(xy), np.array(scores, np.float32),
        np.array(cols, np.float32), np.arange(len(frames)),
    )  # fmt: skip
    assert len(tracks) == 2
    assert all(len(rows) == 40 for rows in tracks.values())
    # Each track keeps one person's colour the whole way, so they never swapped.
    assert all(len({int(cols[r][0]) for r in rows}) == 1 for rows in tracks.values())


def test_event_metrics_matches_one_to_one_by_time_and_team() -> None:
    tracks = [_track(1, "BLU", (20.0, 30.0)), _track(2, "BLU", (35.0, 30.0))]
    ours = build_events(tracks, _pass_ball(), "t", 0.0)
    gt = [
        {"label": "PASS", "frame": 22, "team": "left", "player_id": 900},
        {"label": "PASS", "frame": 300, "team": "left", "player_id": 900},
        {"label": "PASS", "frame": 22, "team": "right", "player_id": 901},
    ]
    s = event_metrics(ours, gt, {"BLU": "left"}, {1: 900}, {"PASS"}, {"pass"})
    assert (s.gt, s.ours, s.matched) == (3, 1, 1)
    assert s.precision == 1.0 and s.passer_agreement == 1.0


def test_redaction_removes_paint_in_the_region_and_leaves_the_rest() -> None:
    h, w = 676, 2560
    frame = np.zeros((h, w, 3), np.uint8)
    frame[:] = (40, 140, 40)  # turf
    cx, cy = (MARK_REGION[:, 0].mean() * w), (MARK_REGION[:, 1].mean() * h)
    frame[int(cy) - 8 : int(cy) + 8, int(cx) - 60 : int(cx) + 60] = 255  # painted letters
    frame[20:40, 20:40] = 255  # a white shirt far from the region
    out = redact(frame)
    assert out[int(cy) - 8 : int(cy) + 8, int(cx) - 60 : int(cx) + 60].min() < 200
    assert (out[20:40, 20:40] == 255).all()
