import { useEffect, useRef, useState } from 'react'
import { CLUBS } from '@/data/league'
import { frameAt } from '@/core/timeline'
import { buffers, tick } from '@/state/runtime'
import { useStore } from '@/state/store'
import { PitchRenderer } from './pitch/PitchRenderer'
import { TagLayer, type TagRegistry, resolveTagPoint } from './TagLayer'

/**
 * The pitch canvas plus the DOM tags that ride on it. One requestAnimationFrame loop reads
 * the stream buffers at render time `t` and draws; React only re-renders when the set of
 * active overlays changes.
 */
export function Stage() {
  const hostRef = useRef<HTMLDivElement>(null)
  const registry = useRef<TagRegistry>(new Map())
  const [renderer, setRenderer] = useState<PitchRenderer | null>(null)
  const meta = useStore((s) => s.meta)

  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    const r = new PitchRenderer()
    let cancelled = false
    let raf = 0
    void (async () => {
      await document.fonts.load('700 14px "Barlow Condensed"').catch(() => undefined)
      await r.mount(host)
      if (cancelled) {
        r.destroy()
        return
      }
      setRenderer(r)
      const loop = (now: number) => {
        r.layout(host.clientWidth, host.clientHeight)
        const t = tick(now)
        const frame = frameAt(buffers.frames, t)
        const active = useStore.getState().active
        r.draw(frame, active, t)
        if (frame) {
          const players = new Map(frame.players.map((p) => [p.id, p]))
          for (const [id, entry] of registry.current) {
            const pt = resolveTagPoint(entry.overlay, players, r)
            if (!pt) continue
            entry.el.style.transform = `translate3d(${pt.x.toFixed(1)}px, ${pt.y.toFixed(1)}px, 0)`
            entry.el.style.visibility = 'visible'
            void id
          }
        }
        raf = requestAnimationFrame(loop)
      }
      raf = requestAnimationFrame(loop)
    })()
    return () => {
      cancelled = true
      cancelAnimationFrame(raf)
      r.destroy()
    }
  }, [])

  useEffect(() => {
    if (!renderer || !meta) return
    const looks: Record<string, { primary: string; secondary: string }> = {}
    for (const code of [meta.home.code, meta.away.code]) {
      const c = CLUBS[code]
      if (c) looks[code] = { primary: c.primary_color, secondary: c.secondary_color }
    }
    renderer.setLooks(looks)
    renderer.layout(hostRef.current?.clientWidth ?? 0, hostRef.current?.clientHeight ?? 0, true)
  }, [renderer, meta])

  return (
    <div className="relative size-full">
      <div ref={hostRef} className="absolute inset-0" />
      <TagLayer registry={registry} />
    </div>
  )
}
