import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { AppNav } from '@/components/AppNav'
import { Stage } from '@/components/Stage'
import { CLUBS, PLAYERS } from '@/data/league'
import { getMatchMeta, listMatches, type MatchSummary } from '@/net/api'
import { navigate, withParams } from '@/router'
import {
  defaultProfile,
  LANGS,
  loadProfile,
  METRICS,
  PERSONAS,
  saveProfile,
  type ViewerProfile,
} from '@/state/profile'
import { SessionContext, useLiveSession } from '@/state/useSession'
import type { MatchMeta } from '@/types/schema'

type Step = 'match' | 'persona' | 'metric' | 'club' | 'player' | 'lang'

/** The questions this viewer still has to answer. One-number mode skips following a player. */
function stepsFor(p: ViewerProfile): Step[] {
  return [
    'match',
    'persona',
    ...(p.metric ? (['metric'] as const) : []),
    'club',
    ...(p.club && !p.metric ? (['player'] as const) : []),
    'lang',
  ]
}

const clubName = (code: string) => CLUBS[code]?.name ?? code
const kit = (code: string) => CLUBS[code]?.primary_color ?? '#9aa5b1'

/**
 * Pick a match, then three quick taps and a language (docs/07 screen 1). One tap answers and
 * moves on. The choice is remembered for next time.
 */
