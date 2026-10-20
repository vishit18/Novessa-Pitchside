import type { MatchMeta, PlayerFrame, TeamSheet, TrackingFrame } from '@/types/schema'

const PITCH_L = 105
const PITCH_W = 68
const GROUP_ORDER = { GK: 0, DEF: 1, MID: 2, FWD: 3 } as const

/** Rows of a formation string, back to front: "4-3-3" is [4, 3, 3]. Falls back to 4-4-2. */
export function formationRows(formation: string): number[] {
  const rows = formation.split('-').map(Number)
  return rows.length >= 2 && rows.every((n) => n > 0) ? rows : [4, 4, 2]
}

/** One side lined up in its own half, attacking toward +x. */
function lineUp(sheet: TeamSheet): PlayerFrame[] {
  const ordered = [...sheet.starters].sort(
    (a, b) => GROUP_ORDER[a.group] - GROUP_ORDER[b.group] || a.slot - b.slot,
  )
  const rows = formationRows(sheet.formation)
  const out: PlayerFrame[] = []
  const keeper = ordered.shift()
  if (keeper) out.push({ id: keeper.player_id, x: 5, y: PITCH_W / 2, v_kmh: 0 })
  rows.forEach((n, r) => {
    const x = 20 + (r * 28) / Math.max(rows.length - 1, 1)
    for (let i = 0; i < n; i++) {
      const p = ordered.shift()
      if (!p) return
      out.push({ id: p.player_id, x, y: ((i + 1) * PITCH_W) / (n + 1), v_kmh: 0 })
    }
  })
  return out
}

/**
 * Both teams lined up for kick-off. Shown while the feed is still connecting, so the pitch
 * has its players on it instead of a dimmed empty screen. Home attacks right, away left.
 */
export function preKickFrame(meta: MatchMeta): TrackingFrame {
  const away = lineUp(meta.away).map((p) => ({ ...p, x: PITCH_L - p.x, y: PITCH_W - p.y }))
  return {
    match_id: meta.match_id,
    t_match: 0,
    ball: { x: PITCH_L / 2, y: PITCH_W / 2, z: 0 },
    players: [...lineUp(meta.home), ...away],
  }
}
