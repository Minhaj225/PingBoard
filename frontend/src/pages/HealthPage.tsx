import { useQuery } from '@tanstack/react-query'
import { healthQuery } from '@/api/health'

/**
 * Phase 0 smoke page: proves the browser can reach the API through the
 * configured VITE_API_URL and that CORS is set up correctly.
 */
export function HealthPage() {
  const { data, isPending, isError, error, refetch, isFetching } = useQuery(healthQuery)

  return (
    <main className="flex min-h-full items-center justify-center bg-surface p-6">
      <section className="w-full max-w-md rounded-xl border border-line bg-surface-raised p-8 shadow-sm">
        <h1 className="text-2xl font-semibold tracking-tight text-ink">PingBoard</h1>
        <p className="mt-1 text-sm text-ink-muted">Phase 0 — end-to-end wiring check</p>

        <div className="mt-6 flex items-center gap-3 rounded-lg bg-surface px-4 py-3">
          <span
            className={`size-2.5 shrink-0 rounded-full ${
              isPending ? 'bg-unknown' : isError ? 'bg-down' : 'bg-up'
            }`}
            aria-hidden
          />
          <span className="font-mono text-sm text-ink">
            {isPending && 'Contacting API…'}
            {isError && `Unreachable: ${error instanceof Error ? error.message : 'unknown error'}`}
            {data && JSON.stringify(data)}
          </span>
        </div>

        <button
          type="button"
          onClick={() => void refetch()}
          disabled={isFetching}
          className="mt-4 rounded-lg bg-ink px-4 py-2 text-sm font-medium text-surface transition hover:bg-slate-700 disabled:opacity-50"
        >
          {isFetching ? 'Checking…' : 'Check again'}
        </button>

        <p className="mt-6 text-xs text-ink-subtle">
          API: <code>{import.meta.env.VITE_API_URL ?? 'http://localhost:8000'}</code>
        </p>
      </section>
    </main>
  )
}
