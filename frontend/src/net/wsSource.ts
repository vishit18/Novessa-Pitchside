import type { WireMessage } from '@/types/overlay'
import type { MatchMeta } from '@/types/schema'
import type { MatchSource, PlaybackControls, SourceHandlers, SourceOptions } from './source'

const MAX_BACKOFF_MS = 8000

function isWireMessage(x: unknown): x is WireMessage {
  if (typeof x !== 'object' || x === null) return false
  const m = x as { type?: unknown; data?: unknown }
  return (
    (m.type === 'frame' || m.type === 'event' || m.type === 'state' || m.type === 'overlay') &&
    typeof m.data === 'object' &&
    m.data !== null
  )
}

/**
 * WS /ws/matches/{id}?viewer=&persona=&club=&player=&metric=&lang=&speed=&t=  (docs/05 Transport)
 *
 * The gateway filters and words every overlay for the profile in the query string. Control
 * messages ({"op": "play" | "pause" | "speed" | "seek"}) go back over the same socket.
 * Reconnects with exponential backoff and resumes from the last match time it saw. Buffering
 * and de-duplication happen downstream in StreamBuffers.
 */
export class WebSocketSource implements MatchSource {
  readonly kind = 'ws' as const
  readonly controls: PlaybackControls
  private ws: WebSocket | null = null
  private handlers: SourceHandlers | null = null
  private attempt = 0
  private timer: number | undefined
  private closedByUs = false
  private lastT: number
  private speed: number
  private paused = false

  constructor(
    private readonly baseUrl: string,
    private readonly opts: SourceOptions,
  ) {
    this.lastT = opts.startAt ?? 0
    this.speed = opts.speed ?? 1
    this.controls = {
      setSpeed: (value) => {
        this.speed = value
        this.send({ op: 'speed', value })
      },
      setPaused: (p) => {
        this.paused = p
        this.send({ op: p ? 'pause' : 'play' })
      },
      seek: (t) => {
        this.lastT = t
        this.send({ op: 'seek', t })
      },
    }
  }

  connect(handlers: SourceHandlers): void {
    this.handlers = handlers
    this.closedByUs = false
    void this.loadMeta(handlers)
    this.open()
  }

  close(): void {
    this.closedByUs = true
    window.clearTimeout(this.timer)
    this.ws?.close()
    this.ws = null
  }

  private get httpBase(): string {
    return this.baseUrl.replace(/^ws/, 'http')
  }

  /** GET /matches/{id} returns MatchMeta: lineups and formations. */
  private async loadMeta(h: SourceHandlers): Promise<void> {
    try {
      const res = await fetch(`${this.httpBase}/matches/${encodeURIComponent(this.opts.matchId)}`)
      if (!res.ok) throw new Error(`match lookup failed (${res.status})`)
      h.onMeta((await res.json()) as MatchMeta)
    } catch (err) {
      h.onStatus('error', err instanceof Error ? err.message : String(err))
    }
  }

  private url(): string {
    const p = this.opts.profile
    const q = new URLSearchParams({
      viewer: p.viewerId,
      persona: p.persona,
      lang: p.lang,
      speed: String(this.speed),
      t: String(Math.max(0, this.lastT)),
    })
    if (p.club) q.set('club', p.club)
    if (p.player) q.set('player', p.player)
    if (p.metric) q.set('metric', p.metric)
    return `${this.baseUrl}/ws/matches/${encodeURIComponent(this.opts.matchId)}?${q}`
  }

  private send(msg: Record<string, unknown>): void {
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(msg))
  }

  private open(): void {
    const h = this.handlers
    if (!h) return
    h.onStatus(this.attempt === 0 ? 'connecting' : 'reconnecting')
    const ws = new WebSocket(this.url())
    this.ws = ws
    ws.onopen = () => {
      this.attempt = 0
      if (this.paused) this.send({ op: 'pause' })
      h.onStatus('live')
    }
    ws.onmessage = (ev) => {
      let parsed: unknown
      try {
        parsed = JSON.parse(String(ev.data))
      } catch {
        return // a malformed message must not take the stream down
      }
      if (isWireMessage(parsed)) {
        if (parsed.type === 'frame') this.lastT = parsed.data.t_match
        h.onMessage(parsed)
      } else {
        const type = (parsed as { type?: unknown }).type
        if (type === 'end') {
          this.closedByUs = true
          h.onStatus('closed', 'full time')
        }
        // {"type": "error"} answers a malformed control message; the socket stays open.
      }
    }
    ws.onerror = () => h.onStatus('error', 'socket error')
    ws.onclose = () => {
      if (this.closedByUs) return
      const delay = Math.min(MAX_BACKOFF_MS, 500 * 2 ** this.attempt)
      this.attempt += 1
      h.onStatus('reconnecting', `retrying in ${Math.round(delay / 100) / 10}s`)
      this.timer = window.setTimeout(() => this.open(), delay)
    }
  }
}
