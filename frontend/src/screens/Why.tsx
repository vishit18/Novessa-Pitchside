import { motion, useReducedMotion } from 'framer-motion'
import { useEffect, useState, type ReactNode } from 'react'
import { AppNav } from '@/components/AppNav'
import { sentenceCase } from '@/core/headline'
import { CLUBS } from '@/data/league'
import { getMomentText } from '@/net/api'
import { navigate, withParams } from '@/router'
import type { Lang, Persona } from '@/state/profile'

/** derby_01, 26:47: Tobias Wragg's penalty puts Ashford Rovers ahead. Same moment as Home. */
const MATCH = 'derby_01'
const MOMENT = 'mom-derby_01-0014'
const GOAL_T = 1590

interface Telling {
  persona: Persona
  lang: Lang
  who: string
  headline: string
  body: string
}

/** Verified agent text for that goal, captured 21 Oct. Replaced by the live text when it loads. */
const CAPTURED: Telling[] = [
  {
    persona: 'analyst',
    lang: 'en',
    who: 'Analyst, English',
    headline: 'Wragg’s high xG leads goal',
    body: 'Ashford held 42.1% possession and applied 22 pressure events before 26:47. Wragg’s 0.762 xG and two shots highlight his key role in converting pressure into a goal.',
  },
  {
    persona: 'casual',
    lang: 'es',
    who: 'Casual fan, Español',
    headline: 'Wragg marca contra todo pronóstico',
    body: 'Aunque Ashford tuvo menos balón, presionaron fuerte y Wragg aprovechó sus oportunidades para abrir el marcador.',
  },
]

/** The brief's five stages, one line each. */
const STAGES: { name: string; line: string }[] = [
  { name: 'Ingest', line: 'Every pass, shot and press, as it happens' },
  { name: 'Interpret', line: 'Code turns events into numbers in under 150 ms' },
  { name: 'Explain', line: 'Agents say why the moment matters' },
  { name: 'Render', line: 'Timed graphics on the pitch' },
  { name: 'Personalise', line: 'Your style, club, player and language' },
]

type Status = 'live' | 'proven' | 'partial' | 'off'

interface Part {
  name: string
  kind: 'Azure' | 'Agent' | 'Code'
  does: string
  status: Status
  note: string
  hardest?: boolean
}

/**
 * Ranked by how much of a viewer's match each one carries, read from the code on 22 Oct, not
 * from the plan. Status is what has actually run end to end.
 */
const STACK: Part[] = [
  {
    name: 'Match and stats engine',
    kind: 'Code',
    does: 'Plays all 90 minutes and computes every number on screen',
    status: 'live',
    note: '3,200 lines of Python. No model touches a number.',
  },
  {
    name: 'Microsoft Foundry',
    kind: 'Azure',
    does: 'The models behind every word: Producer, Analyst, Narrator, Localiser, Recap, Ask',
    status: 'live',
    note: 'gpt-4.1-mini for volume, gpt-5-mini for analysis and recaps',
  },
  {
    name: 'Analyst and Verifier',
    kind: 'Agent',
    does: 'Writes the why, then re-measures every claim against the match',
    status: 'live',
    note: 'A claim is checked as metric, team and time window. One retry, then numbers only.',
    hardest: true,
  },
  {
    name: 'Microsoft Agent Framework',
    kind: 'Azure',
    does: 'Runs the newsroom graph: Producer, Analyst, Verifier, Narrator, Gate',
    status: 'live',
    note: 'One workflow, with a retry edge from Verifier back to Analyst',
  },
  {
    name: 'Producer',
    kind: 'Agent',
    does: 'Picks which moments air, and drops the rest',
    status: 'live',
    note: 'Falls back to a ranking rule when the model is slow',
  },
  {
    name: 'Narrator',
    kind: 'Agent',
    does: 'Rewrites one verified insight for four kinds of viewer',
    status: 'live',
    note: 'May not add a number; if it does, the Analyst text airs',
  },
  {
    name: 'Localiser and Azure AI Translator',
    kind: 'Azure',
    does: 'Six languages, with names, clocks and scores kept intact',
    status: 'live',
    note: 'Translator first, then a model polish; a changed number throws the step away',
  },
  {
    name: 'Azure AI Speech',
    kind: 'Azure',
    does: 'Spoken commentary per language, and spoken questions',
    status: 'live',
    note: 'Audio cached, so a replay costs nothing',
  },
  {
    name: 'Recap Editor',
    kind: 'Agent',
    does: 'Half and full-time stories, also offered to other agents over A2A',
    status: 'live',
    note: 'Every number must be in a fact sheet computed in code',
  },
  {
    name: 'Azure Cosmos DB',
    kind: 'Azure',
    does: 'Shared cache of verified agent text',
    status: 'proven',
    note: 'Checked against the real account. Local runs use files instead.',
  },
  {
    name: 'Azure AI Content Safety',
    kind: 'Azure',
    does: 'Screens every line before it airs',
    status: 'partial',
    note: 'Wired in the Azure config; a word list stands in when it is not reachable',
  },
  {
    name: 'Azure Event Hubs',
    kind: 'Azure',
    does: 'The live event stream from engine to gateway',
    status: 'partial',
    note: '2,190 events through, none lost. Viewers still stream a precomputed timeline.',
  },
  {
    name: 'Application Insights',
    kind: 'Azure',
    does: 'A trace for every model call',
    status: 'proven',
    note: 'Spans arrive; not yet linked to the Foundry tracing tab',
  },
  {
    name: 'Container Apps and Static Web Apps',
    kind: 'Azure',
    does: 'Hosting for the gateway and this site',
    status: 'off',
    note: 'The live gateway is an old build. The site is not deployed yet.',
  },
]

