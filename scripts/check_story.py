"""Run the story check over the warmed agent cache and list anything that credits the wrong
club or puts a moment at the wrong time.

    uv run python -m scripts.check_story [--drop]

`--drop` removes the failing entries (and their translations) so the next agent run rewrites
them under the current rules. Re-warm with `scripts.run_agents` afterwards.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from backend.agents.intel import MatchIntel
from backend.agents.story import goal_time_problems, story_problems
from backend.app.store import MatchStore

CACHE = Path(__file__).resolve().parent.parent / "data" / "cache" / "agents"


async def main(drop: bool) -> None:
    store = MatchStore()
    by_seed = {}
    for mid in store.match_ids():
        loaded = await store.get(mid)
        by_seed[loaded.meta.seed] = MatchIntel(loaded)
    total = 0
    for path in sorted(CACHE.glob("seed_*.json")):
        seed = int(path.stem.split("_")[1])
        intel = by_seed.get(seed)
        if intel is None:
            continue
        data: dict[str, dict[str, Any]] = json.loads(path.read_text("utf-8"))
        bad: set[str] = set()
        for key, entry in data.items():
            moment_id, stage = key.split(":")[1:3]
            problems: list[str] = []
            if stage == "aired" and entry.get("status") == "verified":
                m = intel.get_moment(moment_id)
                a = entry.get("analysis") or {}
                problems += story_problems(
                    store.names, m, intel.teams, a.get("headline", ""), a.get("why", "")
                )
                for v in (entry.get("variants") or {}).values():
                    problems += story_problems(
                        store.names, m, intel.teams, v["headline"], v["body"]
                    )
            elif stage == "recap" and key.endswith(":en"):
                out = entry["output"]
                text = " ".join([*out["paragraphs"], *out["highlights"]])
                problems += goal_time_problems(text, entry["facts"]["goals"])
            if problems:
                bad.add(moment_id)
                print(f"{key}: {'; '.join(dict.fromkeys(problems))}")
        total += len(bad)
        if drop and bad:
            keep = {k: v for k, v in data.items() if k.split(":")[1] not in bad}
            path.write_text(json.dumps(keep, ensure_ascii=False), "utf-8", newline="\n")
            print(f"{path.name}: dropped {len(data) - len(keep)} entries")
    print(f"{total} moments or recaps failed the story check")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--drop", action="store_true")
    asyncio.run(main(ap.parse_args().drop))
