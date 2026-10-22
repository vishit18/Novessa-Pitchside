import type { StringKey } from '@/i18n/strings'
import type { MutableRefObject } from 'react'
import { CLUBS, PLAYERS } from '@/data/league'
import { useSessionState, useT } from '@/state/useSession'
import type { OverlayEnvelope } from '@/types/overlay'
import type { PlayerFrame } from '@/types/schema'
import type { Point } from './pitch/PitchRenderer'

export type TagRegistry = Map<string, { el: HTMLElement; overlay: OverlayEnvelope }>

/**
 * Where on the stage this overlay should sit, in CSS pixels, or null if it can't be placed.
 * `project` maps pitch metres to stage pixels, including any perspective tilt.
 */
export function resolveTagPoint(
  o: OverlayEnvelope,
  players: Map<string, PlayerFrame>,
  project: (x: number, y: number) => Point,
): Point | null {
  const a = o.anchor
  if (!a) return null
  if (a.type === 'player') {
    const p = players.get(a.id)
    return p ? project(p.x, p.y) : null
  }
  const ex = o.payload['end_x']
  const ey = o.payload['end_y']
  if (typeof ex === 'number' && typeof ey === 'number')
    return project((a.x + ex) / 2, (a.y + ey) / 2)
  return project(a.x, a.y)
}

function teamColour(code: string | undefined): string {
  return (code && CLUBS[code]?.primary_color) || '#9aa5b1'
}

/** A name plate that sits above the player, joined to them by a thin leader. */
function PlayerTag({ o }: { o: OverlayEnvelope }) {
  const id = o.anchor?.type === 'player' ? o.anchor.id : ''
  const info = PLAYERS[id]
  const team = id.split('-')[0]
  const speed = o.payload['speed_kmh']
  return (
    <div className="flex -translate-x-1/2 -translate-y-full flex-col items-center pb-[18px]">
      <div className="plate-shadow">
        <div className="plate flex items-stretch" style={{ ['--cut' as string]: '8px' }}>
          <span className="plate-edge w-[5px]" style={{ background: teamColour(team) }} />
          <div className="flex items-baseline gap-2 py-1 pr-3.5 pl-2.5">
            <span className="num text-[16px] font-semibold text-muted">{info?.shirt ?? ''}</span>
            <span className="font-display text-[19px] font-semibold leading-none whitespace-nowrap">
              {info?.name ?? id}
            </span>
            {typeof speed === 'number' && (
              <span className="num text-[24px] font-bold leading-none text-amber">
                {speed.toFixed(1)}
                <span className="ml-1 text-[12px] font-medium text-muted">km/h</span>
              </span>
            )}
          </div>
        </div>
      </div>
      <span className="absolute bottom-0 h-[18px] w-px bg-amber/80" />
    </div>
  )
}

function PassTag({ o }: { o: OverlayEnvelope }) {
  const d = Number(o.payload['difficulty'] ?? 0)
  const dist = Number(o.payload['distance_m'] ?? 0)
  const factors = (o.payload['factors'] as { name: string; points: number }[] | undefined) ?? []
  const done = o.payload['complete'] === true
  const t = useT()
  return (
    <div className="-translate-x-1/2 -translate-y-[120%]">
      <div className="plate-shadow">
        <div className="plate" style={{ ['--cut' as string]: '8px' }}>
          <div className="flex items-center gap-2.5 px-3 py-1.5">
            <span className="num text-[34px] font-bold leading-none text-amber">
              {Math.round(d)}
            </span>
            <span className="font-display text-[15px] leading-tight text-muted">
              {t('passDifficulty')}
              <br />
              {t(done ? 'passDone' : 'passLost', { m: dist.toFixed(0) })}
            </span>
          </div>
          {factors[0] && (
            <div className="border-t border-text/10 px-3 py-1 text-[12px] text-muted">
              {t(`factor_${factors[0].name}` as StringKey)} +{Math.round(factors[0].points)}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

/** DOM tags for anchored overlays. Stage moves them every frame via the registry. */
export function TagLayer({ registry }: { registry: MutableRefObject<TagRegistry> }) {
  const active = useSessionState((s) => s.active)
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
          className="absolute top-0 left-0 will-change-transform"
          style={{ visibility: 'hidden' }}
        >
          <div className="tag relative" style={{ ['--life' as string]: `${o.duration_s}s` }}>
            {o.kind === 'pass_difficulty' ? <PassTag o={o} /> : <PlayerTag o={o} />}
          </div>
        </div>
      ))}
    </div>
  )
}
