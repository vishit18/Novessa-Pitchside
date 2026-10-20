import type { AgentHealth, Insight } from '@/net/control'

/** The LLM answer budget from docs/00: explanations under 4 seconds. */
export const LLM_BUDGET_MS = 4000

export type NodeKind = 'model' | 'code' | 'service'

export interface NodeSpec {
  id: string
  label: string
  job: string
  kind: NodeKind
  /** What airs when this node is down. Shown while it is switched off. */
  fallback: string
  /** Can the chaos switch break it? Only nodes that go through the model client can. */
  breakable: boolean
}

/** The airing pipeline, in order. */
export const PIPELINE: NodeSpec[] = [
  {
    id: 'producer',
    label: 'Producer',
    job: 'Picks the moments worth airing',
    kind: 'model',
    fallback: 'Moments are ranked by their computed significance instead',
    breakable: true,
  },
  {
    id: 'analyst',
    label: 'Analyst',
    job: 'Explains why it matters, with the numbers it used',
    kind: 'model',
    fallback: 'Numbers-only cards air, with no prose',
    breakable: true,
  },
  {
    id: 'verifier',
    label: 'Verifier',
    job: 'Recomputes every claim from the match data',
    kind: 'code',
    fallback: '',
    breakable: false,
  },
  {
    id: 'narrator',
    label: 'Narrator',
    job: 'Writes it for each kind of viewer',
    kind: 'model',
    fallback: 'Every viewer gets the Analyst’s wording',
    breakable: true,
  },
  {
    id: 'gate',
    label: 'Safety gate',
    job: 'Content Safety check before anything airs',
    kind: 'service',
    fallback: '',
    breakable: false,
  },
]

/** Agents that run when a viewer asks, not on every moment. */
export const ON_DEMAND: NodeSpec[] = [
  {
    id: 'localiser',
    label: 'Localiser',
    job: 'Translates and polishes in the viewer’s language',
    kind: 'model',
    fallback: 'Viewers get English with a note',
    breakable: true,
  },
  {
    id: 'recap',
    label: 'Recap editor',
    job: 'Writes half-time and full-time recaps',
    kind: 'model',
    fallback: 'A plain template recap from the numbers',
    breakable: true,
  },
]

export type NodeState = 'idle' | 'ok' | 'degraded' | 'breaker' | 'killed'

/** One word for the state of an agent, worst first. */
export function nodeState(h: AgentHealth | undefined): NodeState {
  if (!h) return 'idle'
  if (h.killed) return 'killed'
  if (h.breaker_open) return 'breaker'
  if (h.calls === 0) return 'idle'
  if (h.fallbacks > 0 || h.failures / h.calls > 0.2) return 'degraded'
  return 'ok'
}

/** Ids whose call count went up between two polls: the agents that just worked. */
export function justWorked(
  prev: Record<string, AgentHealth> | null,
  next: Record<string, AgentHealth>,
): string[] {
  if (!prev) return []
  return Object.entries(next)
    .filter(([id, h]) => h.calls > (prev[id]?.calls ?? 0))
    .map(([id]) => id)
}

export interface VerifierTally {
  proven: number
  rejected: number
  fallbackCards: number
  safetyBlocked: number
}

/** What the Verifier and the gate did, read from each moment's audit trail. */
export function tally(insights: Insight[]): VerifierTally {
  const t: VerifierTally = { proven: 0, rejected: 0, fallbackCards: 0, safetyBlocked: 0 }
  for (const i of insights) {
    for (const line of i.trail) {
      if (line.startsWith('verifier rejected')) t.rejected += 1
      else if (line.startsWith('verifier:') && line.includes('proven')) t.proven += 1
      else if (line.startsWith('content safety blocked')) t.safetyBlocked += 1
    }
    if (i.status === 'fallback') t.fallbackCards += 1
  }
  return t
}

export type Proof = 'proven' | 'retried' | 'failed' | 'skipped'

/** Verifier outcome for one moment: proven first time, proven after a retry, or never proven. */
export function proofOf(i: Insight): Proof {
  const rejected = i.trail.some((l) => l.startsWith('verifier rejected'))
  const proven = i.trail.some((l) => l.startsWith('verifier:') && l.includes('proven'))
  if (proven) return rejected ? 'retried' : 'proven'
  if (i.item.decision !== 'air' && i.item.decision !== 'merge_with') return 'skipped'
  return 'failed'
}

/** Newest first by match time, so the queue reads like the match in reverse. */
export function newestFirst(insights: Insight[]): Insight[] {
  return [...insights].sort((a, b) => b.moment.t_match - a.moment.t_match)
}

/** A bar's width as a fraction of the budget, capped so an outlier cannot leave the track. */
export function budgetFraction(ms: number, budget = LLM_BUDGET_MS): number {
  return Math.max(0, Math.min(1, ms / budget))
}

/** "1.3 s" under ten seconds, whole seconds above, "-" when nothing has been measured. */
export function seconds(ms: number): string {
  if (ms <= 0) return '-'
  const s = ms / 1000
  return s < 10 ? `${s.toFixed(1)} s` : `${Math.round(s)} s`
}

export function dollars(usd: number): string {
  return usd < 0.01 ? `$${usd.toFixed(4)}` : `$${usd.toFixed(2)}`
}
