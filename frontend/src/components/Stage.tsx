import { useContext, useEffect, useRef, useState } from 'react'
import { CLUBS } from '@/data/league'
import { makeTilt, type Tilt } from '@/core/tilt'
import { isGoal } from '@/core/overlays'
import { preKickFrame } from '@/core/formation'
import { carrierOf } from '@/core/possession'
import { frameAt } from '@/core/timeline'
import type { TrackingFrame } from '@/types/schema'
import { useSession, useSessionState } from '@/state/useSession'
import { PitchRenderer } from './pitch/PitchRenderer'
import { PitchPaletteContext } from './pitch/palette'
import { TagLayer, type TagRegistry, resolveTagPoint } from './TagLayer'

/** Camera tilt in landscape. Portrait shows the pitch top-down so it can fill the screen. */
const TILT_DEG = 24
const TILT_FIT = 0.92

/**
 * The pitch canvas plus the DOM tags that ride on it. One requestAnimationFrame loop reads
 * the stream buffers at render time `t` and draws; React only re-renders when the set of
 * active overlays changes. The canvas sits under a CSS perspective tilt; tags are placed with
 * the same projection so they stay upright. With a player in the viewer's profile the camera
 * follows that player (player focus mode).
 */
export function Stage() {
  const hostRef = useRef<HTMLDivElement>(null)
  const tiltRef = useRef<HTMLDivElement>(null)
  const registry = useRef<TagRegistry>(new Map())
  // Both teams lined up, drawn until the first real frame arrives.
  const kickoff = useRef<TrackingFrame | null>(null)
  const session = useSession()
  const [renderer, setRenderer] = useState<PitchRenderer | null>(null)
  const meta = useSessionState((s) => s.meta)
  const goalOn = useSessionState((s) => s.active.some(isGoal))
  const focus = useSessionState((s) => s.profile.player)
  const persona = useSessionState((s) => s.profile.persona)
  const palette = useContext(PitchPaletteContext)

  useEffect(() => {
    const host = hostRef.current
    const tiltEl = tiltRef.current
    if (!host || !tiltEl) return
    const r = new PitchRenderer(palette)
    let cancelled = false
    let raf = 0
    let tilt: Tilt = makeTilt(1, 1, 0)
    let sizeKey = ''
    void (async () => {
      await document.fonts.load('700 14px "Barlow Condensed"').catch(() => undefined)
      await r.mount(host)
      if (cancelled) {
        r.destroy()
        return
      }
      setRenderer(r)
      const loop = (now: number) => {
        const w = host.clientWidth
        const h = host.clientHeight
        if (`${w}x${h}` !== sizeKey) {
          sizeKey = `${w}x${h}`
          const deg = h > w * 1.1 ? 0 : TILT_DEG
          tilt = makeTilt(w, h, deg)
          tiltEl.style.transform = tilt.css
          r.setFit(deg ? TILT_FIT : 1)
        }
        r.layout(w, h)
        const t = session.tick(now)
        const frame = frameAt(session.buffers.frames, t) ?? kickoff.current
        const active = session.store.getState().active
        r.draw(frame, active, t)
        if (frame) {
          const players = new Map(frame.players.map((p) => [p.id, p]))
          const project = (x: number, y: number) => {
            const p = r.screen(x, y)
            return tilt.project(p.x, p.y)
          }
          const followed = session.store.getState().profile.player
          if (followed) session.reportFocusSpeed(players.get(followed)?.v_kmh ?? null, now)
          const carrier = carrierOf(frame)
          session.reportCarrierTeam(carrier ? (carrier.id.split('-')[0] ?? null) : null, now)
          for (const entry of registry.current.values()) {
            const pt = resolveTagPoint(entry.overlay, players, project)
            if (!pt) continue
            entry.el.style.transform = `translate3d(${pt.x.toFixed(1)}px, ${pt.y.toFixed(1)}px, 0)`
            entry.el.style.visibility = 'visible'
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
  }, [session, palette])

  useEffect(() => {
    renderer?.setFocus(focus)
  }, [renderer, focus])

  useEffect(() => {
    renderer?.setLayers(persona)
  }, [renderer, persona])

  useEffect(() => {
    if (!renderer || !meta) return
    const looks: Record<string, { primary: string; secondary: string }> = {}
    for (const code of [meta.home.code, meta.away.code]) {
      const c = CLUBS[code]
      if (c) looks[code] = { primary: c.primary_color, secondary: c.secondary_color }
    }
    renderer.setLooks(looks)
    kickoff.current = preKickFrame(meta)
    renderer.layout(hostRef.current?.clientWidth ?? 0, hostRef.current?.clientHeight ?? 0, true)
  }, [renderer, meta])

  return (
    <div className="relative size-full">
      <div ref={tiltRef} className="absolute inset-0">
        <div ref={hostRef} className="absolute inset-0" />
      </div>
      <div
        className="pointer-events-none absolute inset-0 transition-opacity duration-250 ease-[var(--ease-out)]"
        style={{
          opacity: goalOn ? 1 : 0,
          background: 'radial-gradient(75% 75% at 50% 50%, transparent 35%, rgb(0 0 0 / 0.5))',
        }}
      />
      <TagLayer registry={registry} />
    </div>
  )
}
