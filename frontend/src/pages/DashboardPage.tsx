import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { errorMessage } from '@/api/client'
import { incidentsQuery } from '@/api/incidents'
import { monitorsQuery } from '@/api/monitors'
import { orgsQuery } from '@/api/orgs'
import { roleCovers } from '@/api/types'
import { EmptyState } from '@/components/EmptyState'
import { relativeTime } from '@/components/format'
import { SkeletonRows, SkeletonStats } from '@/components/Skeleton'
import { StatusPill } from '@/components/StatusPill'
import { Alert, Button, Card, PageHeader, Stat } from '@/components/ui'

/**
 * The org's home: what is broken right now, and what to do about it.
 *
 * Ordered so the answer to "is anything wrong?" is the first thing on screen,
 * before any list the reader has to scan.
 */
export function DashboardPage() {
  const { orgId = '' } = useParams()
  const { data: orgs } = useQuery(orgsQuery)
  const org = orgs?.find((candidate) => candidate.id === orgId)
  const canEdit = org ? roleCovers(org.role, 'admin') : false

  const monitors = useQuery(monitorsQuery(orgId))
  const openIncidents = useQuery(incidentsQuery(orgId, 'open'))

  const list = monitors.data ?? []
  const active = list.filter((monitor) => monitor.is_active)
  const down = active.filter((monitor) => monitor.status === 'down')
  const up = active.filter((monitor) => monitor.status === 'up')
  const pending = active.filter((monitor) => monitor.status === 'unknown')
  const incidents = openIncidents.data ?? []

  return (
    <main className="mx-auto max-w-5xl space-y-6 p-6">
      <PageHeader
        title={org?.name ?? 'Dashboard'}
        subtitle={org && <span className="font-mono text-xs text-ink-subtle">/{org.slug}</span>}
        actions={
          canEdit ? (
            <Link to={`/orgs/${orgId}/monitors/new`}>
              <Button>New monitor</Button>
            </Link>
          ) : undefined
        }
      />

      {/* The headline: one sentence, answering the only urgent question. */}
      {monitors.isSuccess && (
        <div
          className={`flex items-center gap-3 rounded-xl border px-5 py-4 ${
            down.length > 0
              ? 'border-down/30 bg-down-soft'
              : active.length === 0
                ? 'border-line bg-surface-sunken'
                : 'border-up/30 bg-up-soft'
          }`}
        >
          <span
            className={`size-2.5 shrink-0 rounded-full ${
              down.length > 0 ? 'bg-down' : active.length === 0 ? 'bg-unknown' : 'bg-up'
            }`}
            aria-hidden
          />
          <p className="font-medium text-ink">
            {down.length > 0
              ? `${down.length} ${down.length === 1 ? 'monitor is' : 'monitors are'} down`
              : active.length === 0
                ? 'Nothing is being monitored yet'
                : 'All monitors are healthy'}
          </p>
        </div>
      )}

      {monitors.isPending ? (
        <SkeletonStats />
      ) : (
        <div className="grid gap-3 sm:grid-cols-4">
          <Stat label="Up" value={String(up.length)} />
          <Stat label="Down" value={String(down.length)} />
          <Stat label="Awaiting first check" value={String(pending.length)} />
          <Stat label="Open incidents" value={String(incidents.length)} />
        </div>
      )}

      {monitors.isError && <Alert>{errorMessage(monitors.error, 'Could not load monitors')}</Alert>}

      {incidents.length > 0 && (
        <section>
          <div className="mb-2 flex items-baseline justify-between">
            <h2 className="text-sm font-semibold text-ink">Open incidents</h2>
            <Link
              to={`/orgs/${orgId}/incidents`}
              className="text-sm text-ink-muted underline-offset-2 hover:text-ink hover:underline"
            >
              View all
            </Link>
          </div>
          <Card className="p-0">
            <ul className="divide-y divide-line">
              {incidents.slice(0, 5).map((incident) => (
                <li key={incident.id}>
                  <Link
                    to={`/orgs/${orgId}/incidents/${incident.id}`}
                    className="flex items-center gap-3 px-5 py-3 transition hover:bg-surface-sunken"
                  >
                    <span className="shrink-0 rounded-full bg-down-soft px-2 py-0.5 text-xs font-medium text-down ring-1 ring-inset ring-down/20">
                      Open
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-ink">
                        {incident.monitor_name ?? 'Monitor'}
                      </p>
                      {incident.cause && (
                        <p className="truncate text-xs text-ink-subtle">{incident.cause}</p>
                      )}
                    </div>
                    <span className="shrink-0 text-xs text-ink-subtle">
                      {relativeTime(incident.started_at)}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </Card>
        </section>
      )}

      <section>
        <div className="mb-2 flex items-baseline justify-between">
          <h2 className="text-sm font-semibold text-ink">Monitors</h2>
          <Link
            to={`/orgs/${orgId}/monitors`}
            className="text-sm text-ink-muted underline-offset-2 hover:text-ink hover:underline"
          >
            View all
          </Link>
        </div>

        {monitors.isPending ? (
          <Card className="p-0">
            <SkeletonRows rows={3} />
          </Card>
        ) : list.length === 0 ? (
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
        ) : (
          <Card className="p-0">
            <ul className="divide-y divide-line">
              {/* Down first: the rows that need attention lead. */}
              {[...list]
                .sort((a, b) => Number(b.status === 'down') - Number(a.status === 'down'))
                .slice(0, 6)
                .map((monitor) => (
                  <li key={monitor.id}>
                    <Link
                      to={`/orgs/${orgId}/monitors/${monitor.id}`}
                      className="flex items-center gap-4 px-5 py-3 transition hover:bg-surface-sunken"
                    >
                      <StatusPill status={monitor.status} paused={!monitor.is_active} />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-ink">{monitor.name}</p>
                        <p className="truncate font-mono text-xs text-ink-subtle">{monitor.url}</p>
                      </div>
                      <span className="hidden shrink-0 text-xs text-ink-subtle sm:inline">
                        {monitor.last_checked_at
                          ? relativeTime(monitor.last_checked_at)
                          : 'never checked'}
                      </span>
                    </Link>
                  </li>
                ))}
            </ul>
          </Card>
        )}
      </section>
    </main>
  )
}
