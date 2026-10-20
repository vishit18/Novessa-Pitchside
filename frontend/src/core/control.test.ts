import { describe, expect, it } from 'vitest'
import type { AgentHealth, Insight } from '@/net/control'
import {
  budgetFraction,
  dollars,
  justWorked,
  newestFirst,
  nodeState,
  proofOf,
  seconds,
  tally,
} from './control'

const health = (over: Partial<AgentHealth> = {}): AgentHealth => ({
  calls: 10,
  failures: 0,
  fallbacks: 0,
  last_latency_ms: 900,
  avg_latency_ms: 900,
  p50_latency_ms: 900,
  p95_latency_ms: 1500,
  breaker_open: false,
  breaker_for_s: 0,
  killed: false,
  killed_for_s: 0,
  ...over,
})

const insight = (trail: string[], t = 0, over: Partial<Insight> = {}): Insight => ({
  moment_id: `m${t}`,
  status: 'verified',
  item: { decision: 'air', priority: 70, slot: 'lower_third', reason: '', brief: '' },
  analysis: null,
  variants: {},
  trail,
  moment: { kind: 'shot', clock: "1'", t_match: t, team: null, summary: '', significance: 60 },
  ...over,
})

describe('nodeState', () => {
  it('ranks killed above breaker above degraded above ok', () => {
    expect(nodeState(undefined)).toBe('idle')
    expect(nodeState(health({ calls: 0 }))).toBe('idle')
    expect(nodeState(health())).toBe('ok')
    expect(nodeState(health({ fallbacks: 1 }))).toBe('degraded')
    expect(nodeState(health({ failures: 3 }))).toBe('degraded')
    expect(nodeState(health({ breaker_open: true, fallbacks: 1 }))).toBe('breaker')
    expect(nodeState(health({ killed: true, breaker_open: true }))).toBe('killed')
  })
})

describe('justWorked', () => {
  it('lists agents whose call count rose, and nothing on the first poll', () => {
    const a = { producer: health({ calls: 2 }), analyst: health({ calls: 5 }) }
    const b = { producer: health({ calls: 2 }), analyst: health({ calls: 6 }), narrator: health() }
    expect(justWorked(null, b)).toEqual([])
    expect(justWorked(a, b)).toEqual(['analyst', 'narrator'])
  })
})

describe('verifier readings', () => {
  const clean = insight(['producer air: x', 'verifier: 2/2 claims proven (attempt 1)'], 10)
  const retried = insight(
    [
      'verifier rejected (attempt 1): 40 is not 31',
      'verifier: 2/2 claims proven (attempt 2)',
      'content safety blocked the text; numbers-only card',
    ],
    20,
  )
  const never = insight(
    ['verifier rejected (attempt 1): no', 'verifier rejected (attempt 2): no'],
    5,
    {
      status: 'fallback',
    },
  )
  const held = insight(['producer hold: later'], 1, {
    item: { decision: 'hold', priority: 10, slot: 'lower_third', reason: '', brief: '' },
  })

  it('classifies each moment', () => {
    expect(proofOf(clean)).toBe('proven')
    expect(proofOf(retried)).toBe('retried')
    expect(proofOf(never)).toBe('failed')
    expect(proofOf(held)).toBe('skipped')
  })

  it('tallies the trails', () => {
    expect(tally([clean, retried, never, held])).toEqual({
      proven: 2,
      rejected: 3,
      fallbackCards: 1,
      safetyBlocked: 1,
    })
  })

  it('puts the latest match time first', () => {
    expect(newestFirst([clean, retried, never]).map((i) => i.moment.t_match)).toEqual([20, 10, 5])
  })
})

describe('formatting', () => {
  it('keeps bars on the track and numbers readable', () => {
    expect(budgetFraction(2000)).toBe(0.5)
    expect(budgetFraction(9000)).toBe(1)
    expect(budgetFraction(-5)).toBe(0)
    expect(seconds(0)).toBe('-')
    expect(seconds(1340)).toBe('1.3 s')
    expect(seconds(15200)).toBe('15 s')
    expect(dollars(0.0042)).toBe('$0.0042')
    expect(dollars(1.234)).toBe('$1.23')
  })
})
