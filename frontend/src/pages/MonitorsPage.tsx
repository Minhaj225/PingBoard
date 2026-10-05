import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { errorMessage } from '@/api/client'
import { monitorsQuery } from '@/api/monitors'
import { orgsQuery } from '@/api/orgs'
import { roleCovers } from '@/api/types'
import { formatInterval, relativeTime } from '@/components/format'
import { StatusPill } from '@/components/StatusPill'
import { EmptyState } from '@/components/EmptyState'
import { SkeletonRows } from '@/components/Skeleton'
import { Alert, Button, Card } from '@/components/ui'

export function MonitorsPage() {
  const { orgId = '' } = useParams()
  const { data: orgs } = useQuery(orgsQuery)
  const org = orgs?.find((candidate) => candidate.id === orgId)
  const monitors = useQuery(monitorsQuery(orgId))

  const canEdit = org ? roleCovers(org.role, 'admin') : false

  return (
    <main className="mx-auto max-w-5xl space-y-4 p-6">
      <Link to="/" className="text-sm text-ink-muted hover:text-ink">
        ← Organizations
      </Link>

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink">Monitors</h1>
          {org && <p className="mt-1 font-mono text-xs text-ink-subtle">/{org.slug}</p>}
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to={`/orgs/${orgId}/incidents`}>
            <Button variant="secondary">Incidents</Button>
          </Link>
          <Link to={`/orgs/${orgId}/channels`}>
            <Button variant="secondary">Channels</Button>
          </Link>
          <Link to={`/orgs/${orgId}/status-pages`}>
            <Button variant="secondary">Status pages</Button>
          </Link>
          <Link to={`/orgs/${orgId}/api-keys`}>
            <Button variant="secondary">API keys</Button>
          </Link>
          <Link to={`/orgs/${orgId}/members`}>
            <Button variant="secondary">Members</Button>
          </Link>
          {canEdit && (
            <Link to={`/orgs/${orgId}/monitors/new`}>
              <Button>New monitor</Button>
            </Link>
          )}
        </div>
      </div>

      {monitors.isPending && (
        <Card className="p-0">
          <SkeletonRows rows={4} />
        </Card>
      )}
      {monitors.isError && <Alert>{errorMessage(monitors.error, 'Could not load monitors')}</Alert>}

      {monitors.data?.length === 0 && (
        <EmptyState
          icon="◎"
          title="No monitors yet"
          description="Add a URL and PingBoard will check it on a schedule, open incidents when it fails, and publish its uptime."
          action={
            canEdit ? (
              <Link to={`/orgs/${orgId}/monitors/new`}>
                <Button>Create your first monitor</Button>
              </Link>
            ) : undefined
          }
        />
      )}

      {monitors.data && monitors.data.length > 0 && (
        <Card className="p-0">
          <ul className="divide-y divide-line">
            {monitors.data.map((monitor) => (
              <li key={monitor.id}>
                <Link
                  to={`/orgs/${orgId}/monitors/${monitor.id}`}
                  className="flex items-center gap-4 px-5 py-4 transition hover:bg-surface"
                >
                  <StatusPill status={monitor.status} paused={!monitor.is_active} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-ink">{monitor.name}</p>
                    <p className="truncate font-mono text-xs text-ink-subtle">{monitor.url}</p>
                  </div>
                  <div className="hidden shrink-0 text-right sm:block">
                    <p className="text-xs text-ink-muted">
                      every {formatInterval(monitor.interval_s)}
                    </p>
                    <p className="text-xs text-ink-subtle">
                      {monitor.last_checked_at
                        ? `checked ${relativeTime(monitor.last_checked_at)}`
                        : 'never checked'}
                    </p>
                  </div>
                  <span className="shrink-0 rounded bg-surface-sunken px-2 py-0.5 font-mono text-xs text-ink-muted">
                    {monitor.method}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </main>
  )
}
