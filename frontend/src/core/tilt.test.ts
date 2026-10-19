import { describe, expect, it } from 'vitest'
import { makeTilt } from './tilt'

describe('makeTilt', () => {
  it('is the identity with no tilt', () => {
    const t = makeTilt(1000, 600, 0)
    expect(t.css).toBe('none')
    expect(t.project(123, 456)).toEqual({ x: 123, y: 456 })
  })

  it('keeps the centre fixed', () => {
    const p = makeTilt(1000, 600, 26).project(500, 300)
    expect(p.x).toBeCloseTo(500)
    expect(p.y).toBeCloseTo(300)
  })

  it('shrinks the far edge and grows the near edge', () => {
    const t = makeTilt(1000, 600, 26)
    const far = t.project(0, 0)
    const near = t.project(0, 600)
    expect(500 - far.x).toBeLessThan(500)
    expect(500 - near.x).toBeGreaterThan(500)
    expect(far.y).toBeGreaterThan(0)
    expect(near.y).toBeLessThan(600 + 100)
  })
})
