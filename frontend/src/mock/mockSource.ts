import { MockFrameModel } from './frames'
import { MockGateway } from './gateway'
import type {
  ConnectionStatus,
  MatchSource,
  PlaybackControls,
  SourceHandlers,
  SourceOptions,
} from '@/net/source'
import type { MatchEvent, MatchMeta } from '@/types/schema'

const FRAME_DT = 0.1
const STATE_DT = 1
const TICK_MS = 33

const files = import.meta.glob('../../../data/matches/*.jsonl', {
  query: '?raw',
  import: 'default',
}) as Record<string, () => Promise<string>>

async function loadMatch(matchId: string): Promise<{ meta: MatchMeta; events: MatchEvent[] }> {
  const key = Object.keys(files).find((k) => k.endsWith(`/${matchId}.jsonl`))
  if (!key) throw new Error(`No sample match "${matchId}" in data/matches`)
  const raw = await files[key]!()
  let meta: MatchMeta | null = null
  const events: MatchEvent[] = []
  for (const line of raw.split('\n')) {
    if (!line.trim()) continue
    const rec = JSON.parse(line) as { record?: string }
    if (rec.record === 'meta') meta = rec as unknown as MatchMeta
    else events.push(rec as unknown as MatchEvent)
  }
  if (!meta) throw new Error(`Match "${matchId}" has no meta record`)
  events.sort((a, b) => a.t_match - b.t_match)
  return { meta, events }
}

/**
 * Plays a sample match from data/matches as if it were the gateway: frames at 10 Hz, events as
 * they happen, a state snapshot every second, and instant overlays derived from the events.
 */
export class MockSource implements MatchSource {
  readonly kind = 'mock' as const
  controls: PlaybackControls
  private timer: number | undefined
  private t: number
  private speed: number
  private paused = false
  private model: MockFrameModel | null = null
  private gateway: MockGateway | null = null
  private events: MatchEvent[] = []
  private nextEvent = 0
  private nextFrameT = 0
  private nextStateT = 0
  private handlers: SourceHandlers | null = null
  private lastWall = 0
  /** Player smoothing is cold right after a seek, so hold back speed bursts for a few seconds. */
  private quietUntil = 0

  constructor(private readonly opts: SourceOptions) {
    this.t = opts.startAt ?? 0
    this.speed = opts.speed ?? 4
    this.controls = {
      setSpeed: (s) => {
        this.speed = s
      },
      setPaused: (p) => {
        this.paused = p
      },
      seek: (to) => this.seekTo(to),
    }
  }

  connect(handlers: SourceHandlers): void {
    this.handlers = handlers
    handlers.onStatus('connecting' satisfies ConnectionStatus)
    loadMatch(this.opts.matchId)
      .then(({ meta, events }) => {
        this.events = events
        this.model = new MockFrameModel(meta, events)
        this.gateway = new MockGateway(meta, events)
        handlers.onMeta(meta)
        this.seekTo(this.t)
        handlers.onStatus('live')
        this.lastWall = performance.now()
        this.timer = window.setInterval(() => this.tick(), TICK_MS)
      })
      .catch((err: unknown) =>
        handlers.onStatus('error', err instanceof Error ? err.message : String(err)),
      )
  }

  close(): void {
    window.clearInterval(this.timer)
  }

  private seekTo(to: number): void {
    if (!this.model || !this.gateway) return
    this.t = Math.max(0, to)
    this.model.reset()
    this.gateway.fastForward(this.events, this.t)
    this.nextEvent = this.events.findIndex((e) => e.t_match > this.t)
    if (this.nextEvent < 0) this.nextEvent = this.events.length
    this.quietUntil = this.t + 6
    this.nextFrameT = Math.ceil(this.t / FRAME_DT) * FRAME_DT
    this.nextStateT = Math.ceil(this.t / STATE_DT) * STATE_DT
    // Warm the player smoothing so the first frame is not a pile on the centre spot.
    for (let w = this.t - 3; w < this.t; w += 0.5) this.model.frame(Math.max(0, w))
    this.handlers?.onMessage({ type: 'frame', data: this.model.frame(this.t) })
    this.handlers?.onMessage(this.gateway.snapshot(this.t))
  }

  private tick(): void {
    const now = performance.now()
    const dtWall = (now - this.lastWall) / 1000
    this.lastWall = now
    const h = this.handlers
    if (!h || !this.model || !this.gateway || this.paused) return
    const target = this.t + dtWall * this.speed
    while (this.nextFrameT <= target) {
      const t = this.nextFrameT
      while (this.nextEvent < this.events.length && this.events[this.nextEvent]!.t_match <= t) {
        for (const m of this.gateway.onEvent(this.events[this.nextEvent]!)) h.onMessage(m)
        this.nextEvent += 1
      }
      const frame = this.model.frame(t)
      h.onMessage({ type: 'frame', data: frame })
      if (t >= this.quietUntil)
        for (const m of this.gateway.onFrameSpeed(t, frame.players, frame.match_id)) h.onMessage(m)
      if (t >= this.nextStateT) {
        h.onMessage(this.gateway.snapshot(t))
        this.nextStateT += STATE_DT
      }
      this.nextFrameT = Math.round((t + FRAME_DT) * 10) / 10
    }
    this.t = target
  }
}
