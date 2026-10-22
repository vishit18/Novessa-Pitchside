import type { PlayerStatsEntry } from '@/types/overlay'

export type Position = 'GK' | 'DEF' | 'MID' | 'FWD'

/** Where one player stands on one measure among the players in the same position. */
export interface Rank {
  rank: number
  of: number
  group: Position
}

/** Fewer players than this in a group and a rank says nothing (two keepers, one sub). */
const MIN_GROUP = 3

/**
 * Rank a player on one measure against everyone in the same position who has played in this
 * match (on the pitch now, or with any minutes before going off). Ties share the better rank.
 * Returns null when the player has no value yet (or zero) or the group is too small to compare.
 */
export function rankAmong(
  players: PlayerStatsEntry[],
  id: string,
  value: (p: PlayerStatsEntry) => number | null,
  positionOf: (id: string) => Position | undefined,
): Rank | null {
  const group = positionOf(id)
  const me = players.find((p) => p.player_id === id)
  const mine = me ? value(me) : null
  // Nothing yet ranks nothing: "#1 of 4" at 0 passes only means nobody has passed.
  if (!group || mine == null || mine <= 0) return null
  const peers = players
    .filter((p) => positionOf(p.player_id) === group && (p.on_pitch || p.distance_km > 0))
    .map(value)
    .filter((v): v is number => v != null)
  if (peers.length < MIN_GROUP) return null
  return { rank: 1 + peers.filter((v) => v > mine).length, of: peers.length, group }
}
