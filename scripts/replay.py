"""Replay a saved match in the terminal at a chosen speed.

uv run python -m scripts.replay --match derby_01 --speed 30
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from engine.clock import ReplayClock, stream
from engine.io import read_match_file

ROOT = Path(__file__).resolve().parent.parent
QUIET = {"pressure", "possession_change", "carry"}


async def run(match_id: str, speed: float, everything: bool) -> None:
    meta, events = read_match_file(ROOT / "data" / "matches" / f"{match_id}.jsonl")
    print(f"{meta.home.code} v {meta.away.code}  at {meta.venue}, {meta.weather}  ({speed}x)")
    clock = ReplayClock(speed=speed)
    clock.play()
    shown = events if everything else [e for e in events if e.type not in QUIET]
    async for e in stream(shown, clock):
        who = f"{e.team or '---'} {e.player_id or ''}".strip()
        extra = ""
        if e.pass_difficulty is not None:
            extra = f" diff={e.pass_difficulty:.0f} {e.ball_speed_kmh:.0f}km/h"
        elif e.xg is not None:
            extra = f" xG={e.xg:.2f} {e.ball_speed_kmh:.0f}km/h {e.outcome}"
        print(f"{e.clock:>8}  {e.type.value:<18} {who}{extra}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--match", default="derby_01")
    ap.add_argument("--speed", type=float, default=4.0)
    ap.add_argument("--all", action="store_true", help="include pressure and possession events")
    args = ap.parse_args()
    asyncio.run(run(args.match, args.speed, args.all))


if __name__ == "__main__":
    main()
