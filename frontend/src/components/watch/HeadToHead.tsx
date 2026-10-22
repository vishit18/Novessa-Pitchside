import { CLUBS } from '@/data/league'
import type { Persona } from '@/state/profile'
import { useSessionState, useT } from '@/state/useSession'
import type { StringKey } from '@/i18n/strings'

type Row = { key: StringKey; home: number; away: number; pct?: boolean }

const colour = (code: string) => CLUBS[code]?.primary_color ?? '#9aa5b1'

/** The numbers each kind of viewer wants, and no more. A first-timer gets one bar. */
const ROWS: Record<Persona, StringKey[]> = {
  analyst: ['statPossession', 'statShots', 'statCorners', 'statFouls', 'statCards'],
  casual: ['statPossession', 'statShots', 'statCorners', 'statCards'],
  kids: ['statBall'],
  accessibility: ['statPossession', 'statShots'],
}

/**
 * Home against away, from the state engine's running counts. The bar is each side's share,
 * so it reads at a glance without the numbers.
 */
export function HeadToHead() {
  const t = useT()
  const meta = useSessionState((s) => s.meta)
  const snap = useSessionState((s) => s.snapshot)
  const persona = useSessionState((s) => s.profile.persona)
  if (!meta || !snap) return null
  const h = meta.home.code
  const a = meta.away.code
  const ts = snap.team_stats
  const cards = (c: string) => (ts[c]?.yellows ?? 0) + (ts[c]?.reds ?? 0)
  const all: Record<string, Row> = {
    statPossession: {
      key: 'statPossession',
      home: snap.possession_match[h] ?? 0,
      away: snap.possession_match[a] ?? 0,
      pct: true,
    },
    statBall: {
      key: 'statBall',
      home: snap.possession_match[h] ?? 0,
      away: snap.possession_match[a] ?? 0,
      pct: true,
    },
    statShots: { key: 'statShots', home: ts[h]?.shots ?? 0, away: ts[a]?.shots ?? 0 },
    statCorners: { key: 'statCorners', home: ts[h]?.corners ?? 0, away: ts[a]?.corners ?? 0 },
    statFouls: { key: 'statFouls', home: ts[h]?.fouls ?? 0, away: ts[a]?.fouls ?? 0 },
    statCards: { key: 'statCards', home: cards(h), away: cards(a) },
  }
  const rows = ROWS[persona].map((k) => all[k]!)
  return (
    <dl className="flex flex-col gap-2.5" dir="ltr">
      {rows.map((r) => {
        const total = r.home + r.away
        const share = total ? r.home / total : 0.5
        const fmt = (v: number) => (r.pct ? `${v.toFixed(0)}%` : String(v))
        return (
          <div key={r.key}>
            <div className="flex items-baseline justify-between">
              <dd className="num m-0 text-[19px] leading-none">{fmt(r.home)}</dd>
              <dt className="text-[13px] text-muted">{t(r.key)}</dt>
              <dd className="num m-0 text-[19px] leading-none">{fmt(r.away)}</dd>
            </div>
            <div className="mt-1 flex h-[5px] gap-[3px]" aria-hidden>
              {total === 0 ? (
                <span className="flex-1 bg-text/10" />
              ) : (
                <>
                  <span
                    className="transition-[flex-grow] duration-300 ease-out"
                    style={{ flexGrow: share * 100, background: colour(h) }}
                  />
                  <span
                    className="transition-[flex-grow] duration-300 ease-out"
                    style={{ flexGrow: (1 - share) * 100, background: colour(a) }}
                  />
                </>
              )}
            </div>
          </div>
        )
      })}
    </dl>
  )
}
