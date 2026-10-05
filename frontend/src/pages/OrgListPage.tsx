import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { orgsQuery } from '@/api/orgs'
import { errorMessage } from '@/api/client'
import { Alert, Button, Card, RoleBadge, Spinner } from '@/components/ui'
import { useAuth } from '@/features/auth/useAuth'

export function OrgListPage() {
  const { user } = useAuth()
  const { data: orgs, isPending, isError, error } = useQuery(orgsQuery)

  return (
    <main className="mx-auto max-w-5xl p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink">Organizations</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Signed in as {user?.name ?? user?.email}.
          </p>
        </div>
        <Link to="/orgs/new">
          <Button>New organization</Button>
        </Link>
      </div>

      <div className="mt-6">
        {isPending && <Spinner label="Loading organizations…" />}
        {isError && <Alert>{errorMessage(error, 'Could not load organizations')}</Alert>}

        {orgs && orgs.length === 0 && (
          <Card className="text-center">
            <p className="text-sm text-ink-muted">You are not in any organization yet.</p>
            <p className="mt-1 text-sm text-ink-subtle">
              Create one to start adding monitors, or accept an invitation.
            </p>
            <Link to="/orgs/new" className="mt-4 inline-block">
              <Button>Create your first organization</Button>
            </Link>
          </Card>
        )}

        {orgs && orgs.length > 0 && (
          <ul className="grid gap-3 sm:grid-cols-2">
            {orgs.map((org) => (
              <li key={org.id}>
                <Link
                  to={`/orgs/${org.id}`}
                  className="block rounded-xl border border-line bg-surface-raised p-4 shadow-sm transition hover:border-line-strong hover:shadow"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate font-medium text-ink">{org.name}</p>
                      <p className="mt-0.5 truncate font-mono text-xs text-ink-subtle">
                        /{org.slug}
                      </p>
                    </div>
                    <RoleBadge role={org.role} />
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </main>
  )
}
