import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <main className="flex min-h-full flex-col items-center justify-center gap-3 bg-surface p-6">
      <h1 className="text-3xl font-semibold text-ink">404</h1>
      <p className="text-sm text-ink-muted">That page doesn’t exist.</p>
      <Link to="/" className="text-sm font-medium text-ink underline underline-offset-4">
        Back to dashboard
      </Link>
    </main>
  )
}
