"""Export a batch of simulated matches as Parquet: the dataset we publish.

    uv run python -m scripts.export_dataset                 # 200 matches into data/export/
    uv run python -m scripts.export_dataset --n 20 --out /tmp/pitchside

Writes `matches.parquet` (one row per match), `events.parquet` (one row per event) and
`players.parquet` (one row per player). The datasheet is data/README.md. Tracking frames are
not exported: they regenerate from the seed (see the datasheet). The same seeds as the
calibration run are used, so the dataset and docs/CALIBRATION.md describe the same matches.
"""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SEED0 = 1000


def one_match(i: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Simulate match `i`; return its row for matches.parquet and its event rows."""
    from engine.league import load_league
    from engine.sim import simulate_match

    league = load_league(ROOT / "data" / "league")
    codes = [c.code for c in league.clubs]
    pairs = [(h, a) for h in codes for a in codes if h != a]
    home, away = pairs[i % len(pairs)]
    m = simulate_match(league, home, away, SEED0 + i, f"m{i:04d}")
    meta = m.meta
    row = {
        "match_id": meta.match_id,
        "seed": meta.seed,
        "competition": meta.competition,
        "matchday": meta.matchday,
        "venue": meta.venue,
        "kickoff_time": meta.kickoff_time,
        "weather": meta.weather,
        "referee": meta.referee,
        "home": meta.home.code,
        "away": meta.away.code,
        "home_formation": meta.home.formation,
        "away_formation": meta.away.formation,
        "home_goals": m.score[0],
        "away_goals": m.score[1],
        "events": len(m.events),
    }
    events = []
    for e in m.events:
        d = e.model_dump(mode="json")
        d["tags"] = json.dumps(d["tags"])
        d["pressure_by"] = json.dumps(d["pressure_by"])
        d["difficulty_factors"] = (
            json.dumps(d["difficulty_factors"]) if d["difficulty_factors"] else None
        )
        events.append(d)
    return row, events


def players_table() -> list[dict[str, Any]]:
    from engine.league import load_league

    league = load_league(ROOT / "data" / "league")
    rows = []
    for club in league.clubs:
        for p in club.players:
            rows.append(
                {
                    "player_id": p.id,
                    "club": club.code,
                    "name": p.name,
                    "shirt": p.shirt,
                    "position": p.position,
                    **{f"attr_{k}": v for k, v in p.attributes.model_dump().items()},
                }
            )
    return rows


def main() -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "export")
    args = ap.parse_args()
    with ProcessPoolExecutor() as pool:
        results = list(pool.map(one_match, range(args.n), chunksize=2))
    args.out.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist([r for r, _ in results]), args.out / "matches.parquet")
    events = [e for _, evs in results for e in evs]
    pq.write_table(pa.Table.from_pylist(events), args.out / "events.parquet")
    pq.write_table(pa.Table.from_pylist(players_table()), args.out / "players.parquet")
    print(f"{len(results)} matches, {len(events)} events, written to {args.out}")


if __name__ == "__main__":
    main()
