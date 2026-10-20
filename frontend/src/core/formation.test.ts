import { describe, expect, it } from 'vitest'
import type { MatchMeta, TeamSheet } from '@/types/schema'
import { formationRows, preKickFrame } from './formation'

function sheet(code: string, formation: string): TeamSheet {
  const starters = [
    { player_id: `${code}-01`, group: 'GK' as const, slot: 1 },
    ...[2, 3, 4, 5].map((n) => ({ player_id: `${code}-0${n}`, group: 'DEF' as const, slot: n })),
    ...[6, 7, 8].map((n) => ({ player_id: `${code}-0${n}`, group: 'MID' as const, slot: n })),
    ...[9, 10, 11].map((n) => ({
      player_id: `${code}-${String(n).padStart(2, '0')}`,
      group: 'FWD' as const,
      slot: n,
    })),
  ]
  return { code, formation, captain: `${code}-08`, starters, bench: [] }
}

const meta = {
  match_id: 'm',
  home: sheet('ASH', '4-3-3'),
  away: sheet('KES', '4-3-3'),
} as MatchMeta

describe('pre-kick line-up', () => {
  it('reads a formation and falls back to 4-4-2', () => {
    expect(formationRows('4-2-3-1')).toEqual([4, 2, 3, 1])
    expect(formationRows('nonsense')).toEqual([4, 4, 2])
  })

  it('puts eleven players per side in their own half', () => {
    const f = preKickFrame(meta)
    const home = f.players.filter((p) => p.id.startsWith('ASH'))
    const away = f.players.filter((p) => p.id.startsWith('KES'))
    expect(home).toHaveLength(11)
    expect(away).toHaveLength(11)
    expect(home.every((p) => p.x < 52.5)).toBe(true)
    expect(away.every((p) => p.x > 52.5)).toBe(true)
  })

  it('keeps the goalkeeper on the goal line, in the middle', () => {
    const gk = preKickFrame(meta).players.find((p) => p.id === 'ASH-01')
    expect(gk).toMatchObject({ x: 5, y: 34 })
  })
})
