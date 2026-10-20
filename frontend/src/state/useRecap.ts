import { useCallback, useEffect, useState } from 'react'
import { fallbackTime } from '@/core/recap'
import { ApiError, getCatchUp, getRecap, type CatchUp, type Recap, type RecapKind } from '@/net/api'

export type RecapState =
  | { status: 'loading'; slow: boolean }
  /** The Recap Editor answered. `catchUp` is the key-moments timeline up to the recap's time. */
  | { status: 'ready'; recap: Recap; catchUp: CatchUp | null }
  /** The gateway has its agents switched off. Only the computed catch-up is available. */
  | { status: 'off'; catchUp: CatchUp | null }
  | { status: 'failed' }

/** A first recap for a match takes about 15 seconds; say so after this long. */
const SLOW_AFTER_MS = 3000

/** Loads one recap and the computed key moments that go with it. */
export function useRecap(
  matchId: string,
  kind: RecapKind,
  persona: string,
  lang: string,
): { state: RecapState; retry: () => void } {
  const [state, setState] = useState<RecapState>({ status: 'loading', slow: false })
  const [nonce, setNonce] = useState(0)

  useEffect(() => {
    let live = true
    const slowTimer = window.setTimeout(
      () =>
        live && setState((s) => (s.status === 'loading' ? { status: 'loading', slow: true } : s)),
      SLOW_AFTER_MS,
    )
    const run = async () => {
      setState({ status: 'loading', slow: false })
      const moments = (t: number) => getCatchUp(matchId, t).catch(() => null)
      try {
        const recap = await getRecap(matchId, kind, persona, lang)
        const catchUp = await moments(recap.t_match)
        if (live) setState({ status: 'ready', recap, catchUp })
      } catch (err) {
        if (err instanceof ApiError && err.status === 503) {
          const catchUp = await moments(fallbackTime(kind))
          if (live) setState({ status: 'off', catchUp })
        } else if (live) {
          setState({ status: 'failed' })
        }
      }
    }
    void run()
    return () => {
      live = false
      window.clearTimeout(slowTimer)
    }
  }, [matchId, kind, persona, lang, nonce])

  const retry = useCallback(() => setNonce((n) => n + 1), [])
  return { state, retry }
}
