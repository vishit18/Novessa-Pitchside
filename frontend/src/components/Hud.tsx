import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import { CLUBS, PLAYERS } from '@/data/league'
import { lateness } from '@/core/overlays'
import { outcomeLabel } from '@/i18n/strings'
import { useSession, useSessionState, useT } from '@/state/useSession'
import type { OverlayEnvelope } from '@/types/overlay'

const colour = (code: string) => CLUBS[code]?.primary_color ?? '#9aa5b1'

/** Score, clock and momentum, top-left. Momentum is the lit line along the bottom edge. */
export function ScoreBug({ showMatchLine = true }: { showMatchLine?: boolean }) {
  const meta = useSessionState((s) => s.meta)
  const snap = useSessionState((s) => s.snapshot)
  const t = useT()
  if (!meta) return null
  const home = meta.home.code
  const away = meta.away.code
  const m = snap?.momentum ?? 0
  const lead = m === 0 ? null : m > 0 ? home : away
  const half = t((snap?.period ?? 1) === 1 ? 'firstHalf' : 'secondHalf')
  return (
    <div className="w-[min(100%,380px)] select-none" role="group" aria-label="Score and momentum">
      <div className="plate-shadow">
        <div className="plate relative">
          {/* Home on the left in every language, as on a real score bug. */}
          <div className="flex items-stretch" dir="ltr">
            <Side code={home} score={snap?.score[home] ?? 0} align="left" />
            <div className="flex min-w-[92px] flex-col items-center justify-center px-2 pb-1">
              <span
                className="num text-[28px] font-semibold leading-none text-amber"
                aria-label="Match clock"
              >
                {snap?.clock ?? '00:00'}
              </span>
              <span className="mt-0.5 text-[12px] text-muted">{half}</span>
            </div>
            <Side code={away} score={snap?.score[away] ?? 0} align="right" />
          </div>
          <div
            className="relative h-[4px] bg-black/40"
            role="img"
            aria-label={t('momentum', { v: Math.abs(m), team: lead ?? '-' })}
            dir="ltr"
          >
            <div className="absolute inset-y-0 left-1/2 w-px bg-white/30" />
            <div
              className="absolute inset-y-0 transition-[left,width] duration-500 ease-out"
              style={{
                left: m >= 0 ? `${50 - m / 2}%` : '50%',
                width: `${Math.abs(m) / 2}%`,
                background: lead ? colour(lead) : 'transparent',
                boxShadow: lead ? `0 0 10px ${colour(lead)}` : 'none',
              }}
            />
          </div>
        </div>
      </div>
      {showMatchLine && (
        <p className="mt-2 hidden text-[12px] text-muted sm:block">
          {t('matchLine', { competition: meta.competition, n: meta.matchday, venue: meta.venue })}
        </p>
      )}
    </div>
  )
}

function Side({ code, score, align }: { code: string; score: number; align: 'left' | 'right' }) {
  const right = align === 'right'
  return (
    <div
      className={`flex flex-1 items-center gap-2.5 py-2 ${right ? 'flex-row-reverse pr-3 pl-1' : 'pl-3 pr-1'}`}
    >
      <span className="h-9 w-[5px]" style={{ background: colour(code) }} />
      <span className="latin text-[24px] font-semibold leading-none">{code}</span>
      {/* Screen readers get the settled score; the rolling digit is decoration. */}
      <span className="sr-only" aria-label={`${code} score`}>
        {score}
      </span>
      <Digit value={score} />
    </div>
  )
}

/** The score digit rolls up when it changes. */
function Digit({ value }: { value: number }) {
  const reduce = useReducedMotion()
  return (
    <span
      className="relative inline-block h-[40px] w-[26px] overflow-hidden text-center"
      aria-hidden="true"
    >
      <AnimatePresence initial={false} mode="popLayout">
        <motion.span
          key={value}
          className="num absolute inset-0 text-[40px] font-bold leading-[40px]"
          initial={{ y: reduce ? 0 : 40, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: reduce ? 0 : -40, opacity: 0 }}
          transition={{ duration: reduce ? 0.1 : 0.35, ease: [0.25, 1, 0.5, 1] }}
        >
          {value}
        </motion.span>
      </AnimatePresence>
    </span>
  )
}

