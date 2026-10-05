import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Alert, Button, Card, Spinner } from '@/components/ui'
import { useAuth } from '@/features/auth/useAuth'

/**
 * Landing page for the GitHub redirect.
 *
 * The API has already set the httpOnly refresh cookie, so all that is left is
 * to exchange it for an access token. No token ever travels in the URL.
 */
export function OAuthCallbackPage() {
  const { restore } = useAuth()
  const navigate = useNavigate()
  const [failed, setFailed] = useState(false)
  const attempted = useRef(false)

  useEffect(() => {
    if (attempted.current) return
    attempted.current = true

    void restore().then((ok) => {
      if (ok) void navigate('/', { replace: true })
      else setFailed(true)
    })
  }, [restore, navigate])

  return (
    <main className="flex min-h-full items-center justify-center bg-surface p-6">
      <Card className="w-full max-w-sm text-center">
        {failed ? (
          <div className="space-y-4">
            <Alert>We could not complete the sign-in.</Alert>
            <Link to="/login">
              <Button variant="secondary">Back to sign in</Button>
            </Link>
          </div>
        ) : (
          <div className="flex justify-center">
            <Spinner label="Finishing sign-in…" />
          </div>
        )}
      </Card>
    </main>
  )
}
