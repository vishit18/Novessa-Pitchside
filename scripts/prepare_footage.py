"""Cut one short window from the SoccerTrack v2 download and slice its ground truth.

    uv run --group vision python -m scripts.prepare_footage --start 1890 --seconds 100

Reads footage/raw (from `hf download`, see docs/06) and writes footage/clip/<match>_w<start>/:
  clip.mp4          downscaled for the web, painted marks removed, no audio
  gt_people.jsonl   labelled people for each frame of the window (evaluation only)
  gt_events.json    labelled ball events in the window, frames relative to the clip
  meta.json         where the window sits in the half, frame rate, credit

The big originals are left in place. footage/ is git-ignored. CC BY 4.0, see docs/ASSET_LICENSES.md.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path

import cv2

from vision.groundtruth import FPS, load_events, stream_people, write_people
from vision.redact import redact

CREDIT = "Footage: SoccerTrack v2 (CC BY 4.0)"


WEB_SIZE = (2560, 676)  # even height: H.264 needs even sides


def cut_clip(video: Path, first_frame: int, frames: int, out: Path) -> None:
    """Cut the window, downscale the 4096x1080 panorama and remove the painted marks.

    Frames are read with OpenCV, redacted, and piped to ffmpeg for encoding. Redaction happens
    here, before anything is written, so no unredacted pixel ever reaches the clip.
    """
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise SystemExit("ffmpeg is not on PATH")
    cap = cv2.VideoCapture(str(video))
    cap.set(cv2.CAP_PROP_POS_FRAMES, first_frame)
    w, h = WEB_SIZE
    cmd = [
        ffmpeg, "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", str(FPS), "-i", "-",
        "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "24", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", str(out),
    ]  # fmt: skip
    enc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert enc.stdin is not None
    try:
        for _ in range(frames):
            ok, frame = cap.read()
            if not ok:
                break
            small = cv2.resize(frame, WEB_SIZE, interpolation=cv2.INTER_AREA)
            enc.stdin.write(redact(small).tobytes())
    finally:
        enc.stdin.close()
        enc.wait()
        cap.release()
    if enc.returncode:
        raise SystemExit(f"ffmpeg failed with exit code {enc.returncode}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--raw", type=Path, default=Path("footage/raw"))
    ap.add_argument("--match", default="117093")
    ap.add_argument(
        "--start", type=float, required=True, help="window start, seconds into the half"
    )
    ap.add_argument("--seconds", type=float, default=100.0)
    ap.add_argument("--out", type=Path, default=Path("footage/clip"))
    args = ap.parse_args()

    first = round(args.start * FPS)
    last = first + round(args.seconds * FPS)
    out = args.out / f"{args.match}_w{round(args.start)}"
    out.mkdir(parents=True, exist_ok=True)

    t = time.time()
    print(f"cutting {args.seconds:.0f} s from {args.start:.0f} s ...")
    cut_clip(args.raw / "videos" / args.match / f"{args.match}_panorama_1st_half.mp4",
             first, last - first, out / "clip.mp4")  # fmt: skip
    print(f"  clip.mp4 {(out / 'clip.mp4').stat().st_size / 1e6:.1f} MB ({time.time() - t:.0f} s)")

    t = time.time()
    print("streaming ground truth (the file is 2.6 GB, this takes a minute) ...")
    gsr = args.raw / "gsr" / args.match / f"{args.match}_1st.json"
    n = write_people(stream_people(gsr, first, last), out / "gt_people.jsonl")
    print(f"  gt_people.jsonl {n} frames ({time.time() - t:.0f} s)")

    events = [
        {**e, "frame": e["frame"] - first, "t": round((e["frame"] - first) / FPS, 2)}
        for e in load_events(args.raw / "bas" / args.match / f"{args.match}_12_class_events.json")
        if first <= e["frame"] < last
    ]
    (out / "gt_events.json").write_text(json.dumps(events, indent=1), "utf-8")
    print(f"  gt_events.json {len(events)} events")

    meta = {
        "match": args.match,
        "half": 1,
        "start_s": args.start,
        "seconds": args.seconds,
        "first_frame": first,
        "frames": last - first,
        "fps": FPS,
        "source_resolution": [4096, 1080],
        "clip_resolution": list(WEB_SIZE),
        "redacted": ["painted university name and crest"],
        "credit": CREDIT,
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=1), "utf-8")
    print(f"done: {out}")


if __name__ == "__main__":
    main()
