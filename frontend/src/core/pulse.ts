import type { PulseSample } from '@/net/api'

/** Same lines as backend/app/pulse.py, so the words here and in the lower thirds agree. */
export const FAST_TEMPO = 19
export const SLOW_TEMPO = 15
/** A regulation match in match seconds; the river is drawn on this scale until stoppage time. */
export const MATCH_S = 90 * 60

export type TempoWord = 'slow' | 'steady' | 'fast'

export function tempoWord(eventsPerMin: number): TempoWord {
  if (eventsPerMin >= FAST_TEMPO) return 'fast'
  if (eventsPerMin <= SLOW_TEMPO) return 'slow'
  return 'steady'
}

/** Which side is pressing harder, or null when it is close. */
export function pressingSide(home: number, away: number, margin = 10): 'home' | 'away' | null {
  if (home - away >= margin) return 'home'
  if (away - home >= margin) return 'away'
  return null
}

/**
 * The momentum river as two closed SVG paths: home's spells above the centre line, away's below.
 * x runs over match time on a fixed 90-minute scale (wider only once stoppage time passes), so
 * the river grows left to right as the match goes on rather than stretching to fill the box.
 */
export function riverPaths(
  samples: PulseSample[],
  width: number,
  height: number,
): { home: string; away: string; span: number } {
  const span = Math.max(MATCH_S, samples.at(-1)?.t_match ?? 0)
  const mid = height / 2
  const x = (t: number) => (t / span) * width
  const y = (m: number) => mid - (Math.max(-100, Math.min(100, m)) / 100) * mid
  if (samples.length < 2) return { home: '', away: '', span }
  const area = (clip: (m: number) => number) => {
    const pts = samples.map((s) => `${x(s.t_match).toFixed(1)},${y(clip(s.momentum)).toFixed(1)}`)
    const first = x(samples[0]!.t_match).toFixed(1)
    const last = x(samples.at(-1)!.t_match).toFixed(1)
    return `M${first},${mid} L${pts.join(' L')} L${last},${mid} Z`
  }
  return {
    home: area((m) => Math.max(0, m)),
    away: area((m) => Math.min(0, m)),
    span,
  }
}
