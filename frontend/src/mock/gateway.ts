import { CLUBS, PLAYERS } from '@/data/league'
import type { OverlayEnvelope, OverlayKind, OverlaySlot, WireMessage } from '@/types/overlay'
import type { MatchEvent, MatchMeta, PlayerFrame, StateSnapshot } from '@/types/schema'

/**
 * A stand-in for the real gateway + state engine, just enough to drive the broadcast view.
 * It derives instant overlays from events the way backend/state does (thresholds mirror
 * config/thresholds.yaml) and keeps a rough score, possession and momentum.
 * Delete this once the WebSocket gateway is live.
 */

const SHOT_SPEED_KMH = 95
const PASS_DIFFICULTY = 75
const SPRINT_KMH = 29
const SPRINT_COOLDOWN_S = 40

const POSSESSION_EVENTS = new Set(['pass', 'carry', 'dribble'])

export function formatClock(t: number, p2Start: number): string {
  const sec = Math.max(0, Math.floor(t))
  if (t < p2Start) {
    const m = Math.floor(sec / 60)
    const s = sec % 60
    const pad = (n: number) => String(n).padStart(2, '0')
    return m >= 45 ? `45+${m - 45}:${pad(s)}` : `${pad(m)}:${pad(s)}`
  }
  const into = Math.floor(t - p2Start) + 45 * 60
  const m = Math.floor(into / 60)
  const s = into % 60
  const pad = (n: number) => String(n).padStart(2, '0')
  return m >= 90 ? `90+${m - 90}:${pad(s)}` : `${pad(m)}:${pad(s)}`
}

export class MockGateway {
  private n = 0
  private score: Record<string, number>
  private momentum = 0
  private lastDecayT = 0
  private possessionMatch: Record<string, number>
  private recent: { t: number; team: string }[] = []
  private lastSprint = new Map<string, number>()
  readonly p2Start: number
  readonly p1End: number

  constructor(
    private readonly meta: MatchMeta,
    events: MatchEvent[],
  ) {
    const home = meta.home.code
    const away = meta.away.code
    this.score = { [home]: 0, [away]: 0 }
    this.possessionMatch = { [home]: 0, [away]: 0 }
    this.p2Start = events.find((e) => e.type === 'period_start' && e.period === 2)?.t_match ?? 2800
    this.p1End = events.find((e) => e.type === 'period_end' && e.period === 1)?.t_match ?? 2700
  }

  reset(): void {
    this.score = { [this.meta.home.code]: 0, [this.meta.away.code]: 0 }
    this.possessionMatch = { [this.meta.home.code]: 0, [this.meta.away.code]: 0 }
    this.momentum = 0
    this.lastDecayT = 0
    this.recent = []
    this.lastSprint.clear()
  }

  /** Bring score and momentum up to a seek target by replaying events silently. */
  fastForward(events: MatchEvent[], toT: number): void {
    this.reset()
    for (const e of events) {
      if (e.t_match > toT) break
      this.updateState(e)
    }
  }

  private name(id: string | null | undefined): string {
    return (id && PLAYERS[id]?.name) || id || 'Unknown'
  }

  private envelope(
    e: MatchEvent,
    kind: OverlayKind,
    slot: OverlaySlot,
    over: Partial<OverlayEnvelope> & { payload: Record<string, unknown> },
  ): WireMessage {
    this.n += 1
    const data: OverlayEnvelope = {
      v: 1,
      msg_id: `ovl-${e.match_id}-${String(this.n).padStart(5, '0')}`,
      match_id: e.match_id,
      moment_id: `mom-${e.match_id}-${e.seq}`,
      op: 'show',
      slot,
      kind,
      priority: 50,
      t_match: e.t_match,
      t_wall_emit: new Date().toISOString(),
      show_at: e.t_match + 0.2,
      duration_s: 5,
      anchor: null,
      persona: ['analyst', 'casual'],
      lang: 'en',
      provenance: { source: 'state_engine', verified: true, evidence: [] },
      ...over,
    }
    return { type: 'overlay', data }
  }

