import { useMemo } from 'react'
import { MATCH_S, pressingSide, riverPaths, tempoWord } from '@/core/pulse'
import { CLUBS } from '@/data/league'
import { useSession, useSessionState, useT } from '@/state/useSession'
import { usePulse } from '@/state/usePulse'
import type { StringKey } from '@/i18n/strings'

const W = 400
const H = 96
const colour = (code: string) => CLUBS[code]?.primary_color ?? '#9aa5b1'

/**
 * Who's on top, over the whole match so far, and how the game feels right now. The river is
 * momentum: home's spells above the line in their kit, away's below in theirs, goals ticked on
 * it. Underneath, control or chaos, tempo and who is pressing harder, in words; analysts also
 * get the numbers. Everything comes from the state engine up to the viewer's own clock.
 */
export function MatchPulse() {
  const session = useSession()
  const t = useT()
  const meta = useSessionState((s) => s.meta)
  const snap = useSessionState((s) => s.snapshot)
  const now = useSessionState((s) => s.t)
  const feed = useSessionState((s) => s.feed)
  const persona = useSessionState((s) => s.profile.persona)
  const rows = usePulse(session.opts.matchId, now)
  const { home: homePath, away: awayPath, span } = useMemo(() => riverPaths(rows, W, H), [rows])
  if (!meta) return null
  const home = meta.home.code
  const away = meta.away.code
  const analyst = persona === 'analyst'
  const goals = feed.filter((f) => f.momentKind === 'goal' && f.team)
  const x = (sec: number) => (sec / span) * W

  const label = snap?.control_chaos.label ?? 'balanced'
  const tempo = tempoWord(snap?.rhythm.events_per_min ?? 17)
  const press = snap ? pressingSide(snap.pressure[home] ?? 0, snap.pressure[away] ?? 0) : null
  const presser = press === 'home' ? home : press === 'away' ? away : null
  const homeName = CLUBS[home]?.name ?? home
  const awayName = CLUBS[away]?.name ?? away

  return (
    <section aria-labelledby="pulse-h" className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between gap-3">
        <h2 id="pulse-h" className="font-display text-[22px] font-bold leading-none">
          {t('pulseTitle')}
        </h2>
        {analyst && snap && (
          <span className="num text-[15px] text-muted" dir="ltr">
            {t('momentumShort')} {snap.momentum > 0 ? '+' : ''}
            {snap.momentum.toFixed(0)}
          </span>
        )}
      </div>

      <figure className="m-0">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="block h-[96px] w-full"
          preserveAspectRatio="none"
          role="img"
          aria-label={t('pulseAria', { home: homeName, away: awayName })}
          direction="ltr"
        >
          <rect x="0" y="0" width={W} height={H} fill="var(--color-raised)" />
          {/* Half-time, and the end of normal time once the scale runs past it. */}
          <line
            x1={x(MATCH_S / 2)}
            x2={x(MATCH_S / 2)}
            y1="0"
            y2={H}
            stroke="var(--color-hairline)"
            strokeDasharray="3 3"
          />
          <path d={homePath} fill={colour(home)} fillOpacity="0.9" />
          <path d={awayPath} fill={colour(away)} fillOpacity="0.9" />
          <line x1="0" x2={W} y1={H / 2} y2={H / 2} stroke="var(--color-text)" strokeWidth="1" />
          {/* Where the viewer is now. */}
          <line
            x1={x(now)}
            x2={x(now)}
            y1="0"
            y2={H}
            stroke="var(--color-text)"
            strokeOpacity="0.35"
          />
          {[0, 15, 30, 45, 60, 75, 90].map((m) => (
            <line
              key={m}
              x1={x(m * 60)}
              x2={x(m * 60)}
              y1={H - 4}
              y2={H}
              stroke="var(--color-muted)"
              vectorEffect="non-scaling-stroke"
            />
          ))}
          {goals.map((g) => (
            <g key={g.id}>
              <line
                x1={x(g.showAt)}
                x2={x(g.showAt)}
                y1={g.team === home ? 0 : H / 2}
                y2={g.team === home ? H / 2 : H}
                stroke="var(--color-text)"
                strokeWidth="2"
                vectorEffect="non-scaling-stroke"
              />
            </g>
          ))}
        </svg>
        <div className="num relative mt-0.5 h-4 text-[12px] text-muted" dir="ltr" aria-hidden>
          {[0, 45, 90].map((m) => (
            <span
              key={m}
              className="absolute top-0 -translate-x-1/2 first:translate-x-0 last:-translate-x-full"
              style={{ left: `${((m * 60) / span) * 100}%` }}
            >
              {m}'
            </span>
          ))}
        </div>
        <figcaption className="mt-1 flex justify-between gap-3 text-[13px] text-muted">
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5" style={{ background: colour(home) }} aria-hidden />
            {t('pulseAbove', { club: homeName })}
          </span>
          <span className="flex items-center gap-1.5">
            {t('pulseBelow', { club: awayName })}
            <span className="h-2.5 w-2.5" style={{ background: colour(away) }} aria-hidden />
          </span>
        </figcaption>
      </figure>

      <dl className="grid grid-cols-3 gap-3 border-t border-hairline pt-3">
        <Reading
          label={t('controlLabel')}
          word={t(`control_${label}` as StringKey)}
          tone={
            label === 'chaotic'
              ? 'var(--color-chaos)'
              : label === 'controlled'
                ? 'var(--color-control)'
                : 'var(--color-muted)'
          }
          level={label === 'chaotic' ? 3 : label === 'balanced' ? 2 : 1}
          detail={analyst && snap ? snap.control_chaos.value.toFixed(0) : null}
        />
        <Reading
          label={t('tempoLabel')}
          word={t(`tempo_${tempo}` as StringKey)}
          tone="var(--color-text)"
          level={tempo === 'fast' ? 3 : tempo === 'steady' ? 2 : 1}
          detail={analyst && snap ? `${snap.rhythm.events_per_min.toFixed(0)}/min` : null}
        />
        <div className="min-w-0">
          <dt className="text-[13px] text-muted">{t('pressingLabel')}</dt>
          <dd className="m-0 mt-1 flex items-center gap-2">
            {presser && (
              <span className="h-4 w-[5px] shrink-0" style={{ background: colour(presser) }} />
            )}
            <span className="truncate font-display text-[19px] font-bold leading-none">
              {presser ? (CLUBS[presser]?.name ?? presser) : t('evenWord')}
            </span>
          </dd>
        </div>
      </dl>
    </section>
  )
}

/** A word for how the match feels, with three marks lit to show where it sits. */
function Reading({
  label,
  word,
  tone,
  level,
  detail,
}: {
  label: string
  word: string
  tone: string
  level: 1 | 2 | 3
  detail: string | null
}) {
  return (
    <div className="min-w-0">
      <dt className="text-[13px] text-muted">{label}</dt>
      <dd className="m-0 mt-1">
        <span className="flex items-baseline gap-1.5">
          <span
            className="truncate font-display text-[19px] font-bold leading-none"
            style={{ color: tone }}
          >
            {word}
          </span>
          {detail && (
            <span className="num text-[13px] text-muted" dir="ltr">
              {detail}
            </span>
          )}
        </span>
        <span className="mt-1.5 flex gap-[3px]" aria-hidden>
          {[1, 2, 3].map((i) => (
            <span
              key={i}
              className="h-[4px] flex-1 transition-colors duration-300"
              style={{ background: i <= level ? tone : 'var(--color-hairline)' }}
            />
          ))}
        </span>
      </dd>
    </div>
  )
}
