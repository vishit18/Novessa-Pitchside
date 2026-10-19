import { describe, expect, it } from 'vitest'
import { activeOverlays, isLive, lateness, lifeFraction, pruneOverlays } from './overlays'
import type { OverlayEnvelope } from '@/types/overlay'

let n = 0
function ovl(over: Partial<OverlayEnvelope> = {}): OverlayEnvelope {
  n += 1
  return {
    v: 1,
    msg_id: `m${n}`,
    match_id: 'x',
    moment_id: `mom${n}`,
    op: 'show',
    slot: 'lower_third',
    kind: 'insight',
    priority: 50,
    t_match: 100,
    t_wall_emit: '2026-01-01T00:00:00Z',
    show_at: 100.2,
    duration_s: 5,
    anchor: null,
    persona: ['analyst'],
    lang: 'en',
    payload: {},
    provenance: { source: 'state_engine', verified: true, evidence: [] },
    ...over,
  }
}

describe('isLive', () => {
  it('is live from show_at until show_at + duration', () => {
    const o = ovl()
    expect(isLive(o, 100.1)).toBe(false)
    expect(isLive(o, 100.2)).toBe(true)
    expect(isLive(o, 105.19)).toBe(true)
    expect(isLive(o, 105.2)).toBe(false)
  })
})

describe('activeOverlays', () => {
  it('shows nothing before show_at, regardless of viewer delay', () => {
    expect(activeOverlays([ovl()], 99)).toHaveLength(0)
  })

  it('same match time gives the same answer however late the messages arrived', () => {
    const a = ovl({ moment_id: 'a', show_at: 10 })
    const b = ovl({ moment_id: 'b', show_at: 12, slot: 'ticker' })
    const t = 13
    expect(
      activeOverlays([a, b], t)
        .map((o) => o.msg_id)
        .sort(),
    ).toEqual(
      activeOverlays([b, a], t)
        .map((o) => o.msg_id)
        .sort(),
    )
  })

  it('keeps one lower third: higher priority wins', () => {
    const low = ovl({ moment_id: 'l', priority: 40 })
    const high = ovl({ moment_id: 'h', priority: 90 })
    const out = activeOverlays([low, high], 101)
    expect(out).toHaveLength(1)
    expect(out[0]!.moment_id).toBe('h')
  })

  it('on equal priority the newest wins', () => {
    const first = ovl({ moment_id: 'first', show_at: 100 })
    const second = ovl({ moment_id: 'second', show_at: 101 })
    expect(activeOverlays([first, second], 102)[0]!.moment_id).toBe('second')
  })

  it('lets player tags stack', () => {
    const a = ovl({
      slot: 'player_tag',
      kind: 'speed_burst',
      anchor: { type: 'player', id: 'A-01' },
    })
    const b = ovl({
      slot: 'player_tag',
      kind: 'speed_burst',
      anchor: { type: 'player', id: 'B-02' },
    })
    expect(activeOverlays([a, b], 101)).toHaveLength(2)
  })

  it('merges an update into the earlier overlay of the same moment', () => {
    const show = ovl({ moment_id: 'g', priority: 95, payload: { headline: 'GOAL', body: '' } })
    const upd = ovl({
      moment_id: 'g',
      op: 'update',
      priority: 95,
      show_at: 102.6,
      payload: { body: 'Set up by Z' },
    })
    const early = activeOverlays([show, upd], 101)[0]!
    expect(early.payload['body']).toBe('')
    const late = activeOverlays([show, upd], 103)[0]!
    expect(late.payload).toEqual({ headline: 'GOAL', body: 'Set up by Z' })
    // the original duration is kept
    expect(late.show_at).toBe(show.show_at)
  })

  it('hide ends an overlay early', () => {
    const show = ovl({ moment_id: 'h' })
    const hide = ovl({ moment_id: 'h', op: 'hide', show_at: 101 })
    expect(activeOverlays([show, hide], 100.5)).toHaveLength(1)
    expect(activeOverlays([show, hide], 101.5)).toHaveLength(0)
  })

  it('clear_slot ends everything in the slot', () => {
    const a = ovl({ slot: 'player_tag', anchor: { type: 'player', id: 'A-01' } })
    const b = ovl({ slot: 'player_tag', anchor: { type: 'player', id: 'B-01' } })
    const keep = ovl({ slot: 'ticker' })
    const clear = ovl({ op: 'clear_slot', slot: 'player_tag', show_at: 101 })
    const out = activeOverlays([a, b, keep, clear], 102)
    expect(out.map((o) => o.slot)).toEqual(['ticker'])
  })
})

describe('pruneOverlays and helpers', () => {
  it('drops overlays well past their duration', () => {
    const o = ovl()
    expect(pruneOverlays([o], 104)).toHaveLength(1)
    expect(pruneOverlays([o], 120)).toHaveLength(0)
  })

  it('lifeFraction runs 0..1', () => {
    const o = ovl({ show_at: 10, duration_s: 4 })
    expect(lifeFraction(o, 9)).toBe(0)
    expect(lifeFraction(o, 12)).toBe(0.5)
    expect(lifeFraction(o, 30)).toBe(1)
  })

  it('lateness is show_at minus t_match, never negative', () => {
    expect(lateness(ovl({ t_match: 100, show_at: 102.6 }))).toBeCloseTo(2.6)
    expect(lateness(ovl({ t_match: 100, show_at: 99 }))).toBe(0)
  })
})
