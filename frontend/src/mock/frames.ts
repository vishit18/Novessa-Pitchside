import { PITCH_LENGTH, PITCH_WIDTH } from '@/types/schema'
import type { MatchEvent, MatchMeta, PlayerFrame, TeamSheet, TrackingFrame } from '@/types/schema'

/**
 * Plausible tracking frames for the mock source, built from the events.
 *
 * The real engine writes its own 10 Hz frames; this only exists so the broadcast view has
 * something to draw before the gateway is up. Nothing here is football-accurate. The ball
 * follows the event geometry, each side holds its formation shape and shifts with the ball,
 * and players chase their target at a capped speed.
 */

const MAX_SPEED_MS = 8.6 // about 31 km/h
const MOVING_TYPES = new Set(['pass', 'carry', 'dribble', 'shot', 'clearance'])
const POSSESSION_TYPES = new Set([
  'pass',
  'carry',
  'dribble',
  'shot',
  'kick_off',
  'free_kick',
  'corner',
  'throw_in',
  'goal',
])

interface Slot {
  id: string
  /** 0..1 depth from own goal to the opposition goal */
  depth: number
  /** 0..1 across the pitch */
  width: number
  gk: boolean
}

function hash(s: string): number {
  let h = 2166136261
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619)
  return ((h >>> 0) % 1000) / 1000
}

/** Turn a sheet into formation slots: GK, then rows from the formation string. */
export function formationSlots(sheet: TeamSheet): Slot[] {
  const rows = sheet.formation.split('-').map(Number)
  const ordered = [...sheet.starters].sort((a, b) => a.slot - b.slot)
  const gk = ordered.find((p) => p.group === 'GK') ?? ordered[0]!
  const rest = ordered.filter((p) => p !== gk)
  const slots: Slot[] = [{ id: gk.player_id, depth: 0.03, width: 0.5, gk: true }]
  let i = 0
  rows.forEach((n, r) => {
    const depth = 0.2 + (0.62 * r) / Math.max(1, rows.length - 1)
    for (let j = 0; j < n; j++) {
      const p = rest[i++]
      if (!p) return
      slots.push({ id: p.player_id, depth, width: (j + 0.5) / n, gk: false })
    }
  })
  return slots
}

const lerp = (a: number, b: number, k: number) => a + (b - a) * k
const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v))

interface Ball {
  x: number
  y: number
}

export class MockFrameModel {
  private readonly ballEvents: MatchEvent[]
  private readonly slots: { home: Slot[]; away: Slot[] }
  private readonly pos = new Map<string, { x: number; y: number }>()
  private lastT = -1

  constructor(
    private readonly meta: MatchMeta,
    events: MatchEvent[],
  ) {
    this.ballEvents = events.filter((e) => e.x != null && e.y != null && e.type !== 'substitution')
    this.slots = { home: formationSlots(meta.home), away: formationSlots(meta.away) }
  }

  /** Forget smoothing state after a seek. */
  reset(): void {
    this.pos.clear()
    this.lastT = -1
  }

  private index(t: number): number {
    const a = this.ballEvents
    let lo = 0
    let hi = a.length - 1
    let ans = 0
    while (lo <= hi) {
      const mid = (lo + hi) >> 1
      if (a[mid]!.t_match <= t) {
        ans = mid
        lo = mid + 1
      } else hi = mid - 1
    }
    return ans
  }

  private ballAt(t: number, i: number): Ball {
    const e = this.ballEvents[i]
    if (!e) return { x: PITCH_LENGTH / 2, y: PITCH_WIDTH / 2 }
    const next = this.ballEvents[i + 1]
    const sx = e.x ?? 52.5
    const sy = e.y ?? 34
    const ex = e.end_x ?? sx
    const ey = e.end_y ?? sy
    let dur = 0
    if (MOVING_TYPES.has(e.type)) {
      const d = Math.hypot(ex - sx, ey - sy)
      const gap = next ? next.t_match - e.t_match : 3
      dur =
        e.type === 'carry' || e.type === 'dribble'
          ? clamp(gap * 0.9, 0.5, 6)
          : clamp(d / (Math.max(20, e.ball_speed_kmh ?? 40) / 3.6), 0.4, Math.max(0.5, gap))
    }
    const k = dur > 0 ? clamp((t - e.t_match) / dur, 0, 1) : 1
    let bx = lerp(sx, ex, k)
    let by = lerp(sy, ey, k)
    // Glide toward the next event's start so the ball does not teleport.
    if (next && next.x != null && next.y != null) {
      const glideFrom = Math.max(e.t_match + dur, next.t_match - 0.6)
      if (t > glideFrom && next.t_match > glideFrom) {
        const g = clamp((t - glideFrom) / (next.t_match - glideFrom), 0, 1)
        bx = lerp(bx, next.x, g)
        by = lerp(by, next.y, g)
      }
    }
    return { x: bx, y: by }
  }

