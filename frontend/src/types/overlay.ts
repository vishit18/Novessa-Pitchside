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

/** Wire messages on WS /ws/matches/{id}?viewer=... */
export type WireMessage =
  | { type: 'frame'; data: TrackingFrame }
  | { type: 'event'; data: MatchEvent }
  | { type: 'state'; data: StateSnapshot }
  | { type: 'overlay'; data: OverlayEnvelope }
