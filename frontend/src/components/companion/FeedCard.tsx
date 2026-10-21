import { metricLabel, type FeedItem } from '@/core/feed'
import { sentenceCase } from '@/core/headline'
import { CLUBS } from '@/data/league'
import { useSessionState, useT } from '@/state/useSession'
import { CheckIcon } from '@/components/icons'

const TONE_STRIP: Record<string, string> = {
  goal: 'var(--color-amber)',
  chance: 'var(--color-control)',
  swing: 'var(--color-pressure)',
  milestone: 'var(--color-amber)',
  info: '#6b7683',
}

function strip(item: FeedItem): string {
  if (item.card === 'yellow') return '#f5c542'
  if (item.card === 'red') return 'var(--color-chaos)'
  return TONE_STRIP[item.tone] ?? '#6b7683'
}

interface Props {
  item: FeedItem
  open: boolean
  onToggle: () => void
  onListen: () => void
}

/** One moment the viewer has been shown. Tap to see why it was picked and what backs it. */
export function FeedCard({ item, open, onToggle, onListen }: Props) {
  const t = useT()
  const lang = useSessionState((s) => s.profile.lang)
  const why = `why-${item.id.replace(/\W+/g, '-')}`
  const club = item.team ? CLUBS[item.team] : undefined
  return (
    <article className="feed-in plate-shadow">
      <div className="plate flex" style={{ ['--cut' as string]: '14px' }}>
        <span aria-hidden className="w-[6px] shrink-0" style={{ background: strip(item) }} />
        <div className="min-w-0 flex-1 px-4 py-3">
          <div className="flex items-baseline gap-3">
            {item.clock && (
              <span className="num text-[20px] leading-none text-amber" dir="ltr">
                {item.clock}
              </span>
            )}
            {club && (
              <span className="latin text-[14px] leading-none text-muted" dir="ltr">
                {club.code}
              </span>
            )}
          </div>
          <h3 dir="auto" className="mt-1.5 font-display text-[26px] font-bold leading-[1]">
            {sentenceCase(item.headline, lang)}
          </h3>
          {item.body && (
            <p dir="auto" className="mt-1.5 text-[15px] leading-snug text-text/85">
              {item.body}
            </p>
          )}

          <div className="mt-2 flex flex-wrap items-center gap-x-4">
            <button
              className="inline-flex min-h-11 items-center text-[14px] text-muted underline decoration-white/25 underline-offset-4 hover:text-text"
              aria-expanded={open}
              aria-controls={why}
              onClick={onToggle}
            >
              {t(open ? 'hideWhy' : 'whyThis')}
            </button>
            {item.audioUrl && (
              <button
                className="inline-flex min-h-11 items-center text-[14px] text-amber hover:underline"
                onClick={onListen}
              >
                {t('listen')}
              </button>
            )}
          </div>

          {open && (
            <div id={why} className="mb-1 border-t border-white/10 pt-3 text-[14px]">
              <p className="flex items-center gap-1.5 text-text/85">
                {item.verified && <CheckIcon className="size-3 text-control" />}
                {t(item.source.startsWith('agent:') ? 'verifiedBy' : 'fromNumbers')}
              </p>
              {item.evidence.length > 0 && (
                <dl className="mt-2 grid grid-cols-[1fr_auto] gap-x-4 gap-y-1">
                  {item.evidence.map((e) => (
                    <div key={e.metric} className="contents">
                      <dt className="text-muted">{metricLabel(e.metric)}</dt>
                      <dd className="num m-0 text-end text-[17px] leading-none" dir="ltr">
                        {Number.isInteger(e.value) ? e.value : e.value.toFixed(1)}
                      </dd>
                    </div>
                  ))}
                </dl>
              )}
            </div>
          )}
        </div>
      </div>
    </article>
  )
}
