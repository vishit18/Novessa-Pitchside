import { insertSorted, lastAtOrBefore, trimBefore } from '@/core/timeline'
import { pruneOverlays } from '@/core/overlays'
import type { OverlayEnvelope, PlayerStatsMessage, WireMessage } from '@/types/overlay'
import type { MatchEvent, StateSnapshot, TrackingFrame } from '@/types/schema'

/**
 * High-frequency stream buffers, kept outside React state so the 60 fps loop never triggers
 * a re-render. Everything is keyed to match time. Duplicates (after a reconnect replay) are
 * dropped by id.
 */
export class StreamBuffers {
  frames: TrackingFrame[] = []
  events: MatchEvent[] = []
  states: StateSnapshot[] = []
  playerStats: PlayerStatsMessage[] = []
  overlays: OverlayEnvelope[] = []
  private seenFrames = new Set<number>()
  private seenEvents = new Set<string>()
  private seenOverlays = new Set<string>()
  /** Newest match time seen on any message. */
  latestT = 0

  ingest(msg: WireMessage): void {
    switch (msg.type) {
      case 'frame': {
        const key = Math.round(msg.data.t_match * 100)
        if (this.seenFrames.has(key)) return
        this.seenFrames.add(key)
        insertSorted(this.frames, msg.data)
        this.latestT = Math.max(this.latestT, msg.data.t_match)
        break
      }
      case 'event':
        if (this.seenEvents.has(msg.data.event_id)) return
        this.seenEvents.add(msg.data.event_id)
        insertSorted(this.events, msg.data)
        break
      case 'state':
        insertSorted(this.states, msg.data)
        break
      case 'player_stats':
        insertSorted(this.playerStats, msg.data)
        break
      case 'overlay': {
        const o = msg.data
        // update/hide messages reuse nothing special; msg_id is unique per message
        if (this.seenOverlays.has(o.msg_id)) return
        this.seenOverlays.add(o.msg_id)
        this.overlays.push(o)
        break
      }
    }
  }

  /** Free memory behind the render clock. Keeps a small tail for interpolation. */
  trim(renderT: number): void {
    trimBefore(this.frames, renderT - 2)
    trimBefore(this.states, renderT - 2)
    trimBefore(this.playerStats, renderT - 2)
    const keepEvents = lastAtOrBefore(this.events, renderT - 60)
    if (keepEvents > 0) this.events.splice(0, keepEvents)
    this.overlays = pruneOverlays(this.overlays, renderT)
    if (this.seenFrames.size > 5000) this.seenFrames.clear()
  }

  /** Latest state snapshot at or before `t`. */
  stateAt(t: number): StateSnapshot | null {
    const i = lastAtOrBefore(this.states, t)
    return i >= 0 ? this.states[i]! : null
  }

  /** Latest player stats at or before `t`. */
  playerStatsAt(t: number): PlayerStatsMessage | null {
    const i = lastAtOrBefore(this.playerStats, t)
    return i >= 0 ? this.playerStats[i]! : null
  }

  clear(): void {
    this.playerStats = []
    this.frames = []
    this.events = []
    this.states = []
    this.overlays = []
    this.seenFrames.clear()
    this.seenEvents.clear()
    this.seenOverlays.clear()
    this.latestT = 0
  }
}
