/** A 2D camera over the drawn pitch: centre (in canvas pixels before zoom) and zoom. */
export interface Camera {
  x: number
  y: number
  zoom: number
}

export interface Bounds {
  left: number
  top: number
  width: number
  height: number
}

/**
 * Ease the camera toward a target, then keep the view on the pitch. `dt` is wall seconds, so
 * the follow feels the same at 30 or 144 fps. The view never shows more than a margin of
 * empty space beyond the pitch edges.
 */
export function followCamera(
  cam: Camera,
  target: Camera,
  dt: number,
  view: { w: number; h: number },
  pitch: Bounds,
  margin = 24,
): Camera {
  const k = 1 - Math.exp(-dt * 3)
  const zoom = cam.zoom + (target.zoom - cam.zoom) * k
  let x = cam.x + (target.x - cam.x) * k
  let y = cam.y + (target.y - cam.y) * k
  x = clampAxis(x, view.w / 2 / zoom, pitch.left - margin, pitch.left + pitch.width + margin)
  y = clampAxis(y, view.h / 2 / zoom, pitch.top - margin, pitch.top + pitch.height + margin)
  return { x, y, zoom }
}

function clampAxis(c: number, half: number, lo: number, hi: number): number {
  if (hi - lo <= half * 2) return (lo + hi) / 2
  return Math.min(hi - half, Math.max(lo + half, c))
}
