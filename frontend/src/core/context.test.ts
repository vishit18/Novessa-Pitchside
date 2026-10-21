import { describe, expect, it } from 'vitest'
import type { PlayerStatsEntry } from '@/types/overlay'
import { rankAmong, type Position } from './context'

const entry = (id: string, km: number, onPitch = true): PlayerStatsEntry => ({
  player_id: id,
  team: id.split('-')[0] ?? '',
  on_pitch: onPitch,
  passes: 0,
  passes_complete: 0,
  pass_accuracy: null,
  avg_difficulty: null,
  longest_pass_m: 0,
  hardest_pass: 0,
  shots: 0,
  xg: 0,
  xa: 0,
  duels_won: 0,
  duels_lost: 0,
  fouls: 0,
  yellows: 0,
  reds: 0,
  distance_km: km,
  top_speed_kmh: 0,
  top_shot_kmh: 0,
  sprints: 0,
})

const pos: Record<string, Position> = {
  'A-1': 'MID',
  'A-2': 'MID',
  'B-1': 'MID',
  'B-2': 'MID',
  'A-9': 'FWD',
  'B-9': 'FWD',
}

describe('rankAmong', () => {
  const players = [entry('A-1', 5.1), entry('A-2', 6.0), entry('B-1', 6.0), entry('B-2', 4.0)]
  players.push(entry('A-9', 7), entry('B-9', 3))

  it('ranks within the same position across both teams, ties sharing the better rank', () => {
    const km = (p: PlayerStatsEntry) => p.distance_km
    expect(rankAmong(players, 'A-1', km, (id) => pos[id])).toEqual({ rank: 3, of: 4, group: 'MID' })
    expect(rankAmong(players, 'B-1', km, (id) => pos[id])?.rank).toBe(1)
    expect(rankAmong(players, 'A-2', km, (id) => pos[id])?.rank).toBe(1)
  })

  it('says nothing for tiny groups or missing values', () => {
    expect(
      rankAmong(
        players,
        'A-9',
        (p) => p.distance_km,
        (id) => pos[id],
      ),
    ).toBeNull()
    expect(
      rankAmong(
        players,
        'A-1',
        (p) => p.pass_accuracy,
        (id) => pos[id],
      ),
    ).toBeNull()
  })

  it('leaves out players who never came on', () => {
    const bench = [...players, entry('B-3', 0, false)]
    pos['B-3'] = 'MID'
    expect(
      rankAmong(
        bench,
        'B-2',
        (p) => p.distance_km,
        (id) => pos[id],
      )?.of,
    ).toBe(4)
  })
})
