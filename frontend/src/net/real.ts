import type { RealOverlay } from '@/core/real'
import { GATEWAY_HTTP } from '@/net/api'

/** One score block from data/real/<clip>/results.json. */
export interface RealResults {
  positions: {
    recall: number
    precision: number
    median_error_m: number
    p90_error_m: number
    matched: number
    gt_players: number
  }
  speed: { median_abs_error_kmh: number; p90_abs_error_kmh: number; top_speed_error_kmh: number }
  passes: { gt: number; ours: number; matched: number; precision: number; recall: number }
  shots: { gt: number; ours: number; matched: number }
  ball_found_fraction: number
  tracks: number
}

export interface RealClip {
  clip: string
  meta: { credit: string; start_s: number; seconds: number; match: string }
  results: RealResults
  /** The gateway has the video file. The overlay data is always there. */
  video: boolean
}

export async function listClips(): Promise<RealClip[]> {
  const res = await fetch(`${GATEWAY_HTTP}/real`)
  if (!res.ok) throw new Error(`/real returned ${res.status}`)
  return (await res.json()) as RealClip[]
}

export async function getOverlay(clip: string): Promise<RealOverlay> {
  const res = await fetch(`${GATEWAY_HTTP}/real/${clip}/overlay`)
  if (!res.ok) throw new Error(`overlay returned ${res.status}`)
  return (await res.json()) as RealOverlay
}

export const videoUrl = (clip: string) => `${GATEWAY_HTTP}/real/${clip}/video`
