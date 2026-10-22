import { Application, BlurFilter, Container, FillGradient, Graphics, Matrix, Text } from 'pixi.js'
import { PLAYERS } from '@/data/league'
import { followCamera, type Camera } from '@/core/camera'
import { Heatmap } from '@/core/heatmap'
import { isGoal, lifeFraction } from '@/core/overlays'
import { attackDirection, carrierOf, optionsFor, pressersOf } from '@/core/possession'
import type { Persona } from '@/state/profile'
import type { OverlayEnvelope } from '@/types/overlay'
import { PITCH_LENGTH, PITCH_WIDTH } from '@/types/schema'
import type { TrackingFrame } from '@/types/schema'
import { FLOODLIGHTS, type PitchPalette } from './palette'

export interface TeamLook {
  primary: string
  secondary: string
}

export interface Point {
  x: number
  y: number
}

/** Heatmap ramp: cool to hot, each band a flat colour so the edges stay crisp. */
const HEAT_BANDS = [
  { upTo: 0.3, color: 0xf2a516, alpha: 0.3 },
  { upTo: 0.55, color: 0xf58a14, alpha: 0.55 },
  { upTo: 0.8, color: 0xff5a1f, alpha: 0.75 },
  { upTo: 1, color: 0xfff0c8, alpha: 0.9 },
]
const hex = (c: string) => parseInt(c.replace('#', ''), 16)

interface PlayerSprite {
  root: Container
  disc: Graphics
  label: Text
  team: string
}

/** How far the camera zooms in on a followed player. */
const FOCUS_ZOOM = { landscape: 2.1, portrait: 1.6 }

/**
 * Draws the 2D tactical pitch with PixiJS. Pitch coordinates are metres (105 x 68, origin
 * bottom-left). In a portrait container the pitch turns 90 degrees so it still fills the screen.
 * Everything sits in one `world` container so a camera can follow a player (player focus mode).
 */
export class PitchRenderer {
  private app = new Application()
  private world = new Container()
  private grass = new Container()
  private lines = new Graphics()
  private heat = new Graphics()
  private heatmap = new Heatmap()
  private heatDirty = false
  private focus: string | null = null
  private cam: Camera = { x: 0, y: 0, zoom: 1 }
  private lastDrawMs = 0
  private pitchMatrix = new Matrix()
  private annotations = new Graphics()
  private playersLayer = new Container()
  private effects = new Graphics()
  private ballShadow = new Graphics()
  private trail: Point[] = []
  private fit = 1
  private ball = new Graphics()
  private sprites = new Map<string, PlayerSprite>()
  private looks: Record<string, TeamLook> = {}
  private layers: Persona = 'casual'
  private ready = false
  private w = 0
  private h = 0
  private portrait = false
  private scale = 1
  private ox = 0
  private oy = 0
  private pad = 0

  /** `pal` repaints the surface and highlights; the default is the floodlights broadcast look. */
  constructor(private readonly pal: PitchPalette = FLOODLIGHTS) {}

  async mount(host: HTMLElement): Promise<void> {
    await this.app.init({
      resizeTo: host,
      backgroundAlpha: 0,
      antialias: true,
      autoDensity: true,
      resolution: Math.min(window.devicePixelRatio || 1, 2),
      preference: 'webgl',
    })
    host.appendChild(this.app.canvas)
    this.app.canvas.style.display = 'block'
    this.app.canvas.setAttribute('aria-hidden', 'true')
    // A light blur only softens the cell edges; the bands in drawHeat keep the contours.
    this.heat.filters = [new BlurFilter({ strength: 5, quality: 3 })]
    this.app.stage.addChild(this.world)
    this.world.addChild(
      this.grass,
      this.lines,
      this.heat,
      this.annotations,
      this.effects,
      this.playersLayer,
      this.ballShadow,
      this.ball,
    )
    // The loop in Stage drives rendering, so stop Pixi's own ticker.
    this.app.ticker.stop()
    this.ready = true
    this.layout(host.clientWidth, host.clientHeight, true)
  }

