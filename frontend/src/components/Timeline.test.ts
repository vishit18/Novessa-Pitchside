import { describe, expect, it } from 'vitest'
import type { KeyMoment } from '@/net/api'
import { previewClock, visibleMoments } from './Timeline'

const moment = (t: number, kind: KeyMoment['kind'] = 'goal'): KeyMoment => ({
  moment_id: `m-${t}`,
  t_match: t,
  clock: '',
  kind,
  headline: '',
  team: 'ASH',
  card: null,
})

describe('timeline', () => {
  it('never marks a moment the viewer has not reached unless spoilers are on', () => {
    const all = [moment(600), moment(1600), moment(5000)]
    expect(visibleMoments(all, 1000, false).map((m) => m.t_match)).toEqual([600])
    expect(visibleMoments(all, 1600, false).map((m) => m.t_match)).toEqual([600, 1600])
    expect(visibleMoments(all, 1000, true)).toHaveLength(3)
  })

  it('previews a football clock, with added time in each half', () => {
    expect(previewClock(0, 2887)).toBe("1'")
    expect(previewClock(1607, 2887)).toBe("27'")
    expect(previewClock(2800, 2887)).toBe("45+2'")
    expect(previewClock(2887 + 60, 2887)).toBe("47'")
    expect(previewClock(2887 + 46 * 60, 2887)).toBe("90+2'")
  })
})
