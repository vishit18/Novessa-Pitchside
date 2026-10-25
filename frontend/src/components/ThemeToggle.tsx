import { useSyncExternalStore } from 'react'
import { translate } from '@/i18n/strings'
import { loadProfile, type Lang } from '@/state/profile'

type Theme = 'light' | 'dark'
const KEY = 'novessa-theme'

const listeners = new Set<() => void>()

/** The theme on the page right now. index.html sets it before first paint; light unless dark was saved. */
function current(): Theme {
  return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light'
}

function setTheme(next: Theme): void {
  document.documentElement.dataset.theme = next
  try {
    localStorage.setItem(KEY, next)
  } catch {
    /* storage unavailable, the toggle still works for this visit */
  }
  listeners.forEach((l) => l())
}

function subscribe(l: () => void): () => void {
  listeners.add(l)
  return () => listeners.delete(l)
}

/**
 * Light and dark switch for the header. The label is in the viewer's language (the page's own
 * language when it has one, else the saved profile's), and every copy on the page stays in step.
 * `compact` shows the icon alone for phone headers; the translated label stays for screen readers.
 */
export function ThemeToggle({ lang, compact = false }: { lang?: Lang; compact?: boolean }) {
  const theme = useSyncExternalStore(subscribe, current)
  const l = lang ?? loadProfile()?.lang ?? 'en'
  const dark = theme === 'dark'
  const label = translate(l, dark ? 'themeLight' : 'themeDark')
  return (
    <button
      type="button"
      onClick={() => setTheme(dark ? 'light' : 'dark')}
      aria-label={translate(l, dark ? 'themeToLight' : 'themeToDark')}
      title={label}
      className={`flex h-9 shrink-0 items-center gap-2 border border-text/40 text-[14px] font-medium text-text hover:border-text hover:bg-text/[0.05] ${compact ? 'min-w-9 justify-center px-2' : 'px-3'}`}
    >
      <svg viewBox="0 0 16 16" className="size-3.5" aria-hidden fill="currentColor">
        {dark ? (
          <path d="M8 3.2a.8.8 0 0 1-.8-.8V1a.8.8 0 0 1 1.6 0v1.4a.8.8 0 0 1-.8.8Zm0 9.6a.8.8 0 0 1 .8.8V15a.8.8 0 0 1-1.6 0v-1.4a.8.8 0 0 1 .8-.8ZM8 11a3 3 0 1 1 0-6 3 3 0 0 1 0 6Zm5-3a.8.8 0 0 1 .8-.8H15a.8.8 0 0 1 0 1.6h-1.2A.8.8 0 0 1 13 8ZM1 7.2h1.2a.8.8 0 0 1 0 1.6H1a.8.8 0 0 1 0-1.6Z" />
        ) : (
          <path d="M6.2 1.3a.7.7 0 0 1 .2.8 6 6 0 0 0 7.5 7.5.7.7 0 0 1 .9.9A7.2 7.2 0 1 1 5.4 1.1a.7.7 0 0 1 .8.2Z" />
        )}
      </svg>
      <span className={compact ? 'sr-only' : undefined}>{label}</span>
    </button>
  )
}
