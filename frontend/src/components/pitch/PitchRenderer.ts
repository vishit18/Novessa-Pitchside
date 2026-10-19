import { Application, Container, FillGradient, Graphics, Matrix, Text } from 'pixi.js'
import { PLAYERS } from '@/data/league'
import { isGoal, lifeFraction } from '@/core/overlays'
import type { OverlayEnvelope } from '@/types/overlay'
import { PITCH_LENGTH, PITCH_WIDTH } from '@/types/schema'
import type { TrackingFrame } from '@/types/schema'

export interface TeamLook {
  primary: string
  secondary: string
}

export interface Point {
  x: number
  y: number
}

const APRON = 0x143a28
const GRASS_A = 0x1b4a33
const GRASS_B = 0x1e5237
const LINE = 0xe9eef2
const AMBER = 0xffb020
const INK = 0x0d1014

const hex = (c: string) => parseInt(c.replace('#', ''), 16)

interface PlayerSprite {
  root: Container
  disc: Graphics
  label: Text
  team: string
}

/**
 * Draws the 2D tactical pitch with PixiJS. Pitch coordinates are metres (105 x 68, origin
 * bottom-left). In a portrait container the pitch turns 90 degrees so it still fills the screen.
 */
export class PitchRenderer {
  private app = new Application()
  private grass = new Container()
  private lines = new Graphics()
  private annotations = new Graphics()
  private playersLayer = new Container()
  private effects = new Graphics()
  private ballShadow = new Graphics()
  private trail: Point[] = []
  private fit = 1
  private ball = new Graphics()
  private sprites = new Map<string, PlayerSprite>()
  private looks: Record<string, TeamLook> = {}
  private ready = false
  private w = 0
  private h = 0
  private portrait = false
  private scale = 1
  private ox = 0
  private oy = 0
  private pad = 0

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
    this.app.stage.addChild(
      this.grass,
      this.lines,
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

  /** Metres to CSS pixels inside the host element. */
  project(x: number, y: number): Point {
    if (this.portrait) return { x: this.ox + y * this.scale, y: this.oy + x * this.scale }
    return { x: this.ox + x * this.scale, y: this.oy + (PITCH_WIDTH - y) * this.scale }
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
    this.drawPitch()
    for (const sp of this.sprites.values()) this.drawDisc(sp)
  }

  private drawPitch(): void {
    this.grass.removeChildren()
    this.lines.clear()
    const m = this.portrait
      ? new Matrix(0, this.scale, this.scale, 0, this.ox, this.oy)
      : new Matrix(this.scale, 0, 0, -this.scale, this.ox, this.oy + PITCH_WIDTH * this.scale)
    const g = new Graphics()
    // Mown apron around the touchlines gives the surface some depth.
    g.rect(-3, -3, PITCH_LENGTH + 6, PITCH_WIDTH + 6).fill(APRON)
    const stripes = 14
    const sw = PITCH_LENGTH / stripes
    for (let i = 0; i < stripes; i++) {
      g.rect(i * sw, 0, sw + 0.01, PITCH_WIDTH).fill(i % 2 ? GRASS_A : GRASS_B)
    }
    g.setFromMatrix(m)
    this.grass.addChild(g)

    // Floodlight falloff: lit toward the far touchline, darker near the camera.
    if (!this.portrait) {
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
    const lw = 0.2
    const stroke = { width: lw, color: LINE, alpha: 0.7 }
    L.rect(0, 0, PITCH_LENGTH, PITCH_WIDTH).stroke(stroke)
    L.moveTo(PITCH_LENGTH / 2, 0)
      .lineTo(PITCH_LENGTH / 2, PITCH_WIDTH)
      .stroke(stroke)
    L.circle(PITCH_LENGTH / 2, PITCH_WIDTH / 2, 9.15).stroke(stroke)
    L.circle(PITCH_LENGTH / 2, PITCH_WIDTH / 2, 0.35).fill({ color: LINE, alpha: 0.7 })
    for (const side of [0, 1]) {
      const sx = side ? PITCH_LENGTH : 0
      const dir = side ? -1 : 1
      L.rect(side ? PITCH_LENGTH - 16.5 : 0, (PITCH_WIDTH - 40.32) / 2, 16.5, 40.32).stroke(stroke)
      L.rect(side ? PITCH_LENGTH - 5.5 : 0, (PITCH_WIDTH - 18.32) / 2, 5.5, 18.32).stroke(stroke)
      L.circle(sx + dir * 11, PITCH_WIDTH / 2, 0.35).fill({ color: LINE, alpha: 0.7 })
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
        color: LINE,
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
    if (frame) {
      const at = new Map<string, Point>()
      for (const p of frame.players) {
        const sp = this.ensureSprite(p.id)
        const pt = this.project(p.x, p.y)
        sp.root.position.set(pt.x, pt.y)
        at.set(p.id, pt)
      }
      const b = this.project(frame.ball.x, frame.ball.y)
      const r = Math.max(3.5, this.scale * 0.42)
      const pr = this.radius()

      // Ball trail: a short fading comet.
      this.trail.push(b)
      if (this.trail.length > 14) this.trail.shift()
      for (let i = 1; i < this.trail.length; i++) {
        const k = i / this.trail.length
        const p0 = this.trail[i - 1]!
        const p1 = this.trail[i]!
        fx.moveTo(p0.x, p0.y)
          .lineTo(p1.x, p1.y)
          .stroke({ width: 1 + k * r * 0.9, color: AMBER, alpha: 0.06 + k * 0.3, cap: 'round' })
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
        fx.circle(near.x, near.y, pr + 5).stroke({ width: 2, color: AMBER, alpha: 0.9 })
        fx.circle(near.x, near.y, pr + 9).stroke({ width: 6, color: AMBER, alpha: 0.12 })
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
          color: AMBER,
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
        .fill(0xf6f7f4)
        .stroke({ width: 1.2, color: INK, alpha: 0.8 })
    }
    this.drawAnnotations(overlays, t)
    this.app.renderer.render(this.app.stage)
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
        .stroke({ width: width + 4, color: AMBER, alpha: 0.16 * fade })
      g.moveTo(a.x, a.y)
        .lineTo(x, y)
        .stroke({ width, color: AMBER, alpha: 0.95 * fade, cap: 'round' })
      g.circle(a.x, a.y, 5).stroke({ width: 1.5, color: AMBER, alpha: fade })
      if (grow >= 1) g.circle(b.x, b.y, 4).fill({ color: AMBER, alpha: fade })
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
