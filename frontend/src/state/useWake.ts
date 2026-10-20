import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Whether the viewer has just moved, tapped or pressed a key. Chrome that should stay out of the
 * picture uses it to fade in, then fade away after `holdMs`. Starts awake, so a first-time viewer
 * sees what is there.
 */
export function useWake(holdMs = 3000): { shown: boolean; wake: () => void } {
  const [shown, setShown] = useState(true)
  const timer = useRef<number | undefined>(undefined)
  const wake = useCallback(() => {
    setShown(true)
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setShown(false), holdMs)
  }, [holdMs])
  useEffect(() => {
    wake()
    window.addEventListener('pointermove', wake)
    window.addEventListener('pointerdown', wake)
    window.addEventListener('keydown', wake)
    return () => {
      window.removeEventListener('pointermove', wake)
      window.removeEventListener('pointerdown', wake)
      window.removeEventListener('keydown', wake)
      window.clearTimeout(timer.current)
    }
  }, [wake])
  return { shown, wake }
}
