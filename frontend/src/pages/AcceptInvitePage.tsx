import { useEffect, useRef } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, Navigate, useLocation, useNavigate, useParams } from 'react-router-dom'
import { errorMessage } from '@/api/client'
import { orgKeys, orgsApi } from '@/api/orgs'
import { Alert, Button, Card, Spinner } from '@/components/ui'
import { useAuth } from '@/features/auth/useAuth'

export function AcceptInvitePage() {
  const { token = '' } = useParams()
  const { user, isBootstrapping } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()

  const accept = useMutation({
    mutationFn: () => orgsApi.acceptInvite(token),
    onSuccess: async (org) => {
      await queryClient.invalidateQueries({ queryKey: orgKeys.all })
      void navigate(`/orgs/${org.id}`, { replace: true })
    },
  })

  // Redeem once, as soon as we know who the user is. React 18 StrictMode mounts
  // effects twice in dev, and the invite is single-use, so guard the call.
  const attempted = useRef(false)
  const { mutate } = accept
  useEffect(() => {
    if (user && !attempted.current) {
      attempted.current = true
      mutate()
    }
  }, [user, mutate])

  if (isBootstrapping) {
    return (
      <main className="flex min-h-full items-center justify-center p-6">
        <Spinner label="Checking your session…" />
      </main>
    )
  }

  // An invite is bound to an email address, so the recipient has to sign in
  // (or register) first. Come back here afterwards.
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />

  return (
    <main className="flex min-h-full items-center justify-center bg-surface p-6">
      <Card className="w-full max-w-sm text-center">
        <h1 className="text-xl font-semibold tracking-tight text-ink">Invitation</h1>

        <div className="mt-4">
          {accept.isPending && <Spinner label="Accepting…" />}
          {accept.isError && (
            <div className="space-y-4">
              <Alert>{errorMessage(accept.error, 'This invitation could not be accepted')}</Alert>
              <p className="text-sm text-ink-muted">
                Invitations are tied to the address they were sent to. You are signed in as{' '}
                <span className="font-medium text-ink">{user.email}</span>.
              </p>
              <Link to="/">
                <Button variant="secondary">Back to organizations</Button>
              </Link>
            </div>
          )}
        </div>
      </Card>
    </main>
  )
}
