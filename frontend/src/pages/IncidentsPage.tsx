import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { errorMessage } from '@/api/client'
import { type IncidentFilter, incidentsQuery } from '@/api/incidents'
import { orgsQuery } from '@/api/orgs'
import { absoluteTime, relativeTime } from '@/components/format'
import { SkeletonRows } from '@/components/Skeleton'
import { Alert, Card } from '@/components/ui'

const TABS: { value: IncidentFilter; label: string }[] = [
  { value: 'open', label: 'Open' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'all', label: 'All' },
]

export function IncidentsPage() {
  const { orgId = '' } = useParams()
  const [filter, setFilter] = useState<IncidentFilter>('open')

  const { data: orgs } = useQuery(orgsQuery)
  const org = orgs?.find((candidate) => candidate.id === orgId)
  const incidents = useQuery(incidentsQuery(orgId, filter))

  return (
    <main className="mx-auto max-w-4xl space-y-4 p-6">
      <Link to={`/orgs/${orgId}/monitors`} className="text-sm text-ink-muted hover:text-ink">
        ← Monitors
      </Link>

      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink">Incidents</h1>
        {org && <p className="mt-1 font-mono text-xs text-ink-subtle">/{org.slug}</p>}
      </div>

      <div
        role="tablist"
        aria-label="Incident status"
        className="inline-flex rounded-lg border border-line bg-surface-raised p-1"
      >
        {TABS.map((tab) => (
          <button
            key={tab.value}
            type="button"
            role="tab"
            aria-selected={filter === tab.value}
            onClick={() => setFilter(tab.value)}
            className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
              filter === tab.value
                ? 'bg-ink text-surface'
                : 'text-ink-muted hover:bg-surface'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {incidents.isPending && (
        <Card className="p-0">
          <SkeletonRows rows={3} />
        </Card>
      )}
      {incidents.isError && <Alert>{errorMessage(incidents.error, 'Could not load incidents')}</Alert>}

      {incidents.data?.length === 0 && (
        <Card className="text-center">
          <p className="text-sm text-ink-muted">
            {filter === 'open' ? 'No open incidents.' : 'Nothing here.'}
          </p>
          {filter === 'open' && (
            <p className="mt-1 text-sm text-ink-subtle">
              Incidents open automatically when a monitor fails repeatedly.
            </p>
          )}
        </Card>
      )}

      {incidents.data && incidents.data.length > 0 && (
        <Card className="p-0">
          <ul className="divide-y divide-line">
            {incidents.data.map((incident) => {
              const open = incident.resolved_at === null
              return (
                <li key={incident.id}>
                  <Link
                    to={`/orgs/${orgId}/incidents/${incident.id}`}
                    className="flex items-start gap-4 px-5 py-4 transition hover:bg-surface"
                  >
                    {/* Word + colour, so state never rests on colour alone. */}
                    <span
                      className={`mt-0.5 shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${
                        open
                          ? 'bg-down-soft text-down ring-down/30'
                          : 'bg-up-soft text-up ring-up/30'
                      }`}
                    >
                      {open ? 'Open' : 'Resolved'}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-ink">
                        {incident.monitor_name ?? 'Monitor'}
                      </p>
                      {incident.cause && (
                        <p className="truncate text-xs text-ink-muted">{incident.cause}</p>
                      )}
                    </div>
                    <div className="hidden shrink-0 text-right sm:block">
                      <p className="text-xs text-ink-muted" title={absoluteTime(incident.started_at)}>
                        started {relativeTime(incident.started_at)}
                      </p>
                      {incident.resolved_at && (
                        <p className="text-xs text-ink-subtle">
                          resolved {relativeTime(incident.resolved_at)}
                        </p>
                      )}
                    </div>
                  </Link>
                </li>
              )
            })}
          </ul>
        </Card>
      )}
    </main>
  )
}
