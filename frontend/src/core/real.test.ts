import { describe, expect, it } from 'vitest'
import {
  activeBursts,
  activePasses,
  boxesAt,
  foot,
  matchClock,
  passLine,
  rowAtOrBefore,
  trackOf,
  type RealEvent,
  type RealOverlay,
} from './real'

const overlay = (): RealOverlay => ({
  match_id: 'real_1_w1',
  fps: 25,
  clip: [2560, 676],
  credit: 'Footage: SoccerTrack v2 (CC BY 4.0)',
  start_s: 0,
  tracks: { '7': { team: 'BLU', label: 'Blue 7' } },
  frames: [
    [0, [[7, 100, 100, 120, 160, 10]], [500, 300]],
    [2, [[7, 110, 100, 130, 160, 20]], [520, 300]],
    [4, [[7, 120, 100, 140, 160, 30]], null],
  ],
  events: [],
  bursts: [{ frame: 50, track: 7, team: 'BLU', kmh: 29 }],
})

const pass = (over: Partial<RealEvent> = {}): RealEvent => ({
  t_match: 10,
  clock: '31:40',
  type: 'pass',
  team: 'BLU',
  player_id: 'BLU-T007',
  receiver_id: 'BLU-T009',
  outcome: 'complete',
  ball_speed_kmh: 70.4,
  pass_difficulty: 41.6,
  x: 10,
  y: 20,
  end_x: 22,
  end_y: 25,
  ...over,
})

describe('rowAtOrBefore', () => {
  it('finds the row at or before a frame', () => {
    const f = overlay().frames
    expect([-1, 0, 1, 2, 3, 4, 9].map((x) => rowAtOrBefore(f, x))).toEqual([-1, 0, 0, 1, 1, 2, 2])
  })
})

describe('boxesAt', () => {
  it('is empty before the first frame and blends between two rows', () => {
    const o = overlay()
    expect(boxesAt(o, -1).boxes).toEqual([])
    const mid = boxesAt(o, 1 / 25) // frame 1, halfway between rows 0 and 2
    expect(mid.boxes[0]).toMatchObject({ id: 7, x1: 105, kmh: 15 })
    expect(mid.ball).toEqual([510, 300])
  })

  it('holds the last position when the next row has no ball', () => {
    expect(boxesAt(overlay(), 3 / 25).ball).toEqual([520, 300])
  })
})

describe('cards and callouts', () => {
  it('shows a completed pass for a few seconds only, and never an incomplete one', () => {
    const ev = [pass(), pass({ t_match: 20, outcome: 'incomplete' })]
    expect(activePasses(ev, 9.9)).toHaveLength(0)
    expect(activePasses(ev, 10)).toHaveLength(1)
    expect(activePasses(ev, 13.4)).toHaveLength(1)
    expect(activePasses(ev, 13.6)).toHaveLength(0)
    expect(activePasses(ev, 20.5)).toHaveLength(0)
  })

  it('shows a sprint callout for two seconds', () => {
    const o = overlay()
    expect(activeBursts(o, 1.9)).toHaveLength(0)
    expect(activeBursts(o, 2.0)).toHaveLength(1)
    expect(activeBursts(o, 3.9)).toHaveLength(1)
    expect(activeBursts(o, 4.0)).toHaveLength(0)
  })

  it('words a pass plainly', () => {
    expect(passLine(pass())).toBe('13 m, 70 km/h, difficulty 42')
    expect(passLine(pass({ ball_speed_kmh: null, x: null }))).toBe('difficulty 42')
  })

  it('reads track numbers and foot points', () => {
    expect(trackOf('BLU-T014')).toBe(14)
    expect(trackOf(null)).toBeNull()
    expect(foot({ id: 1, x1: 10, y1: 0, x2: 30, y2: 50, kmh: 0 })).toEqual([20, 50])
  })
})

describe('matchClock', () => {
  it('adds the clip start so the transport matches the pass list', () => {
    expect(matchClock(1890, 1.76)).toBe('31:31')
    expect(matchClock(1890, 0)).toBe('31:30')
    expect(matchClock(0, 5)).toBe('00:05')
  })
})

describe('labels', () => {
  it('names a tracked player by team, and knows the clip length before the video loads', async () => {
    const { teamOf, clipSeconds } = await import('./real')
    const o = { tracks: { '172': { team: 'WHT', label: 'White 172' } }, frames: [], fps: 25 }
    expect(teamOf(o as never, 'real-WHT-T172')).toBe('White')
    expect(clipSeconds({ frames: [[0], [2500]] as never, fps: 25 })).toBe(100)
  })
})
