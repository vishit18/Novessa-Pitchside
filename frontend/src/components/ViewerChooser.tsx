import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { useEffect, useId, useRef, useState } from 'react'
import { LANGS, PERSONAS, type Lang, type Persona } from '@/state/profile'
import { CheckIcon, ChevronDownIcon } from './icons'

interface Props {
  persona: string
  lang: string
  onChange: (patch: { persona?: Persona; lang?: Lang }) => void
  /** Which side the panel lines up with. */
  align?: 'start' | 'end'
}

/**
 * "Viewing as Casual, English": one button that opens persona and language together, so a
 * screen showing a viewer needs one control for them instead of ten chips and a select.
 * Picking closes it. Escape or a click outside closes it too.
 */
export function ViewerChooser({ persona, lang, onChange, align = 'start' }: Props) {
  const [open, setOpen] = useState(false)
  // On a phone the panel spans the screen under the button instead of hanging off one edge.
  const [phoneTop, setPhoneTop] = useState<number | null>(null)
  const root = useRef<HTMLDivElement>(null)
  const button = useRef<HTMLButtonElement>(null)
  const panelId = useId()
  const reduce = useReducedMotion()
  const p = PERSONAS.find((x) => x.id === persona)
  const l = LANGS.find((x) => x.id === lang)

  useEffect(() => {
    if (!open) return
    const onDown = (e: PointerEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      setOpen(false)
      button.current?.focus()
    }
    const onScroll = () => setOpen(false)
    window.addEventListener('pointerdown', onDown)
    window.addEventListener('keydown', onKey)
    if (window.innerWidth < 640) window.addEventListener('scroll', onScroll, { passive: true })
    // Land on the current persona so the keyboard starts where the viewer is.
    root.current?.querySelector<HTMLButtonElement>('[aria-pressed="true"]')?.focus()
    return () => {
      window.removeEventListener('pointerdown', onDown)
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('scroll', onScroll)
    }
  }, [open])

  const pick = (patch: { persona?: Persona; lang?: Lang }) => {
    setOpen(false)
    button.current?.focus()
    if (patch.persona !== undefined && patch.persona === persona) return
    if (patch.lang !== undefined && patch.lang === lang) return
    onChange(patch)
  }

  const option = (on: boolean) =>
    `flex h-10 w-full items-center justify-between gap-3 px-3 text-start text-[15px] transition-colors ${
      on ? 'text-amber' : 'text-text/85 hover:bg-text/5 hover:text-text'
    }`

  return (
    <div ref={root} className="relative">
      <button
        ref={button}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => {
          const r = button.current?.getBoundingClientRect()
          setPhoneTop(r && window.innerWidth < 640 ? r.bottom + 6 : null)
          setOpen((v) => !v)
        }}
        className="flex h-10 items-center gap-2 border border-text px-3 text-[15px] transition-colors hover:border-amber aria-expanded:border-amber"
      >
        <span className="text-muted">Viewing as</span>
        <span className="font-semibold text-text">
          {p?.label ?? persona}, {l?.label ?? lang}
        </span>
        <ChevronDownIcon
          className={`size-3 text-muted transition-transform duration-150 ${open ? 'rotate-180' : ''}`}
        />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            id={panelId}
            role="group"
            aria-label="Viewer"
            initial={{ opacity: 0, scale: reduce ? 1 : 0.97, y: reduce ? 0 : -4 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, transition: { duration: 0.1 } }}
            transition={{ duration: 0.16, ease: [0.23, 1, 0.32, 1] }}
            style={
              phoneTop === null
                ? { transformOrigin: align === 'end' ? 'top right' : 'top left' }
                : {
                    position: 'fixed',
                    top: phoneTop,
                    left: 16,
                    right: 16,
                    width: 'auto',
                    transformOrigin: 'top center',
                  }
            }
            className={`absolute top-full z-30 mt-1.5 grid w-[min(92vw,460px)] grid-cols-2 gap-3 border border-text/15 bg-ink p-2 shadow-2xl ${
              align === 'end' ? 'end-0' : 'start-0'
            }`}
          >
            <div>
              <p className="px-3 pt-1 pb-1.5 text-[12px] text-muted">Watching as</p>
              {PERSONAS.map((x) => (
                <button
                  key={x.id}
                  aria-pressed={x.id === persona}
                  className={option(x.id === persona)}
                  onClick={() => pick({ persona: x.id })}
                >
                  {x.label}
                  {x.id === persona && <CheckIcon />}
                </button>
              ))}
            </div>
            <div>
              <p className="px-3 pt-1 pb-1.5 text-[12px] text-muted">Language</p>
              {LANGS.map((x) => (
                <button
                  key={x.id}
                  lang={x.id}
                  aria-pressed={x.id === lang}
                  className={option(x.id === lang)}
                  onClick={() => pick({ lang: x.id })}
                >
                  {x.label}
                  {x.id === lang && <CheckIcon />}
                </button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
