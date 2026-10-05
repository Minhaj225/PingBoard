import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '@/features/auth/useAuth'
import { Spinner } from './ui'

/**
 * Gate for authenticated routes.
 *
 * While the initial silent refresh is in flight we render a placeholder rather
 * than redirecting: bouncing to /login first would throw the user out on every
 * page reload, since the access token only lives in memory.
 */
export function ProtectedRoute() {
  const { user, isBootstrapping } = useAuth()
  const location = useLocation()

  if (isBootstrapping) {
    return (
      <div className="flex min-h-full items-center justify-center">
        <Spinner label="Restoring your session…" />
      </div>
    )
  }

  if (!user) {
    // Remember where they were headed so login can send them back.
    return <Navigate to="/login" replace state={{ from: location }} />
  }

  return <Outlet />
}
