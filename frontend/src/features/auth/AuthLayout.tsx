import { Outlet } from 'react-router-dom'
import { AuthProvider } from './AuthProvider'

/**
 * Wraps every route that needs a session.
 *
 * Mounting the provider here rather than above the router means the public
 * status page never bootstraps a session, never calls `/auth/refresh`, and
 * never touches an auth-protected code path.
 */
export function AuthLayout() {
  return (
    <AuthProvider>
      <Outlet />
    </AuthProvider>
  )
}