  private updateState(e: MatchEvent): void {
    const home = this.meta.home.code
    // momentum decays with a 180 s half-life, then the event pushes it
    const dt = Math.max(0, e.t_match - this.lastDecayT)
    this.momentum *= Math.pow(0.5, dt / 180)
    this.lastDecayT = e.t_match
    if (e.team) {
      const sign = e.team === home ? 1 : -1
      const forward = e.team === home ? (e.x ?? 52.5) / 105 : 1 - (e.x ?? 52.5) / 105
      const w: Record<string, number> = {
        pass: 0.4 + forward * 0.8,
        carry: 0.5 + forward,
        dribble: 1 + forward,
        shot: 6,
        corner: 3,
        goal: 10,
        tackle: 1,
        interception: 1,
      }
      this.momentum += sign * (w[e.type] ?? 0)
      if (POSSESSION_EVENTS.has(e.type)) {
        this.possessionMatch[e.team] = (this.possessionMatch[e.team] ?? 0) + 1
        this.recent.push({ t: e.t_match, team: e.team })
      }
    }
    if (e.type === 'goal' && e.team) this.score[e.team] = (this.score[e.team] ?? 0) + 1
    while (this.recent.length && this.recent[0]!.t < e.t_match - 300) this.recent.shift()
  }

  /** Snapshot for the scoreboard, momentum bar and clock. */
  snapshot(t: number): WireMessage {
    const home = this.meta.home.code
    const away = this.meta.away.code
    const share = (counts: Record<string, number>) => {
      const total = (counts[home] ?? 0) + (counts[away] ?? 0) || 1
      return {
        [home]: (100 * (counts[home] ?? 0)) / total,
        [away]: (100 * (counts[away] ?? 0)) / total,
      }
    }
    const rc = { [home]: 0, [away]: 0 }
    for (const r of this.recent) rc[r.team] = (rc[r.team] ?? 0) + 1
    const data: StateSnapshot = {
      t_match: Math.round(t * 10) / 10,
      clock: formatClock(t, this.p2Start),
      period: t >= this.p2Start ? 2 : 1,
      score: { ...this.score },
      possession_match: share(this.possessionMatch),
      possession_5min: share(rc),
      momentum: Math.round(100 * Math.tanh(this.momentum / 30)),
      pressure: { [home]: 50, [away]: 50 },
      control_chaos: { value: 60, label: 'balanced' },
      rhythm: { events_per_min: 0, avg_possession_len: 0, broken: false },
    }
    return { type: 'state', data }
  }

