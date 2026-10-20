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
    readonly cols = 35,
    readonly rows = 23,
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

  /** Cells with any time in them, as pitch rectangles with 0..1 intensity. */
  cells(): { x: number; y: number; w: number; h: number; v: number }[] {
    const out = []
    const w = PITCH_LENGTH / this.cols
    const h = PITCH_WIDTH / this.rows
    for (let r = 0; r < this.rows; r++) {
      for (let c = 0; c < this.cols; c++) {
        const n = this.counts[r * this.cols + c] ?? 0
        if (n > 0) out.push({ x: c * w, y: r * h, w, h, v: n / this.max })
      }
    }
    return out
  }
}