const STATUS_LABEL: Record<Status, string> = {
  live: 'Runs every match',
  proven: 'Proven, not in every match',
  partial: 'Partly wired',
  off: 'Not deployed yet',
}

/**
 * /why: what exists today, what is missing, what Pitchside adds, then the stack ranked honestly.
 * Reads in seconds: numbers, icons and short lines, no paragraphs.
 */
export function Why() {
  const [tellings, setTellings] = useState(CAPTURED)
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

  return (
    <div className="min-h-dvh bg-ink">
      <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-16 px-4 pb-20 pt-4 sm:px-10">
        <AppNav match={MATCH} />

        <header className="flex flex-col gap-4">
          <h1 className="max-w-[18ch] font-display text-[48px] font-bold leading-[0.92] sm:text-[80px]">
            Same moment. Two fans. Two broadcasts.
          </h1>
          <p className="text-[17px] text-muted">
            For broadcasters and streaming platforms: one feed in, a broadcast per viewer out.
          </p>
        </header>

        <section
          aria-label="Today, what is missing, what Pitchside adds"
          className="grid gap-x-8 gap-y-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,2.2fr)]"
        >
          <Beat n={1} title="Today">
            <Fact icon={<StatsIcon />} text="Stats overlays" />
            <Fact icon={<OneToManyIcon />} text="One broadcast for everyone" />
            <Fact icon={<MicIcon />} text="One human pundit" />
          </Beat>

          <Beat n={2} title="Missing">
            <Gap icon="?" text="Why it happened" />
            <Gap icon={<PeopleIcon />} text="Told your way" />
          </Beat>

          <Beat n={3} title="Pitchside adds" wide>
            <Proof tellings={tellings} />
            <ol className="mt-6 grid gap-x-6 gap-y-2.5 sm:grid-cols-2">
              {STAGES.map((s, i) => (
                <li key={s.name} className="grid grid-cols-[1.5rem_1fr] items-baseline gap-x-2">
                  <span className="num text-[18px] text-amber">{i + 1}</span>
                  <span>
                    <span className="font-display text-[22px] font-semibold leading-none">
                      {s.name}
                    </span>
                    <span className="ms-2 text-[15px] text-text/80">{s.line}</span>
                  </span>
                </li>
              ))}
            </ol>
            <p className="mt-5 border-s-2 border-amber ps-3 text-[16px] leading-snug">
              Every number is checked before it airs. 8 of 47 moments were caught and sent back.
            </p>
          </Beat>
        </section>

        <Stack />

        <footer className="flex flex-wrap items-center justify-between gap-4 border-t border-hairline pt-6">
          <p className="text-[14px] text-muted">
            Invented league, clubs and players. No real league data.
          </p>
          <button
            className="btn-primary h-11 bg-amber px-5 text-[16px] font-semibold text-ink"
            onClick={() => navigate(withParams('/split', { match: MATCH, t: String(GOAL_T) }))}
          >
            See both fans live
          </button>
        </footer>
      </div>
    </div>
  )
}

