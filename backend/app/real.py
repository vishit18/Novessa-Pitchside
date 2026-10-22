"""Real footage mode: serve a prepared clip and what the vision pipeline found in it.

Everything here comes from `vision/` and is tagged `source: "vision"`. It is never mixed into the
synthetic matches (CLAUDE.md). The overlay data and validation numbers are small and live in
`data/real/<clip>/`; the video itself is large, stays out of git, and is read from
`footage/clip/<clip>/clip.mp4` (or REAL_FOOTAGE_DIR) when it exists.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

CLIP_ID = re.compile(r"^\d{4,8}_w\d{1,5}$")
REPO = Path(__file__).resolve().parents[2]


def _data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", REPO / "data")) / "real"


def _footage_dir() -> Path:
    return Path(os.environ.get("REAL_FOOTAGE_DIR", REPO / "footage" / "clip"))


def _clip_dir(clip: str) -> Path:
    """The data folder for a clip id. The id is checked so it cannot point outside data/real."""
    if not CLIP_ID.match(clip):
        raise HTTPException(404, "unknown clip")
    d = _data_dir() / clip
    if not d.is_dir():
        raise HTTPException(404, "unknown clip")
    return d


def mount_real(app: FastAPI) -> None:
    """Add the /real routes."""

    @app.get("/real")
    async def clips() -> list[dict[str, Any]]:
        """Prepared clips, each with its meta, validation numbers and whether the video is here."""
        out = []
        root = _data_dir()
        for d in sorted(root.iterdir()) if root.is_dir() else []:
            if not (CLIP_ID.match(d.name) and (d / "meta.json").exists()):
                continue
            out.append(
                {
                    "clip": d.name,
                    "meta": json.loads((d / "meta.json").read_text("utf-8")),
                    "results": json.loads((d / "results.json").read_text("utf-8")),
                    "video": (_footage_dir() / d.name / "clip.mp4").exists(),
                }
            )
        return out

    @app.get("/real/{clip}/overlay")
    async def overlay(clip: str) -> FileResponse:
        """Per-frame boxes, ball, events and speed bursts, in clip pixels."""
        # Revalidate every time: a re-run of the pipeline must reach viewers who loaded the old one.
        return FileResponse(
            _clip_dir(clip) / "overlay.json",
            media_type="application/json",
            headers={"Cache-Control": "no-cache"},
        )

    @app.get("/real/{clip}/video")
    async def video(clip: str) -> FileResponse:
        """The clip, with range requests so a browser can seek."""
        _clip_dir(clip)
        path = _footage_dir() / clip / "clip.mp4"
        if not path.exists():
            raise HTTPException(404, "the video for this clip is not on this server")
        return FileResponse(path, media_type="video/mp4")
