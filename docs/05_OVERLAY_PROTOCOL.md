# Overlay protocol

The brief asks for output "timed and machine-readable enough to be rendered as synchronised graphical overlays on a live match feed, in the way the platform's rendering partner handles overlays in the production path". So our overlays are **data first, pixels second**. Our React renderer is one consumer; a broadcast graphics engine could be another.

Publish this as a versioned spec: `docs/overlay-protocol-v1.md` + JSON Schema in `backend/app/schemas/overlay.schema.json`. That's a real-world-readiness point in itself.

## Message envelope

```json
{
  "v": 1,
  "msg_id": "ovl-m01-00231",
  "match_id": "m01",
  "moment_id": "mom-m01-0042",        // links instant + language overlays for the same moment
  "op": "show",                        // show | update | hide | clear_slot
  "slot": "lower_third",               // lower_third | top_bar | side_panel | player_tag | pitch_annotation | fullscreen_card | ticker
  "kind": "pass_difficulty",           // see kinds below
  "priority": 70,                      // 0–100; renderer resolves collisions by slot + priority
  "t_match": 1387.4,                   // match clock time this refers to (sync key)
  "t_wall_emit": "2026-10-24T19:03:11.204Z",  // set at send time, null in exports
  "show_at": 1387.6,                   // match time to appear
  "duration_s": 6.0,
  "anchor": {"type": "player", "id": "ASH-08"},   // or {"type":"pitch","x":..,"y":..} or null
  "persona": ["analyst", "casual"],    // who this variant is for
  "lang": "en",
  "payload": { ... kind-specific ... },
  "provenance": {
    "source": "state_engine",          // state_engine | agent:analyst | agent:recap ...
    "verified": true,
    "evidence": [{"metric":"pass_difficulty","value":84}]
  }
}
```

## Kinds (minimum set)

| kind | source | payload |
|---|---|---|
| `player_tag` | state engine | name, number, team colour, optional `speed_kmh`, `distance_km` |
| `speed_burst` | state engine (threshold) | player, speed_kmh, rank in match |
| `distance_milestone` | state engine (threshold) | player, km |
| `pass_difficulty` | state engine | difficulty 0–100, distance_m, ball_speed_kmh, factors[] |
| `shot_speed` | state engine | speed_kmh, xG, outcome |
| `momentum_bar` | state engine | value −100…100, trend |
| `control_chaos` | state engine | value, label |
| `pressure_shift` | state engine + agent | from/to team, index delta |
| `insight` | agent (verified) | headline, body, persona-specific text, optional mini-chart data |
| `milestone` | state engine + agent | text, icon key |
| `commentary_line` | agent | text, audio_url (optional) |
| `recap` | agent | sections[] |
| `stat_compare` | state engine | two players / teams, metric, values |

## Transport

The gateway sends JSON text frames over `WS /ws/matches/{id}?viewer=...&persona=...&speed=...&t=...`. Every frame is `{"type": ..., "data": ...}`:

| type | data | rate |
|---|---|---|
| `frame` | `TrackingFrame` (docs/03) | 10 Hz |
| `event` | `MatchEvent` (docs/03) | as they happen |
| `state` | `StateSnapshot` (`backend/state/models.py`): score, clock, possession, momentum, pressure, control/chaos, rhythm | 1 Hz |
| `player_stats` | `{t_match, players: [PlayerStats + on_pitch], leaders}` (see below) | 1 Hz |
| `overlay` | the envelope above | as they happen |

The client may send `{"op": "play"|"pause"}`, `{"op": "speed", "value": 4}` and `{"op": "seek", "t": 1200}`. Query parameters: `persona` (analyst, casual, kids, accessibility), `club`, `player`, `metric`, `lang`. `GET /matches/{id}` returns `MatchMeta`. `t_wall_emit` is set when the gateway sends the message and is null in exports.

## player_stats

