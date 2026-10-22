import { describe, expect, it } from 'vitest'
import type { PulseSample } from '@/net/api'
import { pressingSide, riverPaths, tempoWord } from './pulse'

const s = (t_match: number, momentum: number): PulseSample => ({
  t_match,
  clock: '',
  period: 1,
  momentum,
  control: 50,
  tempo: 17,
  possession_home_5min: 50,
  pressure_home: 30,
  pressure_away: 30,
})

describe('pulse', () => {
  it('names the tempo with the same lines as the lower thirds', () => {
    expect(tempoWord(20)).toBe('fast')
    expect(tempoWord(17)).toBe('steady')
    expect(tempoWord(14)).toBe('slow')
  })

  it('only calls a pressing edge when it is clear', () => {
    expect(pressingSide(60, 30)).toBe('home')
    expect(pressingSide(30, 35)).toBeNull()
    expect(pressingSide(10, 40)).toBe('away')
  })

  it('draws home above the line and away below, on a 90-minute scale', () => {
    const { home, away, span } = riverPaths([s(0, 0), s(1800, 100), s(2700, -100)], 400, 100)
    expect(span).toBe(5400)
    expect(home).toContain('133.3,0.0') // 30 minutes in, full home momentum, top edge
    expect(away).toContain('200.0,100.0') // 45 minutes in, full away momentum, bottom edge
    expect(home.endsWith('Z')).toBe(true)
  })

  it('draws nothing from a single sample', () => {
    expect(riverPaths([s(0, 10)], 400, 100).home).toBe('')
  })
})
