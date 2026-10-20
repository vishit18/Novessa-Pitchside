/** Real footage overlay data from the vision pipeline (data/real/<clip>/overlay.json). */

export interface RealEvent {
  t_match: number
  clock: string
  type: string
  team: string | null
  player_id: string | null
  receiver_id: string | null
  outcome: string | null
  ball_speed_kmh: number | null
  pass_difficulty: number | null
  x: number | null
  y: number | null
  end_x: number | null
  end_y: number | null
}

/** [frame, [[track, x1, y1, x2, y2, km/h], ...], ball pixel or null] */
export type OverlayFrame = [number, number[][], number[] | null]

export interface RealOverlay {
  match_id: string
  fps: number
  clip: [number, number]
  credit: string
  start_s: number
  tracks: Record<string, { team: 'BLU' | 'WHT'; label: string }>
  frames: OverlayFrame[]
  events: RealEvent[]
  bursts: { frame: number; track: number; team: string; kmh: number }[]
}

export interface Box {
  id: number
  x1: number
  y1: number
  x2: number
  y2: number
  kmh: number
}

/** Index of the last row at or before `frame`, or -1 before the first. */
export function rowAtOrBefore(frames: OverlayFrame[], frame: number): number {
  let lo = 0
  let hi = frames.length - 1
  let ans = -1
  while (lo <= hi) {
    const mid = (lo + hi) >> 1
    if (frames[mid]![0] <= frame) {
      ans = mid
      lo = mid + 1
    } else hi = mid - 1
  }
  return ans
}

const lerp = (a: number, b: number, u: number) => a + (b - a) * u

/**
 * Boxes and ball at video time `t` seconds. The file holds every second frame, so positions are
 * blended between the two surrounding rows; a person seen in only one of them is drawn as is.
 */
export function boxesAt(
  o: RealOverlay,
  t: number,
): { boxes: Box[]; ball: [number, number] | null } {
  const frame = t * o.fps
  const i = rowAtOrBefore(o.frames, frame)
  if (i < 0) return { boxes: [], ball: null }
  const a = o.frames[i]!
  const b = o.frames[i + 1]
  const u = b && b[0] > a[0] ? Math.min(1, (frame - a[0]) / (b[0] - a[0])) : 0
  const next = new Map<number, number[]>((b?.[1] ?? []).map((r) => [r[0]!, r]))
  const boxes = a[1].map((r) => {
    const n = next.get(r[0]!)
    const m = (k: number) => (n ? lerp(r[k]!, n[k]!, u) : r[k]!)
    return { id: r[0]!, x1: m(1), y1: m(2), x2: m(3), y2: m(4), kmh: m(5) }
  })
  const ball: [number, number] | null =
    a[2] && b?.[2]
      ? [lerp(a[2][0]!, b[2][0]!, u), lerp(a[2][1]!, b[2][1]!, u)]
      : a[2]
        ? [a[2][0]!, a[2][1]!]
        : null
  return { boxes, ball }
}

/** "BLU-T014" is track 14. */
export function trackOf(playerId: string | null): number | null {
  const m = playerId ? /-T(\d+)$/.exec(playerId) : null
  return m ? Number(m[1]) : null
}

/** Foot point of a box, where a line to or from the player should start. */
export function foot(b: Box): [number, number] {
  return [(b.x1 + b.x2) / 2, b.y2]
}

/** How long a pass card stays up after the ball is played, in seconds. */
export const PASS_CARD_S = 3.5
export const BURST_S = 2

/** Completed passes whose card is up at time `t`. */
export function activePasses(events: RealEvent[], t: number): RealEvent[] {
  return events.filter(
    (e) =>
      e.type === 'pass' &&
      e.outcome === 'complete' &&
      t >= e.t_match &&
      t < e.t_match + PASS_CARD_S,
  )
}

/** Sprint peaks whose callout is up at time `t`. */
export function activeBursts(o: RealOverlay, t: number): RealOverlay['bursts'] {
  const f = t * o.fps
  return o.bursts.filter((b) => f >= b.frame && f < b.frame + BURST_S * o.fps)
}

/** One line for a pass card: "18 m, 71 km/h, difficulty 42". */
export function passLine(e: RealEvent): string {
  const dist =
    e.x != null && e.y != null && e.end_x != null && e.end_y != null
      ? Math.hypot(e.end_x - e.x, e.end_y - e.y)
      : null
  return [
    dist != null ? `${Math.round(dist)} m` : null,
    e.ball_speed_kmh != null ? `${Math.round(e.ball_speed_kmh)} km/h` : null,
    e.pass_difficulty != null ? `difficulty ${Math.round(e.pass_difficulty)}` : null,
  ]
    .filter(Boolean)
    .join(', ')
}
