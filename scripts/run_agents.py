"""Run the newsroom on a match and print what airs. Needs Foundry access (`az login`).

uv run python -m scripts.run_agents --match derby_01 --count 6
"""

from __future__ import annotations

import argparse
import asyncio
import os
import time

from dotenv import load_dotenv

from backend.agents.factory import build_context
from backend.agents.workflow import run_batch
from backend.app.store import MatchStore


async def main(match_id: str, count: int, minutes: float) -> None:
    ctx = await build_context(MatchStore(), match_id)
    moments = [m for m in ctx.intel.list_moments(0, minutes * 60, 50)]
    moments.sort(key=lambda m: -m.significance)
    chosen = sorted(moments[:count], key=lambda m: m.t_match)
    print(f"{match_id}: {len(moments)} candidates, running {len(chosen)}")
    started = time.perf_counter()
    out = await run_batch(ctx, [m.moment_id for m in chosen])
    print(f"done in {time.perf_counter() - started:.1f}s\n")
    for a in sorted(out, key=lambda a: ctx.intel.get_moment(a.moment_id).t_match):
        m = ctx.intel.get_moment(a.moment_id)
        print(f"[{m.clock}] {m.kind} sig={m.significance:.0f} -> {a.status}")
        for p, v in a.variants.items():
            print(f"   {p:13s} {v.headline}: {v.body}")
        for line in a.trail:
            print(f"   . {line}")
    print()
    for agent, h in ctx.llm.health.items():
        avg = sum(h.latencies_ms) / len(h.latencies_ms) if h.latencies_ms else 0
        print(
            f"{agent:9s} calls={h.calls} fail={h.failures} fallback={h.fallbacks} avg={avg:.0f}ms"
        )


if __name__ == "__main__":
    load_dotenv()
    os.environ.setdefault(
        "FOUNDRY_OPENAI_ENDPOINT", "https://novessapitchside1.cognitiveservices.azure.com"
    )
    ap = argparse.ArgumentParser()
    ap.add_argument("--match", default="derby_01")
    ap.add_argument("--count", type=int, default=6)
    ap.add_argument("--minutes", type=float, default=95.0, help="only moments before this minute")
    args = ap.parse_args()
    asyncio.run(main(args.match, args.count, args.minutes))
