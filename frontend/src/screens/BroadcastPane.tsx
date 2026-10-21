import { useCallback, useEffect, type ReactNode } from 'react'
import { AskSheet } from '@/components/AskSheet'
import { GoalSting } from '@/components/GoalSting'
import {
  Controls,
  KickOffCard,
  LowerThird,
  MetricReadout,
  ScoreBug,
  StatusPill,
  Wordmark,
} from '@/components/Hud'
import { Stage } from '@/components/Stage'
import { isRtl } from '@/state/profile'
import type { Session } from '@/state/session'
import { SessionContext, useSession, useSessionState, useT } from '@/state/useSession'

interface Props {
  session: Session
  /** Smaller graphics, for panes that share the screen. */
  compact?: boolean
  /** Show play and speed. Off when a parent view owns the transport. */
  transport?: boolean
  /** Extra content for the top-right corner, under the live indicator. */
  corner?: ReactNode
  /** Leave out the match line and wordmark: the pitch is zoomed in and they sit on players. */
  focus?: boolean
}

/**
 * One viewer's broadcast: pitch, score bug, lower thirds, tags and controls, in that viewer's
 * language and direction. The broadcast screen shows one; the split view shows two.
 */
export function BroadcastPane({
  session,
  compact = false,
  transport = true,
  corner,
  focus = false,
}: Props) {
  return (
    <SessionContext.Provider value={session}>
      <PaneBody compact={compact} transport={transport} corner={corner} focus={focus} />
    </SessionContext.Provider>
  )
}

function PaneBody({ compact, transport, corner, focus }: Omit<Props, 'session'>) {
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
        <div className="flex w-[min(100%,380px)] flex-col gap-3">
          <ScoreBug showMatchLine={!compact && !focus} />
          <MetricReadout />
        </div>
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
          {!compact && !focus && (
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

      <GoalSting compact={compact} />
      <Stalled />
      {!compact && <AskLayer />}
      {(!meta || !snapshot) && !failed && <KickOffCard compact={compact} />}
      {failed && <FeedDown detail={detail} />}
    </div>
  )
}

/** Ask the Analyst over the right of the pitch. "/" opens it, Escape closes it. */
function AskLayer() {
  const session = useSession()
  const open = useSessionState((s) => s.askOpen)
  const close = useCallback(() => session.store.getState().set({ askOpen: false }), [session])
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = e.target instanceof HTMLElement && e.target.closest('input, textarea, select')
      if (e.key === '/' && !typing) {
        e.preventDefault()
        session.store.getState().set({ askOpen: true })
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [session])
  return <AskSheet open={open} onClose={close} />
}

/** A pane that was playing and stopped getting frames says so, rather than sitting frozen. */
function Stalled() {
  const stalled = useSessionState((s) => s.stalled)
  const t = useT()
  if (!stalled) return null
  return (
    <div className="pointer-events-none absolute inset-x-0 top-[38%] z-10 flex justify-center px-4">
      <p
        role="status"
        className="flex items-center gap-3 bg-ink/85 px-4 py-2.5 text-[15px] text-text shadow-lg"
      >
        <span className="pulse-soft size-2 rounded-full bg-amber" aria-hidden />
        {t('stalled')}
      </p>
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
