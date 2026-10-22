import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { useEffect, useRef, type ReactNode } from 'react'
import { CLUBS, PLAYERS } from '@/data/league'
import type { StringKey } from '@/i18n/strings'
import { LANGS, METRICS, PERSONAS, isRtl, type ViewerProfile } from '@/state/profile'
import { useSessionState, useT } from '@/state/useSession'
import type { Group } from '@/types/schema'
import { CheckIcon, ChevronDownIcon } from '@/components/icons'

const GROUPS: Group[] = ['FWD', 'MID', 'DEF', 'GK']

/** "Watching as Casual, English, Ashford Rovers": who this broadcast is for, always visible. */
export function WatchingAsChip({ onOpen, open }: { onOpen: () => void; open: boolean }) {
  const t = useT()
  const p = useSessionState((s) => s.profile)
  const persona = p.metric
    ? (METRICS.find((m) => m.id === p.metric)?.label ?? p.metric)
    : t(`persona_${p.persona}` as StringKey)
  const lang = LANGS.find((l) => l.id === p.lang)?.label ?? p.lang
  const who = p.player ? PLAYERS[p.player]?.name : p.club ? CLUBS[p.club]?.name : null
  return (
    <button
      onClick={onOpen}
      aria-expanded={open}
      aria-haspopup="dialog"
      className="flex h-11 max-w-full items-center gap-2 border border-text px-3 text-start text-[15px] transition-colors hover:border-amber aria-expanded:border-amber"
    >
      <span className="shrink-0 text-muted">{t('watchingAs')}</span>
      <span className="truncate font-semibold">
        {[persona, lang, who].filter(Boolean).join(', ')}
      </span>
      <ChevronDownIcon className="size-3 shrink-0 text-muted" />
    </button>
  )
}

/**
 * Everything that makes this broadcast yours, changed in place while the match plays. Each pick
 * applies at once (the broadcast reconnects at the same second), so the viewer sees what it does.
 */
