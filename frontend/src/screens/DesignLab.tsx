/*
 * Design lab: the same first-impression screen in five looks, one tab each. Every look runs the
 * same two live sessions and the same components (BroadcastPane, Timeline); only tokens, fonts,
 * spacing and entrance motion change. The looks themselves are described at the top of
 * ./lab/directions.ts and styled in ./lab/lab.css.
 */
import { motion, useReducedMotion, type Variants } from 'framer-motion'
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from 'react'
import { PitchPaletteContext } from '@/components/pitch/palette'
import { Timeline } from '@/components/Timeline'
import { sentenceCase } from '@/core/headline'
import { CLUBS } from '@/data/league'
import { getMomentText, listMatches, type MatchSummary } from '@/net/api'
import { navigate, withParams } from '@/router'
import { defaultProfile, isRtl, loadProfile } from '@/state/profile'
import type { Session } from '@/state/session'
import { SessionContext, useLiveSession, useSessionState } from '@/state/useSession'
import { BroadcastPane } from './BroadcastPane'
import { DIRECTIONS, type Direction, type DirectionId } from './lab/directions'
import './lab/lab.css'

const MATCH = 'derby_01'
/**
 * 26:51, just after Wragg's penalty at 26:47. Both viewers have already been told about the goal,
 * so the screen opens on two different explanations of it, with nothing spoiled.
 */
const START_T = 1611
const SEEN_MOMENT = 'mom-derby_01-0014'
const SEEN_CLOCK = '26:47'

export function DesignLab({ query }: { query: URLSearchParams }) {
  const initial = DIRECTIONS.find((d) => d.id === query.get('look')) ?? DIRECTIONS[0]!
  const [dir, setDir] = useState<Direction>(initial)
  const analyst = useMemo(() => defaultProfile({ persona: 'analyst', lang: 'en' }), [])
  const casual = useMemo(() => defaultProfile({ persona: 'casual', lang: 'es' }), [])
  const [startAt] = useState(() => Number(query.get('t') ?? START_T))
  const a = useLiveSession({ matchId: MATCH, profile: analyst, startAt, speed: 1 })
  const b = useLiveSession({ matchId: MATCH, profile: casual, startAt, speed: 1 })

  const pick = (id: DirectionId) => {
    const next = DIRECTIONS.find((d) => d.id === id)
    if (!next) return
    setDir(next)
    window.history.replaceState(null, '', withParams('/design-lab', { look: id }))
  }

  return (
    <div className="flex min-h-dvh flex-col">
      <LabBar current={dir.id} onPick={pick} />
      <PitchPaletteContext.Provider value={dir.pitch}>
        <div
          role="tabpanel"
          id="lab-panel"
          aria-labelledby={`lab-tab-${dir.id}`}
          className={`fl lab-${dir.id} flex-1`}
        >
          <FirstLook key={dir.id} dir={dir} a={a} b={b} />
        </div>
      </PitchPaletteContext.Provider>
    </div>
  )
}

/** The lab's own chrome: neutral on purpose, so it never flatters one look over another. */
function LabBar({ current, onPick }: { current: DirectionId; onPick: (id: DirectionId) => void }) {
  const refs = useRef<(HTMLButtonElement | null)[]>([])
  const onKey = (e: KeyboardEvent, i: number) => {
    const step = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0
    if (!step) return
    e.preventDefault()
    const n = (i + step + DIRECTIONS.length) % DIRECTIONS.length
    onPick(DIRECTIONS[n]!.id)
    refs.current[n]?.focus()
  }
  return (
    <div
      className="sticky top-0 z-40 flex items-center gap-4 overflow-x-auto border-b border-[#3a3a3a] bg-[#232323] px-4 font-[system-ui] text-[13px] text-[#d6d6d6]"
      style={{ fontFamily: 'system-ui, sans-serif' }}
    >
      <span className="shrink-0 py-2.5 text-[#9a9a9a]">Design lab</span>
      <div role="tablist" aria-label="Look" className="flex shrink-0">
        {DIRECTIONS.map((d, i) => {
          const on = d.id === current
          return (
            <button
              key={d.id}
              ref={(el) => {
                refs.current[i] = el
              }}
              role="tab"
              id={`lab-tab-${d.id}`}
              aria-selected={on}
              aria-controls="lab-panel"
              tabIndex={on ? 0 : -1}
              onClick={() => onPick(d.id)}
              onKeyDown={(e) => onKey(e, i)}
              className={`min-h-10 whitespace-nowrap px-3 ${on ? 'bg-[#3a3a3a] text-white' : 'hover:text-white'}`}
            >
              <span className="me-1.5 text-[#8a8a8a]">{i + 1}</span>
              {d.name}
            </button>
          )
        })}
      </div>
    </div>
  )
}

