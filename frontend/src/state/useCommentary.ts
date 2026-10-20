import { useEffect, useMemo, useRef, useState } from 'react'
import { GATEWAY_HTTP } from '@/net/api'
import { useSessionState } from './useSession'

/** One audio element at a time: starting a line stops the one before it. */
export function useAudio() {
  const el = useRef<HTMLAudioElement | null>(null)
  return useMemo(
    () => ({
      play(url: string) {
        el.current?.pause()
        const a = new Audio(url)
        el.current = a
        // Browsers refuse audio until the viewer has tapped something; the toggle is that tap.
        void a.play().catch(() => undefined)
      },
      stop() {
        el.current?.pause()
        el.current = null
      },
    }),
    [],
  )
}

/**
 * Spoken commentary on or off. With it on, each new card is spoken once, as it arrives, in the
 * viewer's language. Needs a session in context.
 */
export function useCommentary() {
  const feed = useSessionState((s) => s.feed)
  const [on, setOn] = useState(false)
  const player = useAudio()
  const spoken = useRef(new Set<string>())
  const newest = feed[0]

  useEffect(() => {
    if (!on || !newest?.audioUrl || spoken.current.has(newest.id)) return
    spoken.current.add(newest.id)
    player.play(`${GATEWAY_HTTP}${newest.audioUrl}`)
  }, [on, newest, player])

  const toggle = () => {
    if (on) player.stop()
    setOn(!on)
  }
  return { on, toggle, player }
}
