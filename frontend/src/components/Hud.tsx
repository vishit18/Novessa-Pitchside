import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import { CLUBS, PLAYERS } from '@/data/league'
import { lateness } from '@/core/overlays'
import { clock, setDelay } from '@/state/runtime'
import { useStore } from '@/state/store'
import type { OverlayEnvelope } from '@/types/overlay'

const colour = (code: string) => CLUBS[code]?.primary_color ?? '#9aa5b1'

/** Score, clock and momentum. Top-left, like a TV score bug. */
export function ScoreBug() {
  const meta = useStore((s) => s.meta)
  const snap = useStore((s) => s.snapshot)
  if (!meta) return null
  const home = meta.home.code
  const away = meta.away.code
  const m = snap?.momentum ?? 0
  const lead = m === 0 ? null : m > 0 ? home : away
  const half = (snap?.period ?? 1) === 1 ? '1st half' : '2nd half'
  return (
    <div className="w-[min(100%,360px)] select-none" role="group" aria-label="Score and momentum">
      <div className="panel flex items-stretch overflow-hidden rounded-[3px]">
        <Side code={home} score={snap?.score[home] ?? 0} align="left" />
        <div className="flex min-w-[88px] flex-col items-center justify-center border-x border-hairline px-3">
          <span
            className="num text-[26px] font-semibold leading-none text-amber"
            aria-label="Match clock"
          >
            {snap?.clock ?? '00:00'}
          </span>
          <span className="mt-0.5 text-[11px] text-muted">{half}</span>
        </div>
        <Side code={away} score={snap?.score[away] ?? 0} align="right" />
      </div>
      <div
        className="mt-1.5 flex items-center gap-2"
        aria-label={`Momentum ${Math.abs(m)} to ${lead ?? 'neither side'}`}
      >
        <span className="num text-[11px] tracking-wider text-muted">{home}</span>
        <div className="relative h-[5px] flex-1 overflow-hidden rounded-full bg-hairline">
          <div className="absolute inset-y-0 left-1/2 w-px bg-muted/60" />
          <div
            className="absolute inset-y-0 transition-[left,width,background-color] duration-500 ease-out"
            style={{
              left: m >= 0 ? `${50 - m / 2}%` : '50%',
              width: `${Math.abs(m) / 2}%`,
              background: lead ? colour(lead) : 'transparent',
            }}
          />
        </div>
        <span className="num text-[11px] tracking-wider text-muted">{away}</span>
      </div>
    </div>
  )
}

function Side({ code, score, align }: { code: string; score: number; align: 'left' | 'right' }) {
  return (
    <div
      className={`flex flex-1 items-center gap-2.5 px-3 py-2 ${align === 'right' ? 'flex-row-reverse' : ''}`}
    >
      <span className="h-8 w-1.5 rounded-[1px]" style={{ background: colour(code) }} />
      <span className="font-display text-[22px] font-semibold leading-none tracking-wide">
        {code}
      </span>
      <span className="num text-[38px] font-bold leading-none" aria-label={`${code} score`}>
        {score}
      </span>
    </div>
  )
}

/** Hold the last lower third a moment so it can animate out. */
function useLowerThird(): OverlayEnvelope | null {
  const active = useStore((s) => s.active)
  return active.find((o) => o.slot === 'lower_third') ?? null
}

