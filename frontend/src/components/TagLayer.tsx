import type { MutableRefObject } from 'react'
import { CLUBS, PLAYERS } from '@/data/league'
import { useStore } from '@/state/store'
import type { OverlayEnvelope } from '@/types/overlay'
import type { PlayerFrame } from '@/types/schema'
import type { PitchRenderer, Point } from './pitch/PitchRenderer'

export type TagRegistry = Map<string, { el: HTMLElement; overlay: OverlayEnvelope }>

/** Where on the stage this overlay should sit, in CSS pixels, or null if it can't be placed. */
export function resolveTagPoint(
  o: OverlayEnvelope,
  players: Map<string, PlayerFrame>,
  r: PitchRenderer,
): Point | null {
  const a = o.anchor
  if (!a) return null
  if (a.type === 'player') {
    const p = players.get(a.id)
    return p ? r.project(p.x, p.y) : null
  }
  const ex = o.payload['end_x']
  const ey = o.payload['end_y']
  if (typeof ex === 'number' && typeof ey === 'number')
    return r.project((a.x + ex) / 2, (a.y + ey) / 2)
  return r.project(a.x, a.y)
}

function teamColour(code: string | undefined): string {
  return (code && CLUBS[code]?.primary_color) || '#9aa5b1'
}

function PlayerTag({ o }: { o: OverlayEnvelope }) {
  const id = o.anchor?.type === 'player' ? o.anchor.id : ''
  const info = PLAYERS[id]
  const team = id.split('-')[0]
  const speed = o.payload['speed_kmh']
  return (
    <div className="flex -translate-x-1/2 -translate-y-[calc(100%+20px)] items-stretch overflow-hidden rounded-[3px] panel shadow-[0_6px_18px_rgb(0_0_0/0.45)]">
      <span className="w-1.5" style={{ background: teamColour(team) }} />
      <div className="flex items-baseline gap-2 px-2.5 py-1">
        <span className="num text-[15px] font-semibold text-muted">{info?.shirt ?? ''}</span>
        <span className="font-display text-[17px] font-semibold uppercase leading-none tracking-wide whitespace-nowrap">
          {info?.name ?? id}
        </span>
        {typeof speed === 'number' && (
          <span className="num text-[20px] font-bold leading-none text-amber">
            {speed.toFixed(1)}
            <span className="ml-0.5 text-[11px] font-medium text-muted">km/h</span>
          </span>
        )}
      </div>
    </div>
  )
}

function PassTag({ o }: { o: OverlayEnvelope }) {
  const d = Number(o.payload['difficulty'] ?? 0)
  const dist = Number(o.payload['distance_m'] ?? 0)
  const factors = (o.payload['factors'] as { name: string; points: number }[] | undefined) ?? []
  const done = o.payload['complete'] === true
  return (
    <div className="-translate-x-1/2 -translate-y-[130%] overflow-hidden rounded-[3px] panel shadow-[0_6px_18px_rgb(0_0_0/0.45)]">
      <div className="flex items-baseline gap-2 px-2.5 py-1">
        <span className="num text-[26px] font-bold leading-none text-amber">{Math.round(d)}</span>
        <span className="font-display text-[13px] font-semibold uppercase leading-tight tracking-wider text-muted">
          pass difficulty
          <br />
          {dist.toFixed(0)} m · {done ? 'completed' : 'lost'}
        </span>
      </div>
      {factors[0] && (
        <div className="border-t border-hairline px-2.5 py-0.5 text-[11px] text-muted">
          {factors[0].name.replaceAll('_', ' ')} +{Math.round(factors[0].points)}
        </div>
      )}
    </div>
  )
}

/** DOM tags for anchored overlays. Stage moves them every frame via the registry. */
export function TagLayer({ registry }: { registry: MutableRefObject<TagRegistry> }) {
  const active = useStore((s) => s.active)
  const tags = active.filter((o) => o.slot === 'player_tag' || o.slot === 'pitch_annotation')
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden">
      {tags.map((o) => (
        <div
          key={o.msg_id}
          ref={(el) => {
            if (el) registry.current.set(o.msg_id, { el, overlay: o })
            else registry.current.delete(o.msg_id)
          }}
          className="absolute left-0 top-0 will-change-transform"
          style={{ visibility: 'hidden' }}
        >
          <div className="tag" style={{ ['--life' as string]: `${o.duration_s}s` }}>
            {o.kind === 'pass_difficulty' ? <PassTag o={o} /> : <PlayerTag o={o} />}
          </div>
        </div>
      ))}
    </div>
  )
}
