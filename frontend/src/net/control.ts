import { GATEWAY_HTTP } from '@/net/api'

/** One agent's counters from GET /agents/health. */
export interface AgentHealth {
  calls: number
  failures: number
  fallbacks: number
  last_latency_ms: number
  avg_latency_ms: number
  p50_latency_ms: number
  p95_latency_ms: number
  breaker_open: boolean
  breaker_for_s: number
  killed: boolean
  killed_for_s: number
}

/** Batch progress for one match. */
export interface RunProgress {
  batches: number
  done: number
  total: number
  failed_batches?: number
  error?: boolean
  seconds?: number
  finished?: boolean
}

export interface ModelUsage {
  prompt: number
  completion: number
  usd: number
}

export interface HealthResponse {
  enabled: boolean
  agents: Record<string, AgentHealth>
  matches: Record<string, RunProgress>
  usage: { models: Record<string, ModelUsage>; usd: number; estimate: boolean }
}

export type Decision = 'air' | 'merge_with' | 'hold' | 'drop'

/** One moment as the agents handled it, from GET /matches/{id}/insights. */
export interface Insight {
  moment_id: string
  status: 'verified' | 'fallback' | 'dropped'
  item: { decision: Decision; priority: number; slot: string; reason: string; brief: string }
  analysis: { headline: string; why: string } | null
  variants: Record<string, { headline: string }>
  trail: string[]
  moment: {
    kind: string
    clock: string
    t_match: number
    team: string | null
    summary: string
    significance: number
  }
}

async function send<T>(path: string, method: 'GET' | 'POST', signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${GATEWAY_HTTP}${path}`, { method, signal })
  if (!res.ok) throw new Error(`${path} returned ${res.status}`)
  return (await res.json()) as T
}

export const getHealth = (signal?: AbortSignal) =>
  send<HealthResponse>('/agents/health', 'GET', signal)

export const getInsights = (matchId: string, signal?: AbortSignal) =>
  send<Insight[]>(`/matches/${encodeURIComponent(matchId)}/insights`, 'GET', signal)

export const startAgents = (matchId: string) =>
  send<{ enabled: boolean }>(`/matches/${encodeURIComponent(matchId)}/agents/start`, 'POST')

/** Chaos switch: make one agent fail for a while. */
export const killAgent = (agent: string, seconds: number) =>
  send<{ killed_for_s: number }>(`/agents/${agent}/kill?seconds=${seconds}`, 'POST')
