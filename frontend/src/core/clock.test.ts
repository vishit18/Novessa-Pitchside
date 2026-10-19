import { describe, expect, it } from 'vitest'
import { ClockSync } from './clock'

/** Feed 10 Hz frames at `speed` x for `seconds` of wall time, sampling at 60 fps. */
function run(c: ClockSync, speed: number, seconds: number, startMatch = 0) {
  let wall = 1000
  let match = startMatch
  const samples: number[] = []
  c.observe(match, wall)
  for (let f = 1; f <= seconds * 60; f++) {
    wall += 1000 / 60
    if (f % 6 === 0) {
      match = startMatch + (f / 60) * speed
      c.observe(match, wall)
    }
    samples.push(c.now(wall))
  }
  return { samples, match }
}

describe('ClockSync', () => {
  it('trails the live edge by the lead and never runs backwards', () => {
    const c = new ClockSync(0.3)
    const { samples, match } = run(c, 1, 5)
    for (let i = 1; i < samples.length; i++)
      expect(samples[i]!).toBeGreaterThanOrEqual(samples[i - 1]! - 1e-9)
    expect(samples.at(-1)!).toBeGreaterThan(match - 0.3 - 0.35)
    expect(samples.at(-1)!).toBeLessThan(match)
  })

  it('learns the playback rate at 4x', () => {
    const c = new ClockSync(0.3)
    run(c, 4, 6)
    expect(c.estimatedRate).toBeGreaterThan(3.5)
    expect(c.estimatedRate).toBeLessThan(4.5)
  })

  it('a longer lead puts the viewer further behind the same stream', () => {
    const a = new ClockSync(0.3)
    const b = new ClockSync(20.3)
    const ra = run(a, 1, 30)
    const rb = run(b, 1, 30)
    expect(ra.samples.at(-1)! - rb.samples.at(-1)!).toBeCloseTo(20, 0)
  })

  it('freezes when the stream stops', () => {
    const c = new ClockSync(0.3)
    run(c, 1, 3)
    const t1 = c.now(1000 + 3000 + 2000)
    const t2 = c.now(1000 + 3000 + 4000)
    expect(Math.abs(t2 - t1)).toBeLessThan(0.3)
  })
})
