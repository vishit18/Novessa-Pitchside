import { useState } from 'react'
import { Wordmark } from '@/components/Hud'
import { navigate, withParams } from '@/router'
import {
  defaultProfile,
  LANGS,
  loadProfile,
  PERSONAS,
  type Lang,
  type Persona,
  type ViewerProfile,
} from '@/state/profile'
import type { Session } from '@/state/session'
import { useLiveSession } from '@/state/useSession'
import { BroadcastPane } from './BroadcastPane'

const SPEEDS = [1, 4, 10]

/**
 * "Same match. Your story." Two viewers on the same match, each with their own profile and
 * socket. Overlays are keyed to match time, so even with different stream delays both see the
 * same overlay on the same piece of football.
 */
export function Split({ query }: { query: URLSearchParams }) {
  const matchId = query.get('match') ?? 'derby_01'
  const baseT = Number(query.get('t') ?? 0)
  const speed0 = Number(query.get('speed') ?? 1)
  const club = loadProfile()?.club ?? null

  const [left, setLeft] = useState(() => ({
    profile: defaultProfile({ persona: 'analyst', lang: 'en', club }),
    startAt: baseT,
  }))
  const [right, setRight] = useState(() => ({
    profile: defaultProfile({ persona: 'casual', lang: 'es', club }),
    startAt: baseT,
  }))
  const a = useLiveSession({ matchId, profile: left.profile, startAt: left.startAt, speed: speed0 })
  const b = useLiveSession({
    matchId,
    profile: right.profile,
    startAt: right.startAt,
    speed: speed0,
  })

  const [speed, setSpeed] = useState(speed0)
  const [paused, setPaused] = useState(false)
  const both = (f: (s: Session) => void) => [a, b].forEach(f)

  // Changing a viewer opens a new socket; pick up where that viewer was.
  const change = (session: Session, set: typeof setLeft) => (patch: Partial<ViewerProfile>) =>
    set((cur) => ({
      profile: { ...cur.profile, ...patch },
      startAt: Math.max(0, session.buffers.latestT),
    }))

  return (
    <main className="flex min-h-dvh w-full flex-col gap-3 bg-ink px-4 py-4 sm:px-6 sm:py-5">
      <header className="flex flex-col gap-3 sm:grid sm:grid-cols-[1fr_auto_1fr] sm:items-center sm:gap-4">
        <Wordmark />
        <h1 className="font-display text-[32px] font-bold leading-none sm:text-[44px] sm:whitespace-nowrap">
          Same match. Your story.
        </h1>
        <button
          className="justify-self-end text-[14px] text-muted underline decoration-white/25 underline-offset-4 hover:text-text max-sm:hidden"
          onClick={() => navigate(withParams('/watch', { match: matchId }))}
        >
          Back to one view
        </button>
      </header>

      <div className="flex flex-1 flex-col gap-5">
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2 lg:gap-8">
          <Column session={a} profile={left.profile} onChange={change(a, setLeft)} />
          <Column session={b} profile={right.profile} onChange={change(b, setRight)} />
        </div>

        <div className="flex justify-center">
          <div className="plate-shadow">
            <div
              className="plate flex flex-wrap items-center justify-center gap-x-5 gap-y-2 px-5 py-2.5"
              style={{ ['--cut' as string]: '10px' }}
              role="toolbar"
              aria-label="Playback for both viewers"
            >
              <button
                className={chip(paused)}
                aria-pressed={paused}
                onClick={() => {
                  both((s) => s.setPaused(!paused))
                  setPaused(!paused)
                }}
              >
                {paused ? 'Play' : 'Pause'}
              </button>
              <div className="flex gap-1" role="group" aria-label="Replay speed">
                {SPEEDS.map((v) => (
                  <button
                    key={v}
                    className={chip(speed === v)}
                    aria-pressed={speed === v}
                    onClick={() => {
                      both((s) => s.setSpeed(v))
                      setSpeed(v)
                    }}
                  >
                    {v}x
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  )
}

function chip(on: boolean): string {
  return `h-9 min-w-9 border px-2.5 text-[15px] font-medium transition-colors ${
    on ? 'border-amber text-amber' : 'border-white/30 text-muted hover:text-text'
  }`
}

function Column({
  session,
  profile,
  onChange,
}: {
  session: Session
  profile: ViewerProfile
  onChange: (patch: Partial<ViewerProfile>) => void
}) {
  const [delay, setDelay] = useState(0)
  return (
    <section className="flex min-w-0 flex-col gap-3" aria-label={`${profile.persona} viewer`}>
      <div className="h-[44dvh] min-h-[280px] w-full overflow-hidden lg:h-[min(62dvh,660px)]">
        <BroadcastPane session={session} compact transport={false} />
      </div>
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2.5">
        <Picker
          label="Watching as"
          options={PERSONAS.map((p) => ({ id: p.id, label: p.label }))}
          value={profile.persona}
          onPick={(id) => onChange({ persona: id as Persona })}
        />
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-[13px] text-muted">
            Language
            <select
              className="h-9 border border-white/30 bg-ink px-2 text-[15px] font-medium text-text"
              value={profile.lang}
              onChange={(e) => onChange({ lang: e.target.value as Lang })}
            >
              {LANGS.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.label}
                </option>
              ))}
            </select>
          </label>
          <button
            className={chip(delay > 0)}
            aria-pressed={delay > 0}
            title="Stream delay: the same moment arrives later for this viewer"
            onClick={() => {
              const next = delay === 0 ? 20 : 0
              setDelay(next)
              session.setDelay(next)
            }}
          >
            {delay > 0 ? `Delayed ${delay}s` : 'Delay 0s'}
          </button>
        </div>
      </div>
    </section>
  )
}

function Picker({
  label,
  options,
  value,
  onPick,
}: {
  label: string
  options: { id: string; label: string }[]
  value: string
  onPick: (id: string) => void
}) {
  return (
    <div className="flex items-center gap-2" role="group" aria-label={label}>
      <span className="text-[13px] text-muted">{label}</span>
      <div className="flex flex-wrap gap-1">
        {options.map((o) => (
          <button
            key={o.id}
            className={chip(o.id === value)}
            aria-pressed={o.id === value}
            onClick={() => onPick(o.id)}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  )
}
