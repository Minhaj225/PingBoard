import { type FormEvent, useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { errorMessage } from '@/api/client'
import { Alert, Button, Card, Field, Input } from '@/components/ui'
import { useAuth } from '@/features/auth/useAuth'

// Mirrors PASSWORD_MIN_LENGTH in the backend schema.
const PASSWORD_MIN_LENGTH = 12

export function RegisterPage() {
  const { user, register } = useAuth()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  if (user) return <Navigate to="/" replace />

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await register(email, password, name.trim() || undefined)
      void navigate('/', { replace: true })
    } catch (err) {
      setError(errorMessage(err, 'Could not create your account'))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="flex min-h-full items-center justify-center bg-surface p-6">
      <Card className="w-full max-w-sm">
        <h1 className="text-xl font-semibold tracking-tight text-ink">Create an account</h1>
        <p className="mt-1 text-sm text-ink-muted">Start monitoring in a couple of minutes.</p>

        <form onSubmit={(e) => void handleSubmit(e)} className="mt-6 space-y-4">
          {error && <Alert>{error}</Alert>}

          <Field label="Name" hint="Optional.">
            <Input
              name="name"
              autoComplete="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </Field>
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
          <Field label="Password" hint={`At least ${PASSWORD_MIN_LENGTH} characters.`}>
            <Input
              type="password"
              name="password"
              autoComplete="new-password"
              required
              minLength={PASSWORD_MIN_LENGTH}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </Field>

          <Button type="submit" disabled={isSubmitting} className="w-full">
            {isSubmitting ? 'Creating account…' : 'Create account'}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-ink-muted">
          Already registered?{' '}
          <Link to="/login" className="font-medium text-ink underline underline-offset-4">
            Sign in
          </Link>
        </p>
      </Card>
    </main>
  )
}
