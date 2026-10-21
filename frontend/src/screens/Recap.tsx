import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { MomentsTimeline } from '@/components/recap/MomentsTimeline'
import { StatBars } from '@/components/recap/StatBars'
import { AppNav } from '@/components/AppNav'
import { footballMinute, KIND_LABEL, leaderLabel, leaderValue, shareText } from '@/core/recap'
import { CLUBS } from '@/data/league'
import { listMatches, type CatchUp, type Recap as RecapData, type RecapKind } from '@/net/api'
import { navigate, withParams } from '@/router'
import { ViewerChooser } from '@/components/ViewerChooser'
import { defaultProfile, loadProfile } from '@/state/profile'
import { useRecap } from '@/state/useRecap'
import { AlertIcon, CheckIcon } from '@/components/icons'

/** Story column, then the numbers. Centred as a pair so wide screens have no empty middle. */
const LAYOUT = 'lg:grid-cols-[minmax(0,68ch)_minmax(0,480px)] lg:justify-center'

const KINDS: RecapKind[] = ['half_time', 'full_time']

const TRANSLATION_NOTE: Record<string, string> = {
  translated: 'Translated with Azure AI Translator. The numbers panel is the source of truth.',
  polished: 'Translated, then polished by a model. The numbers panel is the source of truth.',
  llm: 'Translated by a model. The numbers panel is the source of truth.',
  unavailable: 'Translation was unavailable, so this is the English version.',
}

/**
 * Half-time or full-time recap for one viewer type and language: the headline, the story, a
 * 60 second highlights script, the numbers behind it and the key moments. The prose comes from
 * the Recap Editor; the numbers and moments are computed, so they show even when it cannot write.
 */
export function Recap({ query }: { query: URLSearchParams }) {
  const saved = useMemo(() => loadProfile() ?? defaultProfile({ persona: 'casual' }), [])
  const matchId = query.get('match') ?? 'derby_01'
  const kind: RecapKind = query.get('kind') === 'half_time' ? 'half_time' : 'full_time'
  const persona = query.get('persona') ?? saved.persona
  const lang = query.get('lang') ?? saved.lang
  const { state, retry } = useRecap(matchId, kind, persona, lang)
  const [codes, setCodes] = useState<{ home: string; away: string } | null>(null)

  useEffect(() => {
    listMatches()
      .then((all) => {
        const m = all.find((x) => x.match_id === matchId)
        if (m) setCodes({ home: m.home, away: m.away })
      })
      .catch(() => setCodes(null))
  }, [matchId])

  const go = (patch: Record<string, string>) =>
    navigate(withParams('/recap', { match: matchId, kind, persona, lang, ...patch }))

  const rtl = lang === 'ar'
  const recap = state.status === 'ready' ? state.recap : null
  const catchUp = state.status === 'ready' || state.status === 'off' ? state.catchUp : null

  return (
    <div className="stage-bg min-h-dvh">
      <main className="mx-auto flex min-h-dvh w-full max-w-[1280px] flex-col gap-8 px-4 py-5 sm:px-8">
        <AppNav match={matchId} />
        <h1 className="font-display text-[40px] font-bold leading-none sm:text-[52px]">
          {KIND_LABEL[kind]} recap
        </h1>

        <Toolbar kind={kind} persona={persona} lang={lang} onChange={go} />

        <div lang={lang} dir={rtl ? 'rtl' : 'ltr'} className="contents">
          {state.status === 'loading' && (
            <Loading slow={state.slow} preview={state.preview} codes={codes} />
          )}
          {state.status === 'failed' && (
            <div role="alert" className="max-w-[60ch]">
              <p className="text-[16px]">The recap did not load.</p>
              <p className="mt-1 text-[14px] text-muted">
                The gateway may still be starting. Try again in a few seconds.
              </p>
              <button
                className="mt-3 h-11 border border-amber px-4 text-[15px] font-medium text-amber"
                onClick={retry}
              >
                Try again
              </button>
            </div>
          )}
          {state.status === 'off' && <AgentsOff catchUp={state.catchUp} codes={codes} />}
          {recap && <Written recap={recap} catchUp={catchUp} codes={codes} />}
        </div>
      </main>
    </div>
  )
}

function Toolbar({
  kind,
  persona,
  lang,
  onChange,
}: {
  kind: RecapKind
  persona: string
  lang: string
  onChange: (patch: Record<string, string>) => void
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
      <Chips
        label="Recap"
        value={kind}
        options={KINDS.map((k) => ({ id: k, label: KIND_LABEL[k] }))}
        onPick={(id) => onChange({ kind: id })}
      />
      <ViewerChooser
        persona={persona}
        lang={lang}
        onChange={(patch) => onChange({ ...patch } as Record<string, string>)}
      />
    </div>
  )
}

