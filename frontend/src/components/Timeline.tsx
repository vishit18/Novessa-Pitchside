import { useEffect, useRef, useState } from 'react'
import { CLUBS } from '@/data/league'
import { getKeyMoments, type KeyMoment, type KeyMoments } from '@/net/api'
import { useSession, useSessionState, useT } from '@/state/useSession'
import type { StringKey } from '@/i18n/strings'
import type { Session } from '@/state/session'

const SPEEDS = [1, 4, 10, 30]
const SKIP_S = 30
/** Used until the gateway says how long the match really is. */
const FALLBACK_DURATION = 96 * 60
const SPOILERS_KEY = 'pitchside.spoilers.v1'

/** A rough football clock for a match second, for the drag preview: 61', 45+2'. */
export function previewClock(t: number, halfTime: number | null): string {
  const half = halfTime ?? 47 * 60
  if (t <= half) {
    const m = Math.floor(t / 60)
    return m >= 45 ? `45+${m - 44}'` : `${m + 1}'`
  }
  const m = Math.floor((t - half) / 60) + 45
  return m >= 90 ? `90+${m - 89}'` : `${m + 1}'`
}

/** Which markers to draw: everything with spoilers on, otherwise only what has been watched. */
export function visibleMoments(all: KeyMoment[], seenUpTo: number, spoilers: boolean) {
  return spoilers ? all : all.filter((m) => m.t_match <= seenUpTo + 0.5)
}

function markerLabel(m: KeyMoment): StringKey {
  if (m.kind === 'card') return m.card === 'red' ? 'kind_red' : 'kind_yellow'
  return `kind_${m.kind}` as StringKey
}

function markerColour(m: KeyMoment): string {
  if (m.kind === 'card') return m.card === 'red' ? 'var(--color-red-card)' : '#f5c542'
  if (m.kind === 'goal') return CLUBS[m.team ?? '']?.primary_color ?? 'var(--color-amber)'
  return 'rgb(255 255 255 / 0.55)'
}

function loadSpoilers(): boolean {
  try {
    return window.localStorage.getItem(SPOILERS_KEY) === '1'
  } catch {
    return false
  }
}

/**
 * Play, skip, drag and speed for one viewer. Dragging previews the clock and seeks on release,
 * so a drag is one seek, not hundreds. Markers show goals and cards the viewer has already seen;
 * "Key moments" shows the rest of the match too, for someone who wants to jump to the goals.
 */