Sent to every viewer regardless of profile, once a second. `players` has one entry for every player who has been on the pitch (22 plus any substitutes who came on). Each entry: `player_id`, `team`, `on_pitch`, `passes`, `passes_complete`, `pass_accuracy` (0-1 or null), `avg_difficulty` (or null), `longest_pass_m`, `hardest_pass` (highest difficulty among completed passes), `shots`, `xg`, `xa`, `duels_won`, `duels_lost`, `fouls`, `yellows`, `reds`, `distance_km`, `top_speed_kmh`, `top_shot_kmh`, `sprints`. `leaders` maps each one-number metric to the current match leader, `{metric: {player_id, value}}`, for `sprint_speed` (top speed km/h), `shot_speed` (hardest shot km/h), `pass_difficulty` (`hardest_pass`) and `distance` (km). A metric with no leader yet is omitted. All numbers come from the state engine; the UI computes nothing.

## team_stats (inside `state`)

The `state` message carries `team_stats`: `{TEAM: {fouls, yellows, reds, corners, free_kicks, penalties, shots}}` for both teams, so the UI can show a discipline and set-piece panel without counting events itself.

## Payloads the renderer relies on

- `pass_difficulty`: slot `pitch_annotation`, anchor `{"type": "pitch", "x", "y"}` at the pass start. Payload: `difficulty` (0-100), `distance_m`, `ball_speed_kmh`, `end_x`, `end_y`, `complete` (bool), `player_id`, `factors` `[{name, points}]` (omitted for the casual persona).
- `shot_speed`: slot `lower_third`, anchored to the shooter. Payload: `speed_kmh`, `xg`, `outcome`, `player_id`.
- `speed_burst`: slot `player_tag`, anchored to the player. Payload: `speed_kmh`, `rank_in_match`.
- `distance_milestone`: slot `player_tag`. Payload: `km`.
- Cards, penalties and red cards arrive as `insight` overlays (`moment_kind` `card` or `penalty`, `tone` `info` or `chance`). The payload adds `card` (`yellow` or `red`) for cards and `staff: true` for a manager. A second yellow gives one overlay saying so.
- `milestone` and `insight`: slot `lower_third`. Payload: `headline`, `body`, `team`, `tone` (`goal`, `chance`, `swing`, `milestone`, `info`), optional `moment_kind`.
- `op: "update"` with the same `moment_id` merges its payload into the earlier overlay. Agent text arrives this way after the instant overlay.
- `momentum_bar` is not sent as an overlay in v1. The renderer reads `state.momentum`.

Agent text update: `op: "update"`, same `moment_id`, `msg_id` ending `-text-<lang>`, payload `headline`, `body`, `commentary`, `agent_status` (`verified`), `translation` (`english`, `polished`, `translated`, `llm`, `unavailable`) and `audio_url` when Speech is configured; top-level `lang` is the language the text is really in. `provenance.source` is `agent:analyst`. Only verified text is sent; a moment that fell back keeps its numbers-only card. The viewer's persona picks the variant (kids and accessibility fall back to casual, then analyst).

Gateway extras: `GET /agents/health`, `POST /agents/{agent}/kill?seconds=30` (chaos switch), `GET /matches/{id}/insights` (outputs with verification trails).

Until the agents are live, `insight` overlays carry a numbers-only fallback card written from the state engine (`provenance.source = "state_engine"`).

## Timing and sync

- Everything is keyed to **match time** (`t_match`, `show_at`), not wall time, so a renderer on a delayed stream (streaming is often 20–40 s behind) still lines up perfectly. Show this in the demo: two viewers on different delays see the same overlay at the same football moment.
- Instant overlays: `show_at` ≈ event time + 0.2 s.
- Language overlays: `show_at` = when they're ready, but they carry the original `moment_id` and `t_match` so the UI can say "earlier: …" if it's late.
- Renderer keeps a small buffer and drops anything older than its `duration_s`.

## Persona filtering

The gateway sends each viewer only the variants matching their profile. Rules live in `backend/app/personas.py`, not in the frontend:
- Analyst: all numeric kinds, insights with numbers, pass difficulty factors shown
- Casual: momentum bar, player tags for favourites, insights (casual variant), milestones, goals; no factors
- Player-focus: everything anchored to the chosen player, plus their live card; other players' tags hidden
- One-number mode: only overlays touching the chosen metric, plus goals
- Kids, Accessibility: their own variants; accessibility also emits `commentary_line` with audio

## Export

`GET /matches/{id}/overlays.jsonl` returns the whole overlay timeline. A broadcaster could feed this into their graphics system. Also export in a simple **CSV cue sheet** format (time, slot, text) that a human graphics operator could read.
