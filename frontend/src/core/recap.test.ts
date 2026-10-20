import { describe, expect, it } from 'vitest'
import type { RecapFacts, TeamFacts } from '@/net/api'
import { fallbackTime, formatStat, leaderLabel, leaderValue, shareText, statRows } from './recap'

const team = (over: Partial<TeamFacts> = {}): TeamFacts => ({
  goals: 1,
  possession_pct: 60,
  shots: 12,
  xg: 1.234,
  passes: 400,
  pass_accuracy_pct: 82,
  corners: 5,
  fouls: 9,
  yellow_cards: 1,
  red_cards: 0,
  ...over,
})

const facts = (): RecapFacts => ({
  kind: 'full_time',
  minute_reached: '90+3:10',
  home: 'Ashford Rovers',
  away: 'Kestrel Bay FC',
  score: 'Ashford Rovers 2, Kestrel Bay FC 1',
  goals: [],
  teams: {
    'Ashford Rovers': team(),
    'Kestrel Bay FC': team({ possession_pct: 40, shots: 4, red_cards: 0, xg: 0.5 }),
  },
  leaders: [],
})

describe('statRows', () => {
  it('puts home first and works out each side of the bar', () => {
    const rows = statRows(facts())
    expect(rows.map((r) => r.label)).toEqual([
      'Possession',
      'Shots',
      'Expected goals',
      'Passes',
      'Pass accuracy',
      'Corners',
      'Fouls',
      'Yellow cards',
      'Red cards',
    ])
    const poss = rows[0]!
    expect([poss.home, poss.away, poss.homeShare]).toEqual([60, 40, 0.6])
    expect(rows[1]!.homeShare).toBeCloseTo(12 / 16)
  })

  it('centres a bar when both teams are on zero', () => {
    expect(statRows(facts()).find((r) => r.key === 'red_cards')!.homeShare).toBe(0.5)
  })

  it('returns nothing when a team is missing from the sheet', () => {
    const f = facts()
    delete f.teams['Kestrel Bay FC']
    expect(statRows(f)).toEqual([])
  })
})

describe('formatting', () => {
  it('shows whole numbers, two-place xG and percentages', () => {
    const rows = statRows(facts())
    expect(formatStat(rows[0]!, 'home')).toBe('60%')
    expect(formatStat(rows[1]!, 'away')).toBe('4')
    expect(formatStat(rows[2]!, 'home')).toBe('1.23')
  })

  it('words the leaders and picks a catch-up fallback time', () => {
    expect(leaderLabel('shot_speed')).toBe('Hardest shot')
    expect(leaderLabel('something_new')).toBe('something new')
    expect(leaderValue('sprint_speed', 33.4)).toBe('33.4 km/h')
    expect(leaderValue('pass_difficulty', 91)).toBe('91')
    expect(fallbackTime('half_time')).toBe(2700)
    expect(fallbackTime('full_time')).toBeGreaterThan(10_000)
    expect(shareText('Late winner', 'A 2, B 1', 'https://x/y')).toBe(
      'Late winner\nA 2, B 1\nhttps://x/y',
    )
  })
})
