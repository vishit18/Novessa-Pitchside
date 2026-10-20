# Northbridge League: a synthetic football dataset

A fictional league, simulated match by match, with the events and the player positions a broadcaster's data feed would carry. Every club, player, manager and referee is invented. No real match, player or club is in here, and nothing was copied or fitted from real data.

It exists to feed [Novessa Pitchside](../README.md), and it is published so anyone can build on it: a data feed that is realistic enough to test live graphics, stats and commentary tools against, with none of the licensing problems of the real thing.

## What is in the repo and what you generate

| What | Where | Size |
|---|---|---|
| The league: 8 clubs, 144 players, managers | `data/league/*.json` | small, in git |
| Three demo matches (events as JSON lines) | `data/matches/derby_01..03.jsonl` | about 1 MB each, in git |
| 200 simulated matches as Parquet | `data/export/` | 19 MB, **generated**, not in git |
| Realism check against typical top-flight ranges | [`docs/CALIBRATION.md`](../docs/CALIBRATION.md) | |

Generate the Parquet files with:

```bash
uv sync
uv run python -m scripts.export_dataset            # 200 matches, about a minute
```

That writes `matches.parquet` (200 rows), `events.parquet` (545,639 rows) and `players.parquet` (144 rows). Match `m0000` to `m0199` use seeds 1000 to 1199, covering every home and away pairing of the eight clubs. The league is generated from seed 2026. The same code and seeds always give the same data.

```python
import pyarrow.parquet as pq

events = pq.read_table("data/export/events.parquet").to_pandas()
passes = events[events.type == "pass"]
```

## Events

One row per thing that happened. The same schema comes from the simulator and from the vision pipeline; `source` says which (`synthetic` here).

| Field | Meaning |
|---|---|
| `event_id`, `match_id`, `seq` | Identifiers. `seq` orders events inside a match |
| `t_match` | Seconds since the first kick-off. Monotonic, includes stoppage, and the second half continues from where the first ended |
| `period`, `clock` | 1 or 2, and the display clock: `23:07`, `45+1:12`, `90+2:40` |
| `type` | `kick_off, pass, carry, dribble, shot, save, goal, tackle, interception, clearance, block, foul, card, corner, free_kick, throw_in, offside, possession_change, pressure, substitution, period_start, period_end, injury_stoppage` |
| `team`, `player_id` | Club code and player. Both can be null (a manager card has a team and no player) |
| `x`, `y`, `end_x`, `end_y` | Metres on a 105 by 68 pitch. Origin bottom-left, and the home side attacks left to right in the first half |
| `outcome` | `complete`, `incomplete`, `blocked`, `saved`, `goal`, `yellow`, `red`, and so on |
| `receiver_id` | Intended receiver of a pass |
| `under_pressure`, `pressure_by` | Whether a defender was closing, and who (JSON list) |
| `ball_speed_kmh` | Passes and shots |
| `height`, `body_part` | `ground`, `low`, `high`; foot, head or other |
| `tags` | JSON list: `progressive`, `through_ball`, `penalty`, `second_yellow`, `straight_red`, `manager`, `score:1-0`, `assist:ASH-11` and more |
| `pass_difficulty` | 0 to 100, from an explainable model, passes only |
| `difficulty_factors` | JSON list of the points each factor added to that score (distance, lane obstruction, pressure on the passer, receiver marking, angle, height, weak foot, tempo) |
| `xg` | Expected goals, shots only. A penalty is 0.76 |
| `source` | `synthetic` |

A foul is followed by a free kick for the other side. A foul by a defender in his own box can give a penalty: a `free_kick` tagged `penalty` at the spot, then a `shot` tagged `penalty`. A second yellow is a `yellow` and a `red` at the same instant, both tagged `second_yellow`, and a sent-off player leaves the pitch for good, so the side plays one short.

## Tracking

Player and ball positions at 10 Hz (`match_id`, `t_match`, ball `x, y, z`, and for every player `id, x, y, v_kmh`). These are not exported to Parquet, because they are large and regenerate exactly from the seed:

```python
from engine.league import load_league
from engine.sim import simulate_match

m = simulate_match(load_league("data/league"), "ASH", "KES", seed=43, match_id="derby_01")
frame = m.tracking.frame_at(1607.0)
```

Players that have been sent off are missing from the frames after the card.

## How it was made

The engine simulates football decisions on top of light movement, not full physics.

- A team in possession moves through phases, and whoever has the ball picks an action (pass, carry, dribble, shot, clearance) with a probability set by the phase, where they are on the pitch, the pressure on them, their own attributes and their club's tactical identity (pressing, tempo, directness).
- Players hold a formation that shifts as a block with the ball, drift towards their slot with some noise, and are capped by pace and fatigue. Stamina drains, and sprint speed falls late on.
- Pass completion is a logistic function of the pass difficulty and the passer's skill. Shots use a simple expected-goals model on distance, angle, pressure and body part.
- Fouls, cards, penalties, corners, offsides and substitutions follow rules with seeded randomness.
- Each match gets a seeded script of two or three storylines that the engine nudges towards without forcing, such as a side that dominates the first half and cannot score, or a substitute who changes the game. The script is written to a separate file and is never shown to the agents, so they have to find the story in the data.
- Players have twelve attributes from 1 to 99 (pace, stamina, passing, vision, finishing and so on) generated from the league seed.

## How realistic is it

[`docs/CALIBRATION.md`](../docs/CALIBRATION.md) measures all 200 matches against typical top-flight ranges, with a chart. In short, of the 16 measures that have a reference range, 14 are inside it and 2 (goals and red cards per match) sit just outside by less than the sampling error. The engine was tuned until it got there, in a few rounds that are visible in the git history.

The reference ranges are general football knowledge, not taken from any dataset. Real footage data (SoccerTrack v2) is kept strictly apart. It lives in `vision/`, is tagged `source: "vision"`, and was never used to build, tune or check the engine.

## Known limits

- **It is not real football.** It looks right on the averages, but the shape of real matches, the way a game opens up or goes flat, is only approximated by the storyline arcs.
- **Offside is a flag, not a line.** About 7% of through balls are flagged. There is no offside line, so no goal is ever disallowed.
- **Injuries are only a stoppage.** Nobody is hurt in a way that changes the match. Weather is recorded in the metadata and has no effect on play. Referees are a name and nothing more.
- **Pass difficulty is our own model,** built to be explainable. It is not a published metric and is not validated against real data.
- **No home advantage is modelled,** and clubs differ only by a formation and three tactical numbers: pressing, directness and tempo.
- **Tracking is simplified.** Players move toward targets with noise, so off-the-ball runs are less varied than real ones.
- **Sprint counts have no trusted reference.** The 68 sprints over 30 km/h per match are reported, not judged.

## Licence

The data is released under **CC BY 4.0**: use it, adapt it, credit "Novessa Pitchside synthetic Northbridge League dataset". The code that generates it is MIT. Because every name is invented, there are no personal-data or trademark questions. If any invented name happens to match a real person or club, that is a coincidence, and an automated check against a denylist runs in the tests.
