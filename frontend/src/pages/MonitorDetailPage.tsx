import { useState } from 'react'
import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { apiClient, errorMessage } from '@/api/client'
import { incidentsQuery } from '@/api/incidents'
import { checksQuery, monitorKeys, monitorQuery, monitorsApi } from '@/api/monitors'
import { orgsQuery } from '@/api/orgs'
import { roleCovers } from '@/api/types'
import { EmptyState } from '@/components/EmptyState'
import { absoluteTime, formatInterval, formatLatency, relativeTime } from '@/components/format'
import { LatencyChart } from '@/components/LatencyChart'
import { SkeletonRows, SkeletonStats } from '@/components/Skeleton'
import { StatusPill } from '@/components/StatusPill'
import { Alert, Button, Card, PageHeader, Spinner, Stat } from '@/components/ui'
import { useToast } from '@/features/toast/useToast'

/** How much history each range pulls. Wider range, coarser sample. */
const RANGES = [
  { value: '24h', label: '24h', checks: 200 },
  { value: '7d', label: '7d', checks: 500 },
  { value: '30d', label: '30d', checks: 1000 },
] as const

type Range = (typeof RANGES)[number]['value']

interface Uptime {
  window: string
  checks: number
  failures: number
  uptime_pct: number
  p95_ms: number
  source: string
}

const uptimeQuery = (monitorId: string, window: Range) =>
  queryOptions({
    queryKey: ['monitors', 'detail', monitorId, 'uptime', window] as const,
    queryFn: async ({ signal }): Promise<Uptime> =>
      (await apiClient.get<Uptime>(`/monitors/${monitorId}/uptime`, { params: { window }, signal }))
        .data,
    enabled: Boolean(monitorId),
  })

