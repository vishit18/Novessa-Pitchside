import { useState } from 'react'
import { isPulse, type FeedItem } from '@/core/feed'
import { sentenceCase } from '@/core/headline'
import { CLUBS } from '@/data/league'
import { metricName } from '@/i18n/strings.more'
import { isRtl } from '@/state/profile'
import { useSessionState, useT } from '@/state/useSession'
import { CheckIcon } from '@/components/icons'

const TONE: Record<string, string> = {
  goal: 'var(--color-amber)',
  chance: 'var(--color-control)',
  swing: 'var(--color-pressure)',
  milestone: 'var(--color-text)',
  info: 'var(--color-muted)',
}

function strip(item: FeedItem): string {
  if (item.card === 'yellow') return '#f5c542'
  if (item.card === 'red') return 'var(--color-red-card)'
  if (item.team && item.momentKind === 'goal') return CLUBS[item.team]?.primary_color ?? TONE.goal!
  return TONE[item.tone] ?? 'var(--color-muted)'
}

/**
 * Everything this viewer has been told, newest first, in their words and language. Moments
 * read as moments; the state of play reads as the commentator between them. Nothing appears
 * here before it has been on the viewer's screen, so it never spoils what is coming.
 */
export function StoryFeed() {
  const t = useT()
  const feed = useSessionState((s) => s.feed)
  const lang = useSessionState((s) => s.profile.lang)
  return (
    <section aria-labelledby="story-h" className="flex min-h-0 flex-1 flex-col">
      <h2 id="story-h" className="font-display text-[22px] font-bold leading-none">
        {t('storySoFar')}
      </h2>
      {feed.length === 0 ? (
        <p className="mt-3 text-[15px] leading-snug text-muted">{t('storyEmpty')}</p>
      ) : (
        <ol
          className="mt-3 flex min-h-0 flex-1 flex-col gap-3.5 overflow-y-auto pe-1"
          lang={lang}
          dir={isRtl(lang) ? 'rtl' : 'ltr'}
          aria-live="polite"
        >
          {feed.map((it) =>
            isPulse(it) ? <PulseLine key={it.id} it={it} /> : <Moment key={it.id} it={it} />,
          )}
        </ol>
      )}
    </section>
  )
}

function PulseLine({ it }: { it: FeedItem }) {
  const lang = useSessionState((s) => s.profile.lang)
  return (
    <li className="feed-in grid grid-cols-[3.25rem_1fr] gap-x-3">
      <span className="num pt-0.5 text-[15px] leading-none text-muted" dir="ltr">
        {it.clock ?? ''}
      </span>
      <p className="m-0 text-[15px] leading-snug text-text/75">
        <span className="font-semibold text-text">{sentenceCase(it.headline, lang)}.</span>{' '}
        {it.body}
      </p>
    </li>
  )
}

function Moment({ it }: { it: FeedItem }) {
  const t = useT()
  const lang = useSessionState((s) => s.profile.lang)
  const [open, setOpen] = useState(false)
  const id = `why-${it.id.replace(/\W+/g, '-')}`
  const mine = it.forYou === 'scored' || it.favouriteClub
  const tag =
    it.forYou === 'scored'
      ? t('tagYourGoal')
      : it.yourPlayer
        ? t('tagYourPlayer')
        : mine
          ? t('tagYourSide')
          : null
  return (
    <li className="feed-in grid grid-cols-[3.25rem_1fr] gap-x-3">
      <span className="num pt-0.5 text-[18px] leading-none text-amber" dir="ltr">
        {it.clock ?? ''}
      </span>
      <div className="flex min-w-0 gap-2.5">
        <span className="w-[4px] shrink-0" style={{ background: strip(it) }} aria-hidden />
        <div className="min-w-0">
          {tag && (
            <span className="mb-1 inline-block bg-amber px-1.5 py-0.5 text-[12px] font-semibold leading-none text-white">
              {tag}
            </span>
          )}
          <h3
            className={`m-0 font-display font-bold leading-tight ${it.momentKind === 'goal' ? 'text-[24px]' : 'text-[20px]'}`}
          >
            {sentenceCase(it.headline, lang)}
          </h3>
          {it.body && <p className="m-0 mt-0.5 text-[15px] leading-snug text-text/80">{it.body}</p>}
          {it.evidence.length > 0 && (
            <button
              className="mt-1 min-h-8 text-[13px] text-muted underline decoration-text/25 underline-offset-4 hover:text-text"
              aria-expanded={open}
              aria-controls={id}
              onClick={() => setOpen((v) => !v)}
            >
              {t(open ? 'hideWhy' : 'whyThis')}
            </button>
          )}
          {open && (
            <div id={id} className="mt-1 border-t border-hairline pt-2 text-[13px]">
              <p className="m-0 flex items-center gap-1.5 text-text/80">
                {it.verified && <CheckIcon className="size-3 text-control" />}
                {t(it.source.startsWith('agent:') ? 'verifiedBy' : 'fromNumbers')}
              </p>
              <dl className="m-0 mt-1.5 grid grid-cols-[1fr_auto] gap-x-4 gap-y-1">
                {it.evidence.map((e) => (
                  <div key={e.metric} className="contents">
                    <dt className="text-muted">{metricName(lang, e.metric)}</dt>
                    <dd className="num m-0 text-end text-[15px] leading-none" dir="ltr">
                      {Number.isInteger(e.value) ? e.value : e.value.toFixed(1)}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          )}
        </div>
      </div>
    </li>
  )
}
