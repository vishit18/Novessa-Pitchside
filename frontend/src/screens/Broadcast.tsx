import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AppNav } from '@/components/AppNav'
import { CommentaryToggle } from '@/components/CommentaryToggle'
import { PlayerCard } from '@/components/PlayerCard'
import { Timeline } from '@/components/Timeline'
import { ViewerChrome } from '@/components/ViewerChrome'
import { ForYou } from '@/components/watch/ForYou'
import { HeadToHead } from '@/components/watch/HeadToHead'
import { MatchPulse } from '@/components/watch/MatchPulse'
import { StoryFeed } from '@/components/watch/StoryFeed'
import { WatchingAsChip, WatchingAsSheet } from '@/components/watch/WatchingAs'
import { CLUBS } from '@/data/league'
import {
  defaultProfile,
  isRtl,
  loadProfile,
  saveProfile,
  type ViewerProfile,
} from '@/state/profile'
import type { Session } from '@/state/session'
import { SessionContext, useLiveSession, useSessionState, useT } from '@/state/useSession'
import { BroadcastPane } from './BroadcastPane'

/** Room the page takes around the monitor at full height: nav, fixture bar, timeline, gaps. */
const CHROME_PX = 228

/**
 * The match centre. The broadcast sits in its monitor on the white page like every other screen,
 * with the timeline under it; beside it, what this viewer's match is about: their side or player,
 * who is on top and how it feels, the numbers they care about, and the story so far. Everything
 * personal is changed in place from "Watching as". Full screen (or ?view=clean) is the bare
 * broadcast, for a TV or a capture.
 */
export function Broadcast({ query }: { query: URLSearchParams }) {
  const matchId = query.get('match') ?? 'derby_01'
  const playerParam = query.get('player')
  const clean = query.get('view') === 'clean'
  const [view, setView] = useState(() => {
    const p = loadProfile() ?? defaultProfile({ persona: 'casual' })
    return {
      profile: playerParam ? { ...p, player: playerParam } : p,
      startAt: Number(query.get('t') ?? 0),
      speed: Number(query.get('speed') ?? 1),
    }
  })
  const session = useLiveSession({ matchId, ...view })
  const [sheet, setSheet] = useState(false)

  // A new pick reconnects at the same second and speed, so the change is the only thing that moves.
  const change = useCallback(
    (patch: Partial<ViewerProfile>) =>
      setView((cur) => {
        const profile = { ...cur.profile, ...patch }
        saveProfile(profile)
        const ui = session.store.getState()
        return { profile, startAt: Math.max(0, session.buffers.latestT), speed: ui.speed }
      }),
    [session],
  )

  if (clean) {
    return (
      <main className="h-dvh w-full">
        <h1 className="sr-only">Novessa Pitchside broadcast view</h1>
        <BroadcastPane session={session} corner={<ViewerChrome />} focus={!!view.profile.player} />
      </main>
    )
  }

  return (
    <SessionContext.Provider value={session}>
      <MatchCentre
        session={session}
        matchId={matchId}
        openSheet={() => setSheet(true)}
        sheetOpen={sheet}
      />
      <WatchingAsSheet open={sheet} onClose={() => setSheet(false)} onChange={change} />
    </SessionContext.Provider>
  )
}

