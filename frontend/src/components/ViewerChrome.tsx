import { NavMenu } from '@/components/AppNav'
import { CommentaryToggle } from '@/components/CommentaryToggle'
import { CLUBS, PLAYERS } from '@/data/league'
import { navigate, withParams } from '@/router'
import type { StringKey } from '@/i18n/strings'
import { LANGS, METRICS } from '@/state/profile'
import { useSession, useSessionState, useT } from '@/state/useSession'
import { useWake } from '@/state/useWake'

/**
 * Top-right of the broadcast. The chip says who is watching and how, always. Commentary and the
 * menu (every other page) fade in when the pointer moves or focus lands, and out after three seconds.
 */
export function ViewerChrome() {
  const session = useSession()
  const t = useT()
  const profile = useSessionState((s) => s.profile)
  const { shown, wake } = useWake()
  const matchId = session.opts.matchId

  const persona = profile.metric
    ? (METRICS.find((m) => m.id === profile.metric)?.label ?? profile.metric)
    : t(`persona_${profile.persona}` as StringKey)
  const lang = LANGS.find((l) => l.id === profile.lang)?.label ?? profile.lang
  const who = profile.player
    ? PLAYERS[profile.player]?.name
    : profile.club
      ? CLUBS[profile.club]?.name
      : null

  return (
    <div className="flex flex-col items-end gap-2" onFocusCapture={wake}>
      <button
        className="plate-chip group flex items-center gap-3 bg-raised/90 py-2 pl-4 pr-3 text-start hover:bg-[#1d242d]"
        onClick={() => navigate(withParams('/start', { match: matchId }))}
        aria-label={`${persona}, ${lang}${who ? `, ${who}` : ''}. ${t('changeHow')}`}
      >
        <span className="flex flex-col">
          <span className="font-display text-[20px] font-semibold leading-none">{persona}</span>
          <span className="mt-1 text-[14px] leading-none text-text/80">
            {[lang, who].filter(Boolean).join(', ')}
          </span>
        </span>
        <svg viewBox="0 0 12 12" className="size-3 text-muted group-hover:text-text" aria-hidden>
          <path d="M2 4.5 6 8.5 10 4.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
        </svg>
      </button>
      <div
        className={`flex gap-1.5 transition-opacity duration-200 ${
          shown
            ? 'opacity-100'
            : 'pointer-events-none opacity-0 focus-within:pointer-events-auto focus-within:opacity-100'
        }`}
      >
        <button
          className="flex h-9 items-center gap-2 bg-amber px-3 text-[14px] font-semibold text-ink"
          onClick={() => session.store.getState().set({ askOpen: true })}
          aria-keyshortcuts="/"
        >
          {t('ask')}
          <kbd className="hidden border border-ink/30 px-1 text-[11px] font-medium sm:inline">
            /
          </kbd>
        </button>
        <CommentaryToggle />
        <NavMenu match={matchId} lang={profile.lang} />
      </div>
    </div>
  )
}
