import { describe, expect, it } from 'vitest'
import { followCamera } from './camera'
import { Heatmap } from './heatmap'

const view = { w: 1000, h: 600 }
const pitch = { left: 100, top: 50, width: 800, height: 500 }

describe('followCamera', () => {
  it('moves toward the target without overshooting', () => {
    let cam = { x: 500, y: 300, zoom: 1 }
    const target = { x: 600, y: 320, zoom: 2 }
    for (let i = 0; i < 120; i++) cam = followCamera(cam, target, 1 / 60, view, pitch)
    expect(cam.zoom).toBeGreaterThan(1.9)
    expect(cam.x).toBeLessThanOrEqual(600 + 1e-6)
    expect(cam.x).toBeGreaterThan(590)
  })

  it('keeps the view on the pitch near a corner', () => {
    let cam = { x: 500, y: 300, zoom: 2 }
    const target = { x: 100, y: 50, zoom: 2 }
    for (let i = 0; i < 300; i++) cam = followCamera(cam, target, 1 / 60, view, pitch)
    // half the view at zoom 2 is 250 x 150; left edge may show at most the 24 px margin
    expect(cam.x - 250).toBeGreaterThanOrEqual(100 - 24 - 1e-6)
    expect(cam.y - 150).toBeGreaterThanOrEqual(50 - 24 - 1e-6)
  })

  it('centres on the pitch when zoomed out past it', () => {
    const cam = followCamera({ x: 0, y: 0, zoom: 0.5 }, { x: 0, y: 0, zoom: 0.5 }, 1, view, pitch)
    expect(cam.x).toBeCloseTo(500)
    expect(cam.y).toBeCloseTo(300)
  })
})

describe('Heatmap', () => {
  it('samples at a fixed match-time rate', () => {
    const h = new Heatmap(21, 14, 0.5)
    expect(h.sample(10, 10, 0)).toBe(true)
    expect(h.sample(10, 10, 0.2)).toBe(false)
    expect(h.sample(10, 10, 0.5)).toBe(true)
    expect(h.max).toBe(2)
  })

  it('smooths into the neighbouring cells, hottest where the player was', () => {
    const h = new Heatmap(21, 14, 0.5)
    h.sample(52, 34, 0)
    const cells = h.cells()
    // Spread over the neighbouring cells (5 m each here) and no further.
    expect(
      cells.every((c) => Math.abs(c.x + c.w / 2 - 52) < 10 && Math.abs(c.y + c.h / 2 - 34) < 10),
    ).toBe(true)
    const hottest = cells.reduce((a, b) => (b.v > a.v ? b : a))
    expect(Math.abs(hottest.x + hottest.w / 2 - 52)).toBeLessThan(3)
    expect(Math.abs(hottest.y + hottest.h / 2 - 34)).toBeLessThan(3)
    expect(cells.filter((c) => c.v < 0.3).length).toBeGreaterThan(0)
  })

  it('clamps positions on the touchline into the grid', () => {
    const h = new Heatmap()
    h.sample(105, 68, 0)
    h.sample(0, 0, 1)
    const cells = h.cells()
    expect(cells.some((c) => c.x === 0 && c.y === 0)).toBe(true)
    expect(
      cells.some((c) => Math.abs(c.x + c.w - 105) < 1e-6 && Math.abs(c.y + c.h - 68) < 1e-6),
    ).toBe(true)
  })

  it('starts over after a seek backwards', () => {
    const h = new Heatmap()
    h.sample(50, 30, 100)
    h.sample(50, 30, 101)
    h.sample(50, 30, 10)
    expect(h.max).toBe(1)
  })
})