export function WatchingAsSheet({
  open,
  onClose,
  onChange,
}: {
  open: boolean
  onClose: () => void
  onChange: (patch: Partial<ViewerProfile>) => void
}) {
  const t = useT()
  const reduce = useReducedMotion()
  const p = useSessionState((s) => s.profile)
  const meta = useSessionState((s) => s.meta)
  const panel = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const back = document.activeElement as HTMLElement | null
    panel.current?.querySelector<HTMLElement>('[aria-pressed="true"], button')?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
      back?.focus()
    }
  }, [open, onClose])

  const clubs = meta ? [meta.home.code, meta.away.code] : []
  const sheet = meta && p.club ? (meta.home.code === p.club ? meta.home : meta.away) : null

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            key="scrim"
            className="fixed inset-0 z-40 bg-[#101418]/30"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, transition: { duration: 0.12 } }}
            transition={{ duration: 0.16 }}
            onClick={onClose}
            aria-hidden
          />
          <motion.div
            key="sheet"
            ref={panel}
            role="dialog"
            aria-modal="true"
            aria-labelledby="watching-as-h"
            dir={isRtl(p.lang) ? 'rtl' : 'ltr'}
            lang={p.lang}
            className="fixed inset-y-0 end-0 z-50 flex w-[min(100vw,460px)] flex-col overflow-y-auto bg-ink px-6 pb-8 pt-6 shadow-2xl"
            initial={reduce ? { opacity: 0 } : { x: isRtl(p.lang) ? -40 : 40, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ opacity: 0, transition: { duration: 0.12 } }}
            transition={{ duration: 0.2, ease: [0.23, 1, 0.32, 1] }}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 id="watching-as-h" className="font-display text-[34px] font-bold leading-none">
                  {t('sheetTitle')}
                </h2>
                <p className="mt-2 text-[15px] text-muted">{t('sheetHint')}</p>
              </div>
              <button
                onClick={onClose}
                className="h-10 shrink-0 bg-amber px-4 text-[14px] font-semibold text-white"
              >
                {t('done')}
              </button>
            </div>

            <Group title={t('howYouWatch')}>
              {PERSONAS.map((x) => (
                <Option
                  key={x.id}
                  on={!p.metric && p.persona === x.id}
                  onClick={() => onChange({ persona: x.id, metric: null })}
                  label={t(`persona_${x.id}` as StringKey)}
                  hint={p.lang === 'en' ? x.hint : undefined}
                />
              ))}
              <Option
                on={p.metric !== null}
                onClick={() =>
                  onChange({ persona: 'analyst', metric: p.metric ?? METRICS[0]!.id, player: null })
                }
                label={t('oneNumber')}
              />
              {p.metric && (
                <div className="ms-4 mt-1 flex flex-wrap gap-1.5">
                  {METRICS.map((m) => (
                    <button
                      key={m.id}
                      aria-pressed={p.metric === m.id}
                      onClick={() => onChange({ metric: m.id })}
                      className="h-9 border border-hairline px-2.5 text-[14px] aria-pressed:border-text aria-pressed:bg-text aria-pressed:text-ink"
                    >
                      {m.label}
                    </button>
                  ))}
                </div>
              )}
            </Group>

            <Group title={t('yourClub')}>
              {clubs.map((c) => (
                <Option
                  key={c}
                  on={p.club === c}
                  onClick={() => onChange({ club: c, player: null })}
                  label={CLUBS[c]?.name ?? c}
                  kit={CLUBS[c]?.primary_color}
                />
              ))}
              <Option
                on={p.club === null}
                onClick={() => onChange({ club: null, player: null })}
                label={t('noClub')}
              />
            </Group>

            {sheet && !p.metric && (
              <Group title={t('yourPlayer')}>
                <p className="mb-1 text-[14px] text-muted">{t('yourPlayerHint')}</p>
                {GROUPS.map((g) => {
                  const ids = sheet.starters
                    .filter((s) => s.group === g)
                    .sort((a, b) => a.slot - b.slot)
                  if (!ids.length) return null
                  return (
                    <div key={g} className="mt-1.5">
                      <p className="text-[12px] text-muted">{t(`pos_${g}` as StringKey)}</p>
                      <div className="mt-1 grid grid-cols-2 gap-1.5">
                        {ids.map(({ player_id }) => {
                          const pl = PLAYERS[player_id]
                          return (
                            <button
                              key={player_id}
                              aria-pressed={p.player === player_id}
                              onClick={() =>
                                onChange({ player: p.player === player_id ? null : player_id })
                              }
                              className="flex h-10 items-baseline gap-2 border border-hairline px-2.5 text-start text-[15px] hover:border-text aria-pressed:border-text aria-pressed:bg-text aria-pressed:text-ink"
                            >
                              <span className="num w-5 text-end text-[14px] opacity-70" dir="ltr">
                                {pl?.shirt}
                              </span>
                              <span className="truncate">{pl?.name ?? player_id}</span>
                            </button>
                          )
                        })}
                      </div>
                    </div>
                  )
                })}
              </Group>
            )}

            <Group title={t('language')}>
              <div className="grid grid-cols-2 gap-1.5">
                {LANGS.map((l) => (
                  <button
                    key={l.id}
                    lang={l.id}
                    aria-pressed={p.lang === l.id}
                    onClick={() => onChange({ lang: l.id })}
                    className="flex h-10 items-center justify-between border border-hairline px-3 text-[15px] hover:border-text aria-pressed:border-text"
                  >
                    {l.label}
                    {p.lang === l.id && <CheckIcon />}
                  </button>
                ))}
              </div>
            </Group>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}

function Group({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-7 border-t border-hairline pt-4">
      <h3 className="mb-2 font-display text-[20px] font-bold leading-none">{title}</h3>
      <div className="flex flex-col gap-1">{children}</div>
    </section>
  )
}

function Option({
  on,
  onClick,
  label,
  hint,
  kit,
}: {
  on: boolean
  onClick: () => void
  label: string
  hint?: string
  kit?: string
}) {
  return (
    <button
      aria-pressed={on}
      onClick={onClick}
      className="flex min-h-11 items-center gap-3 px-2 py-1.5 text-start transition-colors hover:bg-raised"
    >
      <span className={`w-[4px] self-stretch ${on ? 'bg-amber' : 'bg-transparent'}`} aria-hidden />
      {kit && <span className="h-5 w-[6px] shrink-0" style={{ background: kit }} aria-hidden />}
      <span className="min-w-0 flex-1">
        <span className={`block text-[16px] ${on ? 'font-semibold' : ''}`}>{label}</span>
        {hint && <span className="block text-[13px] text-muted">{hint}</span>}
      </span>
      {on && <CheckIcon className="size-3.5 shrink-0" />}
    </button>
  )
}
