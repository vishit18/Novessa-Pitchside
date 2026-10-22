import { Component, type ErrorInfo, type ReactNode } from 'react'

interface State {
  error: Error | null
}

/**
 * One screen failing must not blank the whole app. Shows what happened and two ways out:
 * try the screen again, or go home.
 */
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('screen failed', error, info.componentStack)
  }

  render(): ReactNode {
    const { error } = this.state
    if (!error) return this.props.children
    return (
      <main className="grid min-h-dvh place-items-center p-6">
        <div role="alert" className="max-w-md">
          <h1 className="font-display text-[36px] font-bold leading-none">
            This screen stopped working
          </h1>
          <p className="mt-3 text-[15px] text-muted">{error.message}</p>
          <div className="mt-5 flex gap-3">
            <button
              className="btn-primary h-11 bg-amber px-5 text-[15px] font-semibold text-ink"
              onClick={() => window.location.reload()}
            >
              Try again
            </button>
            <a className="flex h-11 items-center border border-text px-5 text-[15px]" href="/">
              Go to the home page
            </a>
          </div>
        </div>
      </main>
    )
  }
}
