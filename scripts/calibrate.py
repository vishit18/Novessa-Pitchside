"""Realism check: simulate many matches and compare them to typical top-flight ranges.

    uv run python -m scripts.calibrate            # 200 matches
    uv run python -m scripts.calibrate --n 40     # a quick run

The reference ranges are general football knowledge written down in docs/03 section 7. They are
not taken from any dataset, and the real-footage data (SoccerTrack v2) is never used here.
Writes docs/img/calibration.png, docs/CALIBRATION.md and data/calibration.json.
"""

from __future__ import annotations

import argparse
import itertools
import json
import statistics
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED0 = 1000


@dataclass(frozen=True)
class Metric:
    key: str
    label: str
    low: float | None
    high: float | None
    note: str = ""


# (low, high) is the typical range for a top-flight match. None means no reference we trust.
METRICS = [
    Metric("goals", "Goals per match", 2.5, 3.0),
    Metric("shots_team", "Shots per team", 10, 15),
    Metric("passes", "Passes per match", 800, 1100),
    Metric("pass_completion", "Pass completion (%)", 75, 88),
    Metric("poss_spread", "Possession gap (points)", 4, 20, "typical gap between the sides"),
    Metric("distance_km", "Distance per outfield starter (km)", 9, 12),
    Metric("top_speed", "Fastest sprint in the match (km/h)", 32, 35),
    Metric("shot_speed", "Fastest shot in the match (km/h)", 100, 125),
    Metric("fouls", "Fouls per match", 20, 24),
    Metric("yellows", "Yellow cards per match", 3, 4),
    Metric("reds", "Red cards per match", 0.05, 0.15, "about one match in ten"),
    Metric("corners", "Corners per match", 9, 11),
    Metric("penalties", "Penalties per match", 0.15, 0.35),
    Metric("offsides", "Offsides per match", 4, 10, "both sides together"),
    Metric("difficulty_median", "Median pass difficulty", 20, 30, "target about 25"),
    Metric("difficulty_hard", "Passes rated above 70 (%)", 3, 7, "target: top 5%"),
    Metric("sprints", "Sprints over 30 km/h per match", None, None, "no trusted reference"),
]


def one_match(i: int) -> dict[str, float]:
    """Simulate match `i` and measure it with the same state engine the app uses."""
    from backend.state.engine import StateEngine
    from engine.clock import merge_by_time
    from engine.league import load_league
    from engine.schema import EventType, MatchEvent, TrackingFrame
    from engine.sim import simulate_match

    league = load_league(ROOT / "data" / "league")
    codes = [c.code for c in league.clubs]
    pairs = [(h, a) for h in codes for a in codes if h != a]
    home, away = pairs[i % len(pairs)]
    m = simulate_match(league, home, away, SEED0 + i, f"cal_{i:03d}")
    engine = StateEngine(m.meta)
    for item in merge_by_time(m.events, m.tracking.iter_frames(5.0)):
        if isinstance(item, MatchEvent):
            engine.ingest_event(item)
        elif isinstance(item, TrackingFrame):
            engine.ingest_frame(item)

    ev = m.events
    passes = [e for e in ev if e.type == EventType.PASS]
    done = sum(1 for e in passes if e.outcome == "complete")
    diffs = sorted(e.pass_difficulty for e in passes if e.pass_difficulty is not None)
    shots = [e for e in ev if e.type == EventType.SHOT]
    stats = engine.team_stats
    poss = engine.possession_match()
    outfield = {
        s.player_id
        for sheet in (m.meta.home, m.meta.away)
        for s in sheet.starters
        if s.group != "GK"
    }
    dist = [p.distance_km for pid, p in engine.players.items() if pid in outfield]
    return {
        "goals": float(sum(m.score)),
        "shots_team": len(shots) / 2,
        "passes": float(len(passes)),
        "pass_completion": 100 * done / max(len(passes), 1),
        "poss_spread": abs(poss[home] - poss[away]),
        "distance_km": statistics.fmean(dist) if dist else 0.0,
        "top_speed": max((p.top_speed_kmh for p in engine.players.values()), default=0.0),
        "shot_speed": max((p.top_shot_kmh for p in engine.players.values()), default=0.0),
        "fouls": float(sum(s.fouls for s in stats.values())),
        "yellows": float(sum(s.yellows for s in stats.values())),
        "reds": float(sum(s.reds for s in stats.values())),
        "corners": float(sum(s.corners for s in stats.values())),
        "penalties": float(sum(s.penalties for s in stats.values())),
        "offsides": float(sum(s.offsides for s in stats.values())),
        "difficulty_median": statistics.median(diffs) if diffs else 0.0,
        "difficulty_hard": 100 * sum(1 for d in diffs if d > 70) / max(len(diffs), 1),
        "sprints": float(sum(p.sprints for p in engine.players.values())),
    }


