import { describe, expect, it } from 'vitest'
import { frameAt, insertSorted, lastAtOrBefore, trimBefore } from './timeline'
import type { TrackingFrame } from '@/types/schema'

const frame = (t: number, x: number): TrackingFrame => ({
  match_id: 'x',
  t_match: t,
  ball: { x, y: 10, z: 0 },
  players: [{ id: 'A-01', x, y: 20, v_kmh: x }],
})

describe('lastAtOrBefore', () => {
  const items = [1, 2, 4, 8].map((t_match) => ({ t_match }))
  it('finds the right index', () => {
    expect(lastAtOrBefore(items, 0.5)).toBe(-1)
    expect(lastAtOrBefore(items, 2)).toBe(1)
    expect(lastAtOrBefore(items, 3.9)).toBe(1)
    expect(lastAtOrBefore(items, 100)).toBe(3)
  })
})

describe('insertSorted and trimBefore', () => {
  it('keeps order when a late message arrives', () => {
    const a = [{ t_match: 1 }, { t_match: 3 }]
    insertSorted(a, { t_match: 2 })
    expect(a.map((x) => x.t_match)).toEqual([1, 2, 3])
  })

  it('trims old items but keeps one behind for interpolation', () => {
    const a = [1, 2, 3, 4, 5].map((t_match) => ({ t_match }))
    trimBefore(a, 3.5)
    expect(a.map((x) => x.t_match)).toEqual([3, 4, 5])
  })
})

describe('frameAt', () => {
  const frames = [frame(0, 0), frame(0.1, 10)]
  it('is null before the first frame', () => {
    expect(frameAt(frames, -1)).toBeNull()
  })
  it('interpolates ball and players', () => {
    const f = frameAt(frames, 0.05)!
    expect(f.ball.x).toBeCloseTo(5)
    expect(f.players[0]!.x).toBeCloseTo(5)
    expect(f.players[0]!.v_kmh).toBeCloseTo(5)
  })
  it('holds the last frame past the end', () => {
    expect(frameAt(frames, 5)!.ball.x).toBe(10)
  })
})
