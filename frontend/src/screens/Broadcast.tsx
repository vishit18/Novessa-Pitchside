import { useMemo } from 'react'
import { CLUBS } from '@/data/league'
import { navigate, withParams } from '@/router'
import { defaultProfile, LANGS, loadProfile, PERSONAS } from '@/state/profile'
import { useLiveSession } from '@/state/useSession'
import { BroadcastPane } from './BroadcastPane'

/** The 16:9 hero: one viewer, full screen. */
export function Broadcast({ query }: { query: URLSearchParams }) {
  const profile = useMemo(() => loadProfile() ?? defaultProfile({ persona: 'analyst' }), [])
  const session = useLiveSession({
    matchId: query.get('match') ?? 'derby_01',
    profile,
    startAt: Number(query.get('t') ?? 0),
    speed: Number(query.get('speed') ?? 1),
  })
  const persona = PERSONAS.find((p) => p.id === profile.persona)?.label ?? profile.persona
  const lang = LANGS.find((l) => l.id === profile.lang)?.label ?? profile.lang
  const club = profile.club ? CLUBS[profile.club]?.name : null

  return (
    <main className="h-dvh w-full">
      <h1 className="sr-only">Novessa Pitchside broadcast view</h1>
      <BroadcastPane
        session={session}
        corner={
          <button
            className="text-[13px] text-muted underline decoration-white/25 underline-offset-4 hover:text-text"
            onClick={() => navigate(withParams('/', { match: session.opts.matchId }))}
          >
            {[persona, lang, club].filter(Boolean).join(', ')}. Change
          </button>
        }
      />
    </main>
  )
}
