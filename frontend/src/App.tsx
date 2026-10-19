import { useEffect } from 'react'
import { Controls, LowerThird, ScoreBug, StatusPill, Wordmark } from '@/components/Hud'
import { Stage } from '@/components/Stage'
import { startMatch } from '@/state/runtime'
import { useStore } from '@/state/store'

function params() {
  const q = new URLSearchParams(window.location.search)
  return {
    matchId: q.get('match') ?? 'derby_01',
    viewer: q.get('viewer') ?? 'demo-viewer',
    startAt: Number(q.get('t') ?? 0),
    speed: Number(q.get('speed') ?? 4),
  }
}

/** Broadcast view: the 16:9 hero screen. */
export default function App() {
  const status = useStore((s) => s.status)
  const detail = useStore((s) => s.statusDetail)
  const meta = useStore((s) => s.meta)

  useEffect(() => {
    const p = params()
    return startMatch({ matchId: p.matchId, viewer: p.viewer, startAt: p.startAt, speed: p.speed })
  }, [])

  const failed = status === 'error' && !meta

  return (
    <main className="stage-bg relative h-dvh w-full overflow-hidden">
      <h1 className="sr-only">Novessa Pitchside broadcast view</h1>
      <Stage />

      <div className="pointer-events-none absolute inset-x-0 top-0 flex flex-col items-start gap-2 p-4 sm:flex-row sm:justify-between sm:gap-3 sm:p-6">
        <div>
          <ScoreBug />
          {meta && (
            <p className="mt-2 hidden text-[12px] leading-snug text-muted sm:block">
              {meta.competition} · Matchday {meta.matchday} · {meta.venue}
            </p>
          )}
        </div>
        <StatusPill />
      </div>

      <div className="absolute inset-x-0 bottom-0 flex flex-col gap-3 p-4 sm:p-6">
        <div className="flex items-end justify-between gap-4">
          <LowerThird />
          <div className="hidden sm:block">
            <Wordmark />
          </div>
        </div>
        <div className="flex justify-center">
          <Controls />
        </div>
      </div>

      {!meta && !failed && (
        <div className="absolute inset-0 grid place-items-center bg-ink/80">
          <div className="text-center">
            <Wordmark />
            <p className="pulse-soft mt-3 text-sm text-muted">Waiting for kick-off</p>
          </div>
        </div>
      )}
      {failed && (
        <div className="absolute inset-0 grid place-items-center bg-ink/90 p-6">
          <div className="panel max-w-md rounded-[4px] p-6">
            <h2 className="font-display text-2xl font-semibold uppercase tracking-wide">
              Feed unavailable
            </h2>
            <p className="mt-2 text-sm text-muted">{detail ?? 'The match feed did not start.'}</p>
            <button
              className="mt-4 h-9 rounded-[3px] border border-amber px-4 text-sm font-medium text-amber hover:bg-amber/10"
              onClick={() => {
                const p = params()
                startMatch({
                  matchId: p.matchId,
                  viewer: p.viewer,
                  startAt: p.startAt,
                  speed: p.speed,
                })
              }}
            >
              Try again
            </button>
          </div>
        </div>
      )}
    </main>
  )
}
