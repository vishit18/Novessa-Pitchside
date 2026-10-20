import { Fragment } from 'react'
import {
  nodeState,
  ON_DEMAND,
  PIPELINE,
  seconds,
  type NodeSpec,
  type NodeState,
  type VerifierTally,
} from '@/core/control'
import type { AgentHealth } from '@/net/control'

const KILL_SECONDS = 30

const STATE_LABEL: Record<NodeState, string> = {
  idle: 'Waiting for work',
  ok: 'Working',
  degraded: 'Using fallbacks',
  breaker: 'Paused after repeated failures',
  killed: 'Switched off',
}

const STATE_BAR: Record<NodeState, string> = {
  idle: 'bg-hairline',
  ok: 'bg-control',
  degraded: 'bg-amber',
  breaker: 'bg-chaos',
  killed: 'bg-chaos',
}

interface GraphProps {
  agents: Record<string, AgentHealth>
  tally: VerifierTally
  lit: ReadonlySet<string>
  onKill: (agent: string) => void
}

/** The airing pipeline as plates in a row. A plate lights up while its agent is working. */
export function AgentGraph({ agents, tally, lit, onKill }: GraphProps) {
  const broken = [...PIPELINE, ...ON_DEMAND].filter((n) => {
    const s = nodeState(agents[n.id])
    return s === 'killed' || s === 'breaker'
  })
  return (
    <section aria-labelledby="graph-h" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <h2 id="graph-h" className="font-display text-[26px] font-semibold leading-none">
          Who is working on the match
        </h2>
        <p className="text-[13px] text-muted">
          Every moment goes left to right. Nothing airs without passing the Verifier.
        </p>
      </div>

      <ol className="grid gap-3 lg:grid-cols-[repeat(5,minmax(0,1fr))] lg:gap-0">
        {PIPELINE.map((spec, i) => (
          <li key={spec.id} className="relative lg:px-1.5 lg:first:ps-0 lg:last:pe-0">
            <NodeCard
              spec={spec}
              health={agents[spec.id]}
              lit={isLit(spec.id, lit)}
              tally={tally}
              onKill={onKill}
              step={i + 1}
            />
            {i < PIPELINE.length - 1 && <Flow lit={isLit(spec.id, lit)} />}
          </li>
        ))}
      </ol>

      <FlowArcs
        rejected={tally.rejected}
        fallbackCards={tally.fallbackCards}
        down={broken.length > 0}
      />

      <p className="max-w-[78ch] text-[13px] leading-relaxed text-muted">
        When the Verifier rejects a claim, the Analyst gets one retry with the measured number
        {tally.rejected > 0 && (
          <>
            {' '}
            (<span className="num text-text">{tally.rejected}</span>{' '}
            {tally.rejected === 1 ? 'rejection' : 'rejections'} so far)
          </>
        )}
        . If the retry fails too, a numbers-only card airs instead of unverified prose.
      </p>

      <div role="status" aria-live="polite">
        {broken.map((n) => (
          <p
            key={n.id}
            className="mt-1 border-s-2 border-chaos bg-chaos/10 px-3 py-2 text-[14px] text-text"
          >
            <span className="font-semibold">{n.label} is down.</span> {n.fallback}. The match
            carries on.
          </p>
        ))}
      </div>

      <ul className="grid gap-3 lg:grid-cols-2" aria-label="Agents that run when a viewer asks">
        {ON_DEMAND.map((spec) => (
          <li key={spec.id}>
            <OnDemand spec={spec} health={agents[spec.id]} lit={lit.has(spec.id)} onKill={onKill} />
          </li>
        ))}
      </ul>
    </section>
  )
}

/**
 * The two routes that are not a straight line, drawn under the plates (wide screens only; on a
 * phone the plates stack and the sentence below says the same). The loop sends a rejected claim
 * back to the Analyst. The dashed route is the numbers-only card, lit while an agent is down.
 * Columns are a fifth of the width each, so a plate's centre sits at 10, 30, 50, 70 and 90 per cent.
 */
