import { useState, type ReactNode } from 'react'
import { newestFirst, proofOf, type Proof } from '@/core/control'
import type { Decision, Insight } from '@/net/control'
import { CheckIcon, CrossIcon, DashIcon } from '@/components/icons'

const DECISION: Record<Decision, string> = {
  air: 'Air',
  merge_with: 'Merge',
  hold: 'Hold',
  drop: 'Drop',
}

const PROOF: Record<Proof, { mark: ReactNode; text: string; tone: string }> = {
  proven: { mark: <CheckIcon />, text: 'Proven', tone: 'text-control' },
  retried: { mark: <CheckIcon />, text: 'Proven on retry', tone: 'text-amber' },
  failed: { mark: <CrossIcon />, text: 'Not proven', tone: 'text-chaos' },
  skipped: { mark: <DashIcon />, text: 'Not checked', tone: 'text-muted' },
}

const KIND = (kind: string) => kind.replace(/_/g, ' ')

function headlineOf(i: Insight): string {
  return i.analysis?.headline || i.variants.analyst?.headline || i.moment.summary
}

/** What the Producer decided and what the Verifier found, one row per moment. */
export function MomentQueue({ insights }: { insights: Insight[] }) {
  const [open, setOpen] = useState<string | null>(null)
  const rows = newestFirst(insights)
  return (
    <section aria-labelledby="queue-h" className="flex min-h-0 flex-col gap-3">
      <div className="flex items-baseline justify-between gap-4">
        <h2 id="queue-h" className="font-display text-[26px] font-semibold leading-none">
          Moments
        </h2>
        <p className="text-[13px] text-muted">
          <span className="num text-text">{rows.length}</span> handled, newest first
        </p>
      </div>
      <ul className="flex max-h-[min(72dvh,760px)] flex-col divide-y divide-hairline overflow-y-auto border-y border-hairline">
        {rows.map((i) => (
          <Row
            key={i.moment_id}
            insight={i}
            open={open === i.moment_id}
            onToggle={() => setOpen(open === i.moment_id ? null : i.moment_id)}
          />
        ))}
      </ul>
    </section>
  )
}

function Row({
  insight: i,
  open,
  onToggle,
}: {
  insight: Insight
  open: boolean
  onToggle: () => void
}) {
  const proof = PROOF[proofOf(i)]
  const panel = `trail-${i.moment_id}`
  return (
    <li>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panel}
        onClick={onToggle}
        className="grid w-full grid-cols-[5.25rem_1fr] items-center gap-x-3 gap-y-1 px-1 py-3 text-start transition-colors hover:bg-text/[0.03] sm:grid-cols-[5.25rem_minmax(0,1fr)_8.5rem_9.5rem]"
      >
        <span className="num text-[22px] leading-none text-amber">{i.moment.clock}</span>
        <span className="min-w-0">
          <span className="block truncate text-[15px] text-text">{headlineOf(i)}</span>
          <span className="block text-[12px] capitalize text-muted">{KIND(i.moment.kind)}</span>
        </span>
        <span className="col-start-2 text-[13px] text-muted sm:col-start-auto">
          Producer: <span className="text-text">{DECISION[i.item.decision]}</span>{' '}
          <span className="num">{i.item.priority}</span>
        </span>
        <span
          className={`col-start-2 flex items-center gap-1.5 text-[13px] font-semibold sm:col-start-auto ${proof.tone}`}
        >
          {proof.mark}
          {i.status === 'fallback' ? 'Numbers only' : proof.text}
        </span>
      </button>
      {open && (
        <div id={panel} className="grid gap-3 px-1 pb-4 ps-[6rem] text-[13px] leading-relaxed">
          {i.item.brief && (
            <p>
              <span className="text-muted">Producer asked: </span>
              {i.item.brief}
            </p>
          )}
          {i.analysis?.why && (
            <p>
              <span className="text-muted">Analyst said: </span>
              {i.analysis.why}
            </p>
          )}
          <ol className="grid list-decimal gap-1 ps-5 text-muted marker:text-hairline">
            {i.trail.map((line, n) => (
              <li key={n}>
                <span className="text-text">{line}</span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </li>
  )
}