  destroy(): void {
    if (!this.ready) return
    this.ready = false
    this.app.destroy(true, { children: true })
  }

  setLooks(looks: Record<string, TeamLook>): void {
    this.looks = looks
  }

  /**
   * What the pitch draws on top of the players, per persona. Analyst: who is pressing the ball
   * and the two simplest passes. First match: a big arrow showing which way the team on the ball
   * is going, and no shirt numbers. Audio-described: a bigger ball and a thicker carrier ring.
   */
  setLayers(persona: Persona): void {
    if (persona === this.layers) return
    this.layers = persona
    if (!this.ready) return
    for (const sp of this.sprites.values()) sp.label.visible = persona !== 'kids'
  }

  /** Metres to CSS pixels inside the host element. */
  project(x: number, y: number): Point {
    if (this.portrait) return { x: this.ox + y * this.scale, y: this.oy + x * this.scale }
    return { x: this.ox + x * this.scale, y: this.oy + (PITCH_WIDTH - y) * this.scale }
  }

  /** Follow one player (player focus mode), or null for the whole pitch. */
  setFocus(id: string | null): void {
    if (id === this.focus) return
    this.focus = id
    this.heatmap.reset()
    // React can call this after the pane unmounted and the graphics were destroyed.
    if (this.ready) this.heat.clear()
  }

  /** Metres to CSS pixels on screen, after the camera. Use this to place DOM tags. */
  screen(x: number, y: number): Point {
    const p = this.project(x, y)
    return {
      x: p.x * this.world.scale.x + this.world.x,
      y: p.y * this.world.scale.y + this.world.y,
    }
  }

  /** Shrink the pitch inside the canvas, e.g. to leave room for a perspective tilt. */
  setFit(fit: number): void {
    if (fit === this.fit) return
    this.fit = fit
    if (this.ready) this.layout(this.w, this.h, true)
  }

  get pixelsPerMetre(): number {
    return this.scale
  }

  /** Re-layout if the host size changed. Cheap when nothing changed. */
  layout(w: number, h: number, force = false): void {
    if (!this.ready) return
    if (!force && w === this.w && h === this.h) return
    this.w = w
    this.h = h
    this.portrait = h > w * 1.1
    const long = this.portrait ? h : w
    const short = this.portrait ? w : h
    this.pad = Math.max(10, Math.min(long, short * 1.5) * 0.03)
    const s =
      Math.min((long - this.pad * 2) / PITCH_LENGTH, (short - this.pad * 2) / PITCH_WIDTH) *
      this.fit
    this.scale = s
    const pw = (this.portrait ? PITCH_WIDTH : PITCH_LENGTH) * s
    const ph = (this.portrait ? PITCH_LENGTH : PITCH_WIDTH) * s
    this.ox = (w - pw) / 2
    this.oy = (h - ph) / 2
    if (!this.focus) this.cam = { x: w / 2, y: h / 2, zoom: 1 }
    this.drawPitch()
    for (const sp of this.sprites.values()) this.drawDisc(sp)
  }

