import { useAudioBlocked } from '@/state/useCommentary'
import { useSessionState, useT } from '@/state/useSession'

/**
 * Shown when the browser has held back a spoken line because the viewer has not tapped the page
 * yet. Any tap or key press plays the waiting line, so the button itself needs no handler.
 */
export function SoundPrompt() {
  const blocked = useAudioBlocked()
  const t = useT()
  if (!blocked) return null
  return (
    <button
      type="button"
      className="plate-chip pointer-events-auto self-start bg-amber px-4 py-2.5 text-[15px] font-semibold text-ink"
    >
      {t('tapForSound')}
    </button>
  )
}

/**
 * The last line of commentary, kept on screen for audio-described viewers. The lower third only
 * shows for a few seconds around a moment; this fills the gap so the words never disappear while
 * the voice is still the main way the match is told. Hidden while a lower third or the goal band
 * is up, so the same words are never on screen twice. Screen readers already get the lower third,
 * so this is left out of the accessibility tree.
 */
export function CaptionBar() {
  const persona = useSessionState((s) => s.profile.persona)
  const newest = useSessionState((s) => s.feed[0])
  const lowerThird = useSessionState((s) => s.active.some((o) => o.slot === 'lower_third'))
  const goalBand = useSessionState((s) => s.goalBand)
  if (persona !== 'accessibility' || !newest || lowerThird || goalBand) return null
  return (
    <p
      aria-hidden
      className="plate-chip pointer-events-none w-[min(100%,640px)] bg-raised/90 px-4 py-2.5 text-[16px] leading-snug text-text"
    >
      {newest.clock && <span className="me-2 font-semibold tabular-nums">{newest.clock}</span>}
      <span className="font-semibold">{newest.headline}</span>
      {newest.body && <span className="text-text/85">{` ${newest.body}`}</span>}
    </p>
  )
}
