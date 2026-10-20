import { useCallback, useEffect, useRef, useState } from 'react'
import { justWorked } from '@/core/control'
import { getHealth, getInsights, type HealthResponse, type Insight } from '@/net/control'

const HEALTH_EVERY_MS = 1000
const INSIGHTS_EVERY_MS = 2500
/** How long a node stays lit after its call count rises. */
const LIT_MS = 1400

export interface ControlData {
  health: HealthResponse | null
  insights: Insight[]
  /** Agent ids that worked in the last second or so. */
  lit: ReadonlySet<string>
  /** The last poll failed. The previous numbers stay on screen. */
  offline: boolean
  refresh: () => void
}

/** Polls the gateway for agent health and the moments the agents have handled. */
export function useControlData(matchId: string): ControlData {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [insights, setInsights] = useState<Insight[]>([])
  const [lit, setLit] = useState<ReadonlySet<string>>(new Set())
  const [offline, setOffline] = useState(false)
  const [nonce, setNonce] = useState(0)
  const last = useRef<HealthResponse['agents'] | null>(null)

  useEffect(() => {
    const ctl = new AbortController()
    const timers = new Set<number>()
    const later = (fn: () => void, ms: number) => {
      const id = window.setTimeout(() => {
        timers.delete(id)
        fn()
      }, ms)
      timers.add(id)
    }

    const pollHealth = async () => {
      try {
        const next = await getHealth(ctl.signal)
        setHealth(next)
        setOffline(false)
        const worked = justWorked(last.current, next.agents)
        last.current = next.agents
        if (worked.length) {
          setLit((cur) => new Set([...cur, ...worked]))
          later(
            () =>
              setLit((cur) => {
                const rest = new Set(cur)
                worked.forEach((id) => rest.delete(id))
                return rest
              }),
            LIT_MS,
          )
        }
      } catch {
        if (!ctl.signal.aborted) setOffline(true)
      }
      if (!ctl.signal.aborted) later(pollHealth, HEALTH_EVERY_MS)
    }

    const pollInsights = async () => {
      try {
        setInsights(await getInsights(matchId, ctl.signal))
      } catch {
        // The health poll already reports the gateway being unreachable.
      }
      if (!ctl.signal.aborted) later(pollInsights, INSIGHTS_EVERY_MS)
    }

    void pollHealth()
    void pollInsights()
    return () => {
      ctl.abort()
      timers.forEach((id) => window.clearTimeout(id))
    }
  }, [matchId, nonce])

  const refresh = useCallback(() => setNonce((n) => n + 1), [])
  return { health, insights, lit, offline, refresh }
}