function Chips({
  label,
  value,
  options,
  onPick,
}: {
  label: string
  value: string
  options: { id: string; label: string }[]
  onPick: (id: string) => void
}) {
  return (
    <div className="flex flex-wrap items-center gap-2" role="group" aria-label={label}>
      <span className="text-[13px] text-muted">{label}</span>
      <div className="flex flex-wrap gap-1">
        {options.map((o) => (
          <button
            key={o.id}
            aria-pressed={o.id === value}
            onClick={() => o.id !== value && onPick(o.id)}
            className={`h-9 min-w-9 border px-3 text-[14px] font-medium ${
              o.id === value
                ? 'border-amber text-amber'
                : 'border-white/30 text-muted hover:text-text'
            }`}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  )
}

/** Native share sheet where there is one (phones), a copied link everywhere else. */
function ShareButton({ text, title }: { text: string; title: string }) {
  const [note, setNote] = useState('')
  const share = async () => {
    try {
      if (navigator.share) {
        await navigator.share({
          title,
          text: text.split('\n').slice(0, 2).join('\n'),
          url: window.location.href,
        })
        return
      }
      await navigator.clipboard.writeText(text)
      setNote('Copied. Paste it anywhere.')
    } catch {
      // Dismissing the share sheet throws; that is not an error worth showing.
      if (!navigator.share) setNote('Could not copy. Copy the address bar instead.')
    }
  }
  return (
    <div className="flex items-center gap-3">
      <button
        className="h-9 border border-white/35 px-4 text-[14px] font-medium text-text hover:border-amber"
        onClick={share}
      >
        Share this recap
      </button>
      <span role="status" className="text-[13px] text-muted">
        {note}
      </span>
    </div>
  )
}

function Loading({
  slow,
  preview,
  codes,
}: {
  slow: boolean
  preview: CatchUp | null
  codes: Codes
}) {
  return (
    <>
      {preview && <Scoreline codes={codes} score={preview.score} clock={preview.clock} />}
      <div className={`grid gap-10 ${LAYOUT}`}>
        <div className="flex flex-col gap-4" role="status">
          <p className="font-display text-[34px] font-semibold leading-none">Writing the recap</p>
          <div className="flex max-w-[62ch] flex-col gap-3" aria-hidden>
            {[92, 100, 84, 96, 60].map((w, i) => (
              <span
                key={i}
                className="pulse-soft block h-4 bg-white/[0.07]"
                style={{ width: `${w}%` }}
              />
            ))}
          </div>
          {slow && (
            <p className="max-w-[62ch] text-[14px] text-muted">
              The first recap for a match takes about 15 seconds while the Verifier checks every
              number. After that it opens straight away.
            </p>
          )}
        </div>
        {preview && <MomentsTimeline catchUp={preview} />}
      </div>
    </>
  )
}

function AgentsOff({ catchUp, codes }: { catchUp: CatchUp | null; codes: Codes }) {
  return (
    <div className={`grid gap-10 ${LAYOUT}`}>
      <div className="flex max-w-[62ch] flex-col gap-4">
        <p role="status" className="bg-amber/10 px-3 py-2 text-[14px]">
          The agents are switched off on this gateway, so there is no written recap. This is what
          the numbers say.
        </p>
        {catchUp && (
          <>
            <Scoreline codes={codes} score={catchUp.score} clock={catchUp.clock} />
            <p className="text-[18px] leading-relaxed">{catchUp.summary}</p>
          </>
        )}
      </div>
      {catchUp && <MomentsTimeline catchUp={catchUp} />}
    </div>
  )
}

type Codes = { home: string; away: string } | null

function Written({
  recap,
  catchUp,
  codes,
}: {
  recap: RecapData
  catchUp: CatchUp | null
  codes: Codes
}) {
  const { facts, output } = recap
  const colours = clubColours(facts.home, facts.away, codes)
  const score: Record<string, number> = {}
  if (codes) {
    score[codes.home] = facts.teams[facts.home]?.goals ?? 0
    score[codes.away] = facts.teams[facts.away]?.goals ?? 0
  }
  return (
    <>
      <Scoreline
        codes={codes}
        score={score}
        clock={footballMinute(facts.minute_reached)}
        action={
          <ShareButton
            title={output.headline}
            text={shareText(output.headline, facts.score, window.location.href)}
          />
        }
      />

      <div className={`grid gap-10 lg:gap-14 ${LAYOUT}`}>
        <article className="flex flex-col gap-6">
          <h2 className="font-display text-[40px] font-bold leading-[0.98] sm:text-[56px]">
            {output.headline}
          </h2>
          <div className="flex flex-col gap-4 text-[18px] leading-[1.6] text-text/90">
            {output.paragraphs.map((p, i) => (
              <p key={i}>{p}</p>
            ))}
          </div>

          <section aria-labelledby="hl-h" className="mt-2 flex flex-col gap-3">
            <h3 id="hl-h" className="font-display text-[30px] font-semibold leading-none">
              Highlights in 60 seconds
            </h3>
            <ol className="flex list-decimal flex-col gap-2.5 ps-6 text-[17px] leading-snug marker:font-display marker:text-amber">
              {output.highlights.map((h, i) => (
                <li key={i}>{h}</li>
              ))}
            </ol>
          </section>

          <Provenance recap={recap} />
        </article>

        <aside className="flex flex-col gap-10">
          <StatBars facts={facts} homeColour={colours.home} awayColour={colours.away} />
          {facts.leaders.length > 0 && <Leaders recap={recap} />}
        </aside>
      </div>

      {catchUp && <MomentsTimeline catchUp={catchUp} wide />}
    </>
  )
}

function Leaders({ recap }: { recap: RecapData }) {
  return (
    <section aria-labelledby="leaders-h" className="flex flex-col gap-3">
      <h2 id="leaders-h" className="font-display text-[30px] font-semibold leading-none">
        Match leaders
      </h2>
      <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-2">
        {recap.facts.leaders.map((l) => (
          <div key={l.metric} className="contents">
            <dt className="text-[14px]">
              <span className="text-muted">{leaderLabel(l.metric)}</span>
              <span className="block text-[16px]">{l.player}</span>
            </dt>
            <dd className="num m-0 self-center text-end text-[24px] leading-none" dir="ltr">
              {leaderValue(l.metric, l.value)}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

/** Where the words came from and whether the numbers were checked. Judges read this. */
function Provenance({ recap }: { recap: RecapData }) {
  const checked = recap.status === 'verified'
  const translated = recap.lang !== 'en'
  const note = TRANSLATION_NOTE[recap.translation]
  // The Verifier reads the English draft. Once it is translated, say exactly what was checked.
  const checkedText = translated
    ? 'Every number was checked against the match data in the English version, before translation.'
    : 'Every number in this recap was checked against the match data.'
  return (
    // Small print is always English, so it sets its own direction inside a right-to-left page.
    <div className="flex flex-col gap-2 text-[14px]" dir="auto">
      <p dir="auto" className={`flex gap-1.5 ${checked ? 'text-control' : 'text-amber'}`}>
        {checked ? <CheckIcon className="mt-1 size-3" /> : <AlertIcon className="mt-1 size-3" />}
        {checked
          ? checkedText
          : 'The writer was unavailable, so this is a plain recap built from the numbers.'}
      </p>
      {note && (
        <p dir="auto" className="text-muted">
          {note}
        </p>
      )}
      {recap.trail.length > 0 && (
        <details dir="auto" className="text-muted">
          <summary className="min-h-8 cursor-pointer underline decoration-white/25 underline-offset-4">
            How it was checked
          </summary>
          <ol className="mt-2 list-decimal ps-5">
            {recap.trail.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ol>
        </details>
      )}
    </div>
  )
}

function clubColours(home: string, away: string, codes: Codes): { home: string; away: string } {
  const byName = (name: string) => Object.values(CLUBS).find((c) => c.name === name)
  return {
    home: byName(home)?.primary_color ?? CLUBS[codes?.home ?? '']?.primary_color ?? '#9aa5b1',
    away: byName(away)?.primary_color ?? CLUBS[codes?.away ?? '']?.primary_color ?? '#9aa5b1',
  }
}

/** The result as a broadcast score: codes and goals large, names small, the clock reached. */
function Scoreline({
  codes,
  score,
  clock,
  action,
}: {
  codes: Codes
  score: Record<string, number>
  clock: string
  /** Sits at the far end of the row, level with the score. */
  action?: ReactNode
}) {
  if (!codes) return null
  const home = CLUBS[codes.home]
  const away = CLUBS[codes.away]
  return (
    <div className="flex flex-wrap items-end gap-x-8 gap-y-3" dir="ltr">
      <div className="flex items-stretch gap-3">
        <span className="w-[6px]" style={{ background: home?.primary_color }} />
        <div>
          <p className="text-[14px] text-muted">{home?.name}</p>
          <p className="num text-[72px] font-bold leading-[0.9] sm:text-[96px]">
            {score[codes.home] ?? 0}
          </p>
        </div>
      </div>
      <div className="flex items-stretch gap-3">
        <span className="w-[6px]" style={{ background: away?.primary_color }} />
        <div>
          <p className="text-[14px] text-muted">{away?.name}</p>
          <p className="num text-[72px] font-bold leading-[0.9] sm:text-[96px]">
            {score[codes.away] ?? 0}
          </p>
        </div>
      </div>
      <p className="num pb-2 text-[28px] leading-none text-amber">{clock}</p>
      {action && <div className="pb-2 sm:ms-auto">{action}</div>}
    </div>
  )
}
