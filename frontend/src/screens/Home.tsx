import { motion, useReducedMotion } from 'framer-motion'
import { sentenceCase } from '@/core/headline'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { AppNav } from '@/components/AppNav'
import { Stage } from '@/components/Stage'
import { CLUBS } from '@/data/league'
import { getMomentText } from '@/net/api'
import { navigate, withParams } from '@/router'
import { defaultProfile, type Lang } from '@/state/profile'
import { SessionContext, useLiveSession } from '@/state/useSession'

/** derby_01, 26:47: Tobias Wragg's penalty puts Ashford Rovers ahead. */
const MATCH = 'derby_01'
const MOMENT = 'mom-derby_01-0014'
const GOAL_T = 1590

interface Telling {
  persona: 'analyst' | 'casual' | 'kids'
  lang: Lang
  who: string
  headline: string
  body: string
}

/**
 * What the agents actually wrote for that goal, verified and localised (captured from the
 * gateway on 25 Oct). Shown until the live text arrives, and instead of it when the agents are off.
 */
const CAPTURED: Telling[] = [
  {
    persona: 'analyst',
    lang: 'en',
    who: 'Analyst, English',
    headline: 'Penalty goal advances Ashford',
    body: 'Ashford Rovers scored a penalty by Tobias Wragg, making it 1-0. They forced 4 shots with 0.78 xG in the last 5 minutes, showing strong attacking pressure.',
  },
  {
    persona: 'casual',
    lang: 'es',
    who: 'Casual fan, Español',
    headline: 'Ashford se adelanta',
    body: 'Tras insistir con varios disparos, Ashford Rovers logró un penalti y Tobias Wragg lo transformó para el 1-0.',
  },
  {
    persona: 'kids',
    lang: 'hi',
    who: 'First match, हिन्दी',
    headline: 'Wragg ने Ashford के लिए गोल किया',
    body: 'Ashford के पास ज्यादा गेंद नहीं थी, लेकिन उन्होंने मेहनत की और Wragg ने गेंद को नेट में भेजा!',
  },
]

/** The six steps every moment goes through, in order. */
const STEPS: { name: string; does: string; on: string }[] = [
  {
    name: 'Stream',
    does: 'Every pass, shot, tackle and press arrives the moment it happens.',
    on: 'Azure Event Hubs, for the live feed',
  },
  {
    name: 'Measure',
    does: 'Code, not a model, turns events into numbers: momentum, pressure, pass difficulty, speed.',
    on: 'Instant graphics in about 50 ms, no model call',
  },
  {
    name: 'Pick',
    does: 'The Producer agent decides which moments are worth a viewer’s attention.',
    on: 'Microsoft Agent Framework',
  },
  {
    name: 'Explain',
    does: 'The Analyst agent says why the moment matters, citing the numbers it used.',
    on: 'Microsoft Foundry models',
  },
  {
    name: 'Prove',
    does: 'The Verifier recomputes every claim from the match data. A wrong number never airs.',
    on: 'Plain code, the same match tools our MCP server exposes',
  },
  {
    name: 'Tell',
    does: 'Narrator, Localiser and Voice reword it for each viewer, in six languages, out loud.',
    on: 'Azure AI Translator, Speech, Content Safety',
  },
]

/**
 * The front door. Says what the problem is, shows the answer working on one real moment, then
 * points at every way in. Everything on it is real output, not a mock-up.
 */
