import { ClockSync } from '@/core/clock'
import { activeOverlays } from '@/core/overlays'
import { MockSource } from '@/mock/mockSource'
import { WebSocketSource } from '@/net/wsSource'
import type { MatchSource, SourceOptions } from '@/net/source'
import type { WireMessage } from '@/types/overlay'
import { StreamBuffers } from './buffers'
import { useStore } from './store'

/** Jitter buffer on top of any deliberate delay, in match seconds. */
const BASE_LEAD_S = 0.3

export const buffers = new StreamBuffers()
export const clock = new ClockSync(BASE_LEAD_S)

let source: MatchSource | null = null
let lastActiveSig = ''
let lastSnapshotT = -1

/**
 * The one place that picks a transport. Swap MockSource for the real gateway here and nowhere
 * else: set VITE_GATEWAY_URL (e.g. ws://localhost:8000) or pass ?source=ws.
 */
export function createSource(opts: SourceOptions): MatchSource {
  const params = new URLSearchParams(window.location.search)
  const gateway = import.meta.env.VITE_GATEWAY_URL as string | undefined
  const want = params.get('source') ?? (gateway ? 'ws' : 'mock')
  if (want === 'ws') {
    return new WebSocketSource(gateway ?? 'ws://localhost:8000', opts)
  }
  return new MockSource(opts)
}

function onMessage(msg: WireMessage): void {
  const now = performance.now()
  if (msg.type === 'frame') {
    // A seek backwards: start the buffers over.
    if (msg.data.t_match < buffers.latestT - 2) {
      buffers.clear()
      clock.reset()
      lastSnapshotT = -1
    }
    clock.observe(msg.data.t_match, now)
  }
  buffers.ingest(msg)
}

export function startMatch(opts: SourceOptions): () => void {
  stopMatch()
  buffers.clear()
  clock.reset()
  source = createSource(opts)
  useStore.getState().set({
    sourceKind: source.kind,
    controls: source.controls ?? null,
    status: 'connecting',
    meta: null,
    snapshot: null,
    active: [],
    speed: opts.speed ?? 4,
    paused: false,
  })
  source.connect({
    onMessage,
    onStatus: (status, detail) => useStore.getState().set({ status, statusDetail: detail ?? null }),
    onMeta: (meta) => useStore.getState().set({ meta }),
  })
  return stopMatch
}

export function stopMatch(): void {
  source?.close()
  source = null
}

export function setDelay(seconds: number): void {
  clock.lead = BASE_LEAD_S + seconds
  useStore.getState().set({ delayS: seconds })
}

/**
 * Advance the render clock and publish anything the DOM layers need. Called every animation
 * frame. Returns the render time so the canvas can interpolate to it.
 */
export function tick(nowMs: number): number {
  const t = clock.now(nowMs)
  buffers.trim(t)

  const active = activeOverlays(buffers.overlays, t)
  const sig = active.map((o) => `${o.msg_id}:${JSON.stringify(o.payload).length}`).join('|')
  const snap = buffers.stateAt(t)
  const patch: Parameters<ReturnType<typeof useStore.getState>['set']>[0] = {}
  if (sig !== lastActiveSig) {
    lastActiveSig = sig
    patch.active = active
  }
  if (snap && snap.t_match !== lastSnapshotT) {
    lastSnapshotT = snap.t_match
    patch.snapshot = snap
  }
  if (patch.active || patch.snapshot) useStore.getState().set(patch)
  return t
}
