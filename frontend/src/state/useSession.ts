import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { useStore } from 'zustand'
import { translate, type StringKey } from '@/i18n/strings'
import type { SourceOptions } from '@/net/source'
import { Session } from './session'
import type { UIState } from './store'

export const SessionContext = createContext<Session | null>(null)

/** The session the surrounding view belongs to. */
export function useSession(): Session {
  const s = useContext(SessionContext)
  if (!s) throw new Error('useSession must be used inside a SessionContext provider')
  return s
}

/** Select from the current session's UI store. */
export function useSessionState<T>(selector: (s: UIState) => T): T {
  return useStore(useSession().store, selector)
}

/** Strings in the current viewer's language. */
export function useT(): (key: StringKey, vars?: Record<string, string | number>) => string {
  const lang = useSessionState((s) => s.profile.lang)
  return useCallback((key, vars) => translate(lang, key, vars), [lang])
}

/**
 * Create a session for these options and run it while the component is mounted.
 * A new session is made when the match or profile changes.
 */
export function useLiveSession(opts: SourceOptions): Session {
  const key = JSON.stringify(opts)
  const [state, setState] = useState(() => ({ key, session: new Session(opts) }))
  let session = state.session
  if (state.key !== key) {
    session = new Session(opts)
    setState({ key, session })
  }
  useEffect(() => {
    session.start()
    return () => session.stop()
  }, [session])
  return session
}
