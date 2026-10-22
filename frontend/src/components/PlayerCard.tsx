import { rankAmong, type Position, type Rank } from '@/core/context'
import { CLUBS, PLAYERS } from '@/data/league'
import type { StringKey } from '@/i18n/strings'
import type { Persona } from '@/state/profile'
import { useSessionState, useT } from '@/state/useSession'
import type { PlayerStatsEntry } from '@/types/overlay'

const positionOf = (id: string) => PLAYERS[id]?.position as Position | undefined

const DASH = '—'
const RANK_AFTER_S = 300

type StatKey =
  'distance' | 'topSpeed' | 'passes' | 'passAccuracy' | 'avgDifficulty' | 'sprints' | 'shots' | 'xg'

/** What each kind of viewer is shown about their player. Model numbers stay with the analyst. */
const STATS: Record<Persona, StatKey[]> = {
  analyst: [
    'distance',
    'topSpeed',
    'passes',
    'passAccuracy',
    'avgDifficulty',
    'sprints',
    'shots',
    'xg',
  ],
  casual: ['distance', 'topSpeed', 'passes', 'shots'],
  kids: ['distance', 'topSpeed'],
  accessibility: ['distance', 'passes', 'shots'],
}

/**
 * The followed player, beside the match in player focus. Their story first (goals, assists,
 * penalties, cards), then the numbers this kind of viewer wants, each ranked against the same
 * position on this pitch once there is something to rank. Every number comes from the stream.
 */
export function PlayerCard() {
  const t = useT()
  const id = useSessionState((s) => s.profile.player)
  const persona = useSessionState((s) => s.profile.persona)
  const speed = useSessionState((s) => s.focusSpeed)
  const all = useSessionState((s) => s.playerStats?.players ?? null)
  const stats = all?.find((p) => p.player_id === id) ?? null
  const statsT = useSessionState((s) => s.playerStats?.t_match ?? 0)
  // Five minutes in, a rank starts to mean something; before that it ranks a few touches.
  const rank = (f: (p: PlayerStatsEntry) => number | null): Rank | null =>
    all && id && statsT >= RANK_AFTER_S ? rankAmong(all, id, f, positionOf) : null
  if (!id) return null
  const info = PLAYERS[id]
  const team = id.split('-')[0] ?? ''
  const club = CLUBS[team]

  const story: string[] = []
  if (stats) {
    if (stats.goals) story.push(t(stats.goals === 1 ? 'oneGoal' : 'nGoals', { n: stats.goals }))
    if (stats.assists)
      story.push(t(stats.assists === 1 ? 'oneAssist' : 'nAssists', { n: stats.assists }))
    const missed = stats.penalties_taken - stats.penalties_scored
    if (missed > 0) story.push(t('penMissed', { n: missed }))
    if (stats.reds) story.push(t('sentOff'))
    else if (stats.yellows) story.push(t('booked'))
  }

  const cells: Record<StatKey, { value: string; unit?: string; rank?: Rank | null }> = {
    distance: {
      value: fmt(stats, (s) => s.distance_km.toFixed(2)),
      unit: 'km',
      rank: rank((p) => p.distance_km),
    },
    topSpeed: {
      value: fmt(stats, (s) => s.top_speed_kmh.toFixed(1)),
      unit: 'km/h',
      rank: rank((p) => p.top_speed_kmh),
    },
    passes: {
      value: fmt(stats, (s) => `${s.passes_complete}/${s.passes}`),
      rank: rank((p) => p.passes_complete),
    },
    passAccuracy: {
      value: fmt(stats, (s) =>
        s.pass_accuracy == null ? DASH : `${Math.round(s.pass_accuracy * 100)}%`,
      ),
      rank: rank((p) => (p.passes >= 5 ? p.pass_accuracy : null)),
    },
    avgDifficulty: {
      value: fmt(stats, (s) => (s.avg_difficulty == null ? DASH : s.avg_difficulty.toFixed(0))),
      rank: rank((p) => (p.passes >= 5 ? p.avg_difficulty : null)),
    },
    sprints: { value: fmt(stats, (s) => String(s.sprints)), rank: rank((p) => p.sprints) },
    shots: { value: fmt(stats, (s) => String(s.shots)), rank: rank((p) => p.shots) },
    xg: { value: fmt(stats, (s) => s.xg.toFixed(2)), rank: rank((p) => p.xg) },
  }

  return (
    <section aria-label={`${t('following')} ${info?.name ?? id}`} className="flex flex-col gap-3">
      <div className="flex items-end gap-3">
        <span className="num text-[64px] font-bold leading-[0.8] text-amber" dir="ltr">
          {info?.shirt ?? ''}
        </span>
        <div className="min-w-0 pb-0.5">
          <p className="flex items-center gap-2 text-[13px] text-muted">
            <span
              className="h-3.5 w-[4px]"
              style={{ background: club?.primary_color ?? '#9aa5b1' }}
            />
            {club?.name ?? team}
            {info && <span>· {t(`pos_${info.position}` as StringKey)}</span>}
          </p>
          <h2 className="truncate font-display text-[30px] font-bold leading-none">
            {info?.name ?? id}
          </h2>
        </div>
        <div className="ms-auto text-end">
          <p className="text-[12px] text-muted">{t('speedNow')}</p>
          <p className="num text-[30px] font-bold leading-none" dir="ltr">
            {speed == null ? DASH : speed.toFixed(0)}
            <span className="ms-1 text-[13px] font-medium text-muted">km/h</span>
          </p>
        </div>
      </div>

      {stats && !stats.on_pitch && (
        <p
          className="self-start bg-text px-2 py-1 text-[14px] font-semibold text-ink"
          role="status"
        >
          {t(stats.reds > 0 ? 'sentOff' : 'subbedOff')}
        </p>
      )}
      {story.length > 0 && (
        <p className="font-display text-[22px] font-bold leading-tight text-amber">
          {story.join(', ')}
        </p>
      )}

      <dl className="grid grid-cols-4 gap-x-4 gap-y-3 border-t border-hairline pt-3">
        {STATS[persona].map((k) => (
          <Stat key={k} label={t(k)} {...cells[k]} />
        ))}
      </dl>
    </section>
  )
}

function fmt(stats: PlayerStatsEntry | null, f: (s: PlayerStatsEntry) => string): string {
  return stats ? f(stats) : DASH
}

function Stat({
  label,
  value,
  unit,
  rank,
}: {
  label: string
  value: string
  unit?: string
  rank?: Rank | null
}) {
  const t = useT()
  return (
    <div className="min-w-0">
      <dt className="truncate text-[12px] leading-tight text-muted">{label}</dt>
      <dd className="num m-0 mt-0.5 text-[22px] font-semibold leading-none" dir="ltr">
        {value}
        {unit && value !== DASH && (
          <span className="ms-0.5 text-[12px] font-medium text-muted">{unit}</span>
        )}
      </dd>
      {rank && (
        <dd className={`m-0 mt-0.5 text-[12px] ${rank.rank === 1 ? 'text-amber' : 'text-muted'}`}>
          {t('rankShort', { rank: rank.rank, n: rank.of })}
        </dd>
      )}
    </div>
  )
}
