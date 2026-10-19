import clubsJson from '@data/league/clubs.json'
import playersJson from '@data/league/players.json'
import type { Club, PlayerInfo } from '@/types/schema'

/** Fictional league data, shipped in the repo under data/league. */
export const CLUBS: Record<string, Club> = Object.fromEntries(
  (clubsJson.clubs as Club[]).map((c) => [c.code, c]),
)

export const PLAYERS: Record<string, PlayerInfo> = Object.fromEntries(
  Object.values(playersJson as Record<string, PlayerInfo[]>)
    .flat()
    .map((p) => [p.id, { id: p.id, name: p.name, shirt: p.shirt, position: p.position }]),
)