export function LowerThird() {
  const o = useLowerThird()
  const reduce = useReducedMotion()
  const dur = reduce ? 0.12 : 0.22
  return (
    <div className="pointer-events-none w-[min(100%,560px)]" aria-live="polite">
      <AnimatePresence mode="wait">
        {o && (
          <motion.div
            key={`${o.moment_id}-${o.kind}`}
            initial={{ opacity: 0, x: reduce ? 0 : -24 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: reduce ? 0 : -12 }}
            transition={{ duration: dur, ease: [0.25, 1, 0.5, 1] }}
          >
            {o.kind === 'shot_speed' ? <ShotSpeed o={o} /> : <Headline o={o} />}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function toneColour(tone: unknown): string {
  if (tone === 'card') return '#f5c542'
  return 'var(--color-amber)'
}

function Headline({ o }: { o: OverlayEnvelope }) {
  const head = String(o.payload['headline'] ?? '')
  const body = String(o.payload['body'] ?? '')
  const late = lateness(o)
  const team = String(o.payload['team'] ?? '')
  return (
    <div className="panel flex overflow-hidden rounded-[3px] shadow-[0_10px_30px_rgb(0_0_0/0.5)]">
      <span className="w-1.5 shrink-0" style={{ background: toneColour(o.payload['tone']) }} />
      <div className="min-w-0 px-4 py-2.5">
        <div className="flex items-center gap-2">
          {team && (
            <span
              className="size-2.5 shrink-0 rounded-[1px]"
              style={{ background: colour(team) }}
            />
          )}
          <span className="font-display text-[36px] font-bold leading-none">{head}</span>
        </div>
        <p className="mt-1 text-[14px] leading-snug text-muted">{body}</p>
        {late > 6 && <p className="mt-1 text-[12px] text-amber">Earlier</p>}
      </div>
    </div>
  )
}

function ShotSpeed({ o }: { o: OverlayEnvelope }) {
  const speed = Number(o.payload['speed_kmh'] ?? 0)
  const xg = o.payload['xg']
  const pid = String(o.payload['player_id'] ?? '')
  const outcome = String(o.payload['outcome'] ?? '')
  return (
    <div className="panel flex overflow-hidden rounded-[3px] shadow-[0_10px_30px_rgb(0_0_0/0.5)]">
      <span className="w-1.5 shrink-0 bg-amber" />
      <div className="flex items-end gap-4 px-4 py-2.5">
        <div className="num text-[56px] font-bold leading-[0.9] text-amber">
          <CountUp to={speed} />
          <span className="ml-1.5 text-[18px] font-medium text-muted">km/h</span>
        </div>
        <div className="pb-0.5">
          <div className="font-display text-[24px] font-semibold leading-none">
            {PLAYERS[pid]?.name ?? pid}’s shot
          </div>
          <div className="mt-1 text-[13px] text-muted">
            {typeof xg === 'number' ? `xG ${xg.toFixed(2)}, ` : ''}
            {outcome}
          </div>
        </div>
      </div>
    </div>
  )
}

/** Count up to a value over ~0.5 s. */
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
      <span className="h-4 w-[3px] bg-amber" />
      <span className="font-display text-[22px] font-semibold leading-none tracking-wide">
        Novessa <span className="text-muted">Pitchside</span>
      </span>
    </div>
  )
}

const SPEEDS = [1, 4, 10, 30]
const DELAYS = [0, 20, 40]

/** Transport and viewer-delay controls. Hidden until the pointer moves or focus lands inside. */
export function Controls() {
  const controls = useStore((s) => s.controls)
  const speed = useStore((s) => s.speed)
  const paused = useStore((s) => s.paused)
  const delayS = useStore((s) => s.delayS)
  const set = useStore((s) => s.set)
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
    'num h-8 min-w-9 rounded-[3px] border border-hairline px-2 text-[15px] font-semibold text-muted transition-colors hover:text-text aria-pressed:border-amber aria-pressed:text-amber'
  return (
    <div
      onFocusCapture={wake}
      className={`panel flex flex-wrap items-center justify-center gap-x-4 gap-y-2 rounded-[4px] px-3 py-2 transition-opacity duration-200 ${
        shown
          ? 'opacity-100'
          : 'pointer-events-none opacity-0 focus-within:pointer-events-auto focus-within:opacity-100'
      }`}
      role="toolbar"
      aria-label="Playback"
    >
      {controls && (
        <>
          <button
            className={btn}
            aria-pressed={paused}
            onClick={() => {
              controls.setPaused(!paused)
              set({ paused: !paused })
            }}
          >
            {paused ? 'Play' : 'Pause'}
          </button>
          <div className="flex items-center gap-1" role="group" aria-label="Replay speed">
            {SPEEDS.map((s) => (
              <button
                key={s}
                className={btn}
                aria-pressed={speed === s}
                onClick={() => {
                  controls.setSpeed(s)
                  set({ speed: s })
                }}
              >
                {s}x
              </button>
            ))}
          </div>
        </>
      )}
      <div className="flex items-center gap-1" role="group" aria-label="Stream delay">
        <span className="mr-1 text-[12px] text-muted">Stream delay</span>
        {DELAYS.map((d) => (
          <button key={d} className={btn} aria-pressed={delayS === d} onClick={() => setDelay(d)}>
            {d}s
          </button>
        ))}
      </div>
      <span className="num hidden text-[13px] text-muted sm:inline">
        {clock.lead.toFixed(1)}s behind live
      </span>
    </div>
  )
}

export function StatusPill() {
  const status = useStore((s) => s.status)
  const detail = useStore((s) => s.statusDetail)
  const kind = useStore((s) => s.sourceKind)
  const live = status === 'live'
  const label =
    status === 'live'
      ? 'Live'
      : status === 'connecting'
        ? 'Connecting'
        : status === 'reconnecting'
          ? 'Reconnecting'
          : 'Offline'
  return (
    <div className="panel flex items-center gap-2 rounded-full px-3 py-1" role="status">
      <span
        className={`size-2 rounded-full ${live ? 'bg-chaos' : 'bg-amber pulse-soft'}`}
        aria-hidden="true"
      />
      <span className="text-[12px] font-medium">{label}</span>
      {kind === 'mock' && <span className="text-[12px] text-muted">sample match</span>}
      {detail && !live && <span className="text-[11px] text-muted">{detail}</span>}
    </div>
  )
}
