import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react'
import { GATEWAY_HTTP } from '@/net/api'
import { useSession, useSessionState } from './useSession'

/**
 * The line the browser refused to play because the viewer has not yet tapped or pressed a key on
 * the page. It is shared across the page so one prompt can show wherever the audio was asked for.
 */
let blockedUrl: string | null = null
const blockedListeners = new Set<() => void>()
const setBlocked = (url: string | null): void => {
  blockedUrl = url
  blockedListeners.forEach((fn) => fn())
}
const subscribeBlocked = (fn: () => void): (() => void) => {
  blockedListeners.add(fn)
  return () => void blockedListeners.delete(fn)
}

/** True while a spoken line is waiting for the viewer's first tap. */
export function useAudioBlocked(): boolean {
  return useSyncExternalStore(
    subscribeBlocked,
    () => blockedUrl !== null,
    () => false,
  )
}

/** One audio element at a time: starting a line stops the one before it. */
export function useAudio() {
  const el = useRef<HTMLAudioElement | null>(null)
  return useMemo(() => {
    const unlockEvents = ['pointerup', 'keydown'] as const
    const stopWaiting = () =>
      unlockEvents.forEach((e) => window.removeEventListener(e, retry, true))
    function retry() {
      stopWaiting()
      if (blockedUrl) start(blockedUrl)
    }
    function start(url: string) {
      el.current?.pause()
      const a = new Audio(url)
      el.current = a
      a.play().then(
        () => {
          if (blockedUrl === url) setBlocked(null)
        },
        (err: unknown) => {
          // Browsers refuse audio until the viewer has tapped or pressed a key. Keep the line,
          // say so on screen, and play it on the first tap or key press instead of dropping it.
          if (el.current !== a || !(err instanceof DOMException) || err.name !== 'NotAllowedError')
            return
          setBlocked(url)
          unlockEvents.forEach((e) => window.addEventListener(e, retry, true))
        },
      )
    }
    return {
      play: start,
      stop() {
        el.current?.pause()
        el.current = null
        stopWaiting()
        setBlocked(null)
      },
    }
  }, [])
}

/**
 * Spoken commentary on or off. With it on, each new card is spoken once, as it arrives, in the
 * viewer's language. Audio-described viewers start with it on. Cards from before it was switched
 * on (the story so far sent on join) are never spoken. Needs a session in context.
 */
export function useCommentary() {
  const session = useSession()
  const feed = useSessionState((s) => s.feed)
  const persona = useSessionState((s) => s.profile.persona)
  const [on, setOn] = useState(persona === 'accessibility')
  const since = useRef(session.store.getState().t)
  const player = useAudio()
  const spoken = useRef(new Set<string>())
  const newest = feed[0]

  useEffect(() => {
    if (!on || !newest?.audioUrl || spoken.current.has(newest.id)) return
    if (newest.showAt < since.current) return
    spoken.current.add(newest.id)
    player.play(`${GATEWAY_HTTP}${newest.audioUrl}`)
  }, [on, newest, player])

  // Leaving the page must not leave a "tap to hear" prompt behind for the next one.
  useEffect(() => () => player.stop(), [player])

  const toggle = () => {
    if (on) player.stop()
    else since.current = session.store.getState().t
    setOn(!on)
  }
  return { on, toggle, player }
}
