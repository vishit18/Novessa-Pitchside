"""Generate the fictional league and the demo matches into data/.

uv run python -m scripts.seed
"""

from __future__ import annotations

from pathlib import Path

from engine.io import write_match
from engine.league import DEFAULT_SEED, generate_league, save_league
from engine.sim import simulate_match

ROOT = Path(__file__).resolve().parent.parent
# (match_id, home, away, seed). Seeds picked after the 200-match calibration to show off the
# discipline and set pieces: derby_01 is 2-1 with a penalty goal, a second-yellow red and five
# offsides; derby_02 is 2-1 with a penalty, a red card, a manager booking and five offsides;
# derby_03 is 3-0 with a penalty and five offsides.
DEMO_MATCHES = [
    ("derby_01", "ASH", "KES", 43),
    ("derby_02", "SAL", "MIL", 2),
    ("derby_03", "POR", "HAR", 17),
]


def main() -> None:
    league = generate_league(DEFAULT_SEED)
    save_league(league, ROOT / "data" / "league")
    print(f"league: {len(league.clubs)} clubs")
    for match_id, home, away, seed in DEMO_MATCHES:
        match = simulate_match(league, home, away, seed, match_id, matchday=1)
        path = write_match(match, ROOT / "data" / "matches")
        print(
            f"{match_id}: {home} {match.score[0]}-{match.score[1]} {away}  "
            f"{len(match.events)} events  {path.stat().st_size // 1024} KB"
        )


if __name__ == "__main__":
    main()
