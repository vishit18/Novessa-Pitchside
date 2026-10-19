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
  "t_wall_emit": "2026-10-24T19:03:11.204Z",
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
