/** Overlay protocol v1 envelope. Spec: docs/05_OVERLAY_PROTOCOL.md. */
import type { MatchEvent, StateSnapshot, TrackingFrame } from './schema'

export type OverlayOp = 'show' | 'update' | 'hide' | 'clear_slot'

export type OverlaySlot =
  | 'lower_third'
  | 'top_bar'
  | 'side_panel'
  | 'player_tag'
  | 'pitch_annotation'
  | 'fullscreen_card'
  | 'ticker'

export type OverlayKind =
  | 'player_tag'
  | 'speed_burst'
  | 'distance_milestone'
  | 'pass_difficulty'
  | 'shot_speed'
  | 'momentum_bar'
  | 'control_chaos'
  | 'pressure_shift'
  | 'insight'
  | 'milestone'
  | 'commentary_line'
  | 'recap'
  | 'stat_compare'

export type Anchor = { type: 'player'; id: string } | { type: 'pitch'; x: number; y: number } | null

export interface Provenance {
  source: string
  verified: boolean
  evidence: { metric: string; value: number }[]
}

export interface OverlayEnvelope {
  v: 1
  msg_id: string
  match_id: string
  moment_id: string | null
  op: OverlayOp
  slot: OverlaySlot
  kind: OverlayKind
  priority: number
  t_match: number
  t_wall_emit: string
  show_at: number
  duration_s: number
  anchor: Anchor
  persona: string[]
  lang: string
  payload: Record<string, unknown>
  provenance: Provenance
}

/** One player's match stats from the state engine. Mirrors player_stats in docs/05. */
export interface PlayerStatsEntry {
  player_id: string
  team: string
  on_pitch: boolean
  passes: number
  passes_complete: number
  /** 0-1, or null before their first pass */
  pass_accuracy: number | null
  avg_difficulty: number | null
  longest_pass_m: number
  /** Highest difficulty among completed passes. */
  hardest_pass: number
  shots: number
  xg: number
  xa: number
  duels_won: number
  duels_lost: number
  fouls: number
  yellows: number
  reds: number
  distance_km: number
  top_speed_kmh: number
  top_shot_kmh: number
  sprints: number
}

/** The four one-number metrics (docs/05 Transport: `metric`). */
export type OneNumberMetric = 'sprint_speed' | 'shot_speed' | 'pass_difficulty' | 'distance'

/** player_stats, once a second, to every viewer. */
export interface PlayerStatsMessage {
  t_match: number
  players: PlayerStatsEntry[]
  /** Current match leader per metric; a metric with no leader yet is omitted. */
  leaders: Partial<Record<OneNumberMetric, { player_id: string; value: number }>>
}

/** Wire messages on WS /ws/matches/{id}?viewer=... */
export type WireMessage =
  | { type: 'frame'; data: TrackingFrame }
  | { type: 'event'; data: MatchEvent }
  | { type: 'state'; data: StateSnapshot }
  | { type: 'overlay'; data: OverlayEnvelope }
  | { type: 'player_stats'; data: PlayerStatsMessage }
