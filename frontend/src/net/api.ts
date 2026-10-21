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

/** A gateway answer that was not a 2xx. `status` lets callers tell "agents off" from a crash. */
export class ApiError extends Error {
  constructor(
    readonly path: string,
    readonly status: number,
  ) {
    super(`${path} returned ${status}`)
  }
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${GATEWAY_HTTP}${path}`)
  if (!res.ok) throw new ApiError(path, res.status)
  return (await res.json()) as T
}

export const listMatches = () => getJson<MatchSummary[]>('/matches')

export const getMatchMeta = (id: string) => getJson<MatchMeta>(`/matches/${encodeURIComponent(id)}`)

/** One story beat in the catch-up. */
export interface CatchUpMoment {
  moment_id: string
  clock: string
  kind: string
  headline: string
  body: string
  team: string | null
}

/** GET /matches/{id}/catchup: the match up to `t` and nothing after it. */
export interface CatchUp {
  match_id: string
  t_match: number
  clock: string
  period: number
  score: Record<string, number>
  summary: string
  moments: CatchUpMoment[]
  note: string
}

export const getCatchUp = (id: string, t: number) =>
  getJson<CatchUp>(`/matches/${encodeURIComponent(id)}/catchup?t=${Math.max(0, t).toFixed(1)}`)

export type RecapKind = 'half_time' | 'full_time'

/** What the Recap Editor wrote. Mirrors backend/agents/models.py Recap. */
export interface Recap {
  match_id: string
  kind: RecapKind
  persona: string
  lang: string
  status: 'verified' | 'fallback'
  translation: string
  t_match: number
  output: { headline: string; paragraphs: string[]; highlights: string[] }
  facts: RecapFacts
  trail: string[]
}

export interface TeamFacts {
  goals: number
  possession_pct: number
  shots: number
  xg: number
  passes: number
  pass_accuracy_pct: number
  corners: number
  fouls: number
  yellow_cards: number
  red_cards: number
}

/** The fact sheet behind a recap: computed in code, so these numbers are safe to show. */
export interface RecapFacts {
  kind: RecapKind
  minute_reached: string
  home: string
  away: string
  score: string
  goals: { clock: string; scorer: string; team: string }[]
  teams: Record<string, TeamFacts>
  leaders: { metric: string; player: string; team: string | null; value: number }[]
}

/** GET /matches/{id}/recap. 503 when the agents are off, and the first call can take 15 s. */
export const getRecap = (id: string, kind: RecapKind, persona: string, lang: string) =>
  getJson<Recap>(
    `/matches/${encodeURIComponent(id)}/recap?kind=${kind}&persona=${persona}&lang=${lang}`,
  )

/** One marker on the timeline: GET /matches/{id}/moments. */
export interface KeyMoment {
  moment_id: string
  t_match: number
  clock: string
  kind: 'goal' | 'card' | 'penalty' | 'big_chance'
  headline: string
  team: string | null
  card: 'yellow' | 'red' | null
}

/** The whole match's goals, cards and chances. Reveals the result: show only on request. */
export interface KeyMoments {
  match_id: string
  duration: number
  half_time: number | null
  moments: KeyMoment[]
}

export const getKeyMoments = (id: string) =>
  getJson<KeyMoments>(`/matches/${encodeURIComponent(id)}/moments`)

/** GET /matches/{id}/moments/{moment}/text: one verified moment as every persona gets it. */
export interface MomentText {
  moment_id: string
  lang: string
  translation: string
  variants: Record<string, { headline: string; body: string; commentary: string }>
}

export const getMomentText = (id: string, moment: string, lang: string) =>
  getJson<MomentText>(
    `/matches/${encodeURIComponent(id)}/moments/${encodeURIComponent(moment)}/text?lang=${lang}`,
  )

/** POST /matches/{id}/ask: Ask the Analyst. Mirrors backend/agents/models.py AskAnswer. */
export interface AskAnswer {
  question: string
  answer: string
  status: 'verified' | 'numbers_only' | 'declined' | 'unavailable'
  lang: string
  translation: string
  t_match: number
  clock: string
  evidence: { key: string; label: string; value: number }[]
  notes: string[]
  tools: string[]
  trail: string[]
}

export async function askAnalyst(
  id: string,
  body: { question: string; t: number; persona: string; lang: string },
): Promise<AskAnswer> {
  const path = `/matches/${encodeURIComponent(id)}/ask`
  const res = await fetch(`${GATEWAY_HTTP}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new ApiError(path, res.status)
  return (await res.json()) as AskAnswer
}
