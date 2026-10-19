import { createStore, type StoreApi } from 'zustand/vanilla'
import type { ConnectionStatus, PlaybackControls } from '@/net/source'
import type { OverlayEnvelope } from '@/types/overlay'
import type { MatchMeta, StateSnapshot } from '@/types/schema'
import type { ViewerProfile } from './profile'

/**
 * Low-frequency UI state for one viewer session. Per-frame data lives in StreamBuffers and is
 * drawn imperatively. Each session gets its own store, so the split view can run two viewers.
 */
export interface UIState {
  profile: ViewerProfile
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
  controls: PlaybackControls | null
  set: (patch: Partial<Omit<UIState, 'set'>>) => void
}

export function createUIStore(profile: ViewerProfile): StoreApi<UIState> {
  return createStore<UIState>((set) => ({
    profile,
    meta: null,
    status: 'connecting',
    statusDetail: null,
    snapshot: null,
    active: [],
    delayS: 0,
    speed: 4,
    paused: false,
    controls: null,
    set: (patch) => set(patch),
  }))
}