  /** Update internal state for an event and return the overlays it triggers. */
  onEvent(e: MatchEvent): WireMessage[] {
    this.updateState(e)
    const out: WireMessage[] = [{ type: 'event', data: e }]
    const pid = e.player_id ?? ''
    const club = e.team ? CLUBS[e.team] : undefined

    if (
      e.type === 'pass' &&
      (e.pass_difficulty ?? 0) >= PASS_DIFFICULTY &&
      e.x != null &&
      e.y != null
    ) {
      const dist = Math.hypot((e.end_x ?? e.x) - e.x, (e.end_y ?? e.y) - e.y)
      out.push(
        this.envelope(e, 'pass_difficulty', 'pitch_annotation', {
          priority: 60,
          duration_s: 5,
          anchor: { type: 'pitch', x: e.x, y: e.y },
          payload: {
            difficulty: e.pass_difficulty,
            distance_m: Math.round(dist * 10) / 10,
            ball_speed_kmh: e.ball_speed_kmh ?? null,
            factors: (e.difficulty_factors ?? []).slice(0, 3),
            complete: e.outcome === 'complete',
            player_id: pid,
            team: e.team,
            end_x: e.end_x,
            end_y: e.end_y,
          },
          provenance: {
            source: 'state_engine',
            verified: true,
            evidence: [{ metric: 'pass_difficulty', value: e.pass_difficulty ?? 0 }],
          },
        }),
      )
    }

    if (e.type === 'shot' && (e.ball_speed_kmh ?? 0) >= SHOT_SPEED_KMH) {
      out.push(
        this.envelope(e, 'shot_speed', 'lower_third', {
          priority: 70,
          duration_s: 5.5,
          anchor: pid ? { type: 'player', id: pid } : null,
          payload: {
            speed_kmh: e.ball_speed_kmh,
            xg: e.xg ?? null,
            outcome: e.outcome,
            player_id: pid,
            team: e.team,
          },
          provenance: {
            source: 'state_engine',
            verified: true,
            evidence: [{ metric: 'ball_speed_kmh', value: e.ball_speed_kmh ?? 0 }],
          },
        }),
      )
    }

    if (e.type === 'goal' && e.team) {
      const home = this.meta.home.code
      const away = this.meta.away.code
      const assist = e.tags?.find((t) => t.startsWith('assist:'))?.slice(7)
      const base = {
        priority: 95,
        duration_s: 9,
        anchor: pid ? ({ type: 'player', id: pid } as const) : null,
      }
      const scoreLine = `${this.score[home] ?? 0}-${this.score[away] ?? 0}`
      out.push(
        this.envelope(e, 'insight', 'lower_third', {
          ...base,
          show_at: e.t_match + 0.2,
          payload: {
            headline: `GOAL  ${this.name(pid)}`,
            body: `${club?.name ?? e.team}  ${scoreLine}  ·  ${e.clock}'`,
            team: e.team,
            player_id: pid,
            tone: 'goal',
          },
        }),
      )
      // The language layer lands a couple of seconds later and attaches by moment_id.
      const late = this.envelope(e, 'insight', 'lower_third', {
        ...base,
        op: 'update',
        show_at: e.t_match + 2.6,
        duration_s: 6.5,
        payload: {
          body: assist
            ? `Set up by ${this.name(assist)}. ${club?.name ?? e.team} lead the count at ${scoreLine}.`
            : `${club?.name ?? e.team} make it ${scoreLine}.`,
          late_by_s: 2.4,
        },
        provenance: { source: 'agent:analyst', verified: true, evidence: [] },
      })
      out.push(late)
    }

    if (e.type === 'card' && pid) {
      out.push(
        this.envelope(e, 'milestone', 'lower_third', {
          priority: 80,
          duration_s: 5,
          anchor: { type: 'player', id: pid },
          payload: {
            headline: `${(e.outcome ?? 'yellow').toUpperCase()} CARD  ${this.name(pid)}`,
            body: `${club?.name ?? e.team}  ·  ${e.clock}'`,
            team: e.team,
            player_id: pid,
            tone: 'card',
          },
        }),
      )
    }
    return out
  }

  /** Speed bursts come from tracking, not events. */
  onFrameSpeed(t: number, players: PlayerFrame[], matchId: string): WireMessage[] {
    const out: WireMessage[] = []
    for (const p of players) {
      if (p.v_kmh < SPRINT_KMH) continue
      const last = this.lastSprint.get(p.id) ?? -1e9
      if (t - last < SPRINT_COOLDOWN_S) continue
      this.lastSprint.set(p.id, t)
      this.n += 1
      out.push({
        type: 'overlay',
        data: {
          v: 1,
          msg_id: `ovl-${matchId}-${String(this.n).padStart(5, '0')}`,
          match_id: matchId,
          moment_id: `mom-${matchId}-spd-${this.n}`,
          op: 'show',
          slot: 'player_tag',
          kind: 'speed_burst',
          priority: 40,
          t_match: t,
          t_wall_emit: new Date().toISOString(),
          show_at: t + 0.15,
          duration_s: 3.2,
          anchor: { type: 'player', id: p.id },
          persona: ['analyst', 'casual'],
          lang: 'en',
          payload: { speed_kmh: Math.round(p.v_kmh * 10) / 10, team: p.id.slice(0, 3) },
          provenance: {
            source: 'state_engine',
            verified: true,
            evidence: [{ metric: 'speed_kmh', value: p.v_kmh }],
          },
        },
      })
      break // one at a time keeps the screen calm
    }
    return out
  }
}
