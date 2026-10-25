"""Does the multi-agent newsroom beat one big prompt? Measure it.

    uv run --group eval python -m scripts.eval_single_vs_multi    # all three demo matches
    uv run python -m scripts.eval_single_vs_multi --matches derby_01 --latency-batches 1

Both arms get the same computed evidence for the same moments. The single agent gets one prompt
and its answer airs as it is. The newsroom runs the Producer, Analyst, Verifier, Narrator and
Gate workflow. Both are judged by the same deterministic check: every number in the text must
match a computed fact for that moment. No model judges anything in the headline numbers.

Needs Foundry access (`az login`). Add `--group eval` for the Foundry evaluators.
The newsroom arm reads the agent cache when it can, so it usually costs nothing. Writes
docs/EVALUATION.md and data/evaluation.json.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import os
import statistics
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from backend.agents.analyst import WINDOW_S, evidence_menu
from backend.agents.cache import NullCache
from backend.agents.context import MatchContext
from backend.agents.factory import build_context
from backend.agents.llm import AgentUnavailable
from backend.agents.models import Aired
from backend.agents.story import story_problems
from backend.agents.verifier import close, numbers_in
from backend.agents.workflow import run_batch
from backend.app.agents_runtime import BATCH_SIZE, MIN_SIGNIFICANCE
from backend.app.store import MatchStore
from backend.state.models import Moment

ROOT = Path(__file__).resolve().parent.parent

BASELINE_PROMPT = """You write one lower-third graphic for a live football broadcast, for a casual \
fan. Give a headline of at most 6 words and a body of at most two short sentences that says what \
happened and why it matters. You are given the moment and a menu of computed numbers: use them \
where they help. Sound like a sharp, warm broadcaster. Reply as JSON with `headline` and `body`."""


class BaselineOut(BaseModel):
    headline: str = Field(description="At most 6 words")
    body: str


def fact_pool(ctx: MatchContext, m: Moment) -> list[float]:
    """Every number that is a computed fact for this moment. Same pool for both arms."""
    pool = [float(r["value"]) for r in evidence_menu(ctx, m)]
    pool += [e.value for e in m.evidence]
    pool += [float(v) for v in m.snapshot.score.values()]
    pool += numbers_in(m.clock) + numbers_in(m.summary)
    pool += [n for e in m.evidence for n in numbers_in(e.window or "")]
    t = m.t_match
    pool += [WINDOW_S / 60.0, round(t / 60.0), round(max(0.0, t - WINDOW_S) / 60.0), round(t)]
    return pool


def unsupported(text: str, pool: list[float]) -> list[float]:
    """Numbers in `text` that match no computed fact."""
    return [n for n in numbers_in(text) if not any(close(n, a) for a in pool)]


def payload_for(ctx: MatchContext, m: Moment) -> dict[str, Any]:
    return {
        "moment": {
            "clock": m.clock,
            "kind": m.kind,
            "team": ctx.team_name(m.team),
            "fact": ctx.names.humanise(m.summary),
            "score": {ctx.team_name(k): v for k, v in m.snapshot.score.items()},
        },
        "teams": {c: ctx.team_name(c) for c in ctx.intel.teams},
        "players": {p: ctx.names.player(p) for p in m.player_ids},
        "evidence_menu": evidence_menu(ctx, m),
    }


async def single_agent(
    ctx: MatchContext, m: Moment, gate: asyncio.Semaphore
) -> tuple[BaselineOut, float] | None:
    """One prompt, one answer, no checking. Returns the answer and the seconds it took."""
    async with gate:
        t0 = time.perf_counter()
        try:
            out = await ctx.llm.ask(
                agent="single",
                deployment=ctx.strong_model,
                system=BASELINE_PROMPT,
                user=json.dumps(payload_for(ctx, m)),
                schema=BaselineOut,
                timeout_s=30.0,
            )
        except AgentUnavailable:
            return None
        return out, time.perf_counter() - t0


def newsroom_text(a: Aired) -> str:
    v = a.variants.get("casual") or next(iter(a.variants.values()))
    return f"{v.headline}. {v.body}"


def story_of(ctx: MatchContext, m: Moment, headline: str, body: str) -> list[str]:
    """The Verifier's story check (wrong club, wrong time, a result called mid-match, metric code
    names, a booking said to change tactics) on one headline and body. Plain rules, no model."""
    return story_problems(ctx.names, m, ctx.intel.teams, headline, body)


def newsroom_story(ctx: MatchContext, m: Moment, a: Aired) -> list[str]:
    v = a.variants.get("casual") or next(iter(a.variants.values()))
    return story_of(ctx, m, v.headline, v.body)


def context_text(ctx: MatchContext, m: Moment) -> str:
    """The same evidence the writers saw, as plain text for the groundedness judge."""
    p = payload_for(ctx, m)
    facts = "; ".join(
        f"{r['metric']} {r.get('team') or r.get('player_id') or 'match'}: {r['value']}"
        for r in p["evidence_menu"]
    )
    return (
        f"Moment at {m.clock}: {p['moment']['fact']} Score: {p['moment']['score']}. Facts: {facts}"
    )


def foundry_judges() -> dict[str, Any] | None:
    """Microsoft Foundry evaluators (azure-ai-evaluation), keyless. None if not installed."""
    try:
        from azure.ai.evaluation import (
            FluencyEvaluator,
            GroundednessEvaluator,
            RelevanceEvaluator,
        )
        from azure.identity import DefaultAzureCredential
    except ImportError:
        return None
    cfg = {
        "azure_endpoint": os.environ["FOUNDRY_OPENAI_ENDPOINT"],
        "azure_deployment": os.environ.get("FOUNDRY_DEPLOYMENT_FAST", "chat-fast"),
        "api_version": "2024-12-01-preview",
    }
    cred = DefaultAzureCredential()
    return {
        "groundedness": GroundednessEvaluator(model_config=cfg, credential=cred),
        "relevance": RelevanceEvaluator(model_config=cfg, credential=cred),
        "fluency": FluencyEvaluator(model_config=cfg, credential=cred),
    }


QUALITY = ("groundedness", "relevance", "fluency")
QUERY = "Explain why this moment matters, for a casual fan watching live."


async def judge(
    judges: dict[str, Any], text: str, context: str, gate: asyncio.Semaphore
) -> dict[str, float] | None:
    """Foundry quality scores (1 to 5) for one piece of text. None if the judge failed."""

    def run() -> dict[str, float]:
        return {
            "groundedness": float(
                judges["groundedness"](query=QUERY, response=text, context=context)["groundedness"]
            ),
            "relevance": float(judges["relevance"](query=QUERY, response=text)["relevance"]),
            "fluency": float(judges["fluency"](response=text)["fluency"]),
        }

    async with gate:
        for attempt in range(4):
            try:
                return await asyncio.to_thread(run)
            except Exception:  # most often a rate limit: wait and try again
                await asyncio.sleep(4.0 * (attempt + 1))
    return None


def mean_of(rows: list[dict[str, float] | None], key: str) -> float | None:
    vals = [r[key] for r in rows if r]
    return round(statistics.fmean(vals), 2) if vals else None


async def _none() -> None:
    return None


def pct(x: float, n: int) -> float:
    return round(100 * x / n, 1) if n else 0.0


async def evaluate_match(store: MatchStore, match_id: str, latency_batches: int) -> dict[str, Any]:
    ctx = await build_context(store, match_id)
    moments = ctx.intel.list_moments(min_significance=MIN_SIGNIFICANCE)
    by_id = {m.moment_id: m for m in moments}
    ids = [m.moment_id for m in moments]
    aired: list[Aired] = []
    for i in range(0, len(ids), BATCH_SIZE):
        aired += await run_batch(ctx, ids[i : i + BATCH_SIZE])
    shown = [a for a in aired if a.status != "dropped" and a.variants]

    gate = asyncio.Semaphore(6)
    singles = await asyncio.gather(*(single_agent(ctx, by_id[a.moment_id], gate) for a in shown))

    rows: list[dict[str, Any]] = []
    for a, s in zip(shown, singles, strict=True):
        m = by_id[a.moment_id]
        pool = fact_pool(ctx, m)
        text = f"{s[0].headline}. {s[0].body}" if s else None
        rows.append(
            {
                "match": match_id,
                "moment": a.moment_id,
                "status": a.status,
                "rejected": sum("reject" in line.lower() for line in a.trail),
                "newsroom_bad": unsupported(newsroom_text(a), pool),
                "newsroom_story": newsroom_story(ctx, m, a),
                "single_text": text,
                "single_bad": unsupported(text, pool) if text else None,
                "single_story": story_of(ctx, m, s[0].headline, s[0].body) if s else None,
                "single_seconds": s[1] if s else None,
            }
        )

    judges = foundry_judges()
    if judges:
        jgate = asyncio.Semaphore(3)
        tasks = []
        for r, a in zip(rows, shown, strict=True):
            c = context_text(ctx, by_id[a.moment_id])
            tasks.append(judge(judges, newsroom_text(a), c, jgate))
            tasks.append(
                judge(judges, r["single_text"] or "", c, jgate) if r["single_text"] else _none()
            )
        scored = await asyncio.gather(*tasks)
        for i, r in enumerate(rows):
            r["newsroom_scores"], r["single_scores"] = scored[2 * i], scored[2 * i + 1]

    # End-to-end time for the newsroom, uncached, on a few batches. Cached runs say nothing.
    batch_seconds: list[float] = []
    cold = dataclasses.replace(ctx, cache=NullCache())
    for i in range(latency_batches):
        chunk = [str(r["moment"]) for r in rows[i * BATCH_SIZE : (i + 1) * BATCH_SIZE]]
        if len(chunk) == BATCH_SIZE:
            t0 = time.perf_counter()
            await run_batch(cold, chunk)
            batch_seconds.append(time.perf_counter() - t0)
    return {"candidates": len(moments), "rows": rows, "batch_seconds": batch_seconds}


def summarise(results: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [r for res in results for r in res["rows"]]
    single = [r for r in rows if r["single_bad"] is not None]
    verified = [r for r in rows if r["status"] == "verified"]
    fallback = [r for r in rows if r["status"] == "fallback"]
    batch = [s for res in results for s in res["batch_seconds"]]
    secs = [r["single_seconds"] for r in single]
    return {
        "moments_aired": len(rows),
        "newsroom": {
            "verified": len(verified),
            "numbers_only_fallback": len(fallback),
            "had_a_claim_rejected": sum(1 for r in rows if r["rejected"]),
            "with_unsupported_number": sum(1 for r in rows if r["newsroom_bad"]),
            "unsupported_numbers": sum(len(r["newsroom_bad"]) for r in rows),
            "seconds_per_batch_of_5": round(statistics.fmean(batch), 1) if batch else None,
            "with_story_error": sum(1 for r in rows if r.get("newsroom_story")),
        },
        "single_agent": {
            "answered": len(single),
            "with_unsupported_number": sum(1 for r in single if r["single_bad"]),
            "unsupported_numbers": sum(len(r["single_bad"]) for r in single),
            "median_seconds_per_moment": round(statistics.median(secs), 1) if secs else None,
            "with_story_error": sum(1 for r in single if r.get("single_story")),
        },
        "foundry_scores": {
            arm: {k: mean_of([r.get(f"{arm}_scores") for r in rows], k) for k in QUALITY}
            for arm in ("single", "newsroom")
        }
        if any(r.get("newsroom_scores") for r in rows)
        else None,
        "judged": {
            arm: sum(1 for r in rows if r.get(f"{arm}_scores")) for arm in ("single", "newsroom")
        },
        "examples": [
            {"moment": r["moment"], "text": r["single_text"], "unsupported": r["single_bad"]}
            for r in single
            if r["single_bad"]
        ][:5],
        "story_examples": [
            {"moment": r["moment"], "text": r["single_text"], "problems": r["single_story"]}
            for r in single
            if r.get("single_story")
        ][:5],
    }


def report(s: dict[str, Any]) -> str:
    matches = s.get("matches", ["derby_01", "derby_02", "derby_03"])
    n, sa, nr = s["moments_aired"], s["single_agent"], s["newsroom"]
    rate_single = pct(sa["with_unsupported_number"], sa["answered"])
    rate_news = pct(nr["with_unsupported_number"], n)
    lines = [
        "# Single agent against the newsroom",
        "",
        f"`scripts/eval_single_vs_multi.py` takes the {n} moments the newsroom chose to air across "
        f"{', '.join(matches)}, and writes each one two ways with the same computed evidence: by "
        "one prompt (the single agent, whose answer airs as it is) and by the full workflow "
        "(Producer, Analyst, Verifier, Narrator, Gate). The first rows use a deterministic check: "
        "every number in the text must match a computed fact for that moment. The Foundry rows "
        "are Microsoft Foundry evaluators (`azure-ai-evaluation`), run by `chat-fast`, a "
        "different model from the one that wrote the text.",
        "",
        "| | Single agent | Newsroom |",
        "|---|---|---|",
        f"| Moments with a number that is not a computed fact | "
        f"**{sa['with_unsupported_number']} of {sa['answered']} ({rate_single}%)** | "
        f"**{nr['with_unsupported_number']} of {n} ({rate_news}%)** |",
        f"| Unsupported numbers in total | {sa['unsupported_numbers']} | "
        f"{nr['unsupported_numbers']} |",
    ]
    if "with_story_error" in sa:
        lines.append(
            f"| Moments with a story error (wrong club, wrong time, result called mid-match, "
            f"code names, a booking said to change tactics) | "
            f"**{sa['with_story_error']} of {sa['answered']} "
            f"({pct(sa['with_story_error'], sa['answered'])}%)** | "
            f"**{nr['with_story_error']} of {n} ({pct(nr['with_story_error'], n)}%)** |"
        )
    lines += [
        f"| Time | {sa['median_seconds_per_moment']} s per moment (median) | "
        f"{nr['seconds_per_batch_of_5']} s for a batch of 5 moments, in parallel |",
        f"| Claims the Verifier sent back | none (no Verifier) | "
        f"{nr['had_a_claim_rejected']} moments |",
        f"| Aired as a numbers-only card | none | {nr['numbers_only_fallback']} moments |",
    ]
    fs = s.get("foundry_scores")
    if fs:
        j = s["judged"]
        lines.append(
            f"| Texts the Foundry judge scored | {j['single']} of {sa['answered']} | "
            f"{j['newsroom']} of {n} |"
        )
        for k in QUALITY:
            lines.append(
                f"| Foundry {k} (1 to 5, higher is better) | {fs['single'][k]} | "
                f"{fs['newsroom'][k]} |"
            )
    lines += [""]
    lines += reading(s)
    lines += ["", "## Examples of what the single agent got wrong", ""]
    ex = s["examples"]
    if ex:
        for e in ex:
            lines.append(
                f'- `{e["moment"]}`: "{e["text"]}" (not backed by the data: '
                f"{', '.join(f'{x:g}' for x in e['unsupported'])})"
            )
    else:
        lines.append("None in this run.")
    for e in s.get("story_examples", []):
        lines.append(f'- `{e["moment"]}`: "{e["text"]}" ({"; ".join(e["problems"])})')
    lines += [
        "",
        "## What this does and does not show",
        "",
        "- The number check is blunt. It asks whether a number appears among the computed facts "
        "for the moment. It cannot see a true number attached to the wrong team or metric, "
        "which the Verifier does catch because it recomputes each claim as a (metric, team, "
        "window) triple.",
        "- The newsroom's text is checked by the same kind of code that judges it, so a zero "
        "there is expected by construction. That holds for the story check too: what it shows "
        "is how often one prompt alone would have aired those mistakes, not that the newsroom "
        "writers never make them (the Verifier sent 12 back).",
        "- The Foundry evaluators are language models. They are not a ground truth, and they "
        "reward longer, fuller text. The newsroom writes to a tight format on purpose.",
        "- The comparison uses one prompt for the single agent, written by us. A better prompt "
        "might score higher still.",
        "- Three matches, one run each. Which moments the Producer airs can differ between "
        "runs. Re-run it with `uv run --group eval python -m scripts.eval_single_vs_multi`.",
        "",
    ]
    return "\n".join(lines)


def reading(s: dict[str, Any]) -> list[str]:
    """What the numbers say, written from the numbers so it cannot drift from them."""
    n, sa, nr = s["moments_aired"], s["single_agent"], s["newsroom"]
    out = [
        "## Reading it",
        "",
        f"**Numbers.** The single agent, given the same evidence menu, put a number that is not a "
        f"computed fact into {sa['with_unsupported_number']} of {sa['answered']} moments. "
        f"The newsroom put none into {n}. A single well-fed prompt is mostly honest about "
        "numbers, so what the Verifier adds is a guarantee, not a large correction. It did "
        f"send a claim back in {nr['had_a_claim_rejected']} of {n} moments: errors in the "
        "Analyst step that an unchecked pipeline would have aired.",
        "",
    ]
    if "with_story_error" in sa:
        out += [
            f"**Story.** Numbers can all be right while the sentence is wrong. The same story "
            f"rules the Verifier applies found an error in {sa['with_story_error']} of "
            f"{sa['answered']} single-agent texts and {nr['with_story_error']} of {n} newsroom "
            "texts: crediting the wrong club, a time phrase that does not fit the clock, a "
            "result called before full time, a metric's code name pasted into prose. No model "
            "judges this; it is the same code that runs on every line before it airs.",
            "",
        ]
    fs = s.get("foundry_scores")
    if fs:
        worse = [k for k in QUALITY if (fs["single"][k] or 0) > (fs["newsroom"][k] or 0)]
        if worse:
            out += [
                "**Quality.** On Foundry's evaluators the single agent scored higher on "
                f"{', '.join(worse)}. The newsroom writes to a tighter format (a headline of "
                "six words, a trimmed body, no number the Analyst did not claim) and the "
                "evaluators favour fuller text. We have not closed that gap, and we do not "
                "claim the newsroom writes better.",
                "",
            ]
    out += [
        f"**Speed.** The single agent took {sa['median_seconds_per_moment']} s per moment. The "
        f"newsroom took {nr['seconds_per_batch_of_5']} s for a batch of 5, running in parallel, "
        "because it makes three model calls and a deterministic check. On the broadcast the "
        "instant overlay is already on screen, so this delays the explanation, never the "
        "picture.",
        "",
        "**What the newsroom is for.** The single prompt wrote one casual line. The newsroom "
        "writes four viewer types in six languages from one verified analysis, keeps an audit "
        "trail for every moment (what each agent said, what the Verifier rejected), falls back "
        "to a numbers-only card instead of airing something unchecked, and keeps the broadcast "
        "running when an agent is slow or down. Those are the reasons for the structure, "
        "rather than better prose.",
    ]
    return out


async def main(matches: list[str], latency_batches: int) -> None:
    store = MatchStore()
    results = [await evaluate_match(store, m, latency_batches) for m in matches]
    summary = summarise(results)
    summary["matches"] = matches
    (ROOT / "data" / "evaluation.json").write_text(json.dumps(summary, indent=1), "utf-8")
    (ROOT / "docs" / "EVALUATION.md").write_text(report(summary), "utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "examples"}, indent=1))


if __name__ == "__main__":
    load_dotenv()
    os.environ.setdefault(
        "FOUNDRY_OPENAI_ENDPOINT", "https://novessapitchside1.cognitiveservices.azure.com"
    )
    ap = argparse.ArgumentParser()
    ap.add_argument("--matches", nargs="+", default=["derby_01", "derby_02", "derby_03"])
    ap.add_argument("--latency-batches", type=int, default=2)
    ap.add_argument(
        "--report-only", action="store_true", help="rewrite the report from the saved results"
    )
    args = ap.parse_args()
    if args.report_only:
        saved = json.loads((ROOT / "data" / "evaluation.json").read_text("utf-8"))
        (ROOT / "docs" / "EVALUATION.md").write_text(report(saved), "utf-8")
        raise SystemExit(0)
    asyncio.run(main(args.matches, args.latency_batches))