export function Home() {
  const [tellings, setTellings] = useState<Telling[]>(CAPTURED)
  useEffect(() => {
    let live = true
    Promise.all(
      CAPTURED.map(async (c) => {
        const out = await getMomentText(MATCH, MOMENT, c.lang)
        const v = out.variants[c.persona]
        return v ? { ...c, headline: v.headline, body: v.body } : c
      }),
    )
      .then((got) => live && setTellings(got))
      .catch(() => undefined)
    return () => {
      live = false
    }
  }, [])

  const watch = () => navigate(withParams('/start', { match: MATCH }))
  const split = () => navigate(withParams('/split', { match: MATCH, t: String(GOAL_T) }))

  return (
    <div className="bg-ink">
      <section
        aria-label="Introduction"
        className="relative isolate min-h-[min(100dvh,980px)] overflow-hidden"
      >
        <HeroPitch />
        <div className="relative mx-auto flex w-full max-w-[1440px] flex-col px-4 pb-16 pt-4 sm:px-10">
          <AppNav match={MATCH} />
          <div className="mt-10 grid items-end gap-12 sm:mt-20 lg:grid-cols-[minmax(0,1fr)_minmax(0,560px)] lg:gap-16">
            <div className="max-w-[760px]">
              <h1 className="font-display text-[52px] font-bold leading-[0.92] text-balance sm:text-[76px] xl:text-[92px]">
                Millions watch the same match. They all get the same broadcast.
              </h1>
              <p className="mt-6 max-w-[58ch] text-[18px] leading-relaxed text-text/85 sm:text-[20px]">
                The analyst wants the pressing numbers. The kid at their first match wants to know
                why everyone is shouting. The fan in Madrid wants it in Spanish. Today they all get
                one set of graphics, one commentary, one language.
              </p>
              <p className="mt-4 max-w-[58ch] text-[18px] leading-relaxed sm:text-[20px]">
                Pitchside gives each of them their own broadcast of the same match. A team of AI
                agents picks the moments that matter, explains why, proves every number, and tells
                it their way.
              </p>
              <div className="mt-9 flex flex-wrap items-center gap-3">
                <button
                  className="btn-primary h-12 bg-amber px-6 text-[17px] font-semibold text-ink transition-transform active:scale-[0.98]"
                  onClick={watch}
                >
                  Start watching
                </button>
                <button
                  className="h-12 border border-text px-6 text-[17px] font-medium text-text transition-colors hover:bg-raised active:scale-[0.98]"
                  onClick={split}
                >
                  See two fans side by side
                </button>
              </div>
            </div>
            <OneMoment tellings={tellings} />
          </div>
        </div>
      </section>

      <main className="mx-auto flex w-full max-w-[1440px] flex-col gap-24 px-4 pb-20 pt-8 sm:px-10">
        <Pipeline />
        <WaysIn />
        <footer className="flex flex-col gap-2 border-t border-hairline pt-6 text-[14px] leading-relaxed text-muted">
          <p className="max-w-[90ch]">
            The league, clubs, players and matches are invented and generated by our own match
            engine, calibrated against 200 simulated matches. No real league data is used. The
            real-footage demo uses SoccerTrack v2 (CC BY 4.0), with painted marks removed.
          </p>
          <p>Built on Microsoft Foundry, Microsoft Agent Framework and Azure.</p>
        </footer>
      </main>
    </div>
  )
}

/** The goal itself, playing quietly behind the headline. */
function HeroPitch() {
  const profile = useMemo(() => defaultProfile({ persona: 'casual' }), [])
  const session = useLiveSession({
    matchId: MATCH,
    profile,
    startAt: GOAL_T - 40,
    speed: 1,
    ambient: true,
  })
  return (
    <div className="absolute inset-0 -z-10" aria-hidden="true">
      <div className="absolute inset-0 opacity-50 max-lg:opacity-30 lg:left-[30%]">
        <SessionContext.Provider value={session}>
          <Stage />
        </SessionContext.Provider>
      </div>
      <div className="absolute inset-0 bg-[linear-gradient(90deg,var(--color-ink)_28%,color-mix(in_srgb,var(--color-ink)_70%,transparent)_60%,color-mix(in_srgb,var(--color-ink)_35%,transparent))] max-lg:bg-ink/70" />
      <div className="absolute inset-x-0 bottom-0 h-40 bg-gradient-to-b from-transparent to-ink" />
    </div>
  )
}

/** One goal, three viewers: the three lower thirds land one after another. */
function OneMoment({ tellings }: { tellings: Telling[] }) {
  const reduce = useReducedMotion()
  const kit = CLUBS['ASH']?.primary_color ?? 'var(--color-amber)'
  return (
    <figure className="flex flex-col gap-3">
      <figcaption className="text-[15px] text-text/85">
        <span className="num me-2 text-[20px] font-semibold text-amber">26:47</span>
        Penalty, Ashford Rovers 1-0. The same goal, as three viewers saw it.
      </figcaption>
      {tellings.map((c, i) => (
        <motion.div
          key={c.persona}
          initial={reduce ? false : { clipPath: 'inset(-20px 100% -20px 0)' }}
          animate={{ clipPath: 'inset(-20px -20px -20px 0)' }}
          transition={{ duration: 0.18, delay: 0.25 + i * 0.22, ease: [0.25, 1, 0.5, 1] }}
        >
          <p className="mb-1 text-[13px] text-muted">{c.who}</p>
          <div className="plate-shadow">
            <div className="plate flex" style={{ ['--cut' as string]: '14px' }}>
              <span className="plate-edge w-[6px] shrink-0" style={{ background: kit }} />
              <div
                className="min-w-0 py-3 pe-6 ps-4"
                lang={c.lang}
                dir={c.lang === 'ar' ? 'rtl' : 'ltr'}
              >
                <p className="font-display text-[26px] font-bold leading-[0.95] sm:text-[30px]">
                  {sentenceCase(c.headline, c.lang)}
                </p>
                <p className="mt-1.5 text-[15px] leading-snug text-text/80">{c.body}</p>
              </div>
            </div>
          </div>
        </motion.div>
      ))}
    </figure>
  )
}

