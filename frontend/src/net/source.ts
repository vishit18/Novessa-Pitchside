import type { ViewerProfile } from '@/state/profile'
import type { WireMessage } from '@/types/overlay'
import type { MatchMeta } from '@/types/schema'

export type ConnectionStatus = 'connecting' | 'live' | 'reconnecting' | 'closed' | 'error'

export interface SourceHandlers {
  onMessage: (msg: WireMessage) => void
  onStatus: (status: ConnectionStatus, detail?: string) => void
  onMeta: (meta: MatchMeta) => void
}

/** Transport controls, sent to the gateway as {"op": ...} control messages. */
export interface PlaybackControls {
  setSpeed: (speed: number) => void
  setPaused: (paused: boolean) => void
  seek: (tMatch: number) => void
}

/**
 * Anything that produces the gateway's wire messages for one viewer. Today that is the
 * WebSocket; a recorded-file source for offline demos would implement the same interface.
 */
export interface MatchSource {
  controls?: PlaybackControls
  connect(handlers: SourceHandlers): void
  close(): void
}

export interface SourceOptions {
  matchId: string
  /** The gateway filters and words every overlay for this profile. */
  profile: ViewerProfile
  /** Mock only: start match time in seconds. */
  startAt?: number
  /** Mock only: replay speed multiplier. */
  speed?: number
  /** A backdrop or preview, not the viewer watching: do not count it as seen. */
  ambient?: boolean
  /** Live through the event bus (Event Hubs in Azure): no pause, seek or speed. */
  live?: boolean
}
