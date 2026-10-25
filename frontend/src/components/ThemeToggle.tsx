import { useEffect, useState } from 'react'

type Theme = 'light' | 'dark'
const KEY = 'novessa-theme'

/** The saved choice, else the viewer's system setting. index.html applies the same rule before first paint. */
function initialTheme(): Theme {
  try {
    const saved = localStorage.getItem(KEY)
    if (saved === 'dark' || saved === 'light') return saved
  } catch {
    /* storage unavailable: fall through to the system setting */
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(initialTheme)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem(KEY, theme)
    } catch {
      /* storage unavailable, the toggle still works for this visit */
    }
  }, [theme])

  return (
    <button
      type="button"
      onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
      aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
      className="fixed right-4 bottom-4 z-50 rounded-full border border-hairline bg-raised px-4 py-2 text-sm font-semibold text-text shadow"
    >
      {theme === 'dark' ? 'Light mode' : 'Dark mode'}
    </button>
  )
}
