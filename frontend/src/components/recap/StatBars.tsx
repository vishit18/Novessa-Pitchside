import { formatStat, statRows } from '@/core/recap'
import type { RecapFacts } from '@/net/api'

interface Props {
  facts: RecapFacts
  homeColour: string
  awayColour: string
}

/**
 * Home and away side by side, one row per number. The bar is each team's share of the two
 * values, so a longer bar on the left means home had more.
 */
export function StatBars({ facts, homeColour, awayColour }: Props) {
  const rows = statRows(facts)
  if (rows.length === 0) return null
  return (
    <section aria-labelledby="stats-h" className="flex flex-col gap-4">
      <h2 id="stats-h" className="font-display text-[26px] font-semibold leading-none">
        The numbers
      </h2>
      <dl className="flex flex-col gap-3.5" dir="ltr">
        {rows.map((r) => (
          <div key={r.key}>
            <div className="flex items-baseline justify-between">
              <dd className="num m-0 text-[22px] leading-none">{formatStat(r, 'home')}</dd>
              <dt className="text-[13px] text-muted">{r.label}</dt>
              <dd className="num m-0 text-[22px] leading-none">{formatStat(r, 'away')}</dd>
            </div>
            {/* Nothing either side (0 and 0) is a quiet track, not a half-and-half split. */}
            <div className="mt-1.5 flex h-[6px] gap-[3px]" aria-hidden>
              {r.home + r.away === 0 ? (
                <span className="flex-1 bg-text/10" />
              ) : (
                <>
                  <span
                    className="transition-[flex-grow] duration-300 ease-out"
                    style={{ flexGrow: r.homeShare * 100, background: homeColour }}
                  />
                  <span
                    className="transition-[flex-grow] duration-300 ease-out"
                    style={{ flexGrow: (1 - r.homeShare) * 100, background: awayColour }}
                  />
                </>
              )}
            </div>
          </div>
        ))}
      </dl>
    </section>
  )
}
