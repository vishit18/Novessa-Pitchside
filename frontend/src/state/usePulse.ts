import { useEffect, useState } from 'react'
import { getPulse, type PulseSample } from '@/net/api'

/** The gateway samples every 30 match seconds; ask again each time a new sample can exist. */
const SAMPLE_S = 30

/**
 * The match's shape up to the viewer's own clock, refreshed as they watch. A seek in either
 * direction refetches, so a viewer who jumps back never sees the river run ahead of the pitch.
 */
export function usePulse(matchId: string, t: number): PulseSample[] {
  const [rows, setRows] = useState<PulseSample[]>([])
  const bucket = Math.floor(Math.max(0, t) / SAMPLE_S)
  useEffect(() => {
    let live = true
    // A short wait so dragging the timeline asks once, where it lands.
    const id = window.setTimeout(() => {
      getPulse(matchId, bucket * SAMPLE_S)
        .then((r) => live && setRows(r))
        .catch(() => undefined)
    }, 250)
    return () => {
      live = false
      window.clearTimeout(id)
    }
  }, [matchId, bucket])
  return rows
}
