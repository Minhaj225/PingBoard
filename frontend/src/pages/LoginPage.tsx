import { type FormEvent, useState } from 'react'
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { authApi } from '@/api/auth'
import { errorMessage } from '@/api/client'
import { Alert, Button, Card, Field, Input } from '@/components/ui'
import { useAuth } from '@/features/auth/useAuth'

const OAUTH_ERRORS: Record<string, string> = {
  invalid_state: 'That sign-in link expired. Please try again.',
  exchange_failed: 'GitHub sign-in failed. Please try again.',
  access_denied: 'GitHub sign-in was cancelled.',
}

export function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [params] = useSearchParams()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const oauthError = params.get('oauth_error')
  const from = (location.state as { from?: Location } | null)?.from?.pathname ?? '/'

  if (user) return <Navigate to={from} replace />

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await login(email, password)
      void navigate(from, { replace: true })
    } catch (err) {
      setError(errorMessage(err, 'Could not sign in'))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="flex min-h-full items-center justify-center bg-surface p-6">
      <Card className="w-full max-w-sm">
        <h1 className="text-xl font-semibold tracking-tight text-ink">Sign in</h1>
        <p className="mt-1 text-sm text-ink-muted">Welcome back to PingBoard.</p>

        <form onSubmit={(e) => void handleSubmit(e)} className="mt-6 space-y-4">
          {oauthError && <Alert>{OAUTH_ERRORS[oauthError] ?? 'GitHub sign-in failed.'}</Alert>}
          {error && <Alert>{error}</Alert>}

          <Field label="Email">
            <Input
              type="email"
              name="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </Field>
          <Field label="Password">
            <Input
              type="password"
              name="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </Field>

          <Button type="submit" disabled={isSubmitting} className="w-full">
            {isSubmitting ? 'Signing in…' : 'Sign in'}
          </Button>
        </form>

        <div className="my-5 flex items-center gap-3 text-xs text-ink-subtle">
          <span className="h-px flex-1 bg-surface-sunken" />
          or
          <span className="h-px flex-1 bg-surface-sunken" />
        </div>

        {/* A full navigation, not fetch: the OAuth flow ends in a redirect. */}
        <a
          href={authApi.githubLoginUrl()}
          className="flex w-full items-center justify-center rounded-lg border border-line-strong px-4 py-2 text-sm font-medium text-ink transition hover:bg-surface"
        >
          Continue with GitHub
        </a>

        <p className="mt-6 text-center text-sm text-ink-muted">
          No account?{' '}
          <Link to="/register" className="font-medium text-ink underline underline-offset-4">
            Create one
          </Link>
        </p>
      </Card>
    </main>
  )
}