  private drawPitch(): void {
    this.grass.removeChildren()
    this.lines.clear()
    const m = this.portrait
      ? new Matrix(0, this.scale, this.scale, 0, this.ox, this.oy)
      : new Matrix(this.scale, 0, 0, -this.scale, this.ox, this.oy + PITCH_WIDTH * this.scale)
    this.pitchMatrix = m
    this.heatDirty = true
    const g = new Graphics()
    // Mown apron around the touchlines gives the surface some depth.
    g.rect(-3, -3, PITCH_LENGTH + 6, PITCH_WIDTH + 6).fill(this.pal.apron)
    const stripes = this.pal.stripes
    if (!stripes) g.rect(0, 0, PITCH_LENGTH, PITCH_WIDTH).fill(this.pal.grassA)
    const sw = PITCH_LENGTH / stripes
    for (let i = 0; i < stripes; i++) {
      g.rect(i * sw, 0, sw + 0.01, PITCH_WIDTH).fill(i % 2 ? this.pal.grassA : this.pal.grassB)
    }
    g.setFromMatrix(m)
    this.grass.addChild(g)

    // Floodlight falloff: lit toward the far touchline, darker near the camera.
    if (!this.portrait && this.pal.light) {
      const light = new Graphics()
      const grad = new FillGradient({
        type: 'linear',
        start: { x: 0, y: 0 },
        end: { x: 0, y: 1 },
        colorStops: [
          { offset: 0, color: 'rgba(0,0,0,0.42)' },
          { offset: 0.45, color: 'rgba(0,0,0,0)' },
          { offset: 1, color: 'rgba(255,238,190,0.14)' },
        ],
      })
      light.rect(-3, -3, PITCH_LENGTH + 6, PITCH_WIDTH + 6).fill(grad)
      light.setFromMatrix(m)
      this.grass.addChild(light)
    }

    const L = this.lines
    const lw = this.pal.lineWidth
    const stroke = { width: lw, color: this.pal.line, alpha: this.pal.lineAlpha }
    L.rect(0, 0, PITCH_LENGTH, PITCH_WIDTH).stroke(stroke)
    L.moveTo(PITCH_LENGTH / 2, 0)
      .lineTo(PITCH_LENGTH / 2, PITCH_WIDTH)
      .stroke(stroke)
    L.circle(PITCH_LENGTH / 2, PITCH_WIDTH / 2, 9.15).stroke(stroke)
    L.circle(PITCH_LENGTH / 2, PITCH_WIDTH / 2, 0.35).fill({
      color: this.pal.line,
      alpha: this.pal.lineAlpha,
    })
    for (const side of [0, 1]) {
      const sx = side ? PITCH_LENGTH : 0
      const dir = side ? -1 : 1
      L.rect(side ? PITCH_LENGTH - 16.5 : 0, (PITCH_WIDTH - 40.32) / 2, 16.5, 40.32).stroke(stroke)
      L.rect(side ? PITCH_LENGTH - 5.5 : 0, (PITCH_WIDTH - 18.32) / 2, 5.5, 18.32).stroke(stroke)
      L.circle(sx + dir * 11, PITCH_WIDTH / 2, 0.35).fill({
        color: this.pal.line,
        alpha: this.pal.lineAlpha,
      })
      // penalty arc, the part outside the box
      const a = Math.acos((16.5 - 11) / 9.15)
      const cx = sx + dir * 11
      const cy = PITCH_WIDTH / 2
      if (side)
        L.moveTo(cx + 9.15 * Math.cos(Math.PI - a), cy + 9.15 * Math.sin(Math.PI - a)).arc(
          cx,
          cy,
          9.15,
          Math.PI - a,
          Math.PI + a,
        )
      else L.moveTo(cx + 9.15 * Math.cos(-a), cy + 9.15 * Math.sin(-a)).arc(cx, cy, 9.15, -a, a)
      L.stroke(stroke)
      // goal mouth
      L.rect(side ? PITCH_LENGTH : -1.6, (PITCH_WIDTH - 7.32) / 2, 1.6, 7.32).stroke({
        width: lw,
        color: this.pal.line,
        alpha: 0.45,
      })
    }
    L.setFromMatrix(m)
  }

  private radius(): number {
    return Math.max(9, this.scale * 1.3)
  }

  private drawDisc(sp: PlayerSprite): void {
    const look = this.looks[sp.team]
    const r = this.radius()
    const primary = hex(look?.primary ?? '#888888')
    sp.disc.clear()
    // soft ground shadow, then the kit disc with a thin secondary-colour rim
    sp.disc.ellipse(r * 0.15, r * 0.55, r * 1.1, r * 0.6).fill({ color: 0x000000, alpha: 0.32 })
    sp.disc.circle(0, 0, r).fill(primary)
    sp.disc.circle(0, 0, r - Math.max(1, r * 0.1)).stroke({
      width: Math.max(1.5, r * 0.18),
      color: hex(look?.secondary ?? '#ffffff'),
    })
    sp.label.style.fontSize = Math.max(10, r * 1.1)
    sp.label.style.fill = textColourFor(look?.primary ?? '#888888')
  }

