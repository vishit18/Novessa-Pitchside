import type { OverlayEnvelope, OverlaySlot } from '@/types/overlay'

/**
 * Slots that hold one thing at a time. Highest priority wins, ties go to the newest.
 * player_tag and pitch_annotation can stack.
 */
const SINGLE_SLOTS: ReadonlySet<OverlaySlot> = new Set([
  'lower_third',
  'top_bar',
  'side_panel',
  'fullscreen_card',
  'ticker',
])

/** Is this overlay on screen at match time `t`? */
export function isLive(o: OverlayEnvelope, t: number): boolean {
  return t >= o.show_at && t < o.show_at + o.duration_s
}

function anchorKey(o: OverlayEnvelope): string {
  if (!o.anchor) return '-'
  return o.anchor.type === 'player' ? o.anchor.id : `${o.anchor.x},${o.anchor.y}`
}

const identity = (o: OverlayEnvelope) => `${o.moment_id ?? o.msg_id}|${o.kind}|${anchorKey(o)}`

/**
 * Fold the op stream into the set of overlays to draw at match time `t`.
 *
 * Messages are replayed in (show_at, arrival) order, so a viewer on a delay sees the same
 * result as a viewer at the live edge, just later. `update` patches the payload of an earlier
 * message with the same moment_id + kind + anchor; `hide` ends one early; `clear_slot` ends
 * every overlay in the slot.
 */
export function activeOverlays(all: OverlayEnvelope[], t: number): OverlayEnvelope[] {
  const ordered = all
    .map((o, i) => ({ o, i }))
    .filter(({ o }) => o.show_at <= t)
    .sort((a, b) => a.o.show_at - b.o.show_at || a.i - b.i)
    .map(({ o }) => o)

  const live = new Map<string, OverlayEnvelope>()
  for (const o of ordered) {
    const id = identity(o)
    switch (o.op) {
      case 'show':
        live.set(id, o)
        break
      case 'update': {
        const prev = live.get(id)
        // An update may lengthen the card (agent text takes longer to read), never shorten it.
        live.set(
          id,
          prev
            ? {
                ...prev,
                duration_s: Math.max(prev.duration_s, o.duration_s),
                payload: { ...prev.payload, ...o.payload },
              }
            : o,
        )
        break
      }
      case 'hide':
        live.delete(id)
        break
      case 'clear_slot':
        for (const [k, v] of live) if (v.slot === o.slot) live.delete(k)
        break
    }
  }

  const stacking: OverlayEnvelope[] = []
  const bestBySlot = new Map<OverlaySlot, OverlayEnvelope>()
  for (const o of live.values()) {
    if (!isLive(o, t)) continue
    if (!SINGLE_SLOTS.has(o.slot)) {
      stacking.push(o)
      continue
    }
    const cur = bestBySlot.get(o.slot)
    if (
      !cur ||
      o.priority > cur.priority ||
      (o.priority === cur.priority && o.show_at >= cur.show_at)
    )
      bestBySlot.set(o.slot, o)
  }
  return [...stacking, ...bestBySlot.values()]
}

/** Drop messages that can no longer matter. The protocol says to drop anything past its duration. */
export function pruneOverlays(all: OverlayEnvelope[], t: number): OverlayEnvelope[] {
  return all.filter((o) => t < o.show_at + o.duration_s + 2)
}

/** 0..1 progress through the overlay's lifetime, for fade-out and progress bars. */
export function lifeFraction(o: OverlayEnvelope, t: number): number {
  return Math.min(1, Math.max(0, (t - o.show_at) / o.duration_s))
}

/** A goal card. The gateway marks it with moment_kind; tone is the older fallback. */
export function isGoal(o: OverlayEnvelope): boolean {
  return o.payload['moment_kind'] === 'goal' || o.payload['tone'] === 'goal'
}

/** How late an overlay is relative to the football it describes, in seconds. */
export function lateness(o: OverlayEnvelope): number {
  return Math.max(0, o.show_at - o.t_match)
}
