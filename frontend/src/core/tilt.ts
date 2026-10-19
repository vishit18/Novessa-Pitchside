/**
 * The pitch canvas sits under a CSS perspective tilt so it reads like a gantry camera.
 * DOM overlays (tags) live outside that transform and stay upright, so we need the same
 * projection in code to find where a point on the canvas ends up on screen.
 */
export interface Tilt {
  /** CSS transform for the canvas wrapper. */
  css: string
  /** Canvas pixel (as drawn, untilted) to stage pixel. */
  project: (x: number, y: number) => { x: number; y: number }
}

export function makeTilt(w: number, h: number, degrees: number): Tilt {
  if (degrees === 0) return { css: 'none', project: (x, y) => ({ x, y }) }
  const a = (degrees * Math.PI) / 180
  const persp = Math.max(w, h) * 1.4
  const cx = w / 2
  const cy = h / 2
  return {
    css: `perspective(${persp}px) rotateX(${degrees}deg)`,
    project: (x, y) => {
      const dx = x - cx
      const dy = y - cy
      const yr = dy * Math.cos(a)
      const z = dy * Math.sin(a)
      const s = persp / (persp - z)
      return { x: cx + dx * s, y: cy + yr * s }
    },
  }
}
