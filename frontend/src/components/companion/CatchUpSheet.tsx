import { useCallback, useEffect, useRef, useState } from 'react'
import { getCatchUp, type CatchUp } from '@/net/api'
import type { Session } from '@/state/session'
import { useT } from '@/state/useSession'

type Load = { state: 'loading' } | { state: 'failed' } | { state: 'ready'; data: CatchUp }

interface Props {
  open: boolean
  matchId: string
  session: Session
  onClose: () => void
}

/**
 * Bottom sheet for "What did I miss?". It asks the gateway for the match up to this viewer's
 * own clock, so it cannot spoil anything: the answer is computed from state at that moment.
 */
export function CatchUpSheet({ open, matchId, session, onClose }: Props) {
  const t = useT()
  const [load, setLoad] = useState<Load>({ state: 'loading' })
  const closeRef = useRef<HTMLButtonElement>(null)
  // The parent re-renders every second as the match clock ticks. Reading onClose through a ref
  // keeps these effects from re-running (and refetching) each time it hands us a new function.
  const onCloseRef = useRef(onClose)
  useEffect(() => {
    onCloseRef.current = onClose
  })
  // Only the newest request may write its answer, so a slow earlier one cannot overwrite it.
  const request = useRef(0)

  const fetchNow = useCallback(() => {
    const mine = ++request.current
    setLoad({ state: 'loading' })
    // The viewer's own render time, not the live edge: that is what makes it spoiler-safe.
    const at = session.clock.now(performance.now())
    getCatchUp(matchId, at)
      .then((data) => request.current === mine && setLoad({ state: 'ready', data }))
      .catch(() => request.current === mine && setLoad({ state: 'failed' }))
  }, [matchId, session])

  // Opening: fetch once, move focus into the sheet, and hand it back to the trigger on close.
  useEffect(() => {
    if (!open) return
    const trigger = document.activeElement as HTMLElement | null
    fetchNow()
    closeRef.current?.focus()
    return () => trigger?.focus?.()
  }, [open, fetchNow])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onCloseRef.current()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  return (
    // `invisible` takes a closed sheet out of the tab order and the accessibility tree. A bare
    // aria-hidden would leave its buttons focusable. Visibility must flip to visible at once on
    // open, so focus can move in; on close it waits for the fade to finish.
    <div
      className={`fixed inset-0 z-20 ${open ? 'visible opacity-100' : 'pointer-events-none invisible opacity-0'}`}
      style={{
        transition: `opacity 200ms cubic-bezier(0.23, 1, 0.32, 1), visibility 0s linear ${open ? '0s' : '200ms'}`,
      }}
    >
      {/* Click-away area only. The close button below is the accessible way out, as is Escape. */}
      <div aria-hidden className="absolute inset-0 bg-black/60" onClick={onClose} />
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="catchup-h"
        className={`absolute inset-x-0 bottom-0 mx-auto flex max-h-[85dvh] w-full max-w-[560px] flex-col bg-raised transition-transform duration-200 ease-out motion-reduce:transition-none ${open ? 'translate-y-0' : 'translate-y-full'}`}
      >
        <div className="overflow-y-auto px-5 pb-4 pt-5">
          <h2 id="catchup-h" className="font-display text-[30px] font-bold leading-none">
            {load.state === 'ready' ? t('missedTitle', { clock: load.data.clock }) : t('missed')}
          </h2>

          {load.state === 'loading' && (
            <p className="pulse-soft mt-4 text-[15px] text-muted" role="status">
              {t('missedLoading')}
            </p>
          )}
          {load.state === 'failed' && (
            <div className="mt-4" role="alert">
              <p className="text-[15px]">{t('missedFailed')}</p>
              <button
                className="mt-3 h-11 border border-amber px-4 text-[15px] font-medium text-amber"
                onClick={fetchNow}
              >
                {t('retry')}
              </button>
            </div>
          )}
          {load.state === 'ready' && (
            <>
              <p dir="auto" className="mt-3 text-[16px] leading-relaxed">
                {load.data.summary}
              </p>
              {load.data.moments.length > 0 && (
                <ol className="mt-4 flex flex-col divide-y divide-white/10 border-y border-white/10">
                  {load.data.moments.map((m) => (
                    <li key={m.moment_id} className="grid grid-cols-[4.5rem_1fr] gap-x-3 py-3">
                      <span className="num text-[20px] leading-none text-amber" dir="ltr">
                        {m.clock}
                      </span>
                      <span>
                        <span
                          dir="auto"
                          className="block font-display text-[20px] font-semibold leading-none"
                        >
                          {m.headline}
                        </span>
                        <span
                          dir="auto"
                          className="mt-1 block text-[14px] leading-snug text-text/80"
                        >
                          {m.body}
                        </span>
                      </span>
                    </li>
                  ))}
                </ol>
              )}
              <p className="mt-4 text-[13px] text-muted">
                {t('noSpoilers', { clock: load.data.clock })}
              </p>
            </>
          )}
        </div>
        <div className="px-5 pb-[max(1rem,env(safe-area-inset-bottom))] pt-1">
          <button
            ref={closeRef}
            className="h-12 w-full bg-amber text-[16px] font-semibold text-ink"
            onClick={onClose}
          >
            {t('missedClose')}
          </button>
        </div>
      </section>
    </div>
  )
}