export function LowerThird() {
  const active = useSessionState((s) => s.active)
  const o = active.find((x) => x.slot === 'lower_third') ?? null
  const reduce = useReducedMotion()
  return (
    <div className="pointer-events-none w-[min(100%,640px)]" aria-live="polite">
      <AnimatePresence mode="wait">
        {o && (
          <motion.div
            key={`${o.moment_id}-${o.kind}`}
            initial={{ clipPath: 'inset(-20px 100% -20px 0)', opacity: reduce ? 0 : 1 }}
            animate={{ clipPath: 'inset(-20px -20px -20px 0)', opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: reduce ? 0.12 : 0.3, ease: [0.25, 1, 0.5, 1] }}
          >
            <div className="plate-shadow">
              <div className="plate" style={{ ['--cut' as string]: '18px' }}>
                {o.kind === 'shot_speed' ? <ShotSpeed o={o} /> : <Headline o={o} />}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

/** The strip down the left of a lower third: card colour for cards, else the team's kit. */
function toneColour(o: OverlayEnvelope): string {
  const card = o.payload['card']
  if (card === 'yellow') return '#f5c542'
  if (card === 'red') return 'var(--color-chaos)'
  const team = String(o.payload['team'] ?? '')
  return team ? colour(team) : 'var(--color-amber)'
}

function Headline({ o }: { o: OverlayEnvelope }) {
  const head = String(o.payload['headline'] ?? '')
  const body = String(o.payload['body'] ?? '')
  const late = lateness(o)
  const t = useT()
  return (
    <div className="flex">
      <span className="w-[7px] shrink-0" style={{ background: toneColour(o) }} />
      <div className="min-w-0 py-3 pr-8 pl-4">
        <div className="font-display text-[28px] sm:text-[42px] font-bold leading-[0.95]">
          {head}
        </div>
        <p className="mt-1.5 max-w-[56ch] text-[15px] leading-snug text-muted">{body}</p>
        {late > 6 && <p className="mt-1 text-[12px] text-amber">{t('earlier')}</p>}
      </div>
    </div>
  )
}

function ShotSpeed({ o }: { o: OverlayEnvelope }) {
  const speed = Number(o.payload['speed_kmh'] ?? 0)
  const xg = o.payload['xg']
  const pid = String(o.payload['player_id'] ?? '')
  const outcome = String(o.payload['outcome'] ?? '')
  const t = useT()
  const lang = useSessionState((s) => s.profile.lang)
  return (
    <div className="flex">
      <span className="w-[7px] shrink-0 bg-amber" />
      <div className="flex items-end gap-5 py-3 pr-9 pl-4">
        <div
          className="num text-[44px] sm:text-[64px] font-bold leading-[0.85] text-amber"
          dir="ltr"
        >
          <CountUp to={speed} />
          <span className="ml-2 text-[20px] font-medium text-muted">km/h</span>
        </div>
        <div className="pb-1">
          <div className="font-display text-[20px] sm:text-[26px] font-semibold leading-none">
            {t('shotBy', { name: PLAYERS[pid]?.name ?? pid })}
          </div>
          <div className="mt-1.5 text-[14px] text-muted">
            {typeof xg === 'number' ? `xG ${xg.toFixed(2)}, ` : ''}
            {outcomeLabel(lang, outcome)}
          </div>
        </div>
      </div>
    </div>
  )
}

/** Count up to a value over half a second. */
function CountUp({ to }: { to: number }) {
  const [v, setV] = useState(0)
  const reduce = useReducedMotion()
  useEffect(() => {
    if (reduce) {
      setV(to)
      return
    }
    const start = performance.now()
    let raf = 0
    const step = (now: number) => {
      const k = Math.min(1, (now - start) / 500)
      setV(to * (1 - Math.pow(1 - k, 3)))
      if (k < 1) raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [to, reduce])
  return <>{v.toFixed(0)}</>
}

export function Wordmark() {
  return (
    <div className="flex select-none items-center gap-2" aria-label="Novessa Pitchside">
      <span className="h-5 w-[4px] bg-amber" />
      <span className="font-display text-[24px] font-semibold leading-none tracking-wide">
        Novessa <span className="text-muted">Pitchside</span>
      </span>
    </div>
  )
}

const SPEEDS = [1, 4, 10, 30]
const DELAYS = [0, 20, 40]

/**
 * Transport and viewer-delay controls. Hidden until the pointer moves or focus lands inside.
 * `transport` off hides play and speed, for views that share one transport across panes.
 */
export function Controls({ transport = true }: { transport?: boolean }) {
  const session = useSession()
  const t = useT()
  const controls = useSessionState((s) => s.controls)
  const speed = useSessionState((s) => s.speed)
  const paused = useSessionState((s) => s.paused)
  const delayS = useSessionState((s) => s.delayS)
  const [shown, setShown] = useState(false)
  const timer = useRef<number | undefined>(undefined)
  const wake = () => {
    setShown(true)
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setShown(false), 3000)
  }
  useEffect(() => {
    window.addEventListener('pointermove', wake)
    window.addEventListener('keydown', wake)
    return () => {
      window.removeEventListener('pointermove', wake)
      window.removeEventListener('keydown', wake)
      window.clearTimeout(timer.current)
    }
  }, [])
  const btn =
    'num h-8 min-w-9 border border-white/15 px-2.5 text-[16px] font-semibold text-muted transition-colors hover:text-text aria-pressed:border-amber aria-pressed:text-amber'
  return (
    <div
      onFocusCapture={wake}
      className={`plate-shadow transition-opacity duration-200 ${
        shown
          ? 'opacity-100'
          : 'pointer-events-none opacity-0 focus-within:pointer-events-auto focus-within:opacity-100'
      }`}
    >
      <div
        className="plate flex flex-wrap items-center justify-center gap-x-5 gap-y-2 px-5 py-2.5"
        style={{ ['--cut' as string]: '10px' }}
        role="toolbar"
        aria-label="Playback"
      >
        {controls && transport && (
          <>
            <button
              className={btn}
              aria-pressed={paused}
              onClick={() => session.setPaused(!paused)}
            >
              {t(paused ? 'play' : 'pause')}
            </button>
            <div className="flex items-center gap-1" role="group" aria-label={t('replaySpeed')}>
              {SPEEDS.map((s) => (
                <button
                  key={s}
                  className={btn}
                  aria-pressed={speed === s}
                  onClick={() => session.setSpeed(s)}
                >
                  {s}x
                </button>
              ))}
            </div>
          </>
        )}
        <div className="flex items-center gap-1" role="group" aria-label={t('streamDelay')}>
          <span className="mr-1.5 text-[13px] text-muted">{t('streamDelay')}</span>
          {DELAYS.map((d) => (
            <button
              key={d}
              className={btn}
              aria-pressed={delayS === d}
              onClick={() => session.setDelay(d)}
            >
              {d}s
            </button>
          ))}
        </div>
        <span className="num hidden text-[14px] text-muted sm:inline">
          {t('behindLive', { s: session.clock.lead.toFixed(1) })}
        </span>
      </div>
    </div>
  )
}

export function StatusPill() {
  const status = useSessionState((s) => s.status)
  const detail = useSessionState((s) => s.statusDetail)
  const t = useT()
  const live = status === 'live'
  const label = t(
    status === 'live'
      ? 'live'
      : status === 'connecting'
        ? 'connecting'
        : status === 'reconnecting'
          ? 'reconnecting'
          : 'offline',
  )
  return (
    <div className="flex items-center gap-2" role="status">
      <span
        className={`size-2.5 rounded-full ${live ? 'bg-chaos shadow-[0_0_10px_var(--color-chaos)]' : 'bg-amber pulse-soft'}`}
        aria-hidden="true"
      />
      <span className="font-display text-[18px] font-semibold leading-none">{label}</span>
      {detail && !live && <span className="text-[13px] text-muted">{detail}</span>}
    </div>
  )
}