export function Timeline({
  transport = true,
  linked = [],
  narrow = false,
}: {
  transport?: boolean
  /** Phone layout: the bar on its own line, buttons below, no clock (the score bug has it). */
  narrow?: boolean
  /** Other viewers that follow this timeline: the split view drives both panes from one bar. */
  linked?: Session[]
}) {
  const session = useSession()
  const all = [session, ...linked]
  const t = useT()
  const now = useSessionState((s) => s.t)
  const seenUpTo = useSessionState((s) => s.seenUpTo)
  const paused = useSessionState((s) => s.paused)
  const speed = useSessionState((s) => s.speed)
  const clock = useSessionState((s) => s.snapshot?.clock ?? null)
  const [key, setKey] = useState<KeyMoments | null>(null)
  const [spoilers, setSpoilers] = useState(loadSpoilers)
  const [drag, setDragState] = useState<number | null>(null)
  // Mirrors `drag` for key-up and blur, which can fire before React has re-rendered with the
  // value the key-down set. Reading the state there missed the seek on a busy page.
  const dragRef = useRef<number | null>(null)
  const setDrag = (v: number | null) => {
    dragRef.current = v
    setDragState(v)
  }

  useEffect(() => {
    let live = true
    getKeyMoments(session.opts.matchId)
      .then((k) => live && setKey(k))
      .catch(() => undefined)
    return () => {
      live = false
    }
  }, [session])

  const duration = key?.duration ?? FALLBACK_DURATION
  const shown = drag ?? now
  const pct = (v: number) => `${Math.min(100, Math.max(0, (v / duration) * 100))}%`
  const commit = (v: number) => {
    setDrag(null)
    for (const s of all) s.seek(Math.min(duration - 1, Math.max(0, v)))
  }
  const toggleSpoilers = () => {
    const next = !spoilers
    setSpoilers(next)
    try {
      window.localStorage.setItem(SPOILERS_KEY, next ? '1' : '0')
    } catch {
      // Storage blocked: the choice lasts for this visit.
    }
  }
  const markers = visibleMoments(key?.moments ?? [], seenUpTo, spoilers)
  const btn =
    'num grid h-9 min-w-9 place-items-center border border-text/25 px-2 text-[15px] font-semibold text-muted transition-colors hover:text-text aria-pressed:border-amber aria-pressed:text-amber'

  return (
    <div className="flex w-full flex-wrap items-center gap-x-3 gap-y-2" dir="ltr">
      {transport && (
        <div className="flex items-center gap-1">
          <button
            className={`${btn} min-w-16 whitespace-nowrap`}
            aria-pressed={paused}
            onClick={() => all.forEach((s) => s.setPaused(!paused))}
          >
            {t(paused ? 'play' : 'pause')}
          </button>
          <button className={btn} aria-label={t('skipBack')} onClick={() => commit(now - SKIP_S)}>
            <SkipIcon back />
          </button>
          <button
            className={btn}
            aria-label={t('skipForward')}
            onClick={() => commit(now + SKIP_S)}
          >
            <SkipIcon />
          </button>
        </div>
      )}

      <span
        className={`num w-[64px] text-end text-[18px] font-semibold text-amber ${narrow && drag === null ? 'hidden' : ''} ${narrow ? 'order-first' : ''}`}
        aria-hidden
      >
        {drag !== null ? previewClock(drag, key?.half_time ?? null) : (clock ?? '00:00')}
      </span>

      <div
        className={`relative h-9 min-w-[180px] flex-1 ${narrow ? 'order-first basis-full' : ''}`}
      >
        <div className="pointer-events-none absolute inset-x-0 top-1/2 h-[4px] -translate-y-1/2 bg-text/15">
          <div className="absolute inset-y-0 left-0 bg-text/25" style={{ width: pct(seenUpTo) }} />
          <div className="absolute inset-y-0 left-0 bg-amber" style={{ width: pct(shown) }} />
          {key?.half_time && (
            <span
              className="absolute top-1/2 h-3 w-px -translate-y-1/2 bg-text/50"
              style={{ left: pct(key.half_time) }}
            />
          )}
        </div>
        {markers.map((m) => (
          <button
            key={m.moment_id}
            className="group absolute top-1/2 z-10 grid size-6 -translate-x-1/2 -translate-y-1/2 place-items-center"
            style={{ left: pct(m.t_match) }}
            onClick={() => commit(m.t_match - 8)}
            aria-label={`${t(markerLabel(m))} ${m.clock}`}
          >
            <span
              className={`block ${m.kind === 'goal' ? 'size-3 rounded-full' : m.kind === 'card' ? 'h-3 w-2' : 'size-2 rotate-45'} ring-1 ring-black/60 transition-transform group-hover:scale-125`}
              style={{ background: markerColour(m) }}
            />
            <span className="pointer-events-none absolute bottom-full mb-1.5 hidden whitespace-nowrap bg-raised px-2 py-1 text-[13px] text-text shadow group-hover:block group-focus-visible:block">
              {m.clock} {t(markerLabel(m))}
            </span>
          </button>
        ))}
        <input
          type="range"
          className="scrub absolute inset-0 size-full"
          min={0}
          max={Math.round(duration)}
          step={1}
          value={Math.round(shown)}
          aria-label={t('matchTime')}
          aria-valuetext={
            drag !== null ? previewClock(drag, key?.half_time ?? null) : (clock ?? '')
          }
          onChange={(e) => setDrag(Number(e.target.value))}
          onPointerUp={(e) => commit(Number((e.target as HTMLInputElement).value))}
          onKeyUp={(e) => {
            if (dragRef.current !== null) commit(Number((e.target as HTMLInputElement).value))
          }}
          onBlur={() => dragRef.current !== null && commit(dragRef.current)}
        />
      </div>

      {transport && (
        <div className="flex items-center gap-1" role="group" aria-label={t('replaySpeed')}>
          {SPEEDS.map((s) => (
            <button
              key={s}
              className={btn}
              aria-pressed={speed === s}
              onClick={() => all.forEach((x) => x.setSpeed(s))}
            >
              {s}x
            </button>
          ))}
        </div>
      )}
      <button
        className={`${btn} font-sans text-[14px] font-medium`}
        aria-pressed={spoilers}
        title={t('keyMomentsHint')}
        onClick={toggleSpoilers}
      >
        {t('keyMoments')}
      </button>
    </div>
  )
}

function SkipIcon({ back = false }: { back?: boolean }) {
  return (
    <svg
      viewBox="0 0 16 16"
      className={`size-4 ${back ? '' : '-scale-x-100'}`}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      aria-hidden
    >
      <path d="M7 3.5 2.5 8 7 12.5M13.5 3.5 9 8l4.5 4.5" />
    </svg>
  )
}
