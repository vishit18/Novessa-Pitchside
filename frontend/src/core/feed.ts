import type { OverlayEnvelope } from '@/types/overlay'

/** One story card in the Companion feed: a moment the viewer has already been shown. */
export interface FeedItem {
  /** Stable across updates: the moment, or the message when there is no moment. */
  id: string
  showAt: number
  kind: OverlayEnvelope['kind']
  headline: string
  body: string
  team: string | null
  /** goal, chance, swing, milestone, info */
  tone: string
  card: 'yellow' | 'red' | null
  /** The score bug's clock when the gateway sent one, such as 60:38. */
  clock: string | null
  /** Spoken commentary for this moment, a path on the gateway. */
  audioUrl: string | null
  /** What the numbers behind the card were, for "why am I seeing this". */
  evidence: { metric: string; value: number }[]
  verified: boolean
  /** state_engine for the instant card, agent:analyst once the agent text has attached. */
  source: string
  /** goal, card, penalty, ... for insights; null for milestones and the state of play. */
  momentKind: string | null
  /** A goal for or against the viewer's club (docs/05 Persona filtering). */
  forYou: 'scored' | 'conceded' | null
  /** About the viewer's club, or their player. */
  favouriteClub: boolean
  yourPlayer: boolean
}

/** Overlays that read as a story beat. Tags, speed bursts and the like stay on the pitch. */
export function isStoryOverlay(o: OverlayEnvelope): boolean {
  return (
    o.slot === 'lower_third' &&
    (o.kind === 'insight' || o.kind === 'milestone' || o.kind === 'state_of_play')
  )
}

/** A state-of-play beat: the commentator filling the quiet, not a moment. */
export const isPulse = (item: FeedItem): boolean => item.kind === 'state_of_play'

const str = (v: unknown): string => (typeof v === 'string' ? v : '')

/**
 * Fold the overlay log into the feed at match time `t`, newest first.
 *
 * Only overlays whose show time has passed are included, so the feed can never show a viewer
 * something that has not been on their screen yet. An `update` (agent text) patches the earlier
 * card for the same moment; a `hide` does not remove a card, because the feed is a record.
 */
export function momentFeed(log: OverlayEnvelope[], t: number): FeedItem[] {
  const ordered = log
    .map((o, i) => ({ o, i }))
    .filter(({ o }) => o.show_at <= t && isStoryOverlay(o))
    .sort((a, b) => a.o.show_at - b.o.show_at || a.i - b.i)
    .map(({ o }) => o)

  const items = new Map<string, FeedItem>()
  for (const o of ordered) {
    if (o.op === 'hide' || o.op === 'clear_slot') continue
    const id = `${o.moment_id ?? o.msg_id}|${o.kind}`
    const prev = items.get(id)
    if (o.op === 'update' && !prev) continue
    const p = o.payload
    const card = p['card']
    items.set(id, {
      id,
      showAt: prev?.showAt ?? o.show_at,
      kind: o.kind,
      headline: str(p['headline']) || prev?.headline || '',
      body: str(p['body']) || prev?.body || '',
      team: str(p['team']) || prev?.team || null,
      tone: str(p['tone']) || prev?.tone || 'info',
      card: card === 'yellow' || card === 'red' ? card : (prev?.card ?? null),
      clock: str(p['clock']) || prev?.clock || null,
      audioUrl: str(p['audio_url']) || prev?.audioUrl || null,
      evidence: o.provenance.evidence.length ? o.provenance.evidence : (prev?.evidence ?? []),
      verified: o.provenance.verified,
      source: o.provenance.source,
      momentKind: str(p['moment_kind']) || prev?.momentKind || null,
      forYou:
        p['for_you'] === 'scored' || p['for_you'] === 'conceded'
          ? p['for_you']
          : (prev?.forYou ?? null),
      favouriteClub: p['favourite_club'] === true || (prev?.favouriteClub ?? false),
      yourPlayer: p['your_player'] === true || (prev?.yourPlayer ?? false),
    })
  }
  return [...items.values()].sort((a, b) => b.showAt - a.showAt)
}

/** A metric key as words: pressure_index becomes "pressure index". */
export function metricLabel(metric: string): string {
  return metric.replace(/_/g, ' ')
}
