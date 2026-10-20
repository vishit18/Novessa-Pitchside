import { useEffect, useMemo, useRef, useState } from 'react'
import { FeedCard } from '@/components/companion/FeedCard'
import { CatchUpSheet } from '@/components/companion/CatchUpSheet'
import { ScoreBug, StatusPill } from '@/components/Hud'
import { GATEWAY_HTTP } from '@/net/api'
import { navigate, withParams } from '@/router'
import { defaultProfile, isRtl, loadProfile } from '@/state/profile'
import type { Session } from '@/state/session'
import {
  SessionContext,
  useLiveSession,
  useSession,
  useSessionState,
  useT,
} from '@/state/useSession'

/**
 * The second-screen view for a phone. One column: the score on top, a feed of the moments this
 * viewer has already been shown, and the two things a thumb needs at the bottom: catch up, and
 * commentary on or off. Nothing here reveals anything the viewer's own clock has not reached.
 */
export function Companion({ query }: { query: URLSearchParams }) {
  const matchId = query.get('match') ?? 'derby_01'
  const profile = useMemo(() => loadProfile() ?? defaultProfile({ persona: 'casual' }), [])
  const session = useLiveSession({
    matchId,
    profile,
    startAt: Number(query.get('t') ?? 0),
    speed: Number(query.get('speed') ?? 1),
  })
  useTicker(session)

  return (
    <SessionContext.Provider value={session}>
      <CompanionBody matchId={matchId} />
    </SessionContext.Provider>
  )
}

/** No pitch is drawn here, so nothing else advances the render clock: do it a few times a second. */
function useTicker(session: Session): void {
  useEffect(() => {
    const id = window.setInterval(() => session.tick(performance.now()), 200)
    return () => window.clearInterval(id)
  }, [session])
}

function CompanionBody({ matchId }: { matchId: string }) {
  const session = useSession()
  const lang = useSessionState((s) => s.profile.lang)
  const feed = useSessionState((s) => s.feed)
  const status = useSessionState((s) => s.status)
  const t = useT()
  const [commentary, setCommentary] = useState(false)
  const [sheetOpen, setSheetOpen] = useState(false)
  const [open, setOpen] = useState<string | null>(null)
  const player = useAudio()

  // With commentary on, speak each new card once, as it arrives.
  const spoken = useRef(new Set<string>())
  const newest = feed[0]
  useEffect(() => {
    if (!commentary || !newest?.audioUrl || spoken.current.has(newest.id)) return
    spoken.current.add(newest.id)
    player.play(`${GATEWAY_HTTP}${newest.audioUrl}`)
  }, [commentary, newest, player])

  const toggleCommentary = () => {
    if (commentary) player.stop()
    setCommentary(!commentary)
  }

  return (
    <main
      className="stage-bg mx-auto flex min-h-dvh w-full max-w-[560px] flex-col"
      lang={lang}
      dir={isRtl(lang) ? 'rtl' : 'ltr'}
    >
      <h1 className="sr-only">Novessa Pitchside companion</h1>
      <header className="sticky top-0 z-10 flex items-start justify-between gap-3 bg-ink/90 px-4 pb-3 pt-3 backdrop-blur-sm">
        <ScoreBug showMatchLine={false} />
        <div className="flex flex-col items-end gap-1">
          <StatusPill />
          <button
            className="inline-flex min-h-11 items-center px-1 text-[14px] text-muted underline decoration-white/25 underline-offset-4 hover:text-text"
            onClick={() => navigate(withParams('/', { match: matchId }))}
          >
            Change
          </button>
        </div>
      </header>

      <section aria-labelledby="feed-h" className="flex-1 px-4 pb-32 pt-2">
        <h2 id="feed-h" className="font-display text-[26px] font-semibold leading-none">
          {t('feedTitle')}
        </h2>
        {feed.length === 0 ? (
          <p className="mt-4 text-[15px] leading-relaxed text-muted">
            {status === 'live' ? t('feedEmpty') : t('waiting')}
          </p>
        ) : (
          <ol className="mt-4 flex flex-col gap-3">
            {feed.map((item) => (
              <li key={item.id}>
                <FeedCard
                  item={item}
                  open={open === item.id}
                  onToggle={() => setOpen(open === item.id ? null : item.id)}
                  onListen={() => item.audioUrl && player.play(`${GATEWAY_HTTP}${item.audioUrl}`)}
                />
              </li>
            ))}
          </ol>
        )}
      </section>

      <div className="fixed inset-x-0 bottom-0 z-10 mx-auto flex w-full max-w-[560px] items-center gap-3 bg-ink/95 px-4 pb-[max(1rem,env(safe-area-inset-bottom))] pt-3 backdrop-blur-sm">
        <button
          className="h-12 flex-1 bg-amber px-4 text-[16px] font-semibold text-ink"
          onClick={() => setSheetOpen(true)}
        >
          {t('missed')}
        </button>
        <button
          className="h-12 border border-white/35 px-4 text-[15px] text-text aria-pressed:border-amber aria-pressed:text-amber"
          aria-pressed={commentary}
          onClick={toggleCommentary}
        >
          {t(commentary ? 'commentaryOn' : 'commentaryOff')}
        </button>
      </div>

      <CatchUpSheet
        open={sheetOpen}
        matchId={matchId}
        session={session}
        onClose={() => setSheetOpen(false)}
      />
    </main>
  )
}

/** One audio element at a time: starting a line stops the one before it. */
function useAudio() {
  const el = useRef<HTMLAudioElement | null>(null)
  return useMemo(
    () => ({
      play(url: string) {
        el.current?.pause()
        const a = new Audio(url)
        el.current = a
        // Browsers refuse audio until the viewer has tapped something; the toggle is that tap.
        void a.play().catch(() => undefined)
      },
      stop() {
        el.current?.pause()
        el.current = null
      },
    }),
    [],
  )
}
