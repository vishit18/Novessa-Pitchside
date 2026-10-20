import { CLUBS, PLAYERS } from '@/data/league'
import type { StringKey } from '@/i18n/strings'
import { useSessionState, useT } from '@/state/useSession'
import type { PlayerStatsEntry } from '@/types/overlay'

const DASH = '—'

/**
 * The live card for player focus mode. Every number comes from the stream: speed from the
 * latest tracking frame, the rest from the state engine's player_stats. Nothing is computed
 * here beyond formatting.
 */
export function PlayerCard() {
  const t = useT()
  const id = useSessionState((s) => s.profile.player)
  const speed = useSessionState((s) => s.focusSpeed)
  const stats = useSessionState(
    (s) => s.playerStats?.players.find((p) => p.player_id === s.profile.player) ?? null,
  )
  if (!id) return null
  const info = PLAYERS[id]
  const team = id.split('-')[0] ?? ''
  const club = CLUBS[team]

  return (
    <section className="plate-shadow h-full" aria-label={`${t('following')} ${info?.name ?? id}`}>
      <div className="plate flex h-full flex-col gap-6 p-6" style={{ ['--cut' as string]: '18px' }}>
        <div className="flex items-center gap-2.5 text-[14px] text-muted">
          <span className="h-4 w-[5px]" style={{ background: club?.primary_color ?? '#9aa5b1' }} />
          {club?.name ?? team}
        </div>

        <div className="flex items-end gap-4">
          <span className="num text-[96px] font-bold leading-[0.8] text-amber" dir="ltr">
            {info?.shirt ?? ''}
          </span>
          <div className="min-w-0 pb-1">
            <h2 className="font-display text-[38px] font-bold leading-[0.95]">
              {info?.name ?? id}
            </h2>
            {info && (
              <p className="mt-1 text-[14px] text-muted">
                {t(`pos_${info.position}` as StringKey)}
              </p>
            )}
          </div>
        </div>

        <div>
          <p className="text-[13px] text-muted">{t('speedNow')}</p>
          <p className="num text-[64px] font-bold leading-none" dir="ltr">
            {speed == null ? DASH : speed.toFixed(1)}
            <span className="ml-2 text-[18px] font-medium text-muted">km/h</span>
          </p>
        </div>

        <dl className="grid grid-cols-2 gap-x-6 gap-y-5 border-t border-white/10 pt-5 max-lg:grid-cols-3">
          <Stat
            label={t('distance')}
            value={fmt(stats, (s) => s.distance_km.toFixed(2))}
            unit="km"
          />
          <Stat
            label={t('topSpeed')}
            value={fmt(stats, (s) => s.top_speed_kmh.toFixed(1))}
            unit="km/h"
          />
          <Stat label={t('passes')} value={fmt(stats, (s) => `${s.passes_complete}/${s.passes}`)} />
          <Stat
            label={t('passAccuracy')}
            value={fmt(stats, (s) =>
              s.pass_accuracy == null ? DASH : `${Math.round(s.pass_accuracy * 100)}%`,
            )}
          />
          <Stat
            label={t('avgDifficulty')}
            value={fmt(stats, (s) =>
              s.avg_difficulty == null ? DASH : s.avg_difficulty.toFixed(0),
            )}
          />
          <Stat label={t('sprints')} value={fmt(stats, (s) => String(s.sprints))} />
          <Stat label={t('shots')} value={fmt(stats, (s) => String(s.shots))} />
          <Stat label={t('xg')} value={fmt(stats, (s) => s.xg.toFixed(2))} />
        </dl>

        <p className="mt-auto text-[13px] leading-snug text-muted">
          {stats ? t('heatmapNote') : `${t('statsPending')} ${t('heatmapNote')}`}
        </p>
      </div>
    </section>
  )
}

function fmt(stats: PlayerStatsEntry | null, f: (s: PlayerStatsEntry) => string): string {
  return stats ? f(stats) : DASH
}

function Stat({ label, value, unit }: { label: string; value: string; unit?: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-[13px] leading-tight text-muted">{label}</dt>
      <dd className="num mt-1 text-[32px] font-semibold leading-none" dir="ltr">
        {value}
        {unit && value !== DASH && (
          <span className="ml-1 text-[14px] font-medium text-muted">{unit}</span>
        )}
      </dd>
    </div>
  )
}
