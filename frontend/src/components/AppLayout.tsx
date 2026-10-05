import { Link, NavLink, Outlet, useParams } from 'react-router-dom'
import { useAuth } from '@/features/auth/useAuth'
import { useTheme } from '@/features/theme/useTheme'
import { Button } from './ui'

/** Org-scoped sections. Hidden when no org is in scope. */
const SECTIONS = [
  { to: 'monitors', label: 'Monitors' },
  { to: 'incidents', label: 'Incidents' },
  { to: 'status-pages', label: 'Status pages' },
  { to: 'channels', label: 'Channels' },
  { to: 'members', label: 'Members' },
  { to: 'api-keys', label: 'API keys' },
] as const

export function AppLayout() {
  const { user, logout } = useAuth()
  const { orgId } = useParams()
  const { theme, toggle } = useTheme()

  return (
    <div className="min-h-full bg-surface">
      <header className="sticky top-0 z-10 border-b border-line bg-surface-raised/80 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-6 py-3">
          <Link to="/" className="shrink-0 text-sm font-semibold tracking-tight text-ink">
            PingBoard
          </Link>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={toggle}
              aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
              className="rounded-lg px-2 py-1.5 text-sm text-ink-muted transition hover:bg-surface-sunken hover:text-ink"
            >
              {theme === 'dark' ? '☀' : '☾'}
            </button>
            <span className="hidden max-w-48 truncate text-sm text-ink-subtle sm:inline">
              {user?.email}
            </span>
            <Button variant="secondary" onClick={() => void logout()}>
              Sign out
            </Button>
          </div>
        </div>

        {/* Section nav only once an organization is in scope — before that
            there is nothing for these links to point at. */}
        {orgId && (
          <nav
            aria-label="Organization sections"
            className="mx-auto flex max-w-5xl gap-1 overflow-x-auto px-4 pb-1 text-sm"
          >
            {SECTIONS.map((section) => (
              <NavLink
                key={section.to}
                to={`/orgs/${orgId}/${section.to}`}
                className={({ isActive }) =>
                  `shrink-0 rounded-lg px-3 py-1.5 transition ${
                    isActive
                      ? 'bg-surface-sunken font-medium text-ink'
                      : 'text-ink-muted hover:bg-surface-sunken hover:text-ink'
                  }`
                }
              >
                {section.label}
              </NavLink>
            ))}
          </nav>
        )}
      </header>

      <Outlet />
    </div>
  )
}