  private ensureSprite(id: string): PlayerSprite {
    let sp = this.sprites.get(id)
    if (sp) return sp
    const root = new Container()
    const disc = new Graphics()
    const shirt = PLAYERS[id]?.shirt ?? Number(id.split('-')[1] ?? 0)
    const label = new Text({
      text: String(shirt),
      style: { fontFamily: 'Barlow Condensed', fontWeight: '700', fontSize: 12, fill: 0xffffff },
    })
    label.anchor.set(0.5, 0.52)
    label.resolution = 3 // stays sharp when the camera zooms in
    label.visible = this.layers !== 'kids'
    root.addChild(disc, label)
    this.playersLayer.addChild(root)
    sp = { root, disc, label, team: id.split('-')[0] ?? '' }
    this.sprites.set(id, sp)
    this.drawDisc(sp)
    return sp
  }

  /** Draw one frame. `t` is render time, used for annotation animation. */
  draw(frame: TrackingFrame | null, overlays: OverlayEnvelope[], t: number): void {
    if (!this.ready) return
    const fx = this.effects
    fx.clear()
    const now = performance.now()
    const dt = this.lastDrawMs ? Math.min(0.1, (now - this.lastDrawMs) / 1000) : 0
    this.lastDrawMs = now
    if (frame) {
      const at = new Map<string, Point>()
      // After a red card (or a substitution) a player leaves the frame: hide his sprite.
      for (const sp of this.sprites.values()) sp.root.visible = false
      // Dim everyone else only while the followed player is actually on the pitch.
      const focusOn = this.focus !== null && frame.players.some((p) => p.id === this.focus)
      for (const p of frame.players) {
        const sp = this.ensureSprite(p.id)
        sp.root.visible = true
        const pt = this.project(p.x, p.y)
        sp.root.position.set(pt.x, pt.y)
        sp.root.alpha = focusOn && p.id !== this.focus ? 0.45 : 1
        // Zooming in should bring the pitch closer, not turn the players into dinner plates.
        sp.root.scale.set(1 / Math.sqrt(this.cam.zoom))
        at.set(p.id, pt)
        if (p.id === this.focus && this.heatmap.sample(p.x, p.y, t)) this.heatDirty = true
      }
      this.moveCamera(this.focus ? (at.get(this.focus) ?? null) : null, dt)
      if (this.heatDirty) this.drawHeat()
      const b = this.project(frame.ball.x, frame.ball.y)
      const big = this.layers === 'accessibility'
      const r = Math.max(3.5, this.scale * 0.42) * (big ? 1.6 : 1)
      // Disc radius on screen after the camera, matching the sprite counter-scale.
      const pr = this.radius() / Math.sqrt(this.cam.zoom)

      // Ball trail: a short fading comet.
      this.trail.push(b)
      if (this.trail.length > 14) this.trail.shift()
      for (let i = 1; i < this.trail.length; i++) {
        const k = i / this.trail.length
        const p0 = this.trail[i - 1]!
        const p1 = this.trail[i]!
        fx.moveTo(p0.x, p0.y)
          .lineTo(p1.x, p1.y)
          .stroke({
            width: 1 + k * r * 0.9,
            color: this.pal.accent,
            alpha: 0.06 + k * 0.3,
            cap: 'round',
          })
      }

      // Ring on whoever is closest to the ball, when they are close enough to be on it.
      let near: Point | null = null
      let nearD = Infinity
      for (const pt of at.values()) {
        const d = Math.hypot(pt.x - b.x, pt.y - b.y)
        if (d < nearD) {
          nearD = d
          near = pt
        }
      }
      if (near && nearD < pr * 2.6) {
        // Thin white ring for the ball carrier; amber is kept for the viewer's own player.
        const followed = this.focus !== null
        const color = followed ? this.pal.line : this.pal.accent
        const ring = (followed ? 1.5 : 2) * (big ? 2.2 : 1)
        fx.circle(near.x, near.y, pr + 5).stroke({ width: ring, color, alpha: 0.85 })
        if (!followed) fx.circle(near.x, near.y, pr + 9).stroke({ width: 6, color, alpha: 0.12 })
      }

      if (this.layers === 'analyst' || this.layers === 'kids') this.drawLayers(frame, at, pr)

      // The followed player: a steady ring with a soft halo.
      const me = this.focus ? at.get(this.focus) : undefined
      if (me) {
        fx.circle(me.x, me.y, pr + 4).stroke({ width: 2.5, color: this.pal.accent, alpha: 1 })
        fx.circle(me.x, me.y, pr + 10).stroke({ width: 8, color: this.pal.accent, alpha: 0.14 })
      }

      // The one orchestrated moment: a ring rolls out from the scorer.
      for (const o of overlays) {
        if (!isGoal(o) || o.anchor?.type !== 'player') continue
        const who = at.get(o.anchor.id)
        const k = (t - o.show_at) / 1.8
        if (!who || k < 0 || k > 1) continue
        const e = 1 - Math.pow(1 - k, 3)
        fx.circle(who.x, who.y, pr + e * pr * 7).stroke({
          width: 3 * (1 - k) + 1,
          color: this.pal.accent,
          alpha: 0.8 * (1 - k),
        })
      }

      this.ballShadow
        .clear()
        .ellipse(b.x + 1, b.y + r * 0.9, r * 0.95, r * 0.5)
        .fill({ color: 0, alpha: 0.35 })
      this.ball
        .clear()
        .circle(b.x, b.y, r)
        .fill(this.pal.ball)
        .stroke({ width: 1.2, color: this.pal.ink, alpha: 0.8 })
    }
    this.drawAnnotations(overlays, t)
    this.app.renderer.render(this.app.stage)
  }

