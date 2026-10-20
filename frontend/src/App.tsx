import { useLocation } from '@/router'
import { Broadcast } from '@/screens/Broadcast'
import { ControlRoom } from '@/screens/ControlRoom'
import { Onboarding } from '@/screens/Onboarding'
import { Split } from '@/screens/Split'
import { loadProfile } from '@/state/profile'

/**
 * Routes: / onboarding and match picker, /watch the broadcast view, /split two viewers side by
 * side. A returning viewer with a saved profile and a match in the URL goes straight to /watch.
 */
export default function App() {
  const { path, query } = useLocation()
  if (path.startsWith('/control')) return <ControlRoom key={query.toString()} query={query} />
  if (path.startsWith('/split')) return <Split key={query.toString()} query={query} />
  if (path.startsWith('/watch')) return <Broadcast key={query.toString()} query={query} />
  if (path === '/' && query.get('match') && query.get('t') && loadProfile())
    return <Broadcast query={query} />
  return <Onboarding query={query} />
}
