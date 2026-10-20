import type { StoreApi } from 'zustand/vanilla'
import { ClockSync } from '@/core/clock'
import { activeOverlays } from '@/core/overlays'
import { GATEWAY_WS } from '@/net/api'
import { WebSocketSource } from '@/net/wsSource'
import type { MatchSource, SourceOptions } from '@/net/source'
import type { WireMessage } from '@/types/overlay'
import { StreamBuffers } from './buffers'
import { createUIStore, type UIState } from './store'

/** Jitter buffer on top of any deliberate delay, in match seconds. */
const BASE_LEAD_S = 0.3

/** The one place that picks a transport. */
export function createSource(opts: SourceOptions): MatchSource {
  return new WebSocketSource(GATEWAY_WS, opts)
}

/**
 * One viewer watching one match: a transport, stream buffers, a render clock and a UI store.
 * The broadcast view runs one; the split view runs two side by side on the same match.
 */
export class Session {
  readonly buffers = new StreamBuffers()
  readonly clock = new ClockSync(BASE_LEAD_S)
  readonly store: StoreApi<UIState>
  private source: MatchSource | null = null
  private lastActiveSig = ''
  private lastSnapshotT = -1
  private lastStatsT = -1
  private lastSpeedMs = 0

  constructor(readonly opts: SourceOptions) {
    this.store = createUIStore(opts.profile)
  }

  start(): void {
    this.stop()
    this.buffers.clear()
    this.clock.reset()
    this.lastActiveSig = ''
    this.lastSnapshotT = -1
    this.lastStatsT = -1
    const source = createSource(this.opts)
    this.source = source
    this.store.getState().set({
      controls: source.controls ?? null,
      status: 'connecting',
      statusDetail: null,
      meta: null,
      snapshot: null,
      playerStats: null,
      focusSpeed: null,
      active: [],
      speed: this.opts.speed ?? 4,
      paused: false,
    })
    source.connect({
      onMessage: (m) => this.onMessage(m),
      onStatus: (status, detail) =>
        this.store.getState().set({ status, statusDetail: detail ?? null }),
      onMeta: (meta) => this.store.getState().set({ meta }),
    })
  }

  stop(): void {
    this.source?.close()
    this.source = null
  }

  setDelay(seconds: number): void {
    this.clock.lead = BASE_LEAD_S + seconds
    this.store.getState().set({ delayS: seconds })
  }

  setSpeed(speed: number): void {
    this.source?.controls?.setSpeed(speed)
    this.store.getState().set({ speed })
  }

  setPaused(paused: boolean): void {
    this.source?.controls?.setPaused(paused)
    this.store.getState().set({ paused })
  }

  private onMessage(msg: WireMessage): void {
    if (msg.type === 'frame') {
      // A seek backwards: start the buffers over.
      if (msg.data.t_match < this.buffers.latestT - 2) {
        this.buffers.clear()
        this.clock.reset()
        this.lastSnapshotT = -1
      }
      this.clock.observe(msg.data.t_match, performance.now())
    }
    this.buffers.ingest(msg)
  }

  /**
   * Advance the render clock and publish anything the DOM layers need. Called every animation
   * frame. Returns the render time so the canvas can interpolate to it.
   */
  tick(nowMs: number): number {
    const t = this.clock.now(nowMs)
    this.buffers.trim(t)
    const active = activeOverlays(this.buffers.overlays, t)
    const sig = active.map((o) => `${o.msg_id}:${JSON.stringify(o.payload)}`).join('|')
    const snap = this.buffers.stateAt(t)
    const stats = this.buffers.playerStatsAt(t)
    const patch: Partial<UIState> = {}
    if (sig !== this.lastActiveSig) {
      this.lastActiveSig = sig
      patch.active = active
    }
    if (snap && snap.t_match !== this.lastSnapshotT) {
      this.lastSnapshotT = snap.t_match
      patch.snapshot = snap
    }
    if (stats && stats.t_match !== this.lastStatsT) {
      this.lastStatsT = stats.t_match
      patch.playerStats = stats
    }
    if (patch.active || patch.snapshot || patch.playerStats) this.store.getState().set(patch)
    return t
  }

  /** Publish the followed player's live speed, a few times a second rather than every frame. */
  reportFocusSpeed(kmh: number | null, nowMs: number): void {
    if (nowMs - this.lastSpeedMs < 250) return
    this.lastSpeedMs = nowMs
    this.store.getState().set({ focusSpeed: kmh })
  }
}
