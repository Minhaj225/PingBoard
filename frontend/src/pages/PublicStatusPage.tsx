import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { publicStatusQuery } from '@/api/statusPages'
import type { PublicState } from '@/api/types'
import { absoluteTime, relativeTime } from '@/components/format'
import { UptimeBar, UptimeLegend } from '@/components/UptimeBar'

/**
 * The anonymous status page.
 *
 * Rendered in its own layout with no navigation, no auth chrome and no call to
 * any authenticated endpoint — a visitor with no session must never be bounced
 * to a login screen.
 */

const BANNER: Record<PublicState, { bg: string; dot: string; text: string }> = {
  operational: { bg: 'bg-up-soft border-up/30', dot: 'bg-up', text: 'All systems operational' },
  degraded: { bg: 'bg-degraded-soft border-degraded/40', dot: 'bg-degraded', text: 'Degraded performance' },
  down: { bg: 'bg-down-soft border-down/30', dot: 'bg-down', text: 'Major outage' },
  unknown: { bg: 'bg-surface border-line', dot: 'bg-unknown', text: 'Status unknown' },
}

const MONITOR_STATE: Record<PublicState, { dot: string; label: string; text: string }> = {
  operational: { dot: 'bg-up', label: 'Operational', text: 'text-up' },
  degraded: { dot: 'bg-degraded', label: 'Degraded', text: 'text-amber-700' },
  down: { dot: 'bg-down', label: 'Down', text: 'text-down' },
  unknown: { dot: 'bg-unknown', label: 'Unknown', text: 'text-ink-muted' },
}

export function PublicStatusPage() {
  const { slug = '' } = useParams()
  const { data, isPending, isError } = useQuery(publicStatusQuery(slug))

  if (isPending) {
    return (
      <Shell>
        <p className="text-center text-sm text-ink-subtle">Loading status…</p>
      </Shell>
    )
  }

  if (isError || !data) {
    return (
      <Shell>
        <div className="rounded-xl border border-line bg-surface-raised p-10 text-center">
          <h1 className="text-lg font-semibold text-ink">Status page not found</h1>
          <p className="mt-1 text-sm text-ink-muted">
            This page may have been moved or taken offline.
          </p>
        </div>
      </Shell>
    )
  }

  const banner = BANNER[data.overall]

  return (
    <Shell>
      <header className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-ink">{data.title}</h1>
        {data.description && <p className="mt-1 text-sm text-ink-muted">{data.description}</p>}
      </header>

      <div className={`mb-6 flex items-center gap-3 rounded-xl border px-5 py-4 ${banner.bg}`}>
        <span className={`size-2.5 shrink-0 rounded-full ${banner.dot}`} aria-hidden />
        <p className="font-medium text-ink">{banner.text}</p>
      </div>

      <section className="rounded-xl border border-line bg-surface-raised">
        <h2 className="sr-only">Services</h2>
        <ul className="divide-y divide-line">
          {data.monitors.map((monitor) => {
            const state = MONITOR_STATE[monitor.status]
            return (
              <li key={monitor.name} className="px-5 py-5">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className={`size-2 shrink-0 rounded-full ${state.dot}`} aria-hidden />
                    <span className="font-medium text-ink">{monitor.name}</span>
                  </div>
                  <div className="flex items-baseline gap-3 text-sm">
                    <span className="text-ink-subtle">{monitor.uptime_90d}% uptime</span>
                    {/* Word + colour, so state never rests on colour alone. */}
                    <span className={`font-medium ${state.text}`}>{state.label}</span>
                  </div>
                </div>
                <div className="mt-3">
                  <UptimeBar days={monitor.days} />
                </div>
              </li>
            )
          })}
          {data.monitors.length === 0 && (
            <li className="px-5 py-8 text-center text-sm text-ink-subtle">
              No services are published on this page yet.
            </li>
          )}
        </ul>
      </section>

      <div className="mt-3">
        <UptimeLegend />
      </div>

      <section className="mt-8">
        <h2 className="text-sm font-semibold text-ink">Recent incidents</h2>
        {data.incidents.length === 0 ? (
          <p className="mt-2 rounded-xl border border-line bg-surface-raised px-5 py-6 text-center text-sm text-ink-subtle">
            No incidents in the last 30 days.
          </p>
        ) : (
          <ol className="mt-3 space-y-3">
            {data.incidents.map((incident) => (
              <li
                key={`${incident.monitor_name}-${incident.started_at}`}
                className="rounded-xl border border-line bg-surface-raised px-5 py-4"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-medium text-ink">{incident.monitor_name}</p>
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${
                      incident.resolved_at
                        ? 'bg-up-soft text-up ring-up/30'
                        : 'bg-down-soft text-down ring-down/30'
                    }`}
                  >
                    {incident.resolved_at ? 'Resolved' : 'Ongoing'}
                  </span>
                </div>
                <p className="mt-0.5 text-xs text-ink-subtle">
                  {absoluteTime(incident.started_at)}
                  {incident.resolved_at && ` — resolved ${relativeTime(incident.resolved_at)}`}
                </p>
                <ol className="mt-3 space-y-2 border-l border-line pl-4">
                  {incident.updates.map((update) => (
                    <li key={update.created_at}>
                      <p className="text-sm text-ink">{update.message}</p>
                      <p className="text-xs text-ink-subtle">{absoluteTime(update.created_at)}</p>
                    </li>
                  ))}
                </ol>
              </li>
            ))}
          </ol>
        )}
      </section>

      <footer className="mt-8 text-center text-xs text-ink-subtle">
        Updated {relativeTime(data.updated_at)} · powered by PingBoard
      </footer>
    </Shell>
  )
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-full bg-surface">
      <main className="mx-auto max-w-3xl px-6 py-12">{children}</main>
    </div>
  )
}
