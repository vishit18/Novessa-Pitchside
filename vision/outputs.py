"""Write what the app needs from a finished analysis (docs/06 steps 8 and "Render").

events.jsonl     MatchEvent lines, source "vision": same schema as the synthetic engine
tracking.jsonl   TrackingFrame lines at 5 Hz: players (team + track id, metres, km/h) and ball
overlay.json     per-frame boxes in clip pixels, ball, events and speed bursts, for the player
results.json     the validation numbers (docs/06 "Validation against ground truth")
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from engine.schema import BallState, MatchEvent, PlayerFrame, TrackingFrame
from vision.ball import BallTrack
from vision.events import MS_TO_KMH, speed_bursts
from vision.track import FPS, Track

SRC = (4096, 1080)
CLIP = (2560, 676)
TEAM_NAME = {"BLU": "Blue", "WHT": "White"}
OVERLAY_EVERY = 2  # frames; the player interpolates between them
TRACKING_EVERY = 5  # frames, so 5 Hz


def label(t: Track) -> str:
    """Short tag text. The dataset is pseudonymised and we do not read shirt numbers, so a tag is
    the kit and a number we assigned (stable for the life of a track)."""
    return f"{TEAM_NAME.get(t.team, 'Other')} {t.track_id}"


def write_all(
    out: Path,
    match_id: str,
    meta: dict[str, Any],
    tracks: list[Track],
    ball: BallTrack,
    events: list[MatchEvent],
    results: dict[str, Any],
) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "events.jsonl").write_text(
        "\n".join(e.model_dump_json() for e in events) + "\n", encoding="utf-8"
    )
    players = [t for t in tracks if t.team != "OTH"]
    index = {
        t.track_id: dict(zip(t.frames.tolist(), range(len(t.frames)), strict=True)) for t in players
    }
    lines = []
    for k in range(0, int(meta["frames"]), TRACKING_EVERY):
        here = [
            PlayerFrame(
                id=f"{t.team}-T{t.track_id:03d}",
                x=round(float(t.xy[index[t.track_id][k], 0]), 2),
                y=round(float(t.xy[index[t.track_id][k], 1]), 2),
                v_kmh=round(float(t.speed_ms[index[t.track_id][k]]) * MS_TO_KMH, 1),
            )
            for t in players
            if k in index[t.track_id]
        ]
        b = ball.xy[k] if ball.valid[k] else (np.nan, np.nan)
        lines.append(
            TrackingFrame(
                match_id=match_id,
                t_match=round(k / FPS, 2),
                ball=BallState(
                    x=0.0 if np.isnan(b[0]) else round(float(b[0]), 2),
                    y=0.0 if np.isnan(b[1]) else round(float(b[1]), 2),
                ),
                players=here,
            ).model_dump_json()
        )
    (out / "tracking.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    sx, sy = CLIP[0] / SRC[0], CLIP[1] / SRC[1]
    frames = []
    for k in range(0, int(meta["frames"]), OVERLAY_EVERY):
        row = []
        for t in players:
            i = index[t.track_id].get(k)
            if i is None:
                continue
            x1, y1, x2, y2 = t.box[i]
            row.append(
                [
                    t.track_id,
                    round(x1 * sx),
                    round(y1 * sy),
                    round(x2 * sx),
                    round(y2 * sy),
                    round(float(t.speed_ms[i]) * MS_TO_KMH, 1),
                ]
            )
        ballpx = None
        if ball.valid[k]:
            ballpx = [round(float(ball.px[k, 0]) * sx), round(float(ball.px[k, 1]) * sy)]
        frames.append([k, row, ballpx])
    overlay = {
        "match_id": match_id,
        "fps": FPS,
        "clip": list(CLIP),
        "credit": meta["credit"],
        "start_s": meta["start_s"],
        "tracks": {str(t.track_id): {"team": t.team, "label": label(t)} for t in players},
        "frames": frames,
        "events": [json.loads(e.model_dump_json()) for e in events],
        "bursts": speed_bursts(tracks),
    }
    (out / "overlay.json").write_text(json.dumps(overlay, separators=(",", ":")), encoding="utf-8")
    (out / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


def score_dict(*parts: Any) -> dict[str, Any]:
    """Dataclass scores to plain dicts for results.json."""
    out: dict[str, Any] = {}
    for name, part in parts:
        d = asdict(part)
        d.pop("track_to_gt", None)
        out[name] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in d.items()}
    return out
