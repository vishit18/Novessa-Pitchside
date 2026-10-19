import type { MatchMeta } from '@/types/schema'

/** Gateway base URL. VITE_GATEWAY_URL overrides; local dev runs the gateway on 127.0.0.1:8000. */
export const GATEWAY_WS =
  (import.meta.env.VITE_GATEWAY_URL as string | undefined) ?? 'ws://127.0.0.1:8000'

export const GATEWAY_HTTP = GATEWAY_WS.replace(/^ws/, 'http')

/** One row of GET /matches. */
export interface MatchSummary {
  match_id: string
  home: string
  away: string
  venue: string
  matchday: number
  kickoff_time: string
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${GATEWAY_HTTP}${path}`)
  if (!res.ok) throw new Error(`${path} returned ${res.status}`)
  return (await res.json()) as T
}

export const listMatches = () => getJson<MatchSummary[]>('/matches')

export const getMatchMeta = (id: string) => getJson<MatchMeta>(`/matches/${encodeURIComponent(id)}`)
