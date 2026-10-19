import type { PlayerFrame, TrackingFrame } from '@/types/schema'

/** Binary search: index of the last item with t_match <= t, or -1. */
export function lastAtOrBefore<T extends { t_match: number }>(items: T[], t: number): number {
  let lo = 0
  let hi = items.length - 1
  let ans = -1
  while (lo <= hi) {
    const mid = (lo + hi) >> 1
    if (items[mid]!.t_match <= t) {
      ans = mid
      lo = mid + 1
    } else hi = mid - 1
  }
  return ans
}

/** Insert keeping t_match order. Late arrivals are fine; the common case is an append. */
export function insertSorted<T extends { t_match: number }>(items: T[], item: T): void {
  let i = items.length
  while (i > 0 && items[i - 1]!.t_match > item.t_match) i--
  items.splice(i, 0, item)
}

/** Drop everything older than `before`, keeping the last older item so interpolation still works. */
export function trimBefore<T extends { t_match: number }>(items: T[], before: number): void {
  const i = lastAtOrBefore(items, before)
  if (i > 0) items.splice(0, i)
}

const lerp = (a: number, b: number, k: number) => a + (b - a) * k

/**
 * Frame at match time `t`, linearly interpolated between the two surrounding frames.
 * Returns null before the first frame. Holds the last frame if `t` is past the end.
 */
export function frameAt(frames: TrackingFrame[], t: number): TrackingFrame | null {
  const i = lastAtOrBefore(frames, t)
  if (i < 0) return null
  const a = frames[i]!
  const b = frames[i + 1]
  if (!b || b.t_match <= a.t_match) return a
  const k = Math.min(1, Math.max(0, (t - a.t_match) / (b.t_match - a.t_match)))
  const byId = new Map<string, PlayerFrame>(b.players.map((p) => [p.id, p]))
  return {
    match_id: a.match_id,
    t_match: t,
    ball: {
      x: lerp(a.ball.x, b.ball.x, k),
      y: lerp(a.ball.y, b.ball.y, k),
      z: lerp(a.ball.z, b.ball.z, k),
    },
    players: a.players.map((p) => {
      const q = byId.get(p.id)
      return q
        ? { id: p.id, x: lerp(p.x, q.x, k), y: lerp(p.y, q.y, k), v_kmh: lerp(p.v_kmh, q.v_kmh, k) }
        : p
    }),
  }
}
