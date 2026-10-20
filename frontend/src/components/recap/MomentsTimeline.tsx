import type { CatchUp } from '@/net/api'

interface Props {
  catchUp: CatchUp
  /** Full-width page section: the list flows into two columns on a wide screen. */
  wide?: boolean
}

/** The story beats up to the recap's clock, from the spoiler-safe catch-up. */
export function MomentsTimeline({ catchUp, wide = false }: Props) {
  if (catchUp.moments.length === 0) return null
  return (
    <section aria-labelledby="moments-h" className="flex flex-col gap-3">
      <h2 id="moments-h" className="font-display text-[26px] font-semibold leading-none">
        Key moments
      </h2>
      <ol
        className={`flex flex-col border-y border-white/10 ${wide ? 'lg:block lg:columns-2 lg:gap-x-14' : ''}`}
      >
        {catchUp.moments.map((m) => (
          <li
            key={m.moment_id}
            className="grid break-inside-avoid grid-cols-[4.5rem_1fr] gap-x-3 border-b border-white/10 py-3 last:border-b-0"
          >
            <span className="num text-[22px] leading-none text-amber" dir="ltr">
              {m.clock}
            </span>
            <span dir="auto">
              <span className="block font-display text-[22px] font-semibold leading-none">
                {m.headline}
              </span>
              <span className="mt-1 block text-[14px] leading-snug text-text/80">{m.body}</span>
            </span>
          </li>
        ))}
      </ol>
    </section>
  )
}
