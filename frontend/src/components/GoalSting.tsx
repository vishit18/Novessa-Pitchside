import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import { CLUBS, PLAYERS } from '@/data/league'
import { useSessionState, useT } from '@/state/useSession'
import type { OverlayEnvelope } from '@/types/overlay'

const HOLD_MS = 2600

interface Sting {
  id: string
  team: string
  scorer: string | null
  clock: string
}

/** The goal insight among the active overlays, if one is showing. */
function goalOverlay(active: OverlayEnvelope[]): OverlayEnvelope | null {
  return active.find((o) => o.kind === 'insight' && o.payload['moment_kind'] === 'goal') ?? null
}

/**
 * The one loud moment in the broadcast. When a goal lands, a band in the scoring club's kit
 * wipes across the pitch with the club, the new score and the scorer, holds for under three
 * seconds and goes. It comes from the deterministic layer, so it never waits for an agent.
 * Each goal plays once per viewer; seeking back over it plays it again.
 */
export function GoalSting({ compact = false }: { compact?: boolean }) {
  const active = useSessionState((s) => s.active)
  const score = useSessionState((s) => s.snapshot?.score ?? null)
  const meta = useSessionState((s) => s.meta)
  const t = useT()
  const reduce = useReducedMotion()
  const [sting, setSting] = useState<Sting | null>(null)
  const played = useRef(new Set<string>())

  const goal = goalOverlay(active)
  useEffect(() => {
    if (!goal) return
    const id = goal.moment_id ?? goal.msg_id
    if (played.current.has(id)) return
    played.current.add(id)
    const scorerId = goal.anchor?.type === 'player' ? goal.anchor.id : null
    setSting({
      id,
      team: String(goal.payload['team'] ?? ''),
      scorer: scorerId ? (PLAYERS[scorerId]?.name ?? null) : null,
      clock: String(goal.payload['clock'] ?? ''),
    })
    const timer = window.setTimeout(() => setSting(null), HOLD_MS)
    return () => window.clearTimeout(timer)
  }, [goal])

  const club = sting ? CLUBS[sting.team] : undefined
  const kit = club?.primary_color ?? 'var(--color-amber)'
  const line =
    meta && score
      ? `${meta.home.code} ${score[meta.home.code] ?? 0}-${score[meta.away.code] ?? 0} ${meta.away.code}`
      : ''

  return (
    <AnimatePresence>
      {sting && (
        <motion.div
          key={sting.id}
          role="status"
          aria-live="assertive"
          className="pointer-events-none absolute inset-x-0 top-1/2 z-20 -translate-y-1/2"
          initial={reduce ? { opacity: 0 } : { clipPath: 'inset(0 100% 0 0)' }}
          animate={reduce ? { opacity: 1 } : { clipPath: 'inset(0 0% 0 0)' }}
          exit={{ opacity: 0, transition: { duration: 0.25 } }}
          transition={{ duration: 0.26, ease: [0.25, 1, 0.5, 1] }}
        >
          <div className="flex items-stretch bg-ink/92 shadow-[0_10px_40px_rgb(0_0_0/0.6)]">
            <span className="w-[18px] shrink-0" style={{ background: kit }} />
            <div
              className={`flex flex-1 flex-wrap items-end gap-x-8 gap-y-1 ${compact ? 'px-5 py-3' : 'px-10 py-5'}`}
              dir="ltr"
            >
              <span
                className={`font-display font-bold uppercase leading-[0.8] tracking-tight ${compact ? 'text-[64px]' : 'text-[120px]'}`}
                style={{ color: kit, textShadow: '0 0 30px rgb(0 0 0 / 0.5)' }}
              >
                {t('kind_goal')}
              </span>
              <span className="flex flex-col pb-1.5">
                <span
                  className={`font-display font-semibold leading-none ${compact ? 'text-[24px]' : 'text-[40px]'}`}
                >
                  {club?.name ?? sting.team}
                </span>
                <span
                  className={`num mt-1.5 text-muted ${compact ? 'text-[16px]' : 'text-[22px]'}`}
                >
                  {[line, sting.scorer, sting.clock].filter(Boolean).join('   ')}
                </span>
              </span>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