export function Onboarding({ query }: { query: URLSearchParams }) {
  const saved = useMemo(() => loadProfile(), [])
  const [profile, setProfile] = useState<ViewerProfile>(() => saved ?? defaultProfile())
  const [matchId, setMatchId] = useState<string | null>(query.get('match'))
  const [step, setStep] = useState<Step>(query.get('match') ? 'persona' : 'match')
  const [matches, setMatches] = useState<MatchSummary[] | null>(null)
  const [meta, setMeta] = useState<MatchMeta | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listMatches()
      .then(setMatches)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
  }, [])

  useEffect(() => {
    if (!matchId) return
    setMeta(null)
    getMatchMeta(matchId)
      .then(setMeta)
      .catch(() => setMeta(null))
  }, [matchId])

  const fixture = matches?.find((m) => m.match_id === matchId) ?? null
  const steps = stepsFor(profile)
  const index = steps.indexOf(step)

  const next = (p: ViewerProfile = profile) => {
    const order = stepsFor(p)
    const after = order[order.indexOf(step) + 1]
    if (after) setStep(after)
    else finish(p)
  }
  const choose = (patch: Partial<ViewerProfile>) => {
    const p = { ...profile, ...patch }
    setProfile(p)
    next(p)
  }
  const finish = (p: ViewerProfile) => {
    saveProfile(p)
    navigate(withParams('/watch', { match: matchId ?? 'derby_01' }))
  }

  return (
    <main className="relative min-h-dvh w-full overflow-hidden bg-ink">
      <Backdrop matchId={matchId ?? matches?.[0]?.match_id ?? 'derby_01'} />
      <div className="relative z-10 px-5 pt-4 sm:px-16">
        <AppNav match={matchId} />
      </div>
      <div className="relative z-10 flex max-w-[680px] flex-col px-5 pb-8 sm:px-16 sm:pb-14">
        <div className="mt-10 sm:mt-16">
          {step !== 'match' && (
            <div className="mb-5 flex items-center gap-4">
              <button
                className="text-[14px] text-muted hover:text-text"
                onClick={() => setStep(steps[Math.max(0, index - 1)] ?? 'match')}
              >
                Back
              </button>
              <Progress total={steps.length} at={index} />
            </div>
          )}

          {step === 'match' && (
            <Question title="Pick a match" hint="Three fixtures from matchday one.">
              {error && (
                <p className="border-s-2 border-chaos ps-3 text-[15px] text-text">
                  Couldn’t reach the match server ({error}). Check the gateway is running, then
                  reload.
                </p>
              )}
              {!matches && !error && <p className="pulse-soft text-muted">Loading fixtures</p>}
              {matches?.map((m) => (
                <Choice
                  key={m.match_id}
                  selected={m.match_id === matchId}
                  onClick={() => {
                    setMatchId(m.match_id)
                    setStep('persona')
                  }}
                >
                  <Fixture m={m} />
                </Choice>
              ))}
              {matches && (
                <button
                  className="mt-3 self-start text-[15px] text-amber underline decoration-amber/40 underline-offset-4 hover:decoration-amber"
                  onClick={() =>
                    navigate(withParams('/split', { match: matchId ?? matches[0]?.match_id ?? '' }))
                  }
                >
                  Or watch two viewers side by side
                </button>
              )}
            </Question>
          )}

          {step === 'persona' && (
            <Question title="How do you watch?" hint={fixture ? fixtureLine(fixture) : undefined}>
              {saved && (
                <Choice selected={false} onClick={() => finish(saved)}>
                  <span className="font-display text-[26px] font-semibold leading-none text-amber">
                    Same as last time
                  </span>
                  <span className="mt-1 block text-[14px] text-text/80">{savedLine(saved)}</span>
                </Choice>
              )}
              {PERSONAS.map((p) => (
                <Choice
                  key={p.id}
                  selected={p.id === profile.persona}
                  onClick={() => choose({ persona: p.id, metric: null })}
                >
                  <span className="font-display text-[26px] font-semibold leading-none">
                    {p.label}
                  </span>
                  <span className="mt-1 block text-[14px] text-muted">{p.hint}</span>
                </Choice>
              ))}
              <Choice
                selected={profile.metric !== null}
                onClick={() => {
                  setProfile({
                    ...profile,
                    persona: 'analyst',
                    metric: profile.metric ?? METRICS[0]?.id ?? null,
                  })
                  setStep('metric')
                }}
              >
                <span className="font-display text-[26px] font-semibold leading-none">
                  Just one number
                </span>
                <span className="mt-1 block text-[14px] text-muted">
                  Pick one measure and the broadcast shows only that, and the goals
                </span>
              </Choice>
            </Question>
          )}

          {step === 'metric' && (
            <Question title="Which number?" hint="Everything else is left out.">
              {METRICS.map((m) => (
                <Choice
                  key={m.id}
                  selected={profile.metric === m.id}
                  onClick={() => choose({ metric: m.id })}
                >
                  <span className="font-display text-[26px] font-semibold leading-none">
                    {m.label}
                  </span>
                  <span className="mt-1 block text-[14px] text-muted">{m.hint}</span>
                </Choice>
              ))}
            </Question>
          )}

          {step === 'club' && fixture && (
            <Question title="Your club" hint="Their moments get a little more room.">
              {[fixture.home, fixture.away].map((code) => (
                <Choice
                  key={code}
                  selected={profile.club === code}
                  onClick={() => choose({ club: code, player: null })}
                >
                  <span className="flex items-center gap-3">
                    <span className="h-7 w-[6px]" style={{ background: kit(code) }} />
                    <span className="font-display text-[26px] font-semibold leading-none">
                      {clubName(code)}
                    </span>
                  </span>
                </Choice>
              ))}
              <Choice
                selected={profile.club === null}
                onClick={() => choose({ club: null, player: null })}
              >
                <span className="text-[16px] text-muted">No side, just the football</span>
              </Choice>
            </Question>
          )}

          {step === 'player' && profile.club && (
            <Question
              title="Your player"
              hint="Optional. The broadcast follows them and leaves the rest out."
            >
              <PlayerGrid
                meta={meta}
                club={profile.club}
                selected={profile.player}
                onPick={(id) => choose({ player: id })}
              />
              <Choice selected={false} onClick={() => choose({ player: null })}>
                <span className="text-[16px] text-muted">Skip, show the whole match</span>
              </Choice>
            </Question>
          )}

          {step === 'lang' && (
            <Question title="Language">
              {LANGS.map((l) => (
                <Choice
                  key={l.id}
                  selected={l.id === profile.lang}
                  onClick={() => choose({ lang: l.id })}
                >
                  <span
                    className="font-display text-[26px] font-semibold leading-none"
                    lang={l.id}
                    dir={l.id === 'ar' ? 'rtl' : 'ltr'}
                  >
                    {l.label}
                  </span>
                </Choice>
              ))}
            </Question>
          )}
        </div>
      </div>
    </main>
  )
}

/** "Casual, English, Port Calder": what a returning viewer chose last time. */
function savedLine(p: ViewerProfile): string {
  const persona = p.metric
    ? (METRICS.find((x) => x.id === p.metric)?.label ?? p.metric)
    : (PERSONAS.find((x) => x.id === p.persona)?.label ?? p.persona)
  const lang = LANGS.find((x) => x.id === p.lang)?.label ?? p.lang
  const who = p.player ? PLAYERS[p.player]?.name : p.club ? CLUBS[p.club]?.name : null
  return [persona, lang, who].filter(Boolean).join(', ')
}

function fixtureLine(m: MatchSummary): string {
  return `${clubName(m.home)} v ${clubName(m.away)}, ${m.venue}`
}