/** Entrance per look. All under 300ms; reduced motion skips them. */
const ENTER: Record<Direction['motion'], { item: Variants; stagger: number }> = {
  rise: {
    item: {
      hidden: { opacity: 0, y: 16 },
      shown: { opacity: 1, y: 0, transition: { duration: 0.22, ease: [0.23, 1, 0.32, 1] } },
    },
    stagger: 0.06,
  },
  drift: {
    item: {
      hidden: { opacity: 0, y: 12 },
      shown: { opacity: 1, y: 0, transition: { duration: 0.3, ease: [0.25, 1, 0.5, 1] } },
    },
    stagger: 0.08,
  },
  wipe: {
    item: {
      hidden: { clipPath: 'inset(0 100% 0 0)' },
      shown: {
        clipPath: 'inset(0 0% 0 0)',
        transition: { duration: 0.18, ease: [0.23, 1, 0.32, 1] },
      },
    },
    stagger: 0.05,
  },
  chalk: {
    item: {
      hidden: { opacity: 0 },
      shown: { opacity: 1, transition: { duration: 0.2, ease: 'linear' } },
    },
    stagger: 0.07,
  },
  plate: {
    item: {
      hidden: { clipPath: 'inset(-20px 100% -20px 0)' },
      shown: {
        clipPath: 'inset(-20px -20px -20px 0)',
        transition: { duration: 0.25, ease: [0.25, 1, 0.5, 1] },
      },
    },
    stagger: 0.06,
  },
}

const EnterContext = createContext<Variants>(ENTER.plate.item)

/** One piece of the screen that takes part in the look's entrance. */
function Item({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <motion.div variants={useContext(EnterContext)} className={className}>
      {children}
    </motion.div>
  )
}

/**
 * What a stranger lands on: the match already playing, two viewers on the same second, the
 * difference visible without reading. The match picker comes after.
 */
function FirstLook({ dir, a, b }: { dir: Direction; a: Session; b: Session }) {
  const reduce = useReducedMotion()
  const enter = ENTER[dir.motion]
  return (
    <EnterContext.Provider value={enter.item}>
      <motion.main
        initial={reduce ? false : 'hidden'}
        animate="shown"
        transition={{ staggerChildren: enter.stagger }}
        className="mx-auto flex w-full max-w-[1600px] flex-col pb-24"
        style={{ padding: '0 var(--fl-pad) 96px', gap: 'var(--fl-gap)' }}
      >
        <Item>
          <header className="flex min-h-14 items-center justify-between gap-4 pt-3">
            <span className="whitespace-nowrap font-display text-[22px] font-bold leading-none">
              Novessa <span className="text-muted">Pitchside</span>
            </span>
            <nav className="flex items-center gap-1 text-[15px]">
              <a
                href="/why"
                onClick={(e) => {
                  e.preventDefault()
                  navigate(withParams('/why'))
                }}
                className="flex min-h-11 items-center whitespace-nowrap px-3 text-muted hover:text-text"
              >
                Why it matters
              </a>
              <a
                href="#matches"
                className="flex min-h-11 items-center whitespace-nowrap px-3 text-muted hover:text-text max-sm:hidden"
              >
                Pick a match
              </a>
            </nav>
          </header>
        </Item>

        <Item className="fl-hero grid items-end gap-x-10 gap-y-3 lg:grid-cols-[minmax(0,1fr)_auto]">
          <div>
            <h1 className="fl-h1">Same moment. Two fans. Two broadcasts.</h1>
            <p className="mt-3 max-w-[56ch] text-[18px] leading-snug text-muted max-sm:hidden">
              Every viewer gets their own broadcast of the same live match. Built for broadcasters
              and streaming platforms.
            </p>
          </div>
          <WatchButton className="fl-cta-top justify-self-start" />
        </Item>

        <div className="relative grid grid-cols-1 lg:grid-cols-2" style={{ gap: 'var(--fl-gap)' }}>
          <Viewer side="a" session={a} who="Analyst" lang="English" />
          <Viewer side="b" session={b} who="Casual fan" lang="Español" />
          <SameSecond session={a} />
          {dir.id === 'tactics' && <ChalkMarks />}
        </div>

        {/* On phones the button waits until both fans have been seen. */}
        <Item className="fl-cta-bottom">
          <WatchButton />
        </Item>

        <Item>
          <div className="plate-shadow mx-auto w-full max-w-[1100px]">
            <div className="plate px-4 py-2.5" style={{ ['--cut' as string]: '10px' }}>
              <SessionContext.Provider value={a}>
                <Timeline linked={[b]} />
              </SessionContext.Provider>
            </div>
          </div>
        </Item>

        <Item>
          <MatchPicker />
        </Item>
      </motion.main>
    </EnterContext.Provider>
  )
}