  /** The persona's extra pitch layer, drawn on the effects graphics just under the players. */
  private drawLayers(frame: TrackingFrame, at: Map<string, Point>, pr: number): void {
    const c = carrierOf(frame)
    const cp = c ? at.get(c.id) : undefined
    if (!c || !cp) return
    const fx = this.effects
    if (this.layers === 'analyst') {
      for (const o of optionsFor(frame, c)) {
        const op = at.get(o.id)
        if (!op) continue
        fx.moveTo(cp.x, cp.y)
          .lineTo(op.x, op.y)
          .stroke({ width: 1.25, color: this.pal.line, alpha: 0.7 })
      }
      for (const p of pressersOf(frame, c)) {
        const pp = at.get(p.id)
        if (!pp) continue
        fx.circle(pp.x, pp.y, pr + 4).stroke({ width: 2, color: this.pal.press, alpha: 0.95 })
        fx.circle(pp.x, pp.y, pr + 9).stroke({ width: 7, color: this.pal.press, alpha: 0.18 })
      }
      return
    }
    // First match: a chevron in the carrier's kit, out ahead of them, pointing the way they attack.
    const team = c.id.split('-')[0] ?? ''
    const dir = attackDirection(frame, team)
    const ahead = this.project(c.x + dir, c.y)
    const dx = ahead.x - cp.x
    const dy = ahead.y - cp.y
    const len = Math.hypot(dx, dy) || 1
    const ux = dx / len
    const uy = dy / len
    const s = Math.max(14, pr * 2.6)
    const tipD = pr * 1.8 + s * 1.4
    const tip = { x: cp.x + ux * tipD, y: cp.y + uy * tipD }
    const back = { x: tip.x - ux * s * 1.4, y: tip.y - uy * s * 1.4 }
    const notch = { x: tip.x - ux * s * 0.8, y: tip.y - uy * s * 0.8 }
    const left = { x: back.x - uy * s, y: back.y + ux * s }
    const right = { x: back.x + uy * s, y: back.y - ux * s }
    const look = this.looks[team]
    fx.poly([tip.x, tip.y, left.x, left.y, notch.x, notch.y, right.x, right.y])
      .fill({ color: hex(look?.primary ?? '#ffb020'), alpha: 0.95 })
      .stroke({ width: 2, color: hex(look?.secondary ?? '#0d1014'), alpha: 0.9, join: 'round' })
  }

