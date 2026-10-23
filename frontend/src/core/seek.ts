import type { WireMessage } from '@/types/overlay'

/** A frame this far from the seek target cannot belong to the stream the seek started. */
export const SEEK_FRAME_WINDOW_S = 15
/** The gateway answers a seek with the latest state at or before the target, never after it. */
const STATE_SLACK_S = 1

/**
 * True for a message that is left over from the stream a seek replaced.
 *
 * The gateway restarts the stream at the target and sends state, stats and overlays first and
 * the first frame last. Messages already on the wire from the old stream can land in between;
 * a frame from the old position makes the later, correct frame look like a seek backwards, and
 * the buffers get cleared just after the new state arrived. While paused, no new state follows,
 * so the clock stays on the old time. Dropping the leftovers until the first frame near the
 * target arrives avoids that.
 */
export function leftOverFromBeforeSeek(msg: WireMessage, target: number): boolean {
  switch (msg.type) {
    case 'frame':
      return Math.abs(msg.data.t_match - target) > SEEK_FRAME_WINDOW_S
    case 'state':
    case 'player_stats':
      return msg.data.t_match > target + STATE_SLACK_S
    default:
      return false
  }
}
