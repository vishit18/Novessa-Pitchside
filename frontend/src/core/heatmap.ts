import { PITCH_LENGTH, PITCH_WIDTH } from '@/types/schema'

/**
 * Where one player has been, as a coarse grid over the pitch. Built from the positions already
 * in the tracking frames, sampled at a fixed match-time rate so replay speed doesn't change
 * the picture. Display only: no stat is derived from it.
 */
export class Heatmap {
  readonly counts: Float32Array
  private lastT = -Infinity
  max = 0

  constructor(
    readonly cols = 42,
    readonly rows = 27,
    private readonly everyS = 0.5,
  ) {
    this.counts = new Float32Array(cols * rows)
  }

  reset(): void {
    this.counts.fill(0)
    this.max = 0
    this.lastT = -Infinity
  }

  /** Record a position at match time `t`. Returns true when the grid changed. */
  sample(x: number, y: number, t: number): boolean {
    if (t < this.lastT - 1) this.reset() // seek backwards: start over
    if (t - this.lastT < this.everyS) return false
    this.lastT = t
    const c = Math.min(this.cols - 1, Math.max(0, Math.floor((x / PITCH_LENGTH) * this.cols)))
    const r = Math.min(this.rows - 1, Math.max(0, Math.floor((y / PITCH_WIDTH) * this.rows)))
    const i = r * this.cols + c
    this.counts[i] = (this.counts[i] ?? 0) + 1
    this.max = Math.max(this.max, this.counts[i] ?? 0)
    return true
  }

  /**
   * Cells with any time in them, as pitch rectangles with 0..1 intensity. Counts are smoothed
   * over each cell's neighbours first, so one stray sample does not read as a hot spot and the
   * banded drawing gets clean contours instead of a checkerboard.
   */
  cells(): { x: number; y: number; w: number; h: number; v: number }[] {
    const { cols, rows } = this
    const smooth = new Float32Array(cols * rows)
    let max = 0
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        let sum = 0
        let wsum = 0
        for (let dr = -1; dr <= 1; dr++) {
          for (let dc = -1; dc <= 1; dc++) {
            const rr = r + dr
            const cc = c + dc
            if (rr < 0 || rr >= rows || cc < 0 || cc >= cols) continue
            const k = dr === 0 && dc === 0 ? 4 : dr === 0 || dc === 0 ? 2 : 1
            sum += (this.counts[rr * cols + cc] ?? 0) * k
            wsum += k
          }
        }
        const v = sum / wsum
        smooth[r * cols + c] = v
        max = Math.max(max, v)
      }
    }
    // Sample the smoothed grid at twice the resolution, bilinearly, so the band edges follow
    // the shape of the field instead of stepping along 2.5 m cells.
    const at = (r: number, c: number) =>
      smooth[Math.min(rows - 1, Math.max(0, r)) * cols + Math.min(cols - 1, Math.max(0, c))] ?? 0
    const out = []
    const k = 2
    const w = PITCH_LENGTH / (cols * k)
    const h = PITCH_WIDTH / (rows * k)
    for (let r = 0; r < rows * k; r++) {
      for (let c = 0; c < cols * k; c++) {
        const fr = (r + 0.5) / k - 0.5
        const fc = (c + 0.5) / k - 0.5
        const r0 = Math.floor(fr)
        const c0 = Math.floor(fc)
        const dr = fr - r0
        const dc = fc - c0
        const raw =
          at(r0, c0) * (1 - dr) * (1 - dc) +
          at(r0, c0 + 1) * (1 - dr) * dc +
          at(r0 + 1, c0) * dr * (1 - dc) +
          at(r0 + 1, c0 + 1) * dr * dc
        const v = max > 0 ? raw / max : 0
        if (v > 0.15) out.push({ x: c * w, y: r * h, w, h, v })
      }
    }
    return out
  }
}
