import { createStore, type StoreApi } from 'zustand/vanilla'
import type { FeedItem } from '@/core/feed'
import type { ConnectionStatus, PlaybackControls } from '@/net/source'
import type { OverlayEnvelope, PlayerStatsMessage } from '@/types/overlay'
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
  playerStats: PlayerStatsMessage | null
  /** Live speed of the followed player, straight from the latest frame. */
  focusSpeed: number | null
  /** Overlays to draw right now, already resolved per slot. */
  active: OverlayEnvelope[]
  /** Story cards this viewer has already been shown, newest first. The Companion's feed. */
  feed: FeedItem[]
  /** Seconds this viewer sits behind the live edge. */
  delayS: number
  speed: number
  paused: boolean
  /** Render time in match seconds, a few times a second: for the timeline. */
  t: number
  /** Furthest match time this viewer has watched to. Markers past it would be spoilers. */
  seenUpTo: number
  /** Ask the Analyst panel open on this viewer's screen. */
  askOpen: boolean
  /** Connected and playing, but no frames for a few seconds. */
  stalled: boolean
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
    playerStats: null,
    focusSpeed: null,
    active: [],
    feed: [],
    delayS: 0,
    speed: 4,
    paused: false,
    t: 0,
    seenUpTo: 0,
    askOpen: false,
    stalled: false,
    controls: null,
    set: (patch) => set(patch),
  }))
}
