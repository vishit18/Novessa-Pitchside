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

  const fetchNow = useCallback(() => {
    setLoad({ state: 'loading' })
    // The viewer's own render time, not the live edge: that is what makes it spoiler-safe.
    const at = session.clock.now(performance.now())
    getCatchUp(matchId, at)
      .then((data) => setLoad({ state: 'ready', data }))
      .catch(() => setLoad({ state: 'failed' }))
  }, [matchId, session])

  useEffect(() => {
    if (!open) return
    fetchNow()
    closeRef.current?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, fetchNow, onClose])

  return (
    <div
      className={`fixed inset-0 z-20 transition-opacity duration-200 ${open ? 'opacity-100' : 'pointer-events-none opacity-0'}`}
      aria-hidden={!open}
    >
      <button
        tabIndex={-1}
        aria-label={t('missedClose')}
        className="absolute inset-0 bg-black/60"
        onClick={onClose}
      />
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="catchup-h"
        className={`absolute inset-x-0 bottom-0 mx-auto flex max-h-[85dvh] w-full max-w-[560px] flex-col bg-raised transition-transform duration-200 ease-out ${open ? 'translate-y-0' : 'translate-y-full'}`}
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
