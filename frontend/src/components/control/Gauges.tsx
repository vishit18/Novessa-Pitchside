import { budgetFraction, dollars, LLM_BUDGET_MS, seconds } from '@/core/control'
import type { AgentHealth, HealthResponse, RunProgress } from '@/net/control'

const COLUMNS = ['producer', 'analyst', 'narrator', 'localiser', 'recap']

/** Answer times against the 4 second budget, plus what the run has cost and how far it is. */
export function Gauges({
  health,
  progress,
}: {
  health: HealthResponse | null
  progress: RunProgress | undefined
}) {
  const measured = COLUMNS.flatMap((id) => {
    const h = health?.agents[id]
    return h && h.calls > 0 ? [{ id, h }] : []
  })
  const tokens = Object.values(health?.usage.models ?? {}).reduce(
    (n, m) => n + m.prompt + m.completion,
    0,
  )
  return (
    <section aria-labelledby="gauge-h" className="flex flex-col gap-6">
      <div className="flex flex-col gap-3">
        <h2 id="gauge-h" className="font-display text-[26px] font-semibold leading-none">
          Answer times
        </h2>
        {measured.length === 0 ? (
          <p className="text-[13px] text-muted">Times show up after the first model call.</p>
        ) : (
          <ul className="flex flex-col gap-3">
            {measured.map(({ id, h }) => (
              <Gauge key={id} id={id} h={h} />
            ))}
          </ul>
        )}
        <p className="text-[12px] text-muted">
          The bar runs to the {LLM_BUDGET_MS / 1000} second budget. Bright is the typical answer,
          pale is the slowest 1 in 20.
        </p>
        <p className="text-[12px] text-muted">
          Instant overlays air first. Agent text attaches to the same moment when it is ready, so a
          slow answer never holds up the picture.
        </p>
      </div>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-4">
        <Figure
          label="Spent so far (estimate)"
          value={health ? dollars(health.usage.usd) : '-'}
          note={tokens ? `${tokens.toLocaleString('en')} tokens` : 'No model calls yet'}
        />
        <Figure
          label="Moments processed"
          value={progress ? `${progress.done} of ${progress.total}` : '-'}
          note={runNote(progress)}
        />
      </dl>
    </section>
  )
}

function runNote(p: RunProgress | undefined): string {
  if (!p) return 'Not started'
  if (p.error) return 'Stopped on an error'
  if (p.finished) return `Finished in ${p.seconds ?? 0} s`
  return p.failed_batches ? `Running, ${p.failed_batches} batches skipped` : 'Running'
}

function Gauge({ id, h }: { id: string; h: AgentHealth }) {
  const slowTail = h.p95_latency_ms > LLM_BUDGET_MS
  const over = h.p50_latency_ms > LLM_BUDGET_MS
  const name = id.charAt(0).toUpperCase() + id.slice(1)
  return (
    <li className="grid grid-cols-[5.5rem_1fr_auto] items-center gap-3">
      <span className="text-[14px]">{name}</span>
      <span
        className="relative h-3 bg-text/[0.06]"
        role="img"
        aria-label={`${name}: typical ${seconds(h.p50_latency_ms)}, slowest 1 in 20 ${seconds(h.p95_latency_ms)}, budget ${LLM_BUDGET_MS / 1000} s`}
      >
        <span
          className={`absolute inset-y-0 start-0 transition-[width] duration-200 ease-out ${slowTail ? 'bg-chaos/40' : 'bg-control/30'}`}
          style={{ width: `${budgetFraction(h.p95_latency_ms) * 100}%` }}
        />
        <span
          className={`absolute inset-y-0 start-0 transition-[width] duration-200 ease-out ${over ? 'bg-chaos' : 'bg-control'}`}
          style={{ width: `${budgetFraction(h.p50_latency_ms) * 100}%` }}
        />
      </span>
      <span className="num w-[8.5rem] text-end text-[15px] text-muted">
        <span className="text-text">{seconds(h.p50_latency_ms)}</span>
        {' / '}
        {seconds(h.p95_latency_ms)}
      </span>
    </li>
  )
}

function Figure({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div>
      <dt className="text-[13px] text-muted">{label}</dt>
      <dd className="m-0">
        <span className="num block text-[34px] font-semibold leading-tight">{value}</span>
        <span className="block text-[12px] text-muted">{note}</span>
      </dd>
    </div>
  )
}
