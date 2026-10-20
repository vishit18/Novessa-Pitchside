import { describe, expect, it } from 'vitest'
import type { OverlayEnvelope } from '@/types/overlay'
import { isStoryOverlay, metricLabel, momentFeed } from './feed'

let n = 0
const overlay = (over: Partial<OverlayEnvelope> & { payload?: Record<string, unknown> }) =>
  ({
    v: 1,
    msg_id: `m${n++}`,
    match_id: 'derby_01',
    moment_id: 'mom1',
    op: 'show',
    slot: 'lower_third',
    kind: 'insight',
    priority: 80,
    t_match: 100,
    t_wall_emit: '',
    show_at: 100,
    duration_s: 7,
    anchor: null,
    persona: ['analyst'],
    lang: 'en',
    payload: { headline: 'Goal', body: 'Wragg scores', team: 'ASH', tone: 'goal' },
    provenance: { source: 'state_engine', verified: true, evidence: [] },
    ...over,
  }) as OverlayEnvelope

describe('momentFeed', () => {
  it('never includes a card whose time has not come', () => {
    const log = [overlay({ show_at: 100 }), overlay({ moment_id: 'mom2', show_at: 500 })]
    expect(momentFeed(log, 99)).toEqual([])
    expect(momentFeed(log, 300).map((i) => i.id)).toEqual(['mom1|insight'])
    expect(momentFeed(log, 500)).toHaveLength(2)
  })

  it('lists newest first', () => {
    const log = [
      overlay({ moment_id: 'a', show_at: 10 }),
      overlay({ moment_id: 'b', show_at: 30 }),
      overlay({ moment_id: 'c', show_at: 20 }),
    ]
    expect(momentFeed(log, 100).map((i) => i.id)).toEqual(['b|insight', 'c|insight', 'a|insight'])
  })

  it('attaches agent text to the instant card and keeps its place', () => {
    const log = [
      overlay({ show_at: 100, payload: { headline: 'Goal', body: 'Numbers', clock: '06:06' } }),
      overlay({
        op: 'update',
        show_at: 104,
        payload: { headline: 'Early lead flips it', body: 'Words', audio_url: '/a.mp3' },
        provenance: {
          source: 'agent:analyst',
          verified: true,
          evidence: [{ metric: 'momentum', value: 62 }],
        },
      }),
    ]
    const [item] = momentFeed(log, 110)
    expect(item).toMatchObject({
      showAt: 100,
      headline: 'Early lead flips it',
      body: 'Words',
      clock: '06:06',
      audioUrl: '/a.mp3',
      source: 'agent:analyst',
    })
    expect(item?.evidence).toEqual([{ metric: 'momentum', value: 62 }])
  })

  it('ignores an update for a card it never saw, and a hide does not remove a card', () => {
    const log = [
      overlay({ moment_id: 'x', op: 'update', show_at: 5 }),
      overlay({ show_at: 10 }),
      overlay({ op: 'hide', show_at: 12 }),
    ]
    expect(momentFeed(log, 20).map((i) => i.id)).toEqual(['mom1|insight'])
  })

  it('keeps card colour and skips pitch overlays', () => {
    const log = [
      overlay({ payload: { headline: 'Red card', body: '', card: 'red' } }),
      overlay({ slot: 'player_tag', kind: 'player_tag', moment_id: null }),
    ]
    expect(isStoryOverlay(log[1]!)).toBe(false)
    const feed = momentFeed(log, 200)
    expect(feed).toHaveLength(1)
    expect(feed[0]?.card).toBe('red')
  })
})

describe('labels', () => {
  it('words things plainly', () => {
    expect(metricLabel('pressure_index')).toBe('pressure index')
  })
})
