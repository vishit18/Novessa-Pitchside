import { useEffect, useRef, useState } from 'react'
import { sentenceCase } from '@/core/headline'
import { AppNav } from '@/components/AppNav'
import { Timeline } from '@/components/Timeline'
import { getKeyMoments } from '@/net/api'
import {
  defaultProfile,
  isRtl,
  LANGS,
  loadProfile,
  PERSONAS,
  type Lang,
  type Persona,
  type ViewerProfile,
} from '@/state/profile'
import type { Session } from '@/state/session'
import { SessionContext, useLiveSession, useSessionState } from '@/state/useSession'
import { BroadcastPane } from './BroadcastPane'

/** How much of each viewer's record to show under their pane. */
const TOLD = 4
/** Without a ?t=, start this long before the first goal so the difference shows straight away. */
const LEAD_IN_S = 40

/**
 * "Same match. Your story." Two viewers on the same match at the same second, each with their
 * own profile and socket. The pitch is the same on purpose: the broadcast around it is not.
 * Under each pane is what that viewer has been told so far, so the difference stays visible
 * between overlays. One timeline drives both.
 */
export function Split({ query }: { query: URLSearchParams }) {
  const matchId = query.get('match') ?? 'derby_01'
  const tParam = query.get('t')
  const baseT = Number(tParam ?? 0)
  const speed0 = Number(query.get('speed') ?? 1)
  const club = loadProfile()?.club ?? null

  const [left, setLeft] = useState(() => ({
    profile: defaultProfile({ persona: 'analyst', lang: 'en', club }),
    startAt: baseT,
  }))
  const [right, setRight] = useState(() => ({
    profile: defaultProfile({ persona: 'kids', lang: 'es', club }),
    startAt: baseT,
  }))
  const a = useLiveSession({ matchId, profile: left.profile, startAt: left.startAt, speed: speed0 })
  const b = useLiveSession({
    matchId,
    profile: right.profile,
    startAt: right.startAt,
    speed: speed0,
  })

  // No time in the link: jump both viewers to just before the first goal, once.
  const jumped = useRef(tParam !== null)
  useEffect(() => {
    if (jumped.current) return
    jumped.current = true
    getKeyMoments(matchId)
      .then((k) => {
        const goal = k.moments.find((m) => m.kind === 'goal')
        if (goal) for (const s of [a, b]) s.seek(Math.max(0, goal.t_match - LEAD_IN_S))
      })
      .catch(() => undefined)
  }, [matchId, a, b])

  // Changing a viewer opens a new socket; pick up where that viewer was.
  const change = (session: Session, set: typeof setLeft) => (patch: Partial<ViewerProfile>) =>
    set((cur) => ({
      profile: { ...cur.profile, ...patch },
      startAt: Math.max(0, session.buffers.latestT),
    }))

  return (
    <main className="flex min-h-dvh w-full flex-col gap-5 bg-ink px-4 pb-28 pt-4 sm:px-6">
      <AppNav match={matchId} />
      <header className="flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between lg:gap-10">
        <h1 className="font-display text-[40px] font-bold leading-none sm:text-[56px]">
          Same match. Your story.
        </h1>
        <p className="max-w-[70ch] text-[16px] leading-relaxed text-text/80">
          Both screens show the same match at the same second. Each is a different viewer’s
          broadcast: what it puts on screen, how it explains it, and in what language. Change either
          viewer and their broadcast changes; the football does not.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 lg:gap-8">
        <Column n={1} session={a} profile={left.profile} onChange={change(a, setLeft)} />
        <Column n={2} session={b} profile={right.profile} onChange={change(b, setRight)} />
      </div>

      <div className="plate-shadow sticky bottom-3 z-20 mx-auto w-full max-w-[1100px]">
        <div className="plate px-4 py-2.5" style={{ ['--cut' as string]: '10px' }}>
          <SessionContext.Provider value={a}>
            <Timeline linked={[b]} />
          </SessionContext.Provider>
        </div>
      </div>
    </main>
  )
}

function chip(on: boolean): string {
  return `h-9 min-w-9 border px-2.5 text-[15px] font-medium transition-colors ${
    on ? 'border-amber text-amber' : 'border-white/30 text-muted hover:text-text'
  }`
}

function Column({
  n,
  session,
  profile,
  onChange,
}: {
  n: number
  session: Session
  profile: ViewerProfile
  onChange: (patch: Partial<ViewerProfile>) => void
}) {
  const persona = PERSONAS.find((p) => p.id === profile.persona)
  const lang = LANGS.find((l) => l.id === profile.lang)?.label ?? profile.lang
  return (
    <section className="flex min-w-0 flex-col gap-3" aria-label={`Viewer ${n}`}>
      <div className="flex items-baseline justify-between gap-4">
        <h2 className="font-display text-[28px] font-semibold leading-none">
          Viewer {n}: {persona?.label ?? profile.persona}, {lang}
        </h2>
        <p className="text-[14px] text-muted max-sm:hidden">{persona?.hint}</p>
      </div>
      <div className="h-[44dvh] min-h-[280px] w-full overflow-hidden lg:h-[min(52dvh,560px)]">
        <BroadcastPane session={session} compact transport={false} />
      </div>
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2.5">
        <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Watching as">
          <span className="text-[13px] text-muted">Watching as</span>
          {PERSONAS.map((p) => (
            <button
              key={p.id}
              className={chip(p.id === profile.persona)}
              aria-pressed={p.id === profile.persona}
              onClick={() => onChange({ persona: p.id as Persona })}
            >
              {p.label}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-[13px] text-muted">
          Language
          <select
            className="h-9 border border-white/30 bg-ink px-2 text-[15px] font-medium text-text"
            value={profile.lang}
            onChange={(e) => onChange({ lang: e.target.value as Lang })}
          >
            {LANGS.map((l) => (
              <option key={l.id} value={l.id}>
                {l.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <SessionContext.Provider value={session}>
        <Told n={n} />
      </SessionContext.Provider>
    </section>
  )
}

/** The last few story cards this viewer has been shown, in their words and language. */
function Told({ n }: { n: number }) {
  const feed = useSessionState((s) => s.feed)
  const lang = useSessionState((s) => s.profile.lang)
  const items = feed.slice(0, TOLD)
  return (
    <div className="border-t border-hairline pt-3">
      <h3 className="text-[14px] text-muted">What viewer {n} has been told</h3>
      {items.length === 0 ? (
        <p className="mt-2 text-[15px] text-muted">Nothing yet. Story cards collect here.</p>
      ) : (
        <ol className="mt-2 flex flex-col gap-2.5" lang={lang} dir={isRtl(lang) ? 'rtl' : 'ltr'}>
          {items.map((it) => (
            <li key={it.id} className="grid grid-cols-[3.5rem_1fr] gap-x-3">
              <span className="num pt-0.5 text-[18px] leading-none text-amber" dir="ltr">
                {it.clock ?? ''}
              </span>
              <span className="min-w-0">
                <span className="block font-display text-[20px] font-semibold leading-tight">
                  {sentenceCase(it.headline, lang)}
                </span>
                <span className="line-clamp-2 block text-[15px] leading-snug text-text/80">
                  {it.body}
                </span>
              </span>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
