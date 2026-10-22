/**
 * How far into each match this viewer has watched, so pages that summarise a match (recap,
 * control room) can hold back what they have not seen yet. Per-browser convenience only: with
 * storage blocked, nothing is held back.
 */
const KEY = 'pitchside.seen.v1'

function read(): Record<string, number> {
  try {
    return JSON.parse(window.localStorage.getItem(KEY) ?? '{}') as Record<string, number>
  } catch {
    return {}
  }
}

/** The furthest match second watched, or null if this match was never opened here. */
export function seenUpTo(matchId: string): number | null {
  const t = read()[matchId]
  return typeof t === 'number' ? t : null
}

export function rememberSeen(matchId: string, t: number): void {
  try {
    const all = read()
    if ((all[matchId] ?? 0) >= t) return
    all[matchId] = Math.round(t)
    window.localStorage.setItem(KEY, JSON.stringify(all))
  } catch {
    // Blocked storage: the gate simply never shows.
  }
}

/** Forget a match, so its summaries stop holding anything back (the viewer said show me). */
export function revealAll(matchId: string): void {
  rememberSeen(matchId, Number.MAX_SAFE_INTEGER)
}