function MatchCentre({
  session,
  matchId,
  openSheet,
  sheetOpen,
}: {
  session: Session
  matchId: string
  openSheet: () => void
  sheetOpen: boolean
}) {
  const t = useT()
  const lang = useSessionState((s) => s.profile.lang)
  const player = useSessionState((s) => s.profile.player)
  const monitor = useRef<HTMLDivElement>(null)
  const full = useFullscreen(monitor)
  const small = useNarrow()

  return (
    <main
      className="flex min-h-dvh w-full flex-col gap-4 bg-ink px-4 pb-4 pt-4 sm:px-6"
      lang={lang}
      dir={isRtl(lang) ? 'rtl' : 'ltr'}
    >
      <AppNav match={matchId} lang={lang} />
      <h1 className="sr-only">{t('navWatch')}</h1>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(360px,420px)]">
        <section className="flex min-w-0 flex-col gap-3">
          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
            <Fixture />
            <div className="flex flex-wrap items-center gap-2">
              <WatchingAsChip onOpen={openSheet} open={sheetOpen} />
              <button
                className="h-11 bg-amber px-4 text-[15px] font-semibold text-ink hover:opacity-90"
                onClick={() => session.store.getState().set({ askOpen: true })}
                aria-keyshortcuts="/"
              >
                {t('ask')}
              </button>
              <div className="[&>button]:h-11 [&>button]:border-text [&>button]:text-text">
                <CommentaryToggle />
              </div>
              <button
                className="h-11 border border-text px-3 text-[15px] hover:border-amber hover:text-amber"
                onClick={full.enter}
              >
                {t('fullscreen')}
              </button>
            </div>
          </div>

          <div
            ref={monitor}
            className={`mx-auto w-full overflow-hidden bg-[#101418] ${
              small && !full.on ? 'aspect-[4/5]' : 'aspect-video'
            }`}
            style={
              full.on || small
                ? undefined
                : { maxWidth: `calc((100dvh - ${CHROME_PX}px) * 16 / 9)` }
            }
          >
            <BroadcastPane
              session={session}
              transport={full.on}
              framed={!full.on}
              compact={small && !full.on}
              ask
              focus={!!player}
              corner={
                full.on ? <ViewerChrome onChoose={() => full.exit().then(openSheet)} /> : undefined
              }
            />
          </div>

          <div
            className="plate-shadow mx-auto w-full"
            style={{ maxWidth: `calc((100dvh - ${CHROME_PX}px) * 16 / 9)` }}
          >
            <div className="plate plate-open px-4 py-2.5" style={{ ['--cut' as string]: '10px' }}>
              <Timeline />
            </div>
          </div>
        </section>

        <aside className="relative min-h-[520px] lg:min-h-0">
          <div className="flex flex-col gap-5 lg:absolute lg:inset-0">
            {player ? <PlayerCard /> : <ForYou onPick={openSheet} />}
            <MatchPulse />
            <HeadToHead />
            <StoryFeed />
          </div>
        </aside>
      </div>
    </main>
  )
}

/** Club names and kit chips for the match being watched, as a heading. */
function Fixture() {
  const meta = useSessionState((s) => s.meta)
  const t = useT()
  if (!meta) return <div className="h-11" />
  const side = (code: string) => (
    <span className="flex items-center gap-2">
      <span
        className="h-6 w-[6px]"
        style={{ background: CLUBS[code]?.primary_color }}
        aria-hidden
      />
      <span className="font-display text-[28px] font-bold leading-none sm:text-[32px]">
        {CLUBS[code]?.name ?? code}
      </span>
    </span>
  )
  return (
    <div className="min-w-0">
      <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
        {side(meta.home.code)}
        <span className="text-[16px] text-muted">v</span>
        {side(meta.away.code)}
      </p>
      <p className="mt-1 text-[13px] text-muted">
        {t('matchLine', { competition: meta.competition, n: meta.matchday, venue: meta.venue })}
      </p>
    </div>
  )
}

/** True below desktop width, where the monitor is small and the graphics should be too. */
function useNarrow(): boolean {
  const query = '(max-width: 1023px)'
  const [narrow, setNarrow] = useState(() => window.matchMedia(query).matches)
  useEffect(() => {
    const mq = window.matchMedia(query)
    const on = () => setNarrow(mq.matches)
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [])
  return narrow
}

/** The monitor goes full screen on its own, so the bare broadcast fills a TV. */
function useFullscreen(ref: React.RefObject<HTMLElement | null>) {
  const [on, setOn] = useState(false)
  useEffect(() => {
    const sync = () => setOn(document.fullscreenElement === ref.current)
    document.addEventListener('fullscreenchange', sync)
    return () => document.removeEventListener('fullscreenchange', sync)
  }, [ref])
  return useMemo(
    () => ({
      on,
      enter: () => void ref.current?.requestFullscreen?.().catch(() => undefined),
      exit: () =>
        document.fullscreenElement
          ? document.exitFullscreen().catch(() => undefined)
          : Promise.resolve(),
    }),
    [on, ref],
  )
}
