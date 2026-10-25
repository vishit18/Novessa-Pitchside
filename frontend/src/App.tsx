import { lazy, Suspense, useEffect } from 'react'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { ThemeToggle } from '@/components/ThemeToggle'
import { useLocation } from '@/router'
import { loadProfile } from '@/state/profile'

// Each screen is its own chunk, so the phone view and the recap never download the pitch
// renderer, and the Control Room never downloads the player card.
const Broadcast = lazy(() => import('@/screens/Broadcast').then((m) => ({ default: m.Broadcast })))
const Companion = lazy(() => import('@/screens/Companion').then((m) => ({ default: m.Companion })))
const ControlRoom = lazy(() =>
  import('@/screens/ControlRoom').then((m) => ({ default: m.ControlRoom })),
)
const Onboarding = lazy(() =>
  import('@/screens/Onboarding').then((m) => ({ default: m.Onboarding })),
)
const Recap = lazy(() => import('@/screens/Recap').then((m) => ({ default: m.Recap })))
const RealFootage = lazy(() =>
  import('@/screens/RealFootage').then((m) => ({ default: m.RealFootage })),
)
const Home = lazy(() => import('@/screens/Home').then((m) => ({ default: m.Home })))
const Split = lazy(() => import('@/screens/Split').then((m) => ({ default: m.Split })))
const Why = lazy(() => import('@/screens/Why').then((m) => ({ default: m.Why })))
const DesignLab = lazy(() => import('@/screens/DesignLab').then((m) => ({ default: m.DesignLab })))

const NAME = 'Novessa Pitchside'

/** Tab title for a route, so several open tabs can be told apart. */
export function titleFor(path: string): string {
  const screen = [
    ['/why', 'Why it matters'],
    ['/design-lab', 'Design lab'],
    ['/real', 'Real footage'],
    ['/recap', 'Recap'],
    ['/companion', 'Companion'],
    ['/control', 'Control room'],
    ['/split', 'Same match, your story'],
    ['/watch', 'Broadcast'],
    ['/start', 'How do you watch?'],
  ].find(([prefix]) => path.startsWith(prefix as string))
  return screen ? `${screen[1]} · ${NAME}` : NAME
}

/** What shows for the instant a screen's code is loading. */
function Loading() {
  return (
    <div className="grid min-h-dvh place-items-center" role="status">
      <p className="pulse-soft font-display text-[28px] font-semibold">
        Novessa <span className="text-muted">Pitchside</span>
      </p>
    </div>
  )
}

/**
 * Routes: / what this is and where to go, /start onboarding and match picker, /watch the broadcast view, /split two viewers side by
 * side, /companion the phone view, /recap half and full-time recaps, /control the producer's
 * view. A returning viewer with a saved profile and a match in the URL goes straight to /watch.
 */
export default function App() {
  const { path, query } = useLocation()
  useEffect(() => {
    document.title = titleFor(path)
  }, [path])

  const screen = (() => {
    if (path.startsWith('/why')) return <Why />
    if (path.startsWith('/design-lab')) return <DesignLab query={query} />
    if (path.startsWith('/real')) return <RealFootage />
    if (path.startsWith('/recap')) return <Recap key={query.toString()} query={query} />
    if (path.startsWith('/companion')) return <Companion key={query.toString()} query={query} />
    if (path.startsWith('/control')) return <ControlRoom key={query.toString()} query={query} />
    if (path.startsWith('/split')) return <Split key={query.toString()} query={query} />
    if (path.startsWith('/watch')) return <Broadcast key={query.toString()} query={query} />
    if (path.startsWith('/start')) return <Onboarding query={query} />
    if (path === '/' && query.get('match') && query.get('t') && loadProfile())
      return <Broadcast query={query} />
    return <Home />
  })()
  return (
    <>
      <ErrorBoundary key={path}>
        <Suspense fallback={<Loading />}>{screen}</Suspense>
      </ErrorBoundary>
      <ThemeToggle />
    </>
  )
}