function Beat({
  n,
  title,
  wide = false,
  children,
}: {
  n: number
  title: string
  wide?: boolean
  children: ReactNode
}) {
  return (
    <div className={`flex flex-col border-t-2 pt-4 ${wide ? 'border-amber' : 'border-hairline'}`}>
      <p className="flex items-baseline gap-3">
        <span className={`num text-[40px] leading-none ${wide ? 'text-amber' : 'text-muted'}`}>
          {n}
        </span>
        <span className="font-display text-[30px] font-bold leading-none">{title}</span>
      </p>
      <div className="mt-6 flex flex-col gap-4">{children}</div>
    </div>
  )
}

function Fact({ icon, text }: { icon: ReactNode; text: string }) {
  return (
    <div className="flex items-center gap-4">
      <span className="grid size-12 shrink-0 place-items-center bg-raised text-text/85">
        {icon}
      </span>
      <span className="text-[17px] leading-tight">{text}</span>
    </div>
  )
}

function Gap({ icon, text }: { icon: ReactNode; text: string }) {
  return (
    <div className="flex items-center gap-4">
      <span className="grid size-12 shrink-0 place-items-center border border-dashed border-muted font-display text-[26px] text-muted">
        {icon}
      </span>
      <span className="text-[17px] leading-tight text-text/85">{text}</span>
    </div>
  )
}

