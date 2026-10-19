import { create } from 'zustand'
import type { ConnectionStatus, PlaybackControls } from '@/net/source'
import type { OverlayEnvelope } from '@/types/overlay'
import type { MatchMeta, StateSnapshot } from '@/types/schema'

/** Low-frequency UI state. Per-frame data lives in StreamBuffers and is drawn imperatively. */
interface UIState {
  meta: MatchMeta | null
  status: ConnectionStatus
  statusDetail: string | null
  snapshot: StateSnapshot | null
  /** Overlays to draw right now, already resolved per slot. */
  active: OverlayEnvelope[]
  /** Seconds this viewer sits behind the live edge. */
  delayS: number
  speed: number
  paused: boolean
  sourceKind: 'mock' | 'ws'
  controls: PlaybackControls | null
  set: (patch: Partial<Omit<UIState, 'set'>>) => void
}

export const useStore = create<UIState>((set) => ({
  meta: null,
  status: 'connecting',
  statusDetail: null,
  snapshot: null,
  active: [],
  delayS: 0,
  speed: 4,
  paused: false,
  sourceKind: 'mock',
  controls: null,
  set: (patch) => set(patch),
}))