def pct(values: list[float], q: float) -> float:
    s = sorted(values)
    return s[min(len(s) - 1, int(q * len(s)))]


def summarise(rows: list[dict[str, float]]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for mt in METRICS:
        v = [r[mt.key] for r in rows]
        mean = statistics.fmean(v)
        half = 1.96 * statistics.stdev(v) / len(v) ** 0.5
        if mt.low is None or mt.high is None:
            verdict = "no reference"
        elif mt.low <= mean <= mt.high:
            verdict = "in range"
        elif mean + half >= mt.low and mean - half <= mt.high:
            verdict = "within sampling error"
        else:
            verdict = "too high" if mean > mt.high else "too low"
        out.append(
            {
                "key": mt.key,
                "label": mt.label,
                "mean": round(mean, 2),
                "ci95": round(half, 2),
                "p10": round(pct(v, 0.10), 2),
                "p90": round(pct(v, 0.90), 2),
                "low": mt.low,
                "high": mt.high,
                "verdict": verdict,
                "note": mt.note,
            }
        )
    return out


def chart(rows: list[dict[str, float]], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cols = 4
    n_rows = -(-len(METRICS) // cols)
    fig, axes = plt.subplots(n_rows, cols, figsize=(16, 3.1 * n_rows))
    for ax, mt in itertools.zip_longest(axes.flat, METRICS):
        if mt is None:
            ax.axis("off")
            continue
        v = [r[mt.key] for r in rows]
        ax.hist(v, bins=18, color="#3b82c4", edgecolor="#0d1014")
        if mt.low is not None and mt.high is not None:
            ax.axvspan(mt.low, mt.high, color="#ffb020", alpha=0.25)
        ax.axvline(statistics.fmean(v), color="#222222", lw=1.2, ls="--")
        ax.set_title(mt.label, fontsize=10)
        ax.tick_params(labelsize=8)
    fig.suptitle(
        f"{len(rows)} simulated matches. Amber band: typical top-flight range. Dashed: our mean.",
        fontsize=12,
    )
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110)


def report(summary: list[dict[str, object]], n: int) -> str:
    lines = [
        "# Calibration report",
        "",
        f"`scripts/calibrate.py` simulates {n} matches (seeds {SEED0} to {SEED0 + n - 1}, every "
        "pairing of the eight clubs, home and away) and measures each one with the same state "
        "engine the app uses. The amber bands are typical top-flight ranges written down in "
        "[docs/03](03_SYNTHETIC_DATA.md) as general football knowledge. They are not copied from "
        "any dataset, and the real-footage data is never used to tune the engine.",
        "",
        "![Distributions of match measures against typical ranges](img/calibration.png)",
        "",
        "| Measure | Our mean (95% interval) | 10th to 90th percentile | Typical range | Verdict |",
        "|---|---|---|---|---|",
    ]
    for r in summary:
        rng = "none" if r["low"] is None else f"{r['low']} to {r['high']}"
        note = f" ({r['note']})" if r["note"] else ""
        lines.append(
            f"| {r['label']}{note} | {r['mean']} ± {r['ci95']} | "
            f"{r['p10']} to {r['p90']} | {rng} | {r['verdict']} |"
        )
    bad = [r for r in summary if r["verdict"] in ("too high", "too low")]
    close = [r for r in summary if r["verdict"] == "within sampling error"]
    lines += ["", "## What is still off", ""]
    if close:
        lines.append(
            "Just outside the band, by less than the sampling error of "
            f"{n} matches, so not clearly wrong: "
            + ", ".join(str(r["label"]).lower() for r in close)
            + "."
        )
        lines.append("")
    if bad:
        for r in bad:
            lines.append(
                f"- {r['label']}: {r['verdict']} ({r['mean']} against {r['low']} to {r['high']})."
            )
    else:
        lines.append("Nothing is clearly outside its range.")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    args = ap.parse_args()
    with ProcessPoolExecutor() as pool:
        rows = list(pool.map(one_match, range(args.n), chunksize=2))
    summary = summarise(rows)
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "calibration.json").write_text(
        json.dumps({"matches": args.n, "summary": summary}, indent=1), encoding="utf-8"
    )
    chart(rows, ROOT / "docs" / "img" / "calibration.png")
    (ROOT / "docs" / "CALIBRATION.md").write_text(report(summary, args.n), encoding="utf-8")
    for r in summary:
        print(f"{r['label']:<42} mean {r['mean']:>8}  {r['verdict']}")


if __name__ == "__main__":
    main()
