"""SoccerTrack v2 ground truth: read, slice and compare. Real footage only (docs/06).

These labels are used for exactly two things: choosing a clip, and scoring our own vision output
against them (`vision/evaluate.py`). They are never an input to detection, tracking or events.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import ijson

FPS = 25


@dataclass(frozen=True)
class GtPerson:
    """One labelled person in one frame."""

    frame: int
    track_id: int
    role: str  # player, goalkeeper, referee, ...
    team: str  # left, right, or ""
    jersey: str
    player_id: int | None
    box: tuple[float, float, float, float]  # x, y, w, h in pixels of the original frame
    pitch_centre: tuple[float, float]  # dataset convention: metres, origin at the centre circle


def stream_people(gsr_path: Path, first_frame: int, last_frame: int) -> Iterator[GtPerson]:
    """Labelled people with first_frame <= frame < last_frame, streamed from the big GSR file.

    The file is 2.6 GB, so it is parsed as a stream and parsing stops once the window is passed.
    Frame k of the video is image id <base> + k + 1; the base is read from the first image.
    """
    with gsr_path.open("rb") as f:
        base: int | None = None
        for item in ijson.items(f, "images.item"):
            base = int(item["image_id"]) - 1
            break
        if base is None:
            raise ValueError("no images in the ground truth file")
    with gsr_path.open("rb") as f:
        for ann in ijson.items(f, "annotations.item"):
            if ann.get("supercategory") != "object":
                continue
            frame = int(ann["image_id"]) - base - 1
            if frame < first_frame:
                continue
            if frame >= last_frame:
                return
            a = ann["attributes"]
            b = ann["bbox_image"]
            p = ann["bbox_pitch"]
            yield GtPerson(
                frame=frame,
                track_id=int(ann["track_id"]),
                role=str(a.get("role", "")),
                team=str(a.get("team", "")),
                jersey=str(a.get("jersey", "")),
                player_id=int(a["player_id"]) if a.get("player_id") not in (None, "") else None,
                box=(float(b["x"]), float(b["y"]), float(b["w"]), float(b["h"])),
                pitch_centre=(float(p["x_bottom_middle"]), float(p["y_bottom_middle"])),
            )


def load_events(bas_path: Path) -> list[dict[str, Any]]:
    """Ball action events with a frame inside the filmed half."""
    data = json.loads(bas_path.read_text("utf-8"))
    return list(data["actions"])


def write_people(people: Iterator[GtPerson], out: Path) -> int:
    """Write one JSON line per frame: {"frame": k, "people": [...]}."""
    n = 0
    current: int | None = None
    row: list[dict[str, Any]] = []
    with out.open("w", encoding="utf-8") as f:

        def flush() -> None:
            nonlocal n
            if current is not None:
                f.write(json.dumps({"frame": current, "people": row}, separators=(",", ":")) + "\n")
                n += 1

        for p in people:
            if p.frame != current:
                flush()
                current, row = p.frame, []
            row.append(
                {
                    "track": p.track_id,
                    "role": p.role,
                    "team": p.team,
                    "jersey": p.jersey,
                    "player_id": p.player_id,
                    "box": [round(v, 1) for v in p.box],
                    "pitch": [round(v, 2) for v in p.pitch_centre],
                }
            )
        flush()
    return n


def read_people(path: Path) -> dict[int, list[dict[str, Any]]]:
    """Load a sliced ground-truth file: frame -> people."""
    out: dict[int, list[dict[str, Any]]] = {}
    for line in path.read_text("utf-8").splitlines():
        rec = json.loads(line)
        out[int(rec["frame"])] = rec["people"]
    return out