function Pipeline() {
  return (
    <section aria-labelledby="pipe-h">
      <h2 id="pipe-h" className="font-display text-[40px] font-bold leading-none sm:text-[56px]">
        What happens to one moment
      </h2>
      <p className="mt-3 max-w-[64ch] text-[17px] leading-relaxed text-muted">
        Numbers are worked out in code. Words come from the agents. Nothing reaches a screen until
        the numbers in it have been checked against the match.
      </p>
      <ol className="mt-10 grid gap-x-6 gap-y-8 sm:grid-cols-2 lg:grid-cols-6">
        {STEPS.map((s, i) => (
          <li key={s.name} className="flex flex-col border-t-2 border-amber/70 pt-4">
            <span className="num text-[18px] text-amber">{i + 1}</span>
            <h3 className="mt-1 font-display text-[28px] font-semibold leading-none">{s.name}</h3>
            <p className="mt-2 text-[15px] leading-relaxed text-text/85">{s.does}</p>
            <p className="mt-auto pt-3 text-[13px] text-muted">{s.on}</p>
          </li>
        ))}
      </ol>
    </section>
  )
}

function WaysIn() {
  const go = (path: string, extra: Record<string, string> = {}) =>
    navigate(withParams(path, { match: MATCH, ...extra }))
  return (
    <section aria-labelledby="ways-h">
      <h2 id="ways-h" className="font-display text-[40px] font-bold leading-none sm:text-[56px]">
        Try it
      </h2>
      <div className="mt-8 grid gap-4 lg:grid-cols-3">
        <Way title="Watch your way" who="For fans" onClick={() => go('/start')}>
          Pick how you watch, your club, your player and your language. The broadcast reshapes
          itself around you: what it shows, how it says it, and what it leaves out.
        </Way>
        <Way
          title="Two fans, side by side"
          who="For broadcasters"
          onClick={() => go('/split', { t: String(GOAL_T) })}
        >
          One match, two viewers, two different broadcasts on the same second of football. Change
          either one and watch the graphics and the words change with it.
        </Way>
        <Way
          title="Phone view"
          who="For streaming and second screens"
          onClick={() => go('/companion')}
        >
          A feed of the moments you have seen, why each one mattered, spoken commentary, and “What
          did I miss?” that never spoils what is still to come.
        </Way>
      </div>
      <ul className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <SmallWay title="Control room" onClick={() => go('/control')}>
          The agents at work: who is doing what, what the Verifier threw out, and what it cost.
        </SmallWay>
        <SmallWay title="Real footage" onClick={() => navigate(withParams('/real'))}>
          The same tags, speeds and passes, found by a vision model on a real amateur match.
        </SmallWay>
        <SmallWay title="Recaps" onClick={() => go('/recap')}>
          Half-time and full-time stories, per viewer and language, every number checked.
        </SmallWay>
        <SmallWay title="How it's built" onClick={() => navigate(withParams('/why'))}>
          Why it matters, then every part that does the work, from Foundry to Event Hubs, and what
          is proven.
        </SmallWay>
      </ul>
    </section>
  )
}

function Way({
  title,
  who,
  onClick,
  children,
}: {
  title: string
  who: string
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button onClick={onClick} className="group plate-shadow block h-full text-start">
      <span
        className="plate flex h-full flex-col px-6 py-5 transition-colors group-hover:bg-raised"
        style={{ ['--cut' as string]: '16px' }}
      >
        <span className="text-[14px] text-amber">{who}</span>
        <span className="mt-1 font-display text-[34px] font-bold leading-none">{title}</span>
        <span className="mt-3 text-[15px] leading-relaxed text-text/80">{children}</span>
      </span>
    </button>
  )
}

function SmallWay({
  title,
  onClick,
  children,
}: {
  title: string
  onClick: () => void
  children: ReactNode
}) {
  return (
    <li>
      <button onClick={onClick} className="group block px-6 text-start">
        <span className="font-display text-[24px] font-semibold leading-none underline decoration-text/25 underline-offset-4 group-hover:decoration-amber">
          {title}
        </span>
        <span className="mt-1.5 block text-[15px] leading-relaxed text-muted">{children}</span>
      </button>
    </li>
  )
}