function FlowArcs({
  rejected,
  fallbackCards,
  down,
}: {
  rejected: number
  fallbackCards: number
  down: boolean
}) {
  const loopOn = rejected > 0
  const bypassOn = down || fallbackCards > 0
  return (
    <div aria-hidden className="relative -mt-1 hidden h-[84px] lg:block" dir="ltr">
      <svg
        className="absolute inset-0 size-full overflow-visible"
        viewBox="0 0 100 84"
        preserveAspectRatio="none"
      >
        <path
          d="M50 0 V22 Q50 30 44 30 H36 Q30 30 30 22 V6"
          fill="none"
          stroke={loopOn ? 'var(--color-amber)' : 'var(--color-hairline)'}
          strokeWidth="2"
          vectorEffect="non-scaling-stroke"
          className="transition-colors duration-200"
        />
        <path
          d="M30 36 V66 Q30 74 36 74 H84 Q90 74 90 66 V6"
          fill="none"
          stroke={bypassOn ? 'var(--color-chaos)' : 'var(--color-hairline)'}
          strokeWidth="2"
          strokeDasharray="6 5"
          vectorEffect="non-scaling-stroke"
          className="transition-colors duration-200"
        />
      </svg>
      <Arrowhead left="30%" top={0} on={loopOn} tone="amber" />
      <Arrowhead left="90%" top={0} on={bypassOn} tone="chaos" />
      <span
        className={`absolute top-[34px] -translate-x-1/2 text-[12px] ${loopOn ? 'text-amber' : 'text-muted'}`}
        style={{ left: '40%' }}
      >
        Rejected claim goes back, once{loopOn && ` (${rejected} so far)`}
      </span>
      <span
        className={`absolute top-[78px] -translate-x-1/2 bg-ink px-2 text-[12px] ${bypassOn ? 'text-chaos' : 'text-muted'}`}
        style={{ left: '60%' }}
      >
        Numbers-only card when a step is down or a claim fails
        {fallbackCards > 0 && ` (${fallbackCards} so far)`}
      </span>
    </div>
  )
}

/** A small triangle pointing up into a plate. Positioned in CSS so it never stretches. */
function Arrowhead({
  left,
  top,
  on,
  tone,
}: {
  left: string
  top: number
  on: boolean
  tone: 'amber' | 'chaos'
}) {
  return (
    <span
      className={`absolute -translate-x-1/2 transition-colors duration-200 ${on ? (tone === 'amber' ? 'text-amber' : 'text-chaos') : 'text-hairline'}`}
      style={{
        left,
        top,
        width: 0,
        height: 0,
        borderInline: '5px solid transparent',
        borderBottom: '8px solid currentColor',
      }}
    />
  )
}

/** The Verifier and the gate run straight after the agent before them, so they light with it. */
const LIGHTS_WITH: Record<string, string> = { verifier: 'analyst', gate: 'narrator' }

function isLit(id: string, lit: ReadonlySet<string>): boolean {
  return lit.has(id) || lit.has(LIGHTS_WITH[id] ?? '')
}

/** Arrow on the seam between two plates. Only drawn when the plates sit side by side. */
function Flow({ lit }: { lit: boolean }) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 12 16"
      className={`absolute -end-[5px] top-9 z-10 hidden h-4 w-3 transition-colors duration-200 lg:block rtl:-scale-x-100 ${
        lit ? 'text-amber' : 'text-hairline'
      }`}
    >
      <path d="M2 1l8 7-8 7" fill="none" stroke="currentColor" strokeWidth="2.5" />
    </svg>
  )
}

/** A short strip for agents that only run on request. */
function OnDemand({
  spec,
  health,
  lit,
  onKill,
}: {
  spec: NodeSpec
  health: AgentHealth | undefined
  lit: boolean
  onKill: (agent: string) => void
}) {
  const state = nodeState(health)
  const down = state === 'killed' || state === 'breaker'
  return (
    <div className="plate-shadow">
      <div className="plate relative flex flex-wrap items-center gap-x-5 gap-y-2 px-4 py-3">
        <span
          aria-hidden
          className={`absolute inset-y-0 start-0 w-[3px] transition-colors duration-200 ${lit ? 'bg-amber' : STATE_BAR[state]}`}
        />
        <div className="min-w-[11rem] flex-1">
          <h3 className="font-display text-[20px] font-semibold leading-none">{spec.label}</h3>
          <p className="mt-1 text-[12px] text-muted">{spec.job}</p>
        </div>
        <p className={`text-[13px] ${down ? 'font-semibold text-chaos' : 'text-muted'}`}>
          {STATE_LABEL[state]}
          {health && (
            <>
              {', '}
              <span className="num text-[15px] text-text">{health.calls}</span>{' '}
              {health.calls === 1 ? 'call' : 'calls'}
            </>
          )}
        </p>
        <KillButton id={spec.id} down={down} onKill={onKill} />
      </div>
    </div>
  )
}

