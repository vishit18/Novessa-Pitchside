import type { ReactNode } from 'react'
import { Controls, KickOffCard, LowerThird, ScoreBug, StatusPill, Wordmark } from '@/components/Hud'
import { Stage } from '@/components/Stage'
import { isRtl } from '@/state/profile'
import type { Session } from '@/state/session'
import { SessionContext, useSessionState, useT } from '@/state/useSession'

interface Props {
  session: Session
  /** Smaller graphics, for panes that share the screen. */
  compact?: boolean
  /** Show play and speed. Off when a parent view owns the transport. */
  transport?: boolean
  /** Extra content for the top-right corner, under the live indicator. */
  corner?: ReactNode
}

/**
 * One viewer's broadcast: pitch, score bug, lower thirds, tags and controls, in that viewer's
 * language and direction. The broadcast screen shows one; the split view shows two.
 */
export function BroadcastPane({ session, compact = false, transport = true, corner }: Props) {
  return (
    <SessionContext.Provider value={session}>
      <PaneBody compact={compact} transport={transport} corner={corner} />
    </SessionContext.Provider>
  )
}

function PaneBody({ compact, transport, corner }: Omit<Props, 'session'>) {
  const lang = useSessionState((s) => s.profile.lang)
  const status = useSessionState((s) => s.status)
  const detail = useSessionState((s) => s.statusDetail)
  const meta = useSessionState((s) => s.meta)
  const snapshot = useSessionState((s) => s.snapshot)
  const failed = status === 'error' && !snapshot

  return (
    <div
      className="stage-bg relative size-full overflow-hidden"
      lang={lang}
      dir={isRtl(lang) ? 'rtl' : 'ltr'}
    >
      <Stage />

      <div
        className={`pointer-events-none absolute inset-x-0 top-0 flex flex-col items-start gap-2 p-4 sm:flex-row sm:justify-between sm:gap-3 sm:p-6 ${compact ? 'hud-compact' : ''}`}
      >
        <ScoreBug showMatchLine={!compact} />
        <div className="flex flex-col items-end gap-2">
          <StatusPill />
          {corner && <div className="pointer-events-auto">{corner}</div>}
        </div>
      </div>

      <div
        className={`absolute inset-x-0 bottom-0 flex flex-col gap-3 p-4 sm:p-6 ${compact ? 'hud-compact' : ''}`}
      >
        <div className="flex items-end justify-between gap-4">
          <LowerThird />
          {!compact && (
            <div className="hidden sm:block">
              <Wordmark />
            </div>
          )}
        </div>
        {/* On a phone the controls float above the lower third so they never reserve space. */}
        <div className="flex justify-center max-sm:absolute max-sm:inset-x-4 max-sm:bottom-full max-sm:mb-2">
          <Controls transport={transport} />
        </div>
      </div>

      {(!meta || !snapshot) && !failed && <KickOffCard compact={compact} />}
      {failed && <FeedDown detail={detail} />}
    </div>
  )
}

function FeedDown({ detail }: { detail: string | null }) {
  const t = useT()
  return (
    <div className="absolute inset-0 grid place-items-center bg-ink/90 p-6">
      <div className="plate-shadow max-w-md">
        <div className="plate p-6">
          <h2 className="font-display text-2xl font-semibold">{t('feedDown')}</h2>
          <p className="mt-2 text-sm text-muted">{detail ?? t('feedDownBody')}</p>
          <button
            className="mt-4 h-9 border border-amber px-4 text-sm font-medium text-amber hover:bg-amber/10"
            onClick={() => window.location.reload()}
          >
            {t('retry')}
          </button>
        </div>
      </div>
    </div>
  )
}
