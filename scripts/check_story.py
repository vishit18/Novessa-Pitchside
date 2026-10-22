"""Re-check the warmed agent cache against today's rules and list anything that fails: the full
Verifier (numbers, a running total passed off as one action, causes the data cannot show, the
right club, the right time) on every verified insight, the story check on every persona variant,
and goal times in recaps.

    uv run python -m scripts.check_story [--drop] [--stale-names FILE] [--drop-ask] [--drop-recaps]

`--stale-names` takes a file with one player name per line that no longer exists (after a
rename); any cached text naming one fails. `--drop-ask` clears cached Ask the Analyst answers
and `--drop-recaps` every cached recap (after the recap fact sheet changes).
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
from backend.agents.models import AnalystOutput
from backend.agents.story import goal_time_problems, story_problems
from backend.agents.verifier import verify
from backend.app.store import MatchStore

CACHE = Path(__file__).resolve().parent.parent / "data" / "cache" / "agents"


def stale_in(entry: dict[str, Any], stale: list[str]) -> list[str]:
    text = json.dumps(entry, ensure_ascii=False)
    return [f"names {n}, who no longer exists" for n in stale if n in text]


async def main(drop: bool, stale: list[str], drop_ask: bool, drop_recaps: bool) -> None:
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
            # Translation tables keep lines for old names; they are simply never looked up again.
            problems: list[str] = [] if stage == "overlay_text" else stale_in(entry, stale)
            if stage == "ask" and drop_ask:
                problems.append("cached answer cleared")
            if stage == "recap" and drop_recaps:
                problems.append("recap cleared")
            if stage == "aired" and entry.get("status") == "verified":
                m = intel.get_moment(moment_id)
                a = entry.get("analysis") or {}
                verdict = verify(intel, m, AnalystOutput.model_validate(a), store.names)
                if verdict.overall == "rejected":
                    problems.append(verdict.reason)
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
    ap.add_argument("--stale-names", type=Path)
    ap.add_argument("--drop-ask", action="store_true")
    ap.add_argument("--drop-recaps", action="store_true")
    args = ap.parse_args()
    names = args.stale_names.read_text("utf-8").splitlines() if args.stale_names else []
    asyncio.run(
        main(args.drop, [n.strip() for n in names if n.strip()], args.drop_ask, args.drop_recaps)
    )
