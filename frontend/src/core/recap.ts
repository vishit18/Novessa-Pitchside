import type { RecapFacts, RecapKind, TeamFacts } from '@/net/api'

export interface StatRow {
  key: keyof TeamFacts
  label: string
  home: number
  away: number
  unit: '' | '%'
  /** Home's share of the two numbers, 0 to 1. Half when both are zero. */
  homeShare: number
}

const ROWS: { key: keyof TeamFacts; label: string; unit: '' | '%'; decimals?: number }[] = [
  { key: 'possession_pct', label: 'Possession', unit: '%' },
  { key: 'shots', label: 'Shots', unit: '' },
  { key: 'xg', label: 'Expected goals', unit: '', decimals: 2 },
  { key: 'passes', label: 'Passes', unit: '' },
  { key: 'pass_accuracy_pct', label: 'Pass accuracy', unit: '%' },
  { key: 'corners', label: 'Corners', unit: '' },
  { key: 'fouls', label: 'Fouls', unit: '' },
  { key: 'yellow_cards', label: 'Yellow cards', unit: '' },
  { key: 'red_cards', label: 'Red cards', unit: '' },
]

/** Side-by-side rows for the stat bars, home team first, from the recap's fact sheet. */
export function statRows(facts: RecapFacts): StatRow[] {
  const home = facts.teams[facts.home]
  const away = facts.teams[facts.away]
  if (!home || !away) return []
  return ROWS.map(({ key, label, unit }) => {
    const h = home[key]
    const a = away[key]
    const total = h + a
    return { key, label, home: h, away: a, unit, homeShare: total > 0 ? h / total : 0.5 }
  })
}

/** "3" for whole numbers, "1.24" for xG, "62%" for percentages. */
export function formatStat(row: StatRow, side: 'home' | 'away'): string {
  const v = row[side]
  const text = Number.isInteger(v) ? String(v) : v.toFixed(2)
  return `${text}${row.unit}`
}

export const KIND_LABEL: Record<RecapKind, string> = {
  half_time: 'Half-time',
  full_time: 'Full-time',
}

/** Text for the share sheet or clipboard: the headline, the score and the link. */
export function shareText(headline: string, score: string, url: string): string {
  return `${headline}\n${score}\n${url}`
}

/** Metric ids from the player-stats leaders, in the words a viewer would use. */
const LEADER_LABEL: Record<string, string> = {
  sprint_speed: 'Fastest sprint',
  shot_speed: 'Hardest shot',
  pass_difficulty: 'Hardest pass',
  distance: 'Furthest run',
}
const LEADER_UNIT: Record<string, string> = {
  sprint_speed: 'km/h',
  shot_speed: 'km/h',
  pass_difficulty: '',
  distance: 'km',
}

export function leaderLabel(metric: string): string {
  return LEADER_LABEL[metric] ?? metric.replace(/_/g, ' ')
}

export function leaderValue(metric: string, value: number): string {
  const unit = LEADER_UNIT[metric] ?? ''
  return `${value}${unit ? ` ${unit}` : ''}`
}

/** Which fallback match time to ask the catch-up for when no recap could be written. */
export function fallbackTime(kind: RecapKind): number {
  // Half-time is the first 45 minutes of play. Full time asks past the end; the gateway clamps.
  return kind === 'half_time' ? 2700 : 1_000_000
}
