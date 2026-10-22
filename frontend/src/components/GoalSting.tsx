import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import { CLUBS, PLAYERS } from '@/data/league'
import { useSession, useSessionState, useT } from '@/state/useSession'
import type { OverlayEnvelope } from '@/types/overlay'

const HOLD_MS = 4200

interface Sting {
  id: string
  team: string
  scorer: string | null
  clock: string
  penalty: boolean
}

/** The goal insight among the active overlays, if one is showing. */
function goalOverlay(active: OverlayEnvelope[]): OverlayEnvelope | null {
  return active.find((o) => o.kind === 'insight' && o.payload['moment_kind'] === 'goal') ?? null
}

/**
 * The one loud moment in the broadcast. When a goal lands, a band in the scoring club's kit
 * wipes across the lower pitch with the club, the scorer, how and when, holds for under three
 * seconds and goes. The lower third waits until it has gone, so the two never land together.
 * It comes from the deterministic layer, so it never waits for an agent. A viewer who supports
 * the other side gets the same news, quieter. Each goal plays once per viewer; seeking back
 * over it plays it again.
 */
export function GoalSting({ compact = false }: { compact?: boolean }) {
  const session = useSession()
  const active = useSessionState((s) => s.active)
  const fan = useSessionState((s) => s.profile.club)
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
      penalty: goal.payload['penalty'] === true,
    })
  }, [goal])

  // Keyed on the sting, not the overlay: agent text attaching to the goal must not restart it.
  const stingId = sting?.id
  useEffect(() => {
    if (!stingId) return
    session.store.getState().set({ goalBand: true })
    const timer = window.setTimeout(() => setSting(null), HOLD_MS)
    return () => {
      window.clearTimeout(timer)
      session.store.getState().set({ goalBand: false })
    }
  }, [stingId, session])

  const club = sting ? CLUBS[sting.team] : undefined
  const kit = club?.primary_color ?? 'var(--color-amber)'
  const against = !!sting && !!fan && fan !== sting.team
  const ours = !!sting && fan === sting.team
  const name = club?.name ?? sting?.team ?? ''
  const details = sting
    ? [sting.scorer, sting.penalty ? t('kind_penalty') : null, sting.clock].filter(
        (x): x is string => !!x,
      )
    : []

  return (
    <AnimatePresence>
      {sting && (
        <motion.div
          key={sting.id}
          role="status"
          aria-live="assertive"
          // Landscape: low on the pitch, clear of both goalmouths and above the lower third's
          // zone. Portrait puts the goals top and bottom, so there it stays on halfway.
          className="pointer-events-none absolute inset-x-0 top-1/2 z-20 -translate-y-1/2 sm:top-auto sm:bottom-[16%] sm:translate-y-0"
          initial={reduce ? { opacity: 0 } : { clipPath: 'inset(0 100% 0 0)' }}
          animate={reduce ? { opacity: 1 } : { clipPath: 'inset(0 0% 0 0)' }}
          exit={{ opacity: 0, transition: { duration: 0.15 } }}
          transition={{ duration: 0.18, ease: [0.25, 1, 0.5, 1] }}
        >
          <div className="flex items-stretch bg-ink/92 shadow-[0_10px_40px_rgb(0_0_0/0.6)]">
            <span className="w-[18px] shrink-0" style={{ background: kit }} />
            <div
              className={`flex flex-1 flex-wrap items-end gap-x-8 gap-y-1 ${compact ? 'px-5 py-3' : 'px-10 py-5'}`}
            >
              {/* The conceding fan gets the news without the shout: no giant GOAL. */}
              {!against && (
                <span
                  className={`font-display font-bold uppercase leading-[0.8] tracking-tight ${
                    compact ? 'text-[64px]' : 'text-[120px]'
                  }`}
                  style={{ color: kit, textShadow: '0 0 30px rgb(0 0 0 / 0.5)' }}
                >
                  {t('kind_goal')}
                </span>
              )}
              <span className="flex flex-col pb-1.5">
                <span
                  className={`font-display font-semibold leading-none ${compact ? 'text-[24px]' : 'text-[40px]'}`}
                >
                  {against ? t('goalFor', { club: name }) : name}
                  {ours && ' '}
                  {ours && (
                    <span
                      className={`ms-3 inline-block bg-amber px-2 align-middle font-semibold text-ink ${compact ? 'text-[14px]' : 'text-[20px]'}`}
                    >
                      {t('tagYourGoal')}
                    </span>
                  )}
                </span>
                <span
                  className={`num mt-1.5 text-muted ${compact ? 'text-[16px]' : 'text-[22px]'}`}
                >
                  {details.map((part, i) => (
                    <span key={part}>
                      {i > 0 && (
                        <span className="mx-2 text-text/30" aria-hidden>
                          ·
                        </span>
                      )}
                      {part}
                    </span>
                  ))}
                </span>
              </span>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