function Fixture({ m }: { m: MatchSummary }) {
  const kick = new Date(m.kickoff_time)
  const time = `${String(kick.getUTCHours()).padStart(2, '0')}:${String(kick.getUTCMinutes()).padStart(2, '0')}`
  return (
    <span className="block">
      <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="h-6 w-[6px]" style={{ background: kit(m.home) }} />
        <span className="font-display text-[26px] font-semibold leading-none">
          {clubName(m.home)}
        </span>
        <span className="text-[15px] text-muted">v</span>
        <span className="font-display text-[26px] font-semibold leading-none">
          {clubName(m.away)}
        </span>
        <span className="h-6 w-[6px]" style={{ background: kit(m.away) }} />
      </span>
      <span className="mt-1.5 block text-[14px] text-muted">
        Matchday {m.matchday} at {m.venue}, kick-off {time}
      </span>
    </span>
  )
}

function PlayerGrid({
  meta,
  club,
  selected,
  onPick,
}: {
  meta: MatchMeta | null
  club: string
  selected: string | null
  onPick: (id: string) => void
}) {
  if (!meta) return <p className="pulse-soft text-muted">Loading the team sheet</p>
  const sheet = meta.home.code === club ? meta.home : meta.away
  const starters = [...sheet.starters].sort((a, b) => a.slot - b.slot)
  return (
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
      {starters.map((s) => {
        const p = PLAYERS[s.player_id]
        return (
          <Choice
            key={s.player_id}
            selected={selected === s.player_id}
            onClick={() => onPick(s.player_id)}
            dense
          >
            <span className="flex items-baseline gap-2.5">
              <span className="num w-6 text-right text-[18px] text-muted">{p?.shirt}</span>
              <span className="font-display text-[20px] font-semibold leading-none">
                {p?.name ?? s.player_id}
              </span>
            </span>
          </Choice>
        )
      })}
    </div>
  )
}

function Question({
  title,
  hint,
  children,
}: {
  title: string
  hint?: string
  children: ReactNode
}) {
  return (
    <section aria-labelledby="q-title">
      <h1 id="q-title" className="font-display text-[44px] font-bold leading-none sm:text-[64px]">
        {title}
      </h1>
      {hint && <p className="mt-3 text-[16px] text-muted">{hint}</p>}
      <div className="mt-8 flex flex-col gap-2.5">{children}</div>
    </section>
  )
}

function Choice({
  selected,
  onClick,
  children,
  dense = false,
}: {
  selected: boolean
  onClick: () => void
  children: ReactNode
  dense?: boolean
}) {
  return (
    <button
      onClick={onClick}
      aria-pressed={selected}
      className="group plate-shadow block w-full text-start focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-amber"
    >
      <span
        className={`plate flex items-stretch transition-colors group-hover:bg-raised ${dense ? '' : ''}`}
        style={{ ['--cut' as string]: dense ? '8px' : '12px' }}
      >
        <span
          className={`plate-edge w-[4px] shrink-0 transition-colors ${selected ? 'bg-amber' : 'bg-transparent group-hover:bg-amber/50'}`}
        />
        <span className={`block min-w-0 flex-1 ${dense ? 'px-3 py-2.5' : 'px-5 py-4'}`}>
          {children}
        </span>
      </span>
    </button>
  )
}

function Progress({ total, at }: { total: number; at: number }) {
  return (
    <div
      className="flex gap-1.5"
      role="progressbar"
      aria-valuemin={1}
      aria-valuemax={total}
      aria-valuenow={at + 1}
    >
      {Array.from({ length: total }, (_, i) => (
        <span key={i} className={`h-[3px] w-8 ${i <= at ? 'bg-amber' : 'bg-text/15'}`} />
      ))}
    </div>
  )
}

/** The selected match playing quietly behind the questions. */
function Backdrop({ matchId }: { matchId: string }) {
  const profile = useMemo(() => defaultProfile({ persona: 'casual' }), [])
  const session = useLiveSession({ matchId, profile, startAt: 600, speed: 1 })
  return (
    <div className="absolute inset-0" aria-hidden="true">
      <div className="absolute inset-0 opacity-60 sm:left-[22%]">
        <SessionContext.Provider value={session}>
          <Stage />
        </SessionContext.Provider>
      </div>
      <div className="absolute inset-0 bg-[linear-gradient(90deg,var(--color-ink)_30%,color-mix(in_srgb,var(--color-ink)_75%,transparent)_55%,color-mix(in_srgb,var(--color-ink)_20%,transparent))] max-sm:bg-ink/85" />
    </div>
  )
}
