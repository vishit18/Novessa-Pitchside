# Synthetic data: the match engine

Judges explicitly score "creativity and optimised synthetic data creation", and the brief lists "data innovation" as its own requirement. So the engine is a feature in its own right, not plumbing. It should produce matches a football fan would believe.

## 1. The fictional league

**Northbridge League**, 8 invented clubs. All names, colours and players are made up. Before committing, sanity-check that no name matches a real professional club or player.

Example clubs (Claude Code can refine, but keep them invented and believable):
- Ashford Rovers, Kestrel Bay FC, Millwater United, Harrowgate Athletic, Port Calder, Redmoor Town, Saltmarsh City, Thornbury Wanderers

Each club has: name, short code (3 letters), two kit colours, a home ground, a **tactical identity** (e.g. high press 4-3-3, deep block 5-4-1, possession 4-2-3-1, direct 4-4-2), and 18 players.

Each player has: id, name (mix of nationalities, invented), shirt number, position, preferred foot, age, and attributes 1–99: `pace, acceleration, stamina, passing, vision, first_touch, finishing, shot_power, tackling, positioning, pressing, composure`.

Generated once with a fixed seed and saved to `data/league/*.json`. Commit these.

## 2. Event schema (contract — Pydantic models in `engine/schema.py`)

Every event, from the engine or from vision:

```json
{
  "event_id": "m01-000412",
  "match_id": "m01",
  "seq": 412,
  "t_match": 1387.4,          // seconds of match time since the first kick-off; monotonic, includes stoppage, period 2 continues from where period 1 ended
  "period": 1,
  "clock": "23:07",           // display clock: "23:07", "45+1:12", "90+2:40"
  "type": "pass",             // see list below
  "team": "ASH",
  "player_id": "ASH-08",
  "x": 61.2, "y": 22.5,       // metres, pitch 105 x 68, origin bottom-left, team attacks left→right in period 1
  "end_x": 78.0, "end_y": 30.1,
  "outcome": "complete",      // complete | incomplete | blocked | saved | goal | won | lost ...
  "receiver_id": "ASH-10",
  "under_pressure": true,
  "pressure_by": ["KES-04"],
  "ball_speed_kmh": 54.3,
  "height": "ground",         // ground | low | high
  "body_part": "right_foot",
  "tags": ["progressive", "through_ball"],
  "pass_difficulty": 84.0,    // passes only, 0-100, from the model in section 5
  "difficulty_factors": [{"name": "pressure_on_passer", "points": 21.3}],  // passes only, points each factor added
  "xg": null,                 // shots only
  "source": "synthetic"       // synthetic | vision
}
```

### Discipline and set pieces

- **Fouls** come from tackles and from off-the-ball contact on a pressured player. Each foul gives a `foul` event (by the offender), then a `free_kick` for the other side. Target: about 20 to 24 fouls a match.
- **Cards** are `card` events. `outcome` is `yellow` or `red`. A second yellow is a `yellow` event followed by a `red` event tagged `second_yellow`. Straight reds are rare. Target: about 3 to 4 yellows a match, a red in roughly one match in ten.
- **A red card means ten men.** The player leaves the pitch (he drops out of the tracking frames), nobody replaces him, and the side keeps its formation minus that slot.
- **Penalties.** A foul by a defender inside his own box gives a `free_kick` event tagged `penalty` at the spot, then a `shot` tagged `penalty` (xG 0.76). There is no separate event type.
- **Manager cards.** A `card` event with `tags: ["manager"]`, `player_id` null and `team` set. Rare: managers are booked about once in ten matches and sent off far less often.
- **Corners** follow saved or blocked shots, deflected clearances and overhit attacking passes. Target: about 9 to 11 a match.
- `Club.manager` is the manager's name (invented).

Event types (minimum): `kick_off, pass, carry, dribble, shot, save, goal, tackle, interception, clearance, block, foul, card, corner, free_kick, throw_in, offside, possession_change, pressure, substitution, period_start, period_end, injury_stoppage`.

Plus a separate high-frequency **tracking frame** stream (10 Hz is enough) for player and ball positions:
```json
{"match_id":"m01","t_match":1387.4,"ball":{"x":61.2,"y":22.5,"z":0.1},
 "players":[{"id":"ASH-08","x":61.0,"y":22.3,"v_kmh":12.4}, ...]}
```
Tracking drives the 2D feed, name tags, speed and distance thresholds.

**Match metadata**: match_id, seed, competition "Northbridge League", matchday, venue, kick-off time, weather, referee (invented), lineups, formations, captains.

## 3. How the engine works

Don't simulate physics in full. Simulate *football decisions* on top of light kinematics. That's what makes it believable.

