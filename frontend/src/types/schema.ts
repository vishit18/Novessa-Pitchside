/** Hand-mirrored from engine/schema.py and backend/state/models.py. Change the Python side first. */

export const PITCH_LENGTH = 105
export const PITCH_WIDTH = 68

export type EventType =
  | 'kick_off'
  | 'pass'
  | 'carry'
  | 'dribble'
  | 'shot'
  | 'save'
  | 'goal'
  | 'tackle'
  | 'interception'
  | 'clearance'
  | 'block'
  | 'foul'
  | 'card'
  | 'corner'
  | 'free_kick'
  | 'throw_in'
  | 'offside'
  | 'possession_change'
  | 'pressure'
  | 'substitution'
  | 'period_start'
  | 'period_end'
  | 'injury_stoppage'

export interface DifficultyFactor {
  name: string
  points: number
}

export interface MatchEvent {
  event_id: string
  match_id: string
  seq: number
  t_match: number
  period: 1 | 2
  clock: string
  type: EventType
  team?: string | null
  player_id?: string | null
  x?: number | null
  y?: number | null
  end_x?: number | null
  end_y?: number | null
  outcome?: string | null
  receiver_id?: string | null
  under_pressure?: boolean
  pressure_by?: string[]
  ball_speed_kmh?: number | null
  pass_difficulty?: number | null
  difficulty_factors?: DifficultyFactor[] | null
  xg?: number | null
  tags?: string[]
  source?: 'synthetic' | 'vision'
}

export interface PlayerFrame {
  id: string
  x: number
  y: number
  v_kmh: number
}

export interface TrackingFrame {
  match_id: string
  t_match: number
  ball: { x: number; y: number; z: number }
  players: PlayerFrame[]
}

export interface ControlChaos {
  value: number
  label: 'controlled' | 'balanced' | 'chaotic'
}

export interface StateSnapshot {
  t_match: number
  clock: string
  period: number
  score: Record<string, number>
  possession_match: Record<string, number>
  possession_5min: Record<string, number>
  /** -100 (away on top) to +100 (home on top) */
  momentum: number
  pressure: Record<string, number>
  control_chaos: ControlChaos
  rhythm: { events_per_min: number; avg_possession_len: number; broken: boolean }
  /** Running discipline and set-piece counts per team (docs/05 team_stats). */
  team_stats: Record<string, TeamStats>
}

export interface TeamStats {
  fouls: number
  yellows: number
  reds: number
  corners: number
  free_kicks: number
  penalties: number
  shots: number
  offsides: number
}

export type Group = 'GK' | 'DEF' | 'MID' | 'FWD'

export interface TeamSheet {
  code: string
  formation: string
  captain: string
  starters: { player_id: string; group: Group; slot: number }[]
  bench: string[]
}

export interface MatchMeta {
  match_id: string
  competition: string
  matchday: number
  venue: string
  kickoff_time: string
  weather: string
  referee: string
  home: TeamSheet
  away: TeamSheet
}

export interface Club {
  code: string
  name: string
  primary_color: string
  secondary_color: string
}

export interface PlayerInfo {
  id: string
  name: string
  shirt: number
  position: Group
}
