import { useEffect, useRef, useState } from 'react'
import { Wordmark } from '@/components/Hud'
import { ThemeToggle } from '@/components/ThemeToggle'
import type { StringKey } from '@/i18n/strings'
import { translate } from '@/i18n/strings'
import { navigate, withParams } from '@/router'
import type { Lang } from '@/state/profile'

/** Every place in the app, in the order a first-time visitor would explore them. */
export const NAV_ITEMS: { path: string; key: StringKey; who: string }[] = [
  { path: '/', key: 'navHome', who: 'What this is' },
  { path: '/watch', key: 'navWatch', who: 'Your broadcast' },
  { path: '/split', key: 'navSplit', who: 'Two fans, one match' },
  { path: '/companion', key: 'navCompanion', who: 'Second screen' },
  { path: '/recap', key: 'navRecap', who: 'Half and full time' },
  { path: '/real', key: 'navReal', who: 'The same idea on video' },
  { path: '/control', key: 'navControl', who: 'The agents at work' },
]

/** Where a nav item goes, keeping the match the viewer is on. */
function hrefFor(path: string, match: string | null): string {
  if (path === '/') return withParams('/')
  // Watch always starts by picking a match and how to watch it. A returning viewer's first
  // option there is "Same as last time", so it is still one click for them.
  if (path === '/watch') return withParams('/start', match ? { match } : {})
  if (path === '/real') return withParams('/real')
  return withParams(path, match ? { match } : {})
}

function isCurrent(path: string, current: string): boolean {
  if (path === '/') return current === '/'
  if (path === '/watch') return current.startsWith('/watch') || current.startsWith('/start')
  return current.startsWith(path)
}

/**
 * The header on every page except the full-screen broadcast. The wordmark goes home; the current
 * page is marked with the amber rule the rest of the app uses for "selected".
 */
export function AppNav({ match = null, lang: langProp }: { match?: string | null; lang?: Lang }) {
  const lang = langProp ?? 'en'
  const current = window.location.pathname
  return (
    <header className="relative z-20 flex flex-wrap items-center justify-between gap-x-8 gap-y-2">
      <button
        className="min-h-11 shrink-0"
        onClick={() => navigate(withParams('/'))}
        aria-label="Novessa Pitchside home"
      >
        <Wordmark />
      </button>
      <div className="flex items-center gap-2 sm:hidden">
        <ThemeToggle lang={langProp} compact />
        <NavMenu match={match ?? 'derby_01'} lang={lang} />
      </div>
      <div className="flex min-w-0 max-w-full items-center gap-4 max-sm:hidden">
        <nav aria-label="Pages" className="-mx-1 max-w-full">
          <ul className="flex items-center gap-1 px-1">
            {NAV_ITEMS.filter((i) => i.path !== '/').map((i) => {
              const on = isCurrent(i.path, current)
              return (
                <li key={i.path}>
                  <a
                    href={hrefFor(i.path, match)}
                    onClick={(e) => {
                      e.preventDefault()
                      navigate(hrefFor(i.path, match))
                    }}
                    aria-current={on ? 'page' : undefined}
                    className={`relative flex min-h-11 items-center whitespace-nowrap px-2.5 text-[15px] transition-colors ${
                      on ? 'text-text' : 'text-muted hover:text-text'
                    }`}
                  >
                    {translate(lang, i.key)}
                    {on && <span className="absolute inset-x-2.5 bottom-1.5 h-[2px] bg-amber" />}
                  </a>
                </li>
              )
            })}
          </ul>
        </nav>
        <ThemeToggle lang={langProp} />
      </div>
    </header>
  )
}

/**
 * The broadcast's way out: one button in the corner that opens every page. The broadcast is
 * full screen, so a header would sit on top of the football.
 */
export function NavMenu({ match, lang }: { match: string; lang: Lang }) {
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const onDown = (e: PointerEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    window.addEventListener('pointerdown', onDown)
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('pointerdown', onDown)
      window.removeEventListener('keydown', onKey)
    }
  }, [open])
  return (
    <div className="relative" ref={root}>
      <button
        className="flex h-9 items-center gap-2 border border-text bg-ink/70 px-3 text-[14px] font-medium text-text hover:bg-raised"
        aria-expanded={open}
        aria-haspopup="true"
        onClick={() => setOpen(!open)}
      >
        <svg viewBox="0 0 14 10" className="h-2.5 w-3.5" aria-hidden>
          <path d="M0 1h14M0 5h14M0 9h14" stroke="currentColor" strokeWidth="1.6" />
        </svg>
        {translate(lang, 'menu')}
      </button>
      {open && (
        <div className="plate-shadow absolute end-0 top-full z-30 mt-2 w-[300px]">
          <ul className="plate py-1.5" style={{ ['--cut' as string]: '10px' }}>
            {NAV_ITEMS.map((i) => (
              <li key={i.path}>
                <a
                  href={hrefFor(i.path, match)}
                  onClick={(e) => {
                    e.preventDefault()
                    setOpen(false)
                    navigate(hrefFor(i.path, match))
                  }}
                  aria-current={isCurrent(i.path, window.location.pathname) ? 'page' : undefined}
                  className="flex items-baseline justify-between gap-3 px-4 py-2 text-[15px] text-text hover:bg-text/[0.05] aria-[current=page]:text-amber"
                >
                  {translate(lang, i.key)}
                  <span className="text-[12px] text-muted" lang="en">
                    {i.who}
                  </span>
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