function WatchButton({ className = '' }: { className?: string }) {
  return (
    <button
      className={`fl-cta ${className}`}
      onClick={() => navigate(withParams(loadProfile() ? '/watch' : '/start', { match: MATCH }))}
    >
      Watch your way
    </button>
  )
}

function Viewer({
  side,
  session,
  who,
  lang,
}: {
  side: 'a' | 'b'
  session: Session
  who: string
  lang: string
}) {
  return (
    <section
      className={`flex min-w-0 flex-col gap-3 ${side === 'a' ? 'order-1' : 'order-3'}`}
      aria-label={`${who}, ${lang}`}
      data-side={side}
    >
      <Item className={`fl-who-row flex ${side === 'b' ? 'lg:justify-end' : ''}`}>
        <span className="fl-who" data-side={side}>
          {side === 'a' ? <BarsIcon /> : <BubbleIcon />}
          <span>{who}</span>
          <span className="opacity-70">{lang}</span>
        </span>
      </Item>
      <Item className="fl-pane">
        <div className="fl-pane-box w-full overflow-hidden">
          <BroadcastPane session={session} compact transport={false} />
        </div>
      </Item>
      <Item>
        <SessionContext.Provider value={session}>
          <LatestTold />
        </SessionContext.Provider>
      </Item>
    </section>
  )
}

interface Told {
  clock: string
  headline: string
  body: string
}

/**
 * The verified explanation of the last moment this viewer saw, in their persona and language.
 * Overlays come and go in seconds; this stays, so the difference between the two viewers is on
 * screen at any instant. Starts on the goal just before START_T, which both have already seen.
 */
function LatestTold() {
  const item = useSessionState((s) => s.feed[0])
  const lang = useSessionState((s) => s.profile.lang)
  const persona = useSessionState((s) => s.profile.persona)
  const [told, setTold] = useState<Told | null>(null)
  const moment = item?.id.startsWith('mom-') ? item.id : SEEN_MOMENT
  const clock = item?.id.startsWith('mom-') ? (item.clock ?? '') : SEEN_CLOCK

  useEffect(() => {
    let live = true
    getMomentText(MATCH, moment, lang)
      .then((out) => {
        const v = out.variants[persona] ?? out.variants['casual'] ?? out.variants['analyst']
        if (live && v) setTold({ clock, headline: v.headline, body: v.body })
      })
      // Not verified yet, or the agents are off: keep the last explanation on screen.
      .catch(() => undefined)
    return () => {
      live = false
    }
  }, [moment, clock, lang, persona])

  if (!told)
    return <p className="text-[15px] text-muted sm:min-h-[88px]">Waiting for the next moment.</p>
  return (
    <div className="grid grid-cols-[3.5rem_1fr] gap-x-3 sm:min-h-[88px]" lang={lang}>
      <span className="num pt-0.5 text-[18px] leading-none text-amber" dir="ltr">
        {told.clock}
      </span>
      <span className="min-w-0" dir={isRtl(lang) ? 'rtl' : 'ltr'}>
        <span className="fl-told-h block font-display text-[22px] font-semibold leading-tight">
          {sentenceCase(told.headline, lang)}
        </span>
        <span className="line-clamp-3 block text-[15px] leading-snug text-muted max-sm:line-clamp-2">
          {told.body}
        </span>
      </span>
    </div>
  )
}

