"""Auto-eventing on real footage, offline: detect, track, assign teams, measure, find events.

    uv run --group vision python -m vision.pipeline detect --clip footage/clip/117093_w1890
    uv run --group vision python -m vision.pipeline events --clip footage/clip/117093_w1890

`detect` is the slow part (GPU, a few minutes) and is cached. Everything after it runs in seconds
from the cache, so tracking and event rules can be tuned quickly. Output uses the same MatchEvent
and TrackingFrame schema as the synthetic engine, with source "vision" (docs/06).
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np

from vision.calibration import PitchCalibration
from vision.detect import TileDetector

FPS = 25


def torso_colour(frame: np.ndarray, box: np.ndarray) -> np.ndarray:
    """Median RGB of the shirt area of one person box, with green turf masked out.

    Small boxes include a lot of grass between the shirt and the box edge, which swamps the shirt
    colour; pixels that are green and saturated are ignored.
    """
    x1, y1, x2, y2 = (int(v) for v in box)
    w, h = x2 - x1, y2 - y1
    sx1, sx2 = x1 + int(0.2 * w), x2 - int(0.2 * w)
    sy1, sy2 = y1 + int(0.15 * h), y1 + int(0.50 * h)
    crop = frame[max(sy1, 0) : max(sy2, sy1 + 1), max(sx1, 0) : max(sx2, sx1 + 1)]
    if crop.size == 0:
        return np.zeros(3, np.float32)
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV).reshape(-1, 3)
    turf = (hsv[:, 0] >= 30) & (hsv[:, 0] <= 95) & (hsv[:, 1] > 55) & (hsv[:, 2] > 35)
    pix = crop.reshape(-1, 3)
    use = pix[~turf] if (~turf).sum() >= 6 else pix
    bgr = np.median(use, axis=0)
    return bgr[::-1].astype(np.float32)  # RGB


def run_detect(clip_dir: Path, video: Path, first_frame: int, frames: int, out: Path) -> None:
    """Detect people and balls in every frame of the window and cache them to `out` (.npz)."""
    det = TileDetector()
    cap = cv2.VideoCapture(str(video))
    cap.set(cv2.CAP_PROP_POS_FRAMES, first_frame)
    p_frame: list[int] = []
    p_box: list[np.ndarray] = []
    p_score: list[float] = []
    p_colour: list[np.ndarray] = []
    b_frame: list[int] = []
    b_box: list[np.ndarray] = []
    b_score: list[float] = []
    t0 = time.time()
    for k in range(frames):
        ok, frame = cap.read()
        if not ok:
            break
        d = det.detect(frame)
        for box, score in zip(d.person_boxes, d.person_scores, strict=True):
            p_frame.append(k)
            p_box.append(box)
            p_score.append(float(score))
            p_colour.append(torso_colour(frame, box))
        for box, score in zip(d.ball_boxes, d.ball_scores, strict=True):
            b_frame.append(k)
            b_box.append(box)
            b_score.append(float(score))
        if k % 100 == 0:
            rate = (k + 1) / (time.time() - t0)
            print(
                f"  frame {k}/{frames}  {rate:.1f} fps  eta {(frames - k) / rate:.0f}s", flush=True
            )
    np.savez_compressed(
        out,
        person_frame=np.array(p_frame, np.int32),
        person_box=np.array(p_box, np.float32).reshape(-1, 4),
        person_score=np.array(p_score, np.float32),
        person_colour=np.array(p_colour, np.float32).reshape(-1, 3),
        ball_frame=np.array(b_frame, np.int32),
        ball_box=np.array(b_box, np.float32).reshape(-1, 4),
        ball_score=np.array(b_score, np.float32),
    )
    print(f"detections cached to {out} ({time.time() - t0:.0f}s)")


def people_by_frame(d: np.lib.npyio.NpzFile, cal: PitchCalibration) -> dict[int, np.ndarray]:
    """Pitch positions of confident person detections on or beside the pitch, per frame."""
    from vision.track import foot_points, on_pitch

    xy = cal.to_pitch(foot_points(d["person_box"]))
    keep = on_pitch(xy, 1.5) & (d["person_score"] >= 0.4)
    out: dict[int, list[np.ndarray]] = {}
    for f, p in zip(d["person_frame"][keep], xy[keep], strict=True):
        out.setdefault(int(f), []).append(p)
    return {f: np.array(v) for f, v in out.items()}


def run_analyse(clip: Path, raw: Path, meta: dict[str, object]) -> None:
    """Track, find events, score against the labels and write the outputs. Seconds, from cache."""
    import json

    from vision.ball import track_ball
    from vision.evaluate import _team_map, event_metrics, position_metrics, speed_metrics
    from vision.events import build_events
    from vision.groundtruth import read_people
    from vision.outputs import score_dict, write_all
    from vision.track import track_people

    d = np.load(clip / "detections.npz")
    cal = PitchCalibration.load(raw / "raw" / str(meta["match"]))
    tracks = track_people(
        d["person_frame"], d["person_box"], d["person_score"], d["person_colour"], cal
    )
    ball = track_ball(
        int(meta["frames"]),  # type: ignore[call-overload]
        d["ball_frame"],
        d["ball_box"],
        d["ball_score"],
        cal,
        people_by_frame(d, cal),
    )
    match_id = f"real_{meta['match']}_w{round(float(meta['start_s']))}"  # type: ignore[arg-type]
    events = build_events(tracks, ball, match_id, float(meta["start_s"]))  # type: ignore[arg-type]
    gt = read_people(clip / "gt_people.jsonl")
    gt_events = json.loads((clip / "gt_events.json").read_text("utf-8"))
    pos = position_metrics(tracks, gt, int(meta["first_frame"]))  # type: ignore[call-overload]
    side, _ = _team_map(tracks, pos.track_to_gt, gt)
    passes = event_metrics(
        events, gt_events, side, pos.track_to_gt, {"PASS", "HIGH PASS", "CROSS"}, {"pass"}
    )
    shots = event_metrics(
        events, gt_events, side, pos.track_to_gt, {"SHOT", "GOAL"}, {"shot"}, 50, False
    )
    speed = speed_metrics(tracks, gt, int(meta["first_frame"]), pos.track_to_gt)  # type: ignore[call-overload]
    results = score_dict(("positions", pos), ("speed", speed), ("passes", passes), ("shots", shots))
    results["ball_found_fraction"] = round(ball.found_fraction, 3)
    results["tracks"] = len(tracks)
    write_all(clip / "out", match_id, meta, tracks, ball, events, results)  # type: ignore[arg-type]
    print(json.dumps(results, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("stage", choices=["detect", "analyse"])
    ap.add_argument("--clip", type=Path, required=True)
    ap.add_argument("--raw", type=Path, default=Path("footage/raw"))
    args = ap.parse_args()
    meta = json.loads((args.clip / "meta.json").read_text("utf-8"))
    if args.stage == "detect":
        video = args.raw / "videos" / meta["match"] / f"{meta['match']}_panorama_1st_half.mp4"
        run_detect(
            args.clip, video, meta["first_frame"], meta["frames"], args.clip / "detections.npz"
        )
    else:
        run_analyse(args.clip, args.raw, meta)


if __name__ == "__main__":
    main()