- **Possession state machine.** The team in possession is in a phase: `build_up → progression → final_third → chance`, or `transition`. Each tick the ball carrier picks an action (pass, carry, dribble, shot, clearance) with probabilities driven by phase, position on the pitch, pressure nearby, player attributes and team tactical identity.
- **Positions.** Each team has a formation shape that shifts as a block with the ball (compact out of possession, stretched in possession). Players drift toward their slot plus noise; pressers move toward the ball. Speeds are capped by attributes and fatigue.
- **Pressure.** Defenders within ~5 m closing at speed create `pressure` events. Pressing teams press more and higher.
- **Outcomes.** Pass completion probability is a logistic function of pass difficulty (§5) and passer skill. Shots use a simple xG model (distance, angle, pressure, body part), and goal probability = xG adjusted by finishing vs keeper.
- **Fatigue and game state.** Stamina drains, sprint speed drops late on. Teams behind push higher after 70'. Red cards change shape. Subs happen around 60–80'.
- **Storylines (this is the secret sauce).** Each generated match gets a seeded script of 2–3 "arcs" the engine nudges toward without forcing: e.g. *home side dominates first half but can't score*, *a substitute changes the game*, *late pressure collapse*, *a star player has a quiet game then one moment*. These create the moments the agents will explain. The script is metadata the agents never see — they have to find the story from the data, which is the honest test.

## 4. Real-time playback

The engine pre-computes the whole match (fast, a second or two) then a **clock** streams events and tracking frames in match time. Speed multiplier: 1×, 4×, 10×, 30×. Pause/seek for the demo. In live mode the engine runs tick by tick instead (to prove it's genuinely streaming), same output.

## 5. Pass difficulty (0–100), our explainable model

Each pass gets a score and the **factors** that produced it, so the overlay can say *why* it was hard:

| Factor | Effect |
|---|---|
| Distance | longer = harder (non-linear) |
| Lane obstruction | defenders near the pass line, by perpendicular distance |
| Pressure on passer | number of defenders within 3 m and their closing speed |
| Receiver marking | nearest defender to receiver at arrival |
| Angle / direction | forward and switches harder than backward |
| Height | lofted harder to execute accurately |
| Weak foot | penalty |
| Tempo | first-time passes harder |

Combine with fixed weights into a logit, scale to 0–100. Calibrate so that across many matches: median ≈ 25, top 5% > 70, and completion rate falls smoothly as difficulty rises. Write the weights in code with comments. Unit-test monotonicity (more pressure never makes a pass easier).

## 6. Derived metrics (state engine, `backend/state/`)

- Possession % (rolling 5 min and full match)
- **Momentum** (−100…+100): weighted recent territory, shots, xG, final-third entries, with exponential decay
- **Pressure index** per team: pressing actions per opponent pass in their own half (like PPDA, inverted), rolling
- **Control vs Chaos index** (0–100): high control = long possessions, low turnover rate, compact shape; chaos = rapid turnovers, transitions, spread shape, fouls
- **Rhythm**: events per minute, average possession length, tempo shifts; flag when rhythm breaks
- Pass networks, progressive passes, line-breaking passes
- Per player: distance covered, sprint count, top speed, passes, pass accuracy, average difficulty, duels, xG, xA
- Ball speed per pass, shot speed per shot
- **Threshold triggers** (configurable in `config/thresholds.yaml`): sprint > 30 km/h, shot > 100 km/h, distance milestones (every 2 km), pass difficulty > 80, etc.
- **Milestones**: first goal, hat-trick watch, 50th/100th pass, fastest sprint of the match, longest pass, a player's best-ever (vs synthetic season baseline)
- **Candidate moments**: goals, big chances, momentum swings beyond a threshold, pressure shift detected, control→chaos flips, red cards, rhythm breaks, standout individual actions. Each gets a `moment_id`, a deterministic significance score, and a state snapshot. These go to the agents.

## 7. Realism check (make it visible — it's scored)

`scripts/calibrate.py` generates 200 matches and prints/plots distributions against typical top-flight ranges that are general football knowledge (not copied from any dataset):
- goals per match ~2.5–3, shots per team ~10–15, pass completion ~75–88%, possession spread, distance per outfield player ~9–12 km, top sprint speeds ~32–35 km/h, shot speeds up to ~120 km/h

Do **not** calibrate against SoccerTrack v2 or any other real dataset; that data is reserved for the vision pipeline (`docs/06`). Save the chart in `docs/img/calibration.png` and reference it in the README. If something is off, tune the engine.

## 8. The dataset we publish

`data/matches/` gets a handful of sample matches in git (JSONL, small). `scripts/export_dataset.py` writes Parquet + a `data/README.md` **datasheet**: what each field means, how it was generated, seeds, known limitations, licence (CC BY 4.0 for the data). This is our "data innovation" deliverable.
