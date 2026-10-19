import type { WireMessage } from '@/types/overlay'
import type { MatchMeta } from '@/types/schema'
import type { MatchSource, SourceHandlers, SourceOptions } from './source'

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
 * WS /ws/matches/{id}?viewer=...  Sends {"type": "frame"|"event"|"state"|"overlay", "data": ...}.
 * Reconnects with exponential backoff. Buffering and de-duplication happen downstream in
 * StreamBuffers, so a replay of recent messages after a reconnect is harmless.
 */
export class WebSocketSource implements MatchSource {
  readonly kind = 'ws' as const
  private ws: WebSocket | null = null
  private handlers: SourceHandlers | null = null
  private attempt = 0
  private timer: number | undefined
  private closedByUs = false

  constructor(
    private readonly baseUrl: string,
    private readonly opts: SourceOptions,
  ) {}

  connect(handlers: SourceHandlers): void {
    this.handlers = handlers
    this.closedByUs = false
    void this.loadMeta(handlers)
    this.open()
  }

  /** GET /matches/{id}: lineups and colours. Accepts either {meta: ...} or the meta itself. */
  private async loadMeta(h: SourceHandlers): Promise<void> {
    const http = this.baseUrl.replace(/^ws/, 'http')
    try {
      const res = await fetch(`${http}/matches/${encodeURIComponent(this.opts.matchId)}`)
      if (!res.ok) throw new Error(`match lookup failed (${res.status})`)
      const body = (await res.json()) as { meta?: MatchMeta } & MatchMeta
      h.onMeta(body.meta ?? body)
    } catch (err) {
      h.onStatus('error', err instanceof Error ? err.message : String(err))
    }
  }

  close(): void {
    this.closedByUs = true
    window.clearTimeout(this.timer)
    this.ws?.close()
    this.ws = null
  }

  private url(): string {
    const q = new URLSearchParams({ viewer: this.opts.viewer })
    return `${this.baseUrl}/ws/matches/${encodeURIComponent(this.opts.matchId)}?${q}`
  }

  private open(): void {
    const h = this.handlers
    if (!h) return
    h.onStatus(this.attempt === 0 ? 'connecting' : 'reconnecting')
    const ws = new WebSocket(this.url())
    this.ws = ws
    ws.onopen = () => {
      this.attempt = 0
      h.onStatus('live')
    }
    ws.onmessage = (ev) => {
      try {
        const parsed: unknown = JSON.parse(String(ev.data))
        if (isWireMessage(parsed)) h.onMessage(parsed)
      } catch {
        // A malformed message must not take the stream down.
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
