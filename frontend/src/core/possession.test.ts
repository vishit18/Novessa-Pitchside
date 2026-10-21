import { describe, expect, it } from 'vitest'
import type { TrackingFrame } from '@/types/schema'
import { attackDirection, carrierOf, optionsFor, pressersOf } from './possession'

const p = (id: string, x: number, y: number) => ({ id, x, y }) as TrackingFrame['players'][number]

const frame = (ballX: number, ballY: number): TrackingFrame => ({
  match_id: 'm',
  t_match: 0,
  ball: { x: ballX, y: ballY, z: 0 },
  players: [
    p('ASH-01', 3, 34),
    p('ASH-08', 50, 34),
    p('ASH-10', 56, 30),
    p('ASH-11', 70, 50),
    p('KES-01', 101, 34),
    p('KES-04', 54, 37),
    p('KES-06', 44, 34),
  ],
})

describe('possession', () => {
  it('finds the carrier only when someone is on the ball', () => {
    expect(carrierOf(frame(50.5, 34))?.id).toBe('ASH-08')
    expect(carrierOf(frame(62, 10))).toBeNull()
  })

  it('lists pressing opponents nearest first and the nearest passing options', () => {
    const f = frame(50.5, 34)
    const c = carrierOf(f)!
    expect(pressersOf(f, c).map((x) => x.id)).toEqual(['KES-04', 'KES-06'])
    expect(optionsFor(f, c).map((x) => x.id)).toEqual(['ASH-10', 'ASH-11'])
  })

  it('reads attacking direction from where the keeper stands', () => {
    expect(attackDirection(frame(50, 34), 'ASH')).toBe(1)
    expect(attackDirection(frame(50, 34), 'KES')).toBe(-1)
  })
})