  private moveCamera(target: Point | null, dt: number): void {
    const zoom = target ? (this.portrait ? FOCUS_ZOOM.portrait : FOCUS_ZOOM.landscape) : 1
    const goal = target ? { ...target, zoom } : { x: this.w / 2, y: this.h / 2, zoom: 1 }
    const pw = (this.portrait ? PITCH_WIDTH : PITCH_LENGTH) * this.scale
    const ph = (this.portrait ? PITCH_LENGTH : PITCH_WIDTH) * this.scale
    this.cam = followCamera(
      this.cam,
      goal,
      dt,
      { w: this.w, h: this.h },
      { left: this.ox, top: this.oy, width: pw, height: ph },
    )
    this.world.scale.set(this.cam.zoom)
    this.world.position.set(
      this.w / 2 - this.cam.x * this.cam.zoom,
      this.h / 2 - this.cam.y * this.cam.zoom,
    )
  }

  /**
   * Heatmap in four hard bands, from deep amber where the player passed through to near white
   * where they lived. Banding reads as a map at a glance; a continuous wash read as smudges.
   */
  private drawHeat(): void {
    this.heatDirty = false
    const g = this.heat
    g.clear()
    if (!this.focus) return
    for (const c of this.heatmap.cells()) {
      const band = HEAT_BANDS.find((b) => c.v <= b.upTo) ?? HEAT_BANDS[HEAT_BANDS.length - 1]!
      g.rect(c.x, c.y, c.w, c.h).fill({ color: band.color, alpha: band.alpha })
    }
    g.setFromMatrix(this.pitchMatrix)
  }

  private drawAnnotations(overlays: OverlayEnvelope[], t: number): void {
    const g = this.annotations
    g.clear()
    for (const o of overlays) {
      if (o.kind !== 'pass_difficulty' || o.anchor?.type !== 'pitch') continue
      const from = o.anchor
      const ex = o.payload['end_x']
      const ey = o.payload['end_y']
      if (typeof ex !== 'number' || typeof ey !== 'number') continue
      const a = this.project(from.x, from.y)
      const b = this.project(ex, ey)
      const life = lifeFraction(o, t)
      const grow = Math.min(1, (t - o.show_at) / 0.35)
      const fade = life > 0.8 ? 1 - (life - 0.8) / 0.2 : 1
      const hard = Number(o.payload['difficulty'] ?? 0)
      const width = 2 + (hard - 70) / 15
      const x = a.x + (b.x - a.x) * grow
      const y = a.y + (b.y - a.y) * grow
      g.moveTo(a.x, a.y)
        .lineTo(x, y)
        .stroke({ width: width + 4, color: this.pal.accent, alpha: 0.16 * fade })
      g.moveTo(a.x, a.y)
        .lineTo(x, y)
        .stroke({ width, color: this.pal.accent, alpha: 0.95 * fade, cap: 'round' })
      g.circle(a.x, a.y, 5).stroke({ width: 1.5, color: this.pal.accent, alpha: fade })
      if (grow >= 1) g.circle(b.x, b.y, 4).fill({ color: this.pal.accent, alpha: fade })
    }
  }
}

/** Dark text on pale shirts, white on dark ones. */
function textColourFor(bg: string): number {
  const n = hex(bg)
  const r = (n >> 16) & 255
  const g = (n >> 8) & 255
  const b = n & 255
  return 0.299 * r + 0.587 * g + 0.114 * b > 150 ? 0x0d1014 : 0xffffff
}
