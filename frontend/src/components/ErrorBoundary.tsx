import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
}

/**
 * Catches render-time crashes so one broken component does not blank the app.
 *
 * Must be a class: React has no hook equivalent for `componentDidCatch`.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // In a real deployment this is where an error reporter would be called.
    console.error('Unhandled render error', error, info.componentStack)
  }

  render(): ReactNode {
    const { error } = this.state
    if (!error) return this.props.children

    return (
      <main className="flex min-h-full items-center justify-center bg-surface p-6">
        <div className="w-full max-w-md rounded-xl border border-line bg-surface-raised p-8 text-center shadow-sm">
          <h1 className="text-lg font-semibold text-ink">Something went wrong</h1>
          <p className="mt-2 text-sm text-ink-muted">
            This part of the page failed to render. Reloading usually clears it.
          </p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="mt-5 rounded-lg bg-ink px-4 py-2 text-sm font-medium text-surface transition hover:opacity-90"
          >
            Reload the page
          </button>
          {import.meta.env.DEV && (
            <pre className="mt-5 max-h-40 overflow-auto rounded-lg bg-surface-sunken p-3 text-left font-mono text-[11px] text-ink-muted">
              {error.message}
            </pre>
          )}
        </div>
      </main>
    )
  }
}