  /** Frame at match time `t`. Call with increasing t for smooth motion. */
  frame(t: number): TrackingFrame {
    const i = this.index(t)
    const ev = this.ballEvents[i]
    const ball = this.ballAt(t, i)
    const period = ev?.period ?? 1

    let attacking = this.meta.home.code
    for (let j = i; j >= 0; j--) {
      const c = this.ballEvents[j]!
      if (c.team && POSSESSION_TYPES.has(c.type)) {
        attacking = c.team
        break
      }
    }

    const dt = this.lastT < 0 ? 0 : clamp(t - this.lastT, 0, 1)
    this.lastT = t
    const players: PlayerFrame[] = []

    for (const side of ['home', 'away'] as const) {
      const sheet = this.meta[side]
      const goesRight = (side === 'home') === (period === 1)
      const hasBall = sheet.code === attacking
      // In the team's own attacking frame: positive means further up the pitch.
      const dir = goesRight ? 1 : -1
      const shift = clamp((ball.x - 52.5) * 0.4 * dir, -24, 24) + (hasBall ? 5 : 0)
      // The closest outfielder to the ball presses (or carries it).
      let nearest: string | null = null
      let nearestD = Infinity
      for (const s of this.slots[side]) {
        if (s.gk) continue
        const bx = this.base(s, goesRight, shift, ball).x
        const by = this.base(s, goesRight, shift, ball).y
        const d = Math.hypot(bx - ball.x, by - ball.y)
        if (d < nearestD) {
          nearestD = d
          nearest = s.id
        }
      }
      for (const s of this.slots[side]) {
        const b = this.base(s, goesRight, shift, ball)
        let tx = b.x
        let ty = b.y
        if (s.id === nearest) {
          tx = ball.x + (hasBall ? 0 : goesRight ? 1.2 : -1.2)
          ty = ball.y
        }
        if (ev?.player_id === s.id && ev.team === sheet.code && ev.t_match + 1.5 > t - 1) {
          tx = ball.x
          ty = ball.y
        }
        if (ev?.receiver_id === s.id && ev.end_x != null && ev.end_y != null) {
          tx = ev.end_x
          ty = ev.end_y
        }
        const wob = 0.5
        tx += Math.sin(t * 0.6 + hash(s.id) * 6.28) * wob
        ty += Math.cos(t * 0.5 + hash(s.id + 'y') * 6.28) * wob

        const cur = this.pos.get(s.id) ?? { x: tx, y: ty }
        let nx = cur.x
        let ny = cur.y
        let v = 0
        if (dt > 0) {
          const dx = tx - cur.x
          const dy = ty - cur.y
          const dist = Math.hypot(dx, dy)
          const want = Math.min(MAX_SPEED_MS * dt, dist * (1 - Math.exp(-dt / 0.9)))
          if (dist > 1e-6) {
            nx = cur.x + (dx / dist) * want
            ny = cur.y + (dy / dist) * want
          }
          v = (Math.hypot(nx - cur.x, ny - cur.y) / dt) * 3.6
        } else {
          nx = tx
          ny = ty
        }
        this.pos.set(s.id, { x: nx, y: ny })
        players.push({
          id: s.id,
          x: clamp(nx, 0, PITCH_LENGTH),
          y: clamp(ny, 0, PITCH_WIDTH),
          v_kmh: Math.round(v * 10) / 10,
        })
      }
    }
    return {
      match_id: this.meta.match_id,
      t_match: Math.round(t * 10) / 10,
      ball: { x: ball.x, y: ball.y, z: 0 },
      players,
    }
  }

  private base(s: Slot, goesRight: boolean, shift: number, ball: Ball): { x: number; y: number } {
    let x = s.depth * PITCH_LENGTH + (s.gk ? 0 : shift * (0.6 + s.depth * 0.4))
    let y = 4 + s.width * (PITCH_WIDTH - 8)
    if (s.gk) {
      // Already in world coordinates for y: track the ball a little.
      return { x: goesRight ? x : PITCH_LENGTH - x, y: lerp(34, ball.y, 0.2) }
    }
    y = lerp(y, goesRight ? ball.y : PITCH_WIDTH - ball.y, 0.18)
    x = clamp(x, 6, PITCH_LENGTH - 6)
    return goesRight ? { x, y } : { x: PITCH_LENGTH - x, y: PITCH_WIDTH - y }
  }
}
