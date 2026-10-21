import type { PlayerFrame, TrackingFrame } from '@/types/schema'

/** Within this many metres of the ball a player counts as on it. */
const CARRY_M = 2.5
/** Opponents within this many metres of the carrier count as pressing. */
const PRESS_M = 8

const teamOf = (id: string) => id.split('-')[0] ?? ''

/** The player on the ball, or null when it is loose or in the air between players. */
export function carrierOf(frame: TrackingFrame): PlayerFrame | null {
  let best: PlayerFrame | null = null
  let bestD = Infinity
  for (const p of frame.players) {
    const d = Math.hypot(p.x - frame.ball.x, p.y - frame.ball.y)
    if (d < bestD) {
      bestD = d
      best = p
    }
  }
  return best && bestD <= CARRY_M ? best : null
}

/** Opponents close enough to the carrier to be pressing them, nearest first. */
export function pressersOf(frame: TrackingFrame, carrier: PlayerFrame): PlayerFrame[] {
  const team = teamOf(carrier.id)
  return frame.players
    .filter((p) => teamOf(p.id) !== team)
    .map((p) => ({ p, d: Math.hypot(p.x - carrier.x, p.y - carrier.y) }))
    .filter(({ d }) => d <= PRESS_M)
    .sort((a, b) => a.d - b.d)
    .map(({ p }) => p)
}

/** The carrier's two nearest team-mates: the simplest passing options. */
export function optionsFor(frame: TrackingFrame, carrier: PlayerFrame, n = 2): PlayerFrame[] {
  const team = teamOf(carrier.id)
  return frame.players
    .filter((p) => p.id !== carrier.id && teamOf(p.id) === team)
    .sort(
      (a, b) =>
        Math.hypot(a.x - carrier.x, a.y - carrier.y) - Math.hypot(b.x - carrier.x, b.y - carrier.y),
    )
    .slice(0, n)
}

/**
 * Which way a team is attacking along the pitch: +1 toward x = 105, -1 toward x = 0. Read from
 * where their rearmost player stands (nearly always the goalkeeper), so it flips at half-time
 * with no extra data.
 */
export function attackDirection(frame: TrackingFrame, team: string): 1 | -1 {
  const xs = frame.players.filter((p) => teamOf(p.id) === team).map((p) => p.x)
  if (xs.length === 0) return 1
  const min = Math.min(...xs)
  const max = Math.max(...xs)
  return min < 105 - max ? 1 : -1
}
