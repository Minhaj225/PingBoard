import { type FormEvent, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { errorMessage } from '@/api/client'
import { incidentKeys, incidentQuery, incidentsApi } from '@/api/incidents'
import { orgsQuery } from '@/api/orgs'
import { roleCovers } from '@/api/types'
import { absoluteTime, relativeTime } from '@/components/format'
import { useToast } from '@/features/toast/useToast'
import { Alert, Button, Card, Field, Input, Spinner } from '@/components/ui'

export function IncidentDetailPage() {
  const { toast } = useToast()
  const { orgId = '', incidentId = '' } = useParams()
  const queryClient = useQueryClient()
  const [message, setMessage] = useState('')

  const { data: orgs } = useQuery(orgsQuery)
  const org = orgs?.find((candidate) => candidate.id === orgId)
  const canEdit = org ? roleCovers(org.role, 'admin') : false

  const incident = useQuery(incidentQuery(orgId, incidentId))

  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: incidentKeys.detail(incidentId) })

  const postUpdate = useMutation({
    mutationFn: () => incidentsApi.postUpdate(orgId, incidentId, message),
    onSuccess: async () => {
      toast('Update posted', 'success')
      setMessage('')
      await refresh()
    },
  })

  const resolve = useMutation({
    mutationFn: () =>
      incidentsApi.resolve(orgId, incidentId, message.trim() || 'Resolved manually.'),
    onSuccess: async () => {
      toast('Incident resolved', 'success')
      setMessage('')
      await queryClient.invalidateQueries({ queryKey: incidentKeys.all })
    },
  })

  if (incident.isPending) {
    return (
      <main className="p-6">
        <Spinner label="Loading incident…" />
      </main>
    )
  }

  if (incident.isError || !incident.data) {
    return (
      <main className="mx-auto max-w-3xl p-6">
        <Alert>{errorMessage(incident.error, 'Could not load this incident')}</Alert>
      </main>
    )
  }

  const data = incident.data
  const open = data.resolved_at === null
  // `updates` has a server-side default, so OpenAPI marks it optional.
  const updates = data.updates ?? []

  function handlePost(event: FormEvent) {
    event.preventDefault()
    postUpdate.mutate()
  }

  return (
    <main className="mx-auto max-w-3xl space-y-4 p-6">
      <Link
        to={`/orgs/${orgId}/incidents`}
        className="text-sm text-ink-muted hover:text-ink"
      >
        ← Incidents
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h1 className="truncate text-2xl font-semibold tracking-tight text-ink">
              {data.monitor_name ?? 'Incident'}
            </h1>
            <span
              className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${
                open
                  ? 'bg-down-soft text-down ring-down/30'
                  : 'bg-up-soft text-up ring-up/30'
              }`}
            >
              {open ? 'Open' : 'Resolved'}
            </span>
          </div>
          <p className="mt-1 text-xs text-ink-subtle">
            Started {relativeTime(data.started_at)} · {absoluteTime(data.started_at)}
            {data.resolved_at && ` · resolved ${relativeTime(data.resolved_at)}`}
          </p>
        </div>
        <span className="shrink-0 rounded bg-surface-sunken px-2 py-0.5 text-xs font-medium text-ink-muted">
          {data.severity}
        </span>
      </div>

      {data.cause && (
        <Card>
          <h2 className="text-sm font-semibold text-ink">What failed</h2>
          <p className="mt-1 font-mono text-sm text-ink-muted">{data.cause}</p>
        </Card>
      )}

      <Card>
        <h2 className="text-sm font-semibold text-ink">Timeline</h2>
        <ol className="mt-4 space-y-4">
          {updates.map((update) => (
            <li key={update.id} className="flex gap-3">
              <div className="flex flex-col items-center">
                <span
                  className={`mt-1 size-2 shrink-0 rounded-full ${
                    update.is_auto ? 'bg-line-strong' : 'bg-ink'
                  }`}
                  aria-hidden
                />
                <span className="w-px flex-1 bg-surface-sunken" aria-hidden />
              </div>
              <div className="min-w-0 flex-1 pb-1">
                <p className="text-sm text-ink">{update.message}</p>
                <p className="mt-0.5 text-xs text-ink-subtle">
                  {update.is_auto ? 'Automatic' : 'Posted by a team member'} ·{' '}
                  <span title={absoluteTime(update.created_at)}>
                    {relativeTime(update.created_at)}
                  </span>
                </p>
              </div>
            </li>
          ))}
        </ol>
      </Card>

      {canEdit && (
        <Card>
          <h2 className="text-sm font-semibold text-ink">Post an update</h2>
          <p className="mt-1 text-sm text-ink-muted">
            Everyone on the configured notification channels will be told.
          </p>

          <form onSubmit={handlePost} className="mt-4 space-y-3">
            {postUpdate.isError && (
              <Alert>{errorMessage(postUpdate.error, 'Could not post the update')}</Alert>
            )}
            {resolve.isError && (
              <Alert>{errorMessage(resolve.error, 'Could not resolve the incident')}</Alert>
            )}

            <Field label="Message">
              <Input
                required
                maxLength={2000}
                placeholder="Investigating — the upstream gateway is flapping."
                value={message}
                onChange={(e) => setMessage(e.target.value)}
              />
            </Field>

            <div className="flex gap-2">
              <Button type="submit" disabled={postUpdate.isPending || !message.trim()}>
                {postUpdate.isPending ? 'Posting…' : 'Post update'}
              </Button>
              {open && (
                <Button
                  type="button"
                  variant="secondary"
                  disabled={resolve.isPending}
                  onClick={() => resolve.mutate()}
                >
                  {resolve.isPending ? 'Resolving…' : 'Resolve incident'}
                </Button>
              )}
            </div>
          </form>
        </Card>
      )}
    </main>
  )
}
