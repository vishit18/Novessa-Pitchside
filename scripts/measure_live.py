"""Measure publish-to-overlay latency on the live ingest path, on Event Hubs and in memory.

    uv run python -m scripts.measure_live                      # the whole suite
    uv run python -m scripts.measure_live --bus memory --speed 30 --until 900

Streams the first `--until` match seconds at `--speed` through the event bus and times each
message from the moment it was wrapped for publishing to the moment its overlay was ready, in
one process, so there is no clock skew between the two ends. Event Hubs needs EVENTHUB_FQDN and
EVENTHUB_NAME and Entra access (`az login` locally, the managed identity in Azure). The budget
is 150 ms at the 95th percentile (docs/00, docs/05). Prints one JSON document.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import sys
from typing import Any

from backend.app.live import LiveIngest
from backend.app.store import MatchStore
from backend.bus import default_bus


async def run(store: MatchStore, bus_name: str, match_id: str, speed: float, until: float) -> Any:
    """One run on one bus. Returns the ingest summary."""
    os.environ["EVENT_BUS"] = bus_name
    bus = default_bus()
    if bus.name != bus_name:
        # default_bus() quietly falls back to memory when Event Hubs is not configured. A latency
        # number labelled Event Hubs that was measured in memory would be worse than no number.
        raise SystemExit(
            f"asked for the {bus_name} bus, got {bus.name}: set EVENTHUB_FQDN and EVENTHUB_NAME"
        )
    live = LiveIngest(store, bus)
    print(f"run: {bus.name} at {speed}x for {until:.0f} match seconds", file=sys.stderr, flush=True)
    live.start(match_id, speed, until)
    # The stream takes until / speed seconds of wall time. Allow that plus a generous margin, and
    # report what was seen if the bus stops delivering, instead of waiting forever.
    limit = until / speed + 120
    try:
        await asyncio.wait_for(live.wait(match_id), timeout=limit)
    except TimeoutError:
        print(f"run timed out after {limit:.0f}s", file=sys.stderr, flush=True)
    summary = live.stats[match_id].summary()
    if summary["status"] != "finished":
        summary["status"] = f"timed out ({summary['status']})"
        await live.stop()
    await bus.close()
    print(f"run done: {summary['status']}", file=sys.stderr, flush=True)
    return {"bus": bus.name, **summary}


async def main(plan: list[tuple[str, float, float]], match_id: str) -> None:
    """Run each (bus, speed, match seconds) in turn and print every summary."""
    store = MatchStore()
    await store.get(match_id)  # build the match first, so it is not part of the timing
    results = []
    for bus_name, speed, until in plan:
        results.append(
            {
                "speed": speed,
                "until_match_s": until,
                **await run(store, bus_name, match_id, speed, until),
            }
        )
    print(json.dumps({"host": platform.node(), "match": match_id, "runs": results}, indent=2))


# With no arguments (how the Container Apps job runs it): Event Hubs at the replay speed the app
# uses, Event Hubs at 30x as a stress pass, and the in-memory bus at 30x for comparison.
SUITE = [("eventhubs", 4.0, 600.0), ("eventhubs", 30.0, 2700.0), ("memory", 30.0, 2700.0)]

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--match", default="derby_01")
    ap.add_argument("--speed", type=float)
    ap.add_argument("--until", type=float, help="match seconds to stream")
    ap.add_argument("--bus", choices=["memory", "eventhubs"])
    args = ap.parse_args()
    # MEASURE_PLAN="eventhubs:4:60,memory:30:900" overrides the suite where flags cannot be passed
    # (the Container Apps job start cannot take arguments that begin with a dash).
    env_plan = os.environ.get("MEASURE_PLAN")
    if env_plan:
        parts = [item.split(":") for item in env_plan.split(",")]
        asyncio.run(main([(b, float(sp), float(u)) for b, sp, u in parts], args.match))
    elif args.bus or args.speed or args.until:
        one = [(args.bus or "eventhubs", args.speed or 30.0, args.until or 900.0)]
        asyncio.run(main(one, args.match))
    else:
        asyncio.run(main(SUITE, args.match))
