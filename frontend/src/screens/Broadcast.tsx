import { useMemo } from 'react'
import { PlayerCard } from '@/components/PlayerCard'
import { CLUBS, PLAYERS } from '@/data/league'
import { navigate, withParams } from '@/router'
import { defaultProfile, LANGS, loadProfile, PERSONAS } from '@/state/profile'
import { SessionContext, useLiveSession } from '@/state/useSession'
import { BroadcastPane } from './BroadcastPane'

/**
 * The 16:9 hero: one viewer, full screen. When the viewer follows a player (from onboarding,
 * or ?player=ASH-08 in the URL) it becomes player focus mode: the camera follows them and
 * their live card sits beside the pitch.
 */
export function Broadcast({ query }: { query: URLSearchParams }) {
  const playerParam = query.get('player')
  const profile = useMemo(() => {
    const p = loadProfile() ?? defaultProfile({ persona: 'analyst' })
    return playerParam ? { ...p, player: playerParam } : p
  }, [playerParam])
  const session = useLiveSession({
    matchId: query.get('match') ?? 'derby_01',
    profile,
    startAt: Number(query.get('t') ?? 0),
    speed: Number(query.get('speed') ?? 1),
  })
  const persona = PERSONAS.find((p) => p.id === profile.persona)?.label ?? profile.persona
  const lang = LANGS.find((l) => l.id === profile.lang)?.label ?? profile.lang
  const who = profile.player
    ? PLAYERS[profile.player]?.name
    : profile.club
      ? CLUBS[profile.club]?.name
      : null

  const change = (
    <button
      className="-my-2 inline-flex min-h-11 items-center px-1 text-[14px] text-muted underline decoration-white/25 underline-offset-4 hover:text-text"
      onClick={() => navigate(withParams('/', { match: session.opts.matchId }))}
    >
      {[persona, lang, who].filter(Boolean).join(', ')}. Change
    </button>
  )
  const phone = (
    <button
      className="-my-2 inline-flex min-h-11 items-center px-1 text-[14px] text-muted underline decoration-white/25 underline-offset-4 hover:text-text"
      onClick={() => navigate(withParams('/companion', { match: session.opts.matchId }))}
    >
      Phone view
    </button>
  )
  const corner = (
    <div className="flex flex-col items-end">
      {change}
      {phone}
    </div>
  )

  if (!profile.player) {
    return (
      <main className="h-dvh w-full">
        <h1 className="sr-only">Novessa Pitchside broadcast view</h1>
        <BroadcastPane session={session} corner={corner} />
      </main>
    )
  }

  return (
    <main className="grid min-h-dvh w-full gap-4 bg-ink p-0 lg:h-dvh lg:grid-cols-[minmax(0,1fr)_400px] lg:p-4">
      <h1 className="sr-only">Novessa Pitchside player focus</h1>
      <div className="h-[62dvh] min-h-0 overflow-hidden lg:h-auto">
        <BroadcastPane session={session} corner={corner} />
      </div>
      <aside className="min-h-0 px-4 pb-4 lg:p-0">
        <SessionContext.Provider value={session}>
          <PlayerCard />
        </SessionContext.Provider>
      </aside>
    </main>
  )
}