function KillButton({
  id,
  down,
  onKill,
}: {
  id: string
  down: boolean
  onKill: (agent: string) => void
}) {
  return (
    <button
      type="button"
      disabled={down}
      onClick={() => onKill(id)}
      className="relative border border-white/35 px-3 py-1.5 text-[13px] text-text transition-colors hover:border-chaos hover:text-chaos disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-white/35 disabled:hover:text-text"
    >
      {down ? 'Recovering' : `Switch off for ${KILL_SECONDS} s`}
    </button>
  )
}

/** Model agents report health; the Verifier and the gate are read from the moments' trails. */
function stateOf(spec: NodeSpec, health: AgentHealth | undefined, t: VerifierTally): NodeState {
  if (spec.kind === 'model') return nodeState(health)
  const seen = spec.id === 'verifier' ? t.proven + t.rejected : t.proven + t.safetyBlocked
  return seen > 0 ? 'ok' : 'idle'
}

interface CardProps {
  spec: NodeSpec
  health: AgentHealth | undefined
  lit: boolean
  tally: VerifierTally
  onKill: (agent: string) => void
  step?: number
  compact?: boolean
}

function NodeCard({ spec, health, lit, tally, onKill, step, compact }: CardProps) {
  const state = stateOf(spec, health, tally)
  const down = state === 'killed' || state === 'breaker'
  const left = health
    ? Math.ceil(state === 'killed' ? health.killed_for_s : health.breaker_for_s)
    : 0
  return (
    <div className="plate-shadow h-full">
      <article
        className="plate relative flex h-full flex-col gap-3 px-4 pb-4 pt-5"
        aria-label={`${spec.label}: ${STATE_LABEL[state]}`}
      >
        <span
          aria-hidden
          className={`absolute inset-x-0 top-0 h-[3px] transition-colors duration-200 ${
            lit ? 'bg-amber' : STATE_BAR[state]
          }`}
          style={lit ? { boxShadow: '0 0 14px 2px rgb(255 176 32 / 0.55)' } : undefined}
        />
        <span
          aria-hidden
          className={`pointer-events-none absolute inset-0 bg-gradient-to-b from-amber/15 to-transparent transition-opacity duration-300 ${
            lit ? 'opacity-100' : 'opacity-0'
          }`}
        />
        <header className="relative">
          <h3 className="font-display text-[24px] font-semibold leading-none">
            {step !== undefined && <span className="num me-2 text-muted">{step}</span>}
            {spec.label}
          </h3>
          <p className="mt-1.5 text-[13px] leading-snug text-muted">{spec.job}</p>
        </header>

        <p
          className={`relative text-[13px] font-semibold ${down ? 'text-chaos' : state === 'degraded' ? 'text-amber' : 'text-text'}`}
        >
          {down && left > 0 ? `${STATE_LABEL[state]}, ${left} s left` : STATE_LABEL[state]}
        </p>

        <NodeStats spec={spec} health={health} tally={tally} compact={compact} />

        {spec.breakable && (
          <div className="mt-auto">
            <KillButton id={spec.id} down={down} onKill={onKill} />
          </div>
        )}
      </article>
    </div>
  )
}

function NodeStats({
  spec,
  health,
  tally,
  compact,
}: {
  spec: NodeSpec
  health: AgentHealth | undefined
  tally: VerifierTally
  compact?: boolean
}) {
  if (spec.id === 'verifier') {
    return (
      <Stats
        rows={[
          ['Claims proven', String(tally.proven)],
          ['Rejected', String(tally.rejected)],
          ['Numbers-only cards', String(tally.fallbackCards)],
        ]}
      />
    )
  }
  if (spec.id === 'gate') {
    return <Stats rows={[['Texts blocked', String(tally.safetyBlocked)]]} />
  }
  if (!health) return compact ? null : <Stats rows={[['Calls', '0']]} />
  return (
    <Stats
      rows={[
        ['Calls', String(health.calls)],
        ['Typical answer', seconds(health.p50_latency_ms)],
        ['Slowest 1 in 20', seconds(health.p95_latency_ms)],
        ...(health.fallbacks > 0 ? [['Fallbacks used', String(health.fallbacks)] as const] : []),
      ]}
    />
  )
}

function Stats({ rows }: { rows: ReadonlyArray<readonly [string, string]> }) {
  return (
    <dl className="relative grid grid-cols-[1fr_auto] gap-x-3 gap-y-1 text-[13px]">
      {rows.map(([k, v]) => (
        <Fragment key={k}>
          <dt className="text-muted">{k}</dt>
          <dd className="num m-0 text-end text-[17px] leading-none text-text">{v}</dd>
        </Fragment>
      ))}
    </dl>
  )
}
