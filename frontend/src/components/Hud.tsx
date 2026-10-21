import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { sentenceCase } from '@/core/headline'
import { useEffect, useRef, useState } from 'react'
import { CLUBS, PLAYERS } from '@/data/league'
import { lateness } from '@/core/overlays'
import { Timeline } from '@/components/Timeline'
import { outcomeLabel } from '@/i18n/strings'
import { metricName } from '@/i18n/strings.more'
import { useSession, useSessionState, useT } from '@/state/useSession'
import type { OverlayEnvelope } from '@/types/overlay'

const colour = (code: string) => CLUBS[code]?.primary_color ?? '#9aa5b1'

/** Score, clock and momentum, top-left. Momentum is the lit line along the bottom edge. */
export function ScoreBug({ showMatchLine = true }: { showMatchLine?: boolean }) {
  const meta = useSessionState((s) => s.meta)
  const snap = useSessionState((s) => s.snapshot)
  const t = useT()
  const flash = useScoreFlash(snap ? Object.values(snap.score).reduce((a, b) => a + b, 0) : 0)
  if (!meta) return null
  const home = meta.home.code
  const away = meta.away.code
  const m = snap?.momentum ?? 0
  const lead = m === 0 ? null : m > 0 ? home : away
  const half = t((snap?.period ?? 1) === 1 ? 'firstHalf' : 'secondHalf')
  return (
    <div className="w-[min(100%,380px)] select-none" role="group" aria-label="Score and momentum">
      <div
        className="plate-shadow transition-[filter] duration-300"
        style={flash ? { filter: 'drop-shadow(0 0 18px rgb(255 176 32 / 0.85))' } : undefined}
      >
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
            {/* Half the bar each way from the centre line, scaled rather than resized. */}
            <div
              className="absolute inset-y-0 w-1/2 transition-transform duration-300 ease-[var(--ease-out)]"
              style={{
                left: m >= 0 ? '0%' : '50%',
                transformOrigin: m >= 0 ? 'right' : 'left',
                transform: `scaleX(${Math.abs(m) / 100})`,
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

/** True for a moment after the total score goes up, so the score bug can light up. */
function useScoreFlash(total: number): boolean {
  const [flash, setFlash] = useState(false)
  const last = useRef(total)
  useEffect(() => {
    if (total > last.current) {
      setFlash(true)
      const id = window.setTimeout(() => setFlash(false), 1400)
      last.current = total
      return () => window.clearTimeout(id)
    }
    last.current = total
  }, [total])
  return flash
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
          transition={{ duration: reduce ? 0.1 : 0.28, ease: [0.25, 1, 0.5, 1] }}
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
            exit={{ opacity: 0, transition: { duration: reduce ? 0.12 : 0.15 } }}
            transition={{ duration: reduce ? 0.12 : 0.28, ease: [0.25, 1, 0.5, 1] }}
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

/**
 * A story beat. Analysts get tighter type and the numbers behind it as chips; a First match
 * viewer gets a bigger headline and no more than two lines of body.
 */
function Headline({ o }: { o: OverlayEnvelope }) {
  const lang = useSessionState((s) => s.profile.lang)
  const persona = useSessionState((s) => s.profile.persona)
  const head = String(o.payload['headline'] ?? '')
  const body = String(o.payload['body'] ?? '')
  const late = lateness(o)
  const t = useT()
  const analyst = persona === 'analyst'
  const kids = persona === 'kids'
  const evidence = analyst ? o.provenance.evidence.slice(0, 4) : []
  const headSize = analyst
    ? 'text-[24px] sm:text-[34px]'
    : kids
      ? 'text-[34px] sm:text-[52px]'
      : 'text-[28px] sm:text-[42px]'
  const bodySize = analyst
    ? 'max-w-[68ch] text-[15px] sm:text-[17px]'
    : kids
      ? 'line-clamp-2 max-w-[44ch] text-[18px] sm:text-[22px]'
      : 'max-w-[56ch] text-[16px] sm:text-[20px]'
  return (
    <div className="flex">
      <span className="w-[7px] shrink-0" style={{ background: toneColour(o) }} />
      <div className="min-w-0 py-3 pr-8 pl-4">
        <div className={`font-display font-bold leading-[0.95] ${headSize}`}>
          {sentenceCase(head, lang)}
        </div>
        <p className={`mt-1.5 leading-snug text-text/80 ${bodySize}`}>{body}</p>
        {evidence.length > 0 && (
          <ul className="mt-2 flex flex-wrap gap-1.5" aria-label={t('askHow')}>
            {evidence.map((e) => (
              <li
                key={e.metric}
                className="flex items-baseline gap-1.5 border border-white/15 bg-black/30 px-2 py-0.5 text-[13px] text-muted"
              >
                {metricName(lang, e.metric)}
                <span className="num text-[15px] font-semibold text-text" dir="ltr">
                  {formatEvidence(e.metric, e.value)}
                </span>
              </li>
            ))}
          </ul>
        )}
        {late > 6 && <p className="mt-1 text-[12px] text-amber">{t('earlier')}</p>}
      </div>
    </div>
  )
}

function formatEvidence(metric: string, v: number): string {
  if (metric.startsWith('xg')) return v.toFixed(2)
  return Number.isInteger(v) ? String(v) : v.toFixed(1)
}

/** First match: which team has the ball, in words, so the arrow on the pitch has a caption. */
export function BallChip() {
  const persona = useSessionState((s) => s.profile.persona)
  const team = useSessionState((s) => s.carrierTeam)
  const t = useT()
  if (persona !== 'kids' || !team) return null
  return (
    <div className="plate-shadow w-fit">
      <p
        className="plate flex items-center gap-2.5 py-2 pr-4 pl-2.5 text-[18px] font-semibold"
        style={{ ['--cut' as string]: '8px' }}
      >
        <span className="h-6 w-[6px]" style={{ background: colour(team) }} aria-hidden />
        {t('hasBall', { club: CLUBS[team]?.name ?? team })}
      </p>
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

const DELAYS = [0, 20, 40]

/**
 * The timeline (play, skip, drag, speed) and the viewer's stream delay. Hidden until the pointer
 * moves or focus lands inside, and always shown while paused. `transport` off hides play, skip
 * and speed, for views that share one transport across panes.
 */
export function Controls({ transport = true }: { transport?: boolean }) {
  const session = useSession()
  const t = useT()
  const controls = useSessionState((s) => s.controls)
  const paused = useSessionState((s) => s.paused)
  const delayS = useSessionState((s) => s.delayS)
  const [awake, setAwake] = useState(false)
  const timer = useRef<number | undefined>(undefined)
  const wake = () => {
    setAwake(true)
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setAwake(false), 3000)
  }
  useEffect(() => {
    window.addEventListener('pointermove', wake)
    window.addEventListener('pointerdown', wake)
    window.addEventListener('keydown', wake)
    return () => {
      window.removeEventListener('pointermove', wake)
      window.removeEventListener('pointerdown', wake)
      window.removeEventListener('keydown', wake)
      window.clearTimeout(timer.current)
    }
  }, [])
  const shown = awake || paused
  const btn =
    'num h-9 min-w-9 border border-white/25 px-2 text-[15px] font-semibold text-muted transition-colors hover:text-text aria-pressed:border-amber aria-pressed:text-amber'
  return (
    <div
      onFocusCapture={wake}
      onPointerMove={wake}
      className={`plate-shadow w-full max-w-[1100px] transition-opacity duration-200 ${
        shown
          ? 'opacity-100'
          : 'pointer-events-none opacity-0 focus-within:pointer-events-auto focus-within:opacity-100'
      }`}
    >
      <div
        className="plate flex flex-col gap-2 px-4 py-2.5"
        style={{ ['--cut' as string]: '10px' }}
        role="toolbar"
        aria-label="Playback"
      >
        {controls && <Timeline transport={transport} />}
        <div className="flex flex-wrap items-center justify-end gap-x-4 gap-y-1">
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
    </div>
  )
}

/**
 * Connection and playback in one word. "Live" only when connected at normal speed and playing;
 * a viewer at 4x or paused is watching a replay and is told so.
 */
export function StatusPill() {
  const status = useSessionState((s) => s.status)
  const detail = useSessionState((s) => s.statusDetail)
  const speed = useSessionState((s) => s.speed)
  const paused = useSessionState((s) => s.paused)
  const t = useT()
  const connected = status === 'live'
  const live = connected && !paused && speed === 1
  const label = connected
    ? paused
      ? t('pausedLabel')
      : speed === 1
        ? t('live')
        : `${t('replay')} ${speed}x`
    : t(
        status === 'connecting'
          ? 'connecting'
          : status === 'reconnecting'
            ? 'reconnecting'
            : 'offline',
      )
  return (
    <div className="flex items-center gap-2" role="status">
      <span
        className={`size-2.5 rounded-full ${live ? 'bg-chaos shadow-[0_0_10px_var(--color-chaos)]' : connected ? 'bg-white/60' : 'bg-amber pulse-soft'}`}
        aria-hidden="true"
      />
      <span className="font-display text-[18px] font-semibold leading-none">{label}</span>
      {detail && !connected && <span className="text-[13px] text-muted">{detail}</span>}
    </div>
  )
}

/**
 * Shown over the pitch while the feed connects. The pitch behind it is lit and lined up, so the
 * screen reads as "about to start" rather than broken. After a few seconds it says why it is slow.
 */
export function KickOffCard({ compact = false }: { compact?: boolean }) {
  const meta = useSessionState((s) => s.meta)
  const t = useT()
  const [slow, setSlow] = useState(false)
  useEffect(() => {
    const id = window.setTimeout(() => setSlow(true), 6000)
    return () => window.clearTimeout(id)
  }, [])
  const home = meta ? CLUBS[meta.home.code]?.name : null
  const away = meta ? CLUBS[meta.away.code]?.name : null
  return (
    <div
      className={`pointer-events-none absolute inset-x-0 bottom-[22%] flex justify-center px-4 ${compact ? 'hud-compact' : ''}`}
    >
      <div className="plate-shadow w-[min(100%,580px)]" role="status">
        <div className="plate overflow-hidden" style={{ ['--cut' as string]: '14px' }}>
          <div className="px-6 pb-4 pt-4">
            {home && away && (
              <p className="font-display text-[30px] font-bold leading-none sm:text-[36px]">
                {home} <span className="text-muted">v</span> {away}
              </p>
            )}
            <p className="mt-2 text-[16px] text-text/90">{t('settingUp')}</p>
            {slow && <p className="mt-1 text-[14px] text-muted">{t('warmingUp')}</p>}
          </div>
          <div className="relative h-[3px] overflow-hidden bg-black/40" aria-hidden="true">
            <div className="kickoff-bar absolute inset-y-0 w-1/3 bg-amber" />
          </div>
        </div>
      </div>
    </div>
  )
}

const READOUT: Record<string, { label: string; unit: string; digits: number }> = {
  sprint_speed: { label: 'Fastest sprint', unit: 'km/h', digits: 1 },
  shot_speed: { label: 'Hardest shot', unit: 'km/h', digits: 1 },
  pass_difficulty: { label: 'Hardest pass', unit: 'out of 100', digits: 0 },
  distance: { label: 'Furthest run', unit: 'km', digits: 2 },
}

/**
 * One-number mode: the viewer's chosen measure, always on screen. Overlays for that measure
 * come and go as they happen; this is the running leader, so there is a number to look at in
 * between.
 */
export function MetricReadout() {
  const metric = useSessionState((s) => s.profile.metric)
  const stats = useSessionState((s) => s.playerStats)
  if (!metric || !READOUT[metric]) return null
  const spec = READOUT[metric]
  const lead = stats?.leaders[metric as keyof typeof stats.leaders]
  const team = lead ? lead.player_id.split('-')[0] : ''
  return (
    <div className="w-[min(100%,380px)] select-none" role="group" aria-label={spec.label}>
      <div className="plate-shadow">
        <div className="plate flex items-stretch" style={{ ['--cut' as string]: '10px' }}>
          <span
            className="w-[6px] shrink-0"
            style={{ background: team ? colour(team) : 'transparent' }}
          />
          <div className="min-w-0 py-2.5 pl-3 pr-4">
            <p className="text-[14px] text-muted">{spec.label} so far</p>
            {lead ? (
              <>
                <p className="num text-[44px] font-bold leading-[0.95] text-amber" dir="ltr">
                  {lead.value.toFixed(spec.digits)}
                  <span className="ml-2 text-[16px] font-medium text-muted">{spec.unit}</span>
                </p>
                <p className="mt-1 text-[16px] text-text/90">
                  {PLAYERS[lead.player_id]?.name ?? lead.player_id}
                </p>
              </>
            ) : (
              <p className="mt-1 text-[16px] text-muted">Waiting for the first one</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
