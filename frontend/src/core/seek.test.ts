import { describe, expect, it } from 'vitest'
import { leftOverFromBeforeSeek } from './seek'
import type { WireMessage } from '@/types/overlay'

const frame = (t: number) =>
  ({
    type: 'frame',
    data: { match_id: 'x', t_match: t, ball: { x: 0, y: 0, z: 0 }, players: [] },
  }) as WireMessage
const state = (t: number) => ({ type: 'state', data: { t_match: t } }) as unknown as WireMessage
const stats = (t: number) =>
  ({ type: 'player_stats', data: { t_match: t } }) as unknown as WireMessage
const overlay = { type: 'overlay', data: { msg_id: 'a' } } as unknown as WireMessage

describe('leftOverFromBeforeSeek', () => {
  it('drops a frame from the old position after a seek back to the start', () => {
    expect(leftOverFromBeforeSeek(frame(630), 0)).toBe(true)
  })
  it('keeps the first frame of the new stream, which starts at the target', () => {
    expect(leftOverFromBeforeSeek(frame(0), 0)).toBe(false)
    expect(leftOverFromBeforeSeek(frame(1200.4), 1200)).toBe(false)
  })
  it('drops a frame from the old position after a seek forward', () => {
    expect(leftOverFromBeforeSeek(frame(600), 3000)).toBe(true)
  })
  it('keeps state and stats at or just before the target, drops ones after it', () => {
    expect(leftOverFromBeforeSeek(state(0), 0)).toBe(false)
    expect(leftOverFromBeforeSeek(state(595), 600)).toBe(false)
    expect(leftOverFromBeforeSeek(state(630), 0)).toBe(true)
    expect(leftOverFromBeforeSeek(stats(630), 0)).toBe(true)
  })
  it('never drops overlays', () => {
    expect(leftOverFromBeforeSeek(overlay, 0)).toBe(false)
  })
})
