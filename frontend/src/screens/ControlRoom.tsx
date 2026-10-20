import { useEffect, useMemo, useState } from 'react'
import { AgentGraph } from '@/components/control/AgentGraph'
import { Gauges } from '@/components/control/Gauges'
import { MomentQueue } from '@/components/control/MomentQueue'
import { Wordmark } from '@/components/Hud'
import { tally } from '@/core/control'
import { GATEWAY_HTTP, listMatches, type MatchSummary } from '@/net/api'
import { killAgent, startAgents } from '@/net/control'
import { navigate, withParams } from '@/router'
import { useControlData } from '@/state/useControlData'

const KILL_SECONDS = 30

/**
 * Producer's view of the agent team: who is working, what each decided, whether the Verifier
 * is proving claims, how fast and how much. Polls the gateway; the chaos switch lives on each
 * agent plate.
 */
export function ControlRoom({ query }: { query: URLSearchParams }) {
  const matchId = query.get('match') ?? 'derby_01'
  const [matches, setMatches] = useState<MatchSummary[]>([])
  const { health, insights, lit, offline, refresh } = useControlData(matchId)
  const counts = useMemo(() => tally(insights), [insights])
  const progress = health?.matches[matchId]
  const running = !!progress && !progress.finished

  useEffect(() => {
    listMatches()
      .then(setMatches)
      .catch(() => setMatches([]))
  }, [])

  const start = () => void startAgents(matchId).then(refresh)
  const kill = (agent: string) => void killAgent(agent, KILL_SECONDS)

  return (
    <main className="stage-bg flex min-h-dvh w-full flex-col gap-6 px-4 py-5 sm:px-8">
      <header className="flex flex-wrap items-center justify-between gap-x-8 gap-y-3">
        <div className="flex flex-wrap items-baseline gap-x-5 gap-y-1">
          <Wordmark />
          <h1 className="font-display text-[26px] font-semibold leading-none">Control room</h1>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-[13px] text-muted">
            Match
            <select
              value={matchId}
              onChange={(e) => navigate(withParams('/control', { match: e.target.value }))}
              className="border border-hairline bg-raised px-2 py-1.5 text-[14px] text-text"
            >
              {(matches.length ? matches.map((m) => m.match_id) : [matchId]).map((id) => (
                <option key={id} value={id}>
                  {matchLabel(matches, id)}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            onClick={start}
            disabled={!health?.enabled || running}
            className="bg-amber px-4 py-1.5 text-[14px] font-semibold text-ink transition-opacity disabled:cursor-not-allowed disabled:opacity-40"
          >
            {running ? 'Agents running' : progress ? 'Agents finished' : 'Start the agents'}
          </button>
          <button
            type="button"
            onClick={() => navigate(withParams('/watch', { match: matchId }))}
            className="border border-hairline px-3 py-1.5 text-[14px] text-text hover:border-amber"
          >
            Open the broadcast
          </button>
        </div>
      </header>

      {offline && (
        <p role="alert" className="border-s-2 border-chaos bg-chaos/10 px-3 py-2 text-[14px]">
          Can’t reach the gateway at {GATEWAY_HTTP}. The numbers below are the last ones received.
          Retrying every second.
        </p>
      )}
      {health && !health.enabled && (
        <p role="status" className="border-s-2 border-amber bg-amber/10 px-3 py-2 text-[14px]">
          The agents are switched off on this gateway, so only instant overlays run. Set
          FOUNDRY_OPENAI_ENDPOINT and restart it to turn them on.
        </p>
      )}

      <AgentGraph agents={health?.agents ?? {}} tally={counts} lit={lit} onKill={kill} />

      <div className="grid flex-1 gap-8 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)] lg:gap-10">
        {insights.length ? (
          <MomentQueue insights={insights} />
        ) : (
          <EmptyQueue enabled={health?.enabled ?? false} started={!!progress} />
        )}
        <Gauges health={health} progress={progress} />
      </div>
    </main>
  )
}

function matchLabel(matches: MatchSummary[], id: string): string {
  const m = matches.find((x) => x.match_id === id)
  return m ? `${m.home} v ${m.away} (${id})` : id
}

function EmptyQueue({ enabled, started }: { enabled: boolean; started: boolean }) {
  return (
    <section aria-labelledby="queue-h" className="flex flex-col gap-3">
      <h2 id="queue-h" className="font-display text-[26px] font-semibold leading-none">
        Moments
      </h2>
      <p className="max-w-[52ch] text-[14px] leading-relaxed text-muted">
        {!enabled
          ? 'Nothing to show while the agents are off.'
          : started
            ? 'The first batch is with the Producer. Moments appear here as they are proven, usually within a minute on a cold cache.'
            : 'No moments yet. Start the agents, or open the broadcast and press play. They begin when a viewer connects.'}
      </p>
    </section>
  )
}
