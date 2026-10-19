import { Application, Container, Graphics, Matrix, Text } from 'pixi.js'
import { PLAYERS } from '@/data/league'
import { lifeFraction } from '@/core/overlays'
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
  private ballShadow = new Graphics()
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
    const s = Math.min((long - this.pad * 2) / PITCH_LENGTH, (short - this.pad * 2) / PITCH_WIDTH)
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
    const stripes = 14
    const sw = PITCH_LENGTH / stripes
    for (let i = 0; i < stripes; i++) {
      g.rect(i * sw, 0, sw + 0.01, PITCH_WIDTH).fill(i % 2 ? GRASS_A : GRASS_B)
    }
    g.setFromMatrix(m)
    this.grass.addChild(g)

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

  private drawDisc(sp: PlayerSprite): void {
    const look = this.looks[sp.team]
    const r = Math.max(8, this.scale * 1.05)
    sp.disc.clear()
    sp.disc.circle(0, r * 0.28, r).fill({ color: 0x000000, alpha: 0.28 })
    sp.disc.circle(0, 0, r).fill(hex(look?.primary ?? '#888888'))
    sp.disc
      .circle(0, 0, r)
      .stroke({ width: Math.max(1.5, r * 0.16), color: hex(look?.secondary ?? '#ffffff') })
    sp.label.style.fontSize = Math.max(9, r * 1.05)
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
    if (frame) {
      for (const p of frame.players) {
        const sp = this.ensureSprite(p.id)
        const pt = this.project(p.x, p.y)
        sp.root.position.set(pt.x, pt.y)
      }
      const b = this.project(frame.ball.x, frame.ball.y)
      const r = Math.max(3.5, this.scale * 0.42)
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