export function MonitorDetailPage() {
  const { orgId = '', monitorId = '' } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [range, setRange] = useState<Range>('24h')

  const monitor = useQuery(monitorQuery(monitorId))
  const checks = useQuery(checksQuery(monitorId, RANGES.find((r) => r.value === range)?.checks))
  const uptime = useQuery(uptimeQuery(monitorId, range))
  const { data: orgs } = useQuery(orgsQuery)

  const org = orgs?.find((candidate) => candidate.id === orgId)
  const canEdit = org ? roleCovers(org.role, 'admin') : false
  const incidents = useQuery({ ...incidentsQuery(orgId, 'all'), enabled: Boolean(orgId) })

  const refreshAll = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: monitorKeys.detail(monitorId) }),
      queryClient.invalidateQueries({ queryKey: monitorKeys.checks(monitorId) }),
    ])
  }

  const runNow = useMutation({
    mutationFn: () => monitorsApi.runNow(monitorId),
    onSuccess: async (result) => {
      toast(
        result.ok
          ? `Check passed in ${formatLatency(result.latency_ms)}`
          : `Check failed: ${result.error ?? 'unknown error'}`,
        result.ok ? 'success' : 'error',
      )
      await refreshAll()
    },
    onError: (error) => toast(errorMessage(error, 'The check could not be run'), 'error'),
  })

  const toggleActive = useMutation({
    mutationFn: () =>
      monitor.data?.is_active ? monitorsApi.pause(monitorId) : monitorsApi.resume(monitorId),
    onSuccess: async (updated) => {
      toast(updated.is_active ? 'Monitor resumed' : 'Monitor paused', 'success')
      await queryClient.invalidateQueries({ queryKey: monitorKeys.all })
    },
  })

  const remove = useMutation({
    mutationFn: () => monitorsApi.remove(monitorId),
    onSuccess: async () => {
      toast('Monitor deleted', 'success')
      await queryClient.invalidateQueries({ queryKey: monitorKeys.all })
      void navigate(`/orgs/${orgId}/monitors`, { replace: true })
    },
    onError: (error) => toast(errorMessage(error, 'Could not delete the monitor'), 'error'),
  })

  if (monitor.isPending) {
    return (
      <main className="mx-auto max-w-4xl space-y-4 p-6">
        <Spinner label="Loading monitor…" />
        <SkeletonStats />
      </main>
    )
  }

  if (monitor.isError || !monitor.data) {
    return (
      <main className="mx-auto max-w-3xl p-6">
        <Alert>{errorMessage(monitor.error, 'Could not load this monitor')}</Alert>
        <Link to="/" className="mt-4 inline-block text-sm text-ink-muted hover:text-ink">
          ← Organizations
        </Link>
      </main>
    )
  }

  const m = monitor.data
  const rows = checks.data?.items ?? []
  const monitorIncidents = (incidents.data ?? []).filter((i) => i.monitor_id === m.id)

  return (
    <main className="mx-auto max-w-4xl space-y-6 p-6">
      <PageHeader
        title={
          <span className="flex items-center gap-2">
            <span className="truncate">{m.name}</span>
            <StatusPill status={m.status} paused={!m.is_active} />
          </span>
        }
        subtitle={
          <a
            href={m.url}
            target="_blank"
            rel="noreferrer noopener"
            className="font-mono text-xs text-ink-subtle underline-offset-2 hover:text-ink hover:underline"
          >
            {m.method} {m.url}
          </a>
        }
        actions={
          canEdit ? (
            <>
              <Button onClick={() => runNow.mutate()} disabled={runNow.isPending}>
                {runNow.isPending ? 'Running…' : 'Run now'}
              </Button>
              <Button
                variant="secondary"
                onClick={() => toggleActive.mutate()}
                disabled={toggleActive.isPending}
              >
                {m.is_active ? 'Pause' : 'Resume'}
              </Button>
            </>
          ) : undefined
        }
      />

      <div className="grid gap-3 sm:grid-cols-4">
        <Stat label={`Uptime (${range})`} value={uptime.data ? `${uptime.data.uptime_pct}%` : '—'} />
        <Stat label={`p95 (${range})`} value={uptime.data ? `${uptime.data.p95_ms} ms` : '—'} />
        <Stat label="Interval" value={`every ${formatInterval(m.interval_s)}`} />
        <Stat
          label={m.consecutive_failures > 0 ? 'Consecutive failures' : 'Last check'}
          value={
            m.consecutive_failures > 0
              ? String(m.consecutive_failures)
              : m.last_checked_at
                ? relativeTime(m.last_checked_at)
                : 'never'
          }
        />
      </div>

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-ink">Response time</h2>
            <p className="mt-0.5 text-xs text-ink-subtle">
              Failed checks are marked in red and listed below.
            </p>
          </div>
          <div
            role="group"
            aria-label="Time range"
            className="inline-flex rounded-lg border border-line p-0.5"
          >
            {RANGES.map((option) => (
              <button
                key={option.value}
                type="button"
                aria-pressed={range === option.value}
                onClick={() => setRange(option.value)}
                className={`rounded-md px-3 py-1 text-xs font-medium transition ${
                  range === option.value
                    ? 'bg-ink text-surface'
                    : 'text-ink-muted hover:bg-surface-sunken hover:text-ink'
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
        <div className="mt-4">
          {checks.isPending ? (
            <div className="flex h-64 items-center justify-center">
              <Spinner label="Loading history…" />
            </div>
          ) : (
            <LatencyChart checks={rows} />
          )}
        </div>
      </Card>

      {monitorIncidents.length > 0 && (
        <section>
          <h2 className="mb-2 text-sm font-semibold text-ink">Incidents for this monitor</h2>
          <Card className="p-0">
            <ul className="divide-y divide-line">
              {monitorIncidents.slice(0, 5).map((incident) => (
                <li key={incident.id}>
                  <Link
                    to={`/orgs/${orgId}/incidents/${incident.id}`}
                    className="flex items-center gap-3 px-5 py-3 transition hover:bg-surface-sunken"
                  >
                    <span
                      className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${
                        incident.resolved_at
                          ? 'bg-up-soft text-up ring-up/30'
                          : 'bg-down-soft text-down ring-down/30'
                      }`}
                    >
                      {incident.resolved_at ? 'Resolved' : 'Open'}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-sm text-ink-muted">
                      {incident.cause ?? 'Check failed'}
                    </span>
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
          <h2 className="text-sm font-semibold text-ink">Check history</h2>
          {checks.isFetching && <span className="text-xs text-ink-subtle">refreshing…</span>}
        </div>

        <Card className="p-0">
          {checks.isPending ? (
            <SkeletonRows rows={4} />
          ) : rows.length === 0 ? (
            <div className="p-6">
              <EmptyState
                title="No checks recorded yet"
                description={
                  m.is_active
                    ? 'The worker will check this monitor on its next scheduled run.'
                    : 'This monitor is paused, so no checks are being made.'
                }
                action={
                  canEdit ? (
                    <Button onClick={() => runNow.mutate()} disabled={runNow.isPending}>
                      Run one now
                    </Button>
                  ) : undefined
                }
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-y border-line bg-surface-sunken text-xs uppercase tracking-wide text-ink-subtle">
                  <tr>
                    <th scope="col" className="px-5 py-2 font-medium">Result</th>
                    <th scope="col" className="px-5 py-2 font-medium">When</th>
                    <th scope="col" className="px-5 py-2 font-medium">Status</th>
                    <th scope="col" className="px-5 py-2 font-medium">Latency</th>
                    <th scope="col" className="px-5 py-2 font-medium">Detail</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {rows.slice(0, 50).map((check) => (
                    <tr key={check.id}>
                      <td className="px-5 py-2">
                        {/* Icon + word: never colour alone. */}
                        <span
                          className={`inline-flex items-center gap-1.5 font-medium ${
                            check.ok ? 'text-up' : 'text-down'
                          }`}
                        >
                          <span aria-hidden>{check.ok ? '✓' : '✕'}</span>
                          {check.ok ? 'Passed' : 'Failed'}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-5 py-2 text-ink-muted">
                        <span title={absoluteTime(check.checked_at)}>
                          {relativeTime(check.checked_at)}
                        </span>
                      </td>
                      <td className="px-5 py-2 font-mono text-xs text-ink-muted">
                        {check.status_code ?? '—'}
                      </td>
                      <td className="whitespace-nowrap px-5 py-2 text-ink-muted">
                        {formatLatency(check.latency_ms)}
                      </td>
                      <td
                        className="max-w-xs truncate px-5 py-2 text-ink-subtle"
                        title={check.error ?? ''}
                      >
                        {check.error ?? '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
        {rows.length > 50 && (
          <p className="mt-2 text-xs text-ink-subtle">
            Showing the 50 most recent of {rows.length} checks in this range.
          </p>
        )}
      </section>

      {canEdit && (
        <Card>
          <h2 className="text-sm font-semibold text-ink">Danger zone</h2>
          <p className="mt-1 text-sm text-ink-muted">
            Deleting a monitor also deletes its entire check history. This cannot be undone.
          </p>
          <Button
            variant="danger"
            className="mt-4"
            disabled={remove.isPending}
            onClick={() => {
              if (window.confirm(`Delete “${m.name}” and all of its check history?`)) {
                remove.mutate()
              }
            }}
          >
            {remove.isPending ? 'Deleting…' : 'Delete monitor'}
          </Button>
        </Card>
      )}
    </main>
  )
}
