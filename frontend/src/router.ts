import { useEffect, useState } from 'react'

/** Minimal path router: three screens don't need a library. */
export function navigate(to: string): void {
  window.history.pushState(null, '', to)
  window.dispatchEvent(new PopStateEvent('popstate'))
}

export function useLocation(): { path: string; query: URLSearchParams } {
  const read = () => ({
    path: window.location.pathname,
    query: new URLSearchParams(window.location.search),
  })
  const [loc, setLoc] = useState(read)
  useEffect(() => {
    const on = () => setLoc(read())
    window.addEventListener('popstate', on)
    return () => window.removeEventListener('popstate', on)
  }, [])
  return loc
}

/** Keep debug params (source, t, speed) when moving between screens. */
export function withParams(path: string, extra: Record<string, string> = {}): string {
  const keep = new URLSearchParams()
  const cur = new URLSearchParams(window.location.search)
  for (const k of ['source', 't', 'speed']) {
    const v = cur.get(k)
    if (v !== null) keep.set(k, v)
  }
  for (const [k, v] of Object.entries(extra)) keep.set(k, v)
  const q = keep.toString()
  return q ? `${path}?${q}` : path
}