/** The visual proof: the same goal, as two viewers were told it. */
function Proof({ tellings }: { tellings: Telling[] }) {
  const reduce = useReducedMotion()
  const kit = CLUBS['ASH']?.primary_color ?? 'var(--color-amber)'
  return (
    <figure>
      <figcaption className="mb-3 flex items-baseline gap-3 text-[15px] text-text/85">
        <span className="num text-[22px] font-semibold text-amber">26:47</span>
        Penalty, Ashford Rovers 1-0
      </figcaption>
      <div className="grid gap-3 md:grid-cols-2">
        {tellings.map((c, i) => (
          <motion.div
            key={c.persona}
            initial={reduce ? false : { clipPath: 'inset(-20px 100% -20px 0)' }}
            animate={{ clipPath: 'inset(-20px -20px -20px 0)' }}
            transition={{ duration: 0.18, delay: 0.2 + i * 0.18, ease: [0.25, 1, 0.5, 1] }}
            className="flex flex-col"
          >
            <p className="mb-1 text-[13px] text-muted">{c.who}</p>
            <div className="plate-shadow flex-1">
              <div className="plate flex h-full" style={{ ['--cut' as string]: '14px' }}>
                <span className="plate-edge w-[6px] shrink-0" style={{ background: kit }} />
                <div className="min-w-0 py-3 pe-5 ps-4" lang={c.lang}>
                  <p className="font-display text-[24px] font-bold leading-[0.95]">
                    {sentenceCase(c.headline, c.lang)}
                  </p>
                  <p className="mt-1.5 text-[14px] leading-snug text-text/80">{c.body}</p>
                </div>
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </figure>
  )
}

function Stack() {
  return (
    <section aria-labelledby="stack-h">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h2 id="stack-h" className="font-display text-[40px] font-bold leading-none sm:text-[52px]">
          What does the work
        </h2>
        <ul className="flex flex-wrap gap-x-5 gap-y-1 text-[13px] text-muted">
          {(Object.keys(STATUS_LABEL) as Status[]).map((s) => (
            <li key={s} className="flex items-center gap-2">
              <StatusDot status={s} />
              {STATUS_LABEL[s]}
            </li>
          ))}
        </ul>
      </div>
      <p className="mt-2 text-[15px] text-muted">Most work first. Read from the code.</p>
      <ol className="mt-8 flex flex-col">
        {STACK.map((p, i) => (
          <li
            key={p.name}
            className={`grid grid-cols-[2.25rem_minmax(0,1fr)] gap-x-3 border-t py-3.5 md:grid-cols-[2.25rem_minmax(0,17rem)_minmax(0,1fr)_minmax(0,22rem)] md:gap-x-6 ${
              p.hardest ? 'border-amber bg-amber/[0.06]' : 'border-hairline'
            }`}
          >
            <span className="num text-[22px] leading-none text-muted">{i + 1}</span>
            <span className="flex flex-col gap-1">
              <span className="font-display text-[22px] font-semibold leading-none">{p.name}</span>
              <span className="flex flex-wrap items-center gap-2 text-[12px] text-muted">
                <span>{p.kind}</span>
                {p.hardest && (
                  <span className="bg-amber px-1.5 py-0.5 font-semibold text-ink">
                    Hardest piece
                  </span>
                )}
              </span>
            </span>
            <span className="col-start-2 text-[15px] leading-snug md:col-start-auto">{p.does}</span>
            <span className="col-start-2 flex items-start gap-2 text-[13px] leading-snug text-muted md:col-start-auto">
              <span className="pt-1">
                <StatusDot status={p.status} />
              </span>
              <span>
                <span className="sr-only">{STATUS_LABEL[p.status]}. </span>
                {p.note}
              </span>
            </span>
          </li>
        ))}
      </ol>
    </section>
  )
}

function StatusDot({ status }: { status: Status }) {
  const cls = {
    live: 'bg-amber',
    proven: 'border-2 border-amber',
    partial: 'border-2 border-dashed border-muted',
    off: 'border border-muted/60',
  }[status]
  return <span className={`inline-block size-2.5 shrink-0 rounded-full ${cls}`} aria-hidden />
}

function StatsIcon() {
  return (
    <svg viewBox="0 0 24 24" className="size-6" aria-hidden>
      <path
        d="M4 19h16M7 16v-5M12 16V6M17 16v-8"
        stroke="currentColor"
        strokeWidth="2"
        fill="none"
      />
    </svg>
  )
}

function OneToManyIcon() {
  return (
    <svg viewBox="0 0 24 24" className="size-6" aria-hidden>
      <rect x="2" y="9" width="7" height="6" stroke="currentColor" strokeWidth="1.8" fill="none" />
      <path
        d="M9 12h3M12 6v12M12 6h3M12 12h3M12 18h3"
        stroke="currentColor"
        strokeWidth="1.8"
        fill="none"
      />
      <circle cx="19" cy="6" r="2" fill="currentColor" />
      <circle cx="19" cy="12" r="2" fill="currentColor" />
      <circle cx="19" cy="18" r="2" fill="currentColor" />
    </svg>
  )
}

function MicIcon() {
  return (
    <svg viewBox="0 0 24 24" className="size-6" aria-hidden>
      <rect
        x="9"
        y="3"
        width="6"
        height="11"
        rx="3"
        stroke="currentColor"
        strokeWidth="1.8"
        fill="none"
      />
      <path
        d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21"
        stroke="currentColor"
        strokeWidth="1.8"
        fill="none"
      />
    </svg>
  )
}

function PeopleIcon() {
  return (
    <svg viewBox="0 0 24 24" className="size-6" aria-hidden>
      <circle
        cx="8"
        cy="8"
        r="3"
        stroke="currentColor"
        strokeWidth="1.8"
        fill="none"
        strokeDasharray="2 2"
      />
      <circle
        cx="16"
        cy="8"
        r="3"
        stroke="currentColor"
        strokeWidth="1.8"
        fill="none"
        strokeDasharray="2 2"
      />
      <path
        d="M3 19c0-3 2.2-5 5-5s5 2 5 5M11 19c0-3 2.2-5 5-5s5 2 5 5"
        stroke="currentColor"
        strokeWidth="1.8"
        fill="none"
        strokeDasharray="2 2"
      />
    </svg>
  )
}
