/**
 * Maps the stream's match time onto a smooth render clock.
 *
 * Messages arrive in bursts (frames at 10 Hz, faster when replaying at 4x or 30x), but the
 * screen redraws at 60 fps. ClockSync estimates how fast match time is moving, advances the
 * render clock between messages, and pulls it gently back toward `latest - lead`.
 *
 * `lead` is how far behind the live edge this viewer sits: a small jitter buffer plus any
 * deliberate stream delay. Overlays and frames are keyed to match time, so a viewer 30 s behind
 * still sees every overlay on the same football moment as one at the live edge.
 */
export class ClockSync {
  private latest = 0
  private lastObsMs = 0
  /** Wall time of the last message of any kind, for spotting a stalled feed. */
  private lastSeenMs = 0
  private rate = 1
  private t = 0
  private lastNowMs = 0
  private started = false
  /** Seconds behind the live edge. */
  lead: number

  constructor(lead = 0.3) {
    this.lead = lead
  }

  /** Call for every message that carries a match time. */
  observe(tMatch: number, nowMs: number): void {
    this.lastSeenMs = nowMs
    if (!this.started) {
      this.started = true
      this.latest = tMatch
      this.lastObsMs = nowMs
      this.lastNowMs = nowMs
      this.t = tMatch - this.lead
      return
    }
    const dtWall = (nowMs - this.lastObsMs) / 1000
    if (tMatch > this.latest && dtWall >= 0.05) {
      const inst = (tMatch - this.latest) / dtWall
      this.rate = this.rate * 0.8 + Math.min(inst, 120) * 0.2
      this.lastObsMs = nowMs
    }
    if (tMatch > this.latest) this.latest = tMatch
  }

  /** Forget everything, e.g. after a seek backwards. */
  reset(): void {
    this.started = false
    this.rate = 1
  }

  /** Render time for this animation frame. */
  now(nowMs: number): number {
    if (!this.started) return 0
    const dt = Math.max(0, Math.min(0.25, (nowMs - this.lastNowMs) / 1000))
    this.lastNowMs = nowMs
    const stale = nowMs - this.lastObsMs > 400
    const rate = stale ? 0 : this.rate
    const target = this.latest - this.lead
    const err = target - this.t
    if (Math.abs(err) > Math.max(3, this.rate * 1.5)) {
      this.t = target
    } else {
      this.t += rate * dt + err * Math.min(1, 4 * dt)
    }
    return this.t
  }

  /** Milliseconds since the last message, or 0 before the first. */
  quietFor(nowMs: number): number {
    return this.started ? nowMs - this.lastSeenMs : 0
  }

  get liveEdge(): number {
    return this.latest
  }

  get estimatedRate(): number {
    return this.rate
  }
}
