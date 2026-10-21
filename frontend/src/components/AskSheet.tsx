import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { CLUBS, PLAYERS } from '@/data/league'
import { ApiError, askAnalyst, type AskAnswer } from '@/net/api'
import { MicButton } from './MicButton'
import { isRtl } from '@/state/profile'
import { useSession, useSessionState, useT } from '@/state/useSession'

type State =
  | { kind: 'idle' }
  | { kind: 'asking'; question: string; since: number }
  | { kind: 'answered'; answer: AskAnswer }
  | { kind: 'failed'; question: string }

const MAX = 280

/**
 * Ask the Analyst. The viewer types a question; the gateway's Scout picks lookups, code runs them
 * up to this viewer's clock, the Analyst answers and the Verifier checks every number. The panel
 * shows the answer, whether it was checked, and the numbers behind it. With Speech on, the viewer
 * can hold the mic and say the question instead (MicButton).
 *
 * `placement` is "side" on the broadcast (a panel over the right of the pitch) and "bottom" on
 * the phone view (a sheet from the bottom edge).
 */
export function AskSheet({
  open,
  onClose,
  placement = 'side',
}: {
  open: boolean
  onClose: () => void
  placement?: 'side' | 'bottom'
}) {
  const session = useSession()
  const t = useT()
  const profile = useSessionState((s) => s.profile)
  const now = useSessionState((s) => s.t)
  const reduce = useReducedMotion()
  const [state, setState] = useState<State>({ kind: 'idle' })
  const [text, setText] = useState('')
  const input = useRef<HTMLTextAreaElement>(null)
  const panel = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const id = window.setTimeout(() => input.current?.focus(), 50)
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => {
      window.clearTimeout(id)
      window.removeEventListener('keydown', onKey)
    }
  }, [open, onClose])

  const subject = profile.player
    ? PLAYERS[profile.player]?.name
    : profile.club
      ? CLUBS[profile.club]?.name
      : null
  const suggestions = [t('askQ1'), t('askQ2', { name: subject ?? 'Tobias Wragg' }), t('askQ3')]

  const send = async (question: string) => {
    const q = question.trim().slice(0, MAX)
    if (!q || state.kind === 'asking') return
    setState({ kind: 'asking', question: q, since: performance.now() })
    try {
      const answer = await askAnalyst(session.opts.matchId, {
        question: q,
        t: Math.max(0, now),
        persona: profile.persona,
        lang: profile.lang,
      })
      setState({ kind: 'answered', answer })
      setText('')
    } catch (err) {
      setState({ kind: 'failed', question: q })
      if (!(err instanceof ApiError)) console.warn('ask failed', err)
    }
  }
  const submit = (e: FormEvent) => {
    e.preventDefault()
    void send(text)
  }

  const side = placement === 'side'
  const rtl = isRtl(profile.lang)
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          ref={panel}
          role="dialog"
          aria-modal="false"
          aria-labelledby="ask-title"
          lang={profile.lang}
          dir={rtl ? 'rtl' : 'ltr'}
          className={
            side
              ? 'absolute inset-y-4 end-4 z-40 flex w-[min(440px,calc(100%-2rem))] flex-col'
              : 'fixed inset-x-0 bottom-0 z-40 mx-auto flex max-h-[85dvh] w-full max-w-[560px] flex-col'
          }
          initial={reduce ? { opacity: 0 } : side ? { x: 24, opacity: 0 } : { y: 40, opacity: 0 }}
          animate={{ x: 0, y: 0, opacity: 1 }}
          exit={{ opacity: 0, transition: { duration: 0.15 } }}
          transition={{ duration: 0.22, ease: [0.25, 1, 0.5, 1] }}
        >
          <div className="plate-shadow flex min-h-0 flex-1 flex-col">
            <div
              className="plate flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-5"
              style={{ ['--cut' as string]: '16px', background: 'var(--color-raised)' }}
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 id="ask-title" className="font-display text-[30px] font-bold leading-none">
                    {t('askTitle')}
                  </h2>
                  <p className="mt-1.5 text-[13px] text-muted">
                    {t('askUpTo', {
                      clock: clockOf(state, session.store.getState().snapshot?.clock),
                    })}
                  </p>
                </div>
                <button
                  className="grid size-9 shrink-0 place-items-center border border-white/25 text-muted hover:text-text"
                  onClick={onClose}
                  aria-label={t('askClose')}
                >
                  <svg viewBox="0 0 12 12" className="size-3" aria-hidden>
                    <path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" strokeWidth="1.6" />
                  </svg>
                </button>
              </div>

              {state.kind === 'answered' && <Answer a={state.answer} />}
              {state.kind === 'asking' && <Working question={state.question} since={state.since} />}
              {state.kind === 'failed' && (
                <div role="alert" className="flex flex-col gap-2">
                  <p className="text-[15px] text-text/80">“{state.question}”</p>
                  <p className="text-[16px]">{t('askOff')}</p>
                  <button
                    className="self-start border border-amber px-3 py-1.5 text-[14px] text-amber"
                    onClick={() => void send(state.question)}
                  >
                    {t('retry')}
                  </button>
                </div>
              )}

              {state.kind !== 'asking' && (
                <>
                  {state.kind === 'idle' && (
                    <ul className="flex flex-col gap-1.5" aria-label="Suggested questions">
                      {suggestions.map((q) => (
                        <li key={q}>
                          <button
                            className="w-full border border-white/15 px-3 py-2.5 text-start text-[15px] leading-snug text-text/90 transition-colors hover:border-amber/60 hover:text-text"
                            onClick={() => void send(q)}
                          >
                            {q}
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                  <form onSubmit={submit} className="mt-auto flex flex-col gap-2">
                    <label htmlFor="ask-input" className="sr-only">
                      {t('askPlaceholder')}
                    </label>
                    <textarea
                      id="ask-input"
                      ref={input}
                      value={text}
                      maxLength={MAX}
                      rows={2}
                      placeholder={state.kind === 'answered' ? t('askAgain') : t('askPlaceholder')}
                      onChange={(e) => setText(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault()
                          void send(text)
                        }
                      }}
                      className="w-full resize-none border border-white/30 bg-ink/80 px-3 py-2.5 text-[16px] text-text placeholder:text-muted focus-visible:border-amber focus-visible:outline-none"
                    />
                    <div className="flex items-center justify-between gap-3">
                      <MicButton
                        matchId={session.opts.matchId}
                        lang={profile.lang}
                        onText={(heard) => {
                          setText(heard)
                          void send(heard)
                        }}
                      />
                      <button
                        type="submit"
                        disabled={!text.trim()}
                        className="ms-auto h-11 shrink-0 bg-amber px-5 text-[15px] font-semibold text-ink transition-opacity disabled:opacity-40"
                      >
                        {t('askSend')}
                      </button>
                    </div>
                  </form>
                </>
              )}
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

function clockOf(state: State, live: string | undefined): string {
  return state.kind === 'answered' ? state.answer.clock : (live ?? '00:00')
}

/** While the agents work: the question, an honest description and a seconds counter. */
function Working({ question, since }: { question: string; since: number }) {
  const t = useT()
  const [secs, setSecs] = useState(0)
  useEffect(() => {
    const id = window.setInterval(() => setSecs((performance.now() - since) / 1000), 250)
    return () => window.clearInterval(id)
  }, [since])
  return (
    <div role="status" className="flex flex-col gap-3">
      <p className="text-[17px] font-medium">“{question}”</p>
      <p className="flex items-center gap-3 text-[15px] text-text/80">
        <span className="pulse-soft size-2 rounded-full bg-amber" aria-hidden />
        {t('askWorking')}
        <span className="num text-muted" dir="ltr">
          {secs.toFixed(0)}s
        </span>
      </p>
    </div>
  )
}

const TOOL_LABEL: Record<string, string> = {
  state_now: 'Match state',
  player: 'Player stats',
  team_recent: 'Team, recent minutes',
  compare: 'Then versus now',
  leaders: 'Leaders',
  moments: 'Key moments',
}

function Answer({ a }: { a: AskAnswer }) {
  const t = useT()
  const [how, setHow] = useState(false)
  const tone =
    a.status === 'verified'
      ? { strip: 'bg-control', label: t('askChecked') }
      : a.status === 'numbers_only'
        ? { strip: 'bg-amber', label: t('askNumbersOnly') }
        : { strip: 'bg-white/30', label: t('askDeclined') }
  return (
    <article className="flex flex-col gap-3" aria-live="polite">
      <p className="text-[15px] text-muted">“{a.question}”</p>
      <div className="flex gap-3">
        <span className={`w-[4px] shrink-0 ${tone.strip}`} aria-hidden />
        <div className="min-w-0">
          <p className="text-[18px] leading-relaxed">{a.answer}</p>
          <p className="mt-2 flex items-center gap-1.5 text-[13px] text-muted">
            {a.status === 'verified' && (
              <svg viewBox="0 0 12 12" className="size-3 text-control" aria-hidden>
                <path d="M2 6.5 5 9l5-6" fill="none" stroke="currentColor" strokeWidth="1.8" />
              </svg>
            )}
            {tone.label}
          </p>
        </div>
      </div>
      {(a.evidence.length > 0 || a.notes.length > 0) && (
        <div>
          <button
            className="text-[14px] text-muted underline decoration-white/25 underline-offset-4 hover:text-text"
            aria-expanded={how}
            onClick={() => setHow(!how)}
          >
            {t('askHow')}
          </button>
          {how && (
            <div
              className="mt-3 flex flex-col gap-3 border-t border-hairline pt-3"
              lang="en"
              dir="ltr"
            >
              <p className="flex flex-wrap gap-1.5">
                {a.tools.map((tool, i) => (
                  <span
                    key={`${tool}-${i}`}
                    className="bg-white/[0.06] px-2 py-0.5 text-[12px] text-text/80"
                  >
                    {TOOL_LABEL[tool] ?? tool}
                  </span>
                ))}
              </p>
              <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1.5 text-[13px]">
                {a.evidence.map((r) => (
                  <div key={r.key} className="contents">
                    <dt className="text-text/75">{r.label}</dt>
                    <dd className="num m-0 text-end text-[15px]">{r.value}</dd>
                  </div>
                ))}
              </dl>
              {a.notes.length > 0 && (
                <ul className="flex flex-col gap-1 text-[13px] text-text/75">
                  {a.notes.map((n) => (
                    <li key={n}>{n}</li>
                  ))}
                </ul>
              )}
              <ol className="flex flex-col gap-1 text-[12px] text-muted">
                {a.trail.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
            </div>
          )}
        </div>
      )}
    </article>
  )
}