/**
 * The one shared fact between the two panes: the clock. Centred above them side by side; between
 * them when they stack.
 */
function SameSecond({ session }: { session: Session }) {
  return (
    <div className="pointer-events-none order-2 flex justify-center lg:absolute lg:inset-x-0 lg:top-0">
      <SessionContext.Provider value={session}>
        <SameSecondChip />
      </SessionContext.Provider>
    </div>
  )
}

function SameSecondChip() {
  const clock = useSessionState((s) => s.snapshot?.clock)
  return (
    <span className="fl-same text-[15px]">
      Same second
      <span className="num text-[18px]">{clock ?? '00:00'}</span>
    </span>
  )
}

/** Tactics board only: chalk arrows from the shared clock out to each viewer's name. */
function ChalkMarks() {
  const chalk = {
    fill: 'none',
    stroke: '#ECEAE2',
    strokeWidth: 2.2,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    pathLength: 1,
  }
  const arrow = (side: 'left' | 'right') => (
    <svg
      className="fl-chalk pointer-events-none absolute top-[2px] hidden h-[30px] w-[220px] lg:block"
      style={
        side === 'left'
          ? { right: 'calc(50% + 120px)' }
          : { left: 'calc(50% + 120px)', scale: '-1 1' }
      }
      viewBox="0 0 220 30"
      aria-hidden
    >
      <path {...chalk} d="M216 18 C 160 8, 80 26, 8 14" />
      <path {...chalk} d="M20 6 L 7 14 L 20 22" />
    </svg>
  )
  return (
    <>
      {arrow('left')}
      {arrow('right')}
    </>
  )
}

/** Second, after the story: the three demo matches, each a way in. */
function MatchPicker() {
  const [matches, setMatches] = useState<MatchSummary[] | null>(null)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    listMatches()
      .then(setMatches)
      .catch(() => setFailed(true))
  }, [])
  const go = (match: string) => navigate(withParams(loadProfile() ? '/watch' : '/start', { match }))
  return (
    <section id="matches" aria-labelledby="matches-h" className="pt-10">
      <h2 id="matches-h" className="font-display text-[32px] font-bold leading-none">
        Pick a match
      </h2>
      {failed && (
        <p className="mt-4 text-[15px] text-muted">
          The match list did not load. Check the gateway is running, then reload.
        </p>
      )}
      <ul className="mt-5 grid gap-3 md:grid-cols-3">
        {(matches ?? []).map((m) => (
          <li key={m.match_id}>
            <button
              onClick={() => go(m.match_id)}
              className="fl-match flex w-full flex-col gap-2 p-5 text-start"
            >
              <Team code={m.home} />
              <Team code={m.away} />
              <span className="mt-1 text-[14px] text-muted">{m.venue}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}

function Team({ code }: { code: string }) {
  const club = CLUBS[code]
  return (
    <span className="flex items-center gap-2.5 font-display text-[22px] font-semibold leading-none">
      <span className="h-5 w-[5px]" style={{ background: club?.primary_color }} aria-hidden />
      {club?.name ?? code}
    </span>
  )
}

function BarsIcon() {
  return (
    <svg viewBox="0 0 16 16" className="size-4 shrink-0" aria-hidden>
      <path d="M3 13V8M8 13V3M13 13V6" stroke="currentColor" strokeWidth="2.2" fill="none" />
    </svg>
  )
}

function BubbleIcon() {
  return (
    <svg viewBox="0 0 16 16" className="size-4 shrink-0" aria-hidden>
      <path
        d="M2.5 3.5h11v7h-6l-3 2.5v-2.5h-2z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  )
}
