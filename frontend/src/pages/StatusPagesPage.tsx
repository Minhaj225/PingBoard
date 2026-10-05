import { type FormEvent, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { errorMessage } from '@/api/client'
import { monitorsQuery } from '@/api/monitors'
import { orgsQuery } from '@/api/orgs'
import { statusPageKeys, statusPagesApi, statusPagesQuery } from '@/api/statusPages'
import { roleCovers } from '@/api/types'
import { useToast } from '@/features/toast/useToast'
import { Alert, Button, Card, Field, Input, Spinner } from '@/components/ui'

/** Mirrors the backend's SLUG_PATTERN. */
const SLUG_PATTERN = '[a-z0-9]+(-[a-z0-9]+)*'

export function StatusPagesPage() {
  const { toast } = useToast()
  const { orgId = '' } = useParams()
  const queryClient = useQueryClient()

  const { data: orgs } = useQuery(orgsQuery)
  const org = orgs?.find((candidate) => candidate.id === orgId)
  const canEdit = org ? roleCovers(org.role, 'admin') : false

  const pages = useQuery(statusPagesQuery(orgId))
  const monitors = useQuery(monitorsQuery(orgId))

  const [title, setTitle] = useState('')
  const [slug, setSlug] = useState('')
  const [description, setDescription] = useState('')
  const [selected, setSelected] = useState<string[]>([])

  const refresh = () => queryClient.invalidateQueries({ queryKey: statusPageKeys.list(orgId) })

  const create = useMutation({
    mutationFn: () =>
      statusPagesApi.create(orgId, {
        title,
        slug: slug.trim(),
        description: description.trim() || undefined,
        monitor_ids: selected,
      }),
    onSuccess: async () => {
      toast('Status page created', 'success')
      setTitle('')
      setSlug('')
      setDescription('')
      setSelected([])
      await refresh()
    },
  })

  const toggleMonitor = useMutation({
    mutationFn: ({ pageId, monitorIds }: { pageId: string; monitorIds: string[] }) =>
      statusPagesApi.update(orgId, pageId, { monitor_ids: monitorIds }),
    onSuccess: refresh,
  })

  const togglePublished = useMutation({
    mutationFn: ({ pageId, published }: { pageId: string; published: boolean }) =>
      statusPagesApi.update(orgId, pageId, { is_published: published }),
    onSuccess: refresh,
  })

  const remove = useMutation({
    mutationFn: (pageId: string) => statusPagesApi.remove(orgId, pageId),
    onSuccess: refresh,
  })

  function handleCreate(event: FormEvent) {
    event.preventDefault()
    create.mutate()
  }

  return (
    <main className="mx-auto max-w-3xl space-y-4 p-6">
      <Link to={`/orgs/${orgId}/monitors`} className="text-sm text-ink-muted hover:text-ink">
        ← Monitors
      </Link>

      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink">Status pages</h1>
        <p className="mt-1 text-sm text-ink-muted">
          A public page anyone can open without signing in. Only the services you pick appear on it.
        </p>
      </div>

      {pages.isPending && <Spinner label="Loading status pages…" />}
      {pages.isError && <Alert>{errorMessage(pages.error, 'Could not load status pages')}</Alert>}

      {pages.data?.length === 0 && (
        <Card className="text-center">
          <p className="text-sm text-ink-muted">No status pages yet.</p>
        </Card>
      )}

      {pages.data?.map((page) => {
        // `monitor_ids` has a server-side default, so OpenAPI marks it optional.
        const pageMonitorIds = page.monitor_ids ?? []
        const included = new Set(pageMonitorIds)
        return (
          <Card key={page.id}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <h2 className="truncate font-medium text-ink">{page.title}</h2>
                  {!page.is_published && (
                    <span className="rounded-full bg-surface-sunken px-2 py-0.5 text-xs font-medium text-ink-muted">
                      Unpublished
                    </span>
                  )}
                </div>
                <a
                  href={`/status/${page.slug}`}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="mt-0.5 block truncate font-mono text-xs text-ink-subtle underline-offset-2 hover:text-ink-muted hover:underline"
                >
                  {page.public_url}
                </a>
              </div>
              {canEdit && (
                <div className="flex shrink-0 gap-2">
                  <Button
                    variant="secondary"
                    disabled={togglePublished.isPending}
                    onClick={() =>
                      togglePublished.mutate({ pageId: page.id, published: !page.is_published })
                    }
                  >
                    {page.is_published ? 'Unpublish' : 'Publish'}
                  </Button>
                  <Button
                    variant="ghost"
                    className="text-down hover:bg-down-soft"
                    disabled={remove.isPending}
                    onClick={() => {
                      if (window.confirm(`Delete the status page “${page.title}”?`)) {
                        remove.mutate(page.id)
                      }
                    }}
                  >
                    Delete
                  </Button>
                </div>
              )}
            </div>

            {canEdit && monitors.data && monitors.data.length > 0 && (
              <fieldset className="mt-4">
                <legend className="text-xs font-medium text-ink-muted">Services shown</legend>
                <div className="mt-2 flex flex-wrap gap-2">
                  {monitors.data.map((monitor) => {
                    const on = included.has(monitor.id)
                    return (
                      <label
                        key={monitor.id}
                        className={`cursor-pointer rounded-lg border px-3 py-1.5 text-sm transition ${
                          on
                            ? 'border-ink bg-ink text-surface'
                            : 'border-line-strong bg-surface-raised text-ink hover:bg-surface'
                        }`}
                      >
                        <input
                          type="checkbox"
                          className="sr-only"
                          checked={on}
                          onChange={() => {
                            const next = on
                              ? pageMonitorIds.filter((id) => id !== monitor.id)
                              : [...pageMonitorIds, monitor.id]
                            toggleMonitor.mutate({ pageId: page.id, monitorIds: next })
                          }}
                        />
                        {monitor.name}
                      </label>
                    )
                  })}
                </div>
              </fieldset>
            )}
          </Card>
        )
      })}

      {canEdit && (
        <Card>
          <h2 className="text-sm font-semibold text-ink">New status page</h2>
          <form onSubmit={handleCreate} className="mt-4 space-y-4">
            {create.isError && (
              <Alert>{errorMessage(create.error, 'Could not create the status page')}</Alert>
            )}

            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Title">
                <Input
                  required
                  maxLength={160}
                  placeholder="Acme Status"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </Field>
              <Field label="Slug" hint="Appears in the public URL.">
                <Input
                  required
                  minLength={2}
                  maxLength={80}
                  pattern={SLUG_PATTERN}
                  placeholder="acme"
                  value={slug}
                  onChange={(e) => setSlug(e.target.value)}
                />
              </Field>
            </div>

            <Field label="Description" hint="Optional. Shown under the title.">
              <Input
                maxLength={500}
                placeholder="Live health of our public services."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </Field>

            {monitors.data && monitors.data.length > 0 && (
              <fieldset>
                <legend className="mb-2 text-sm font-medium text-ink">
                  Services to include
                </legend>
                <div className="flex flex-wrap gap-2">
                  {monitors.data.map((monitor) => {
                    const on = selected.includes(monitor.id)
                    return (
                      <label
                        key={monitor.id}
                        className={`cursor-pointer rounded-lg border px-3 py-1.5 text-sm transition ${
                          on
                            ? 'border-ink bg-ink text-surface'
                            : 'border-line-strong bg-surface-raised text-ink hover:bg-surface'
                        }`}
                      >
                        <input
                          type="checkbox"
                          className="sr-only"
                          checked={on}
                          onChange={() =>
                            setSelected((prev) =>
                              on ? prev.filter((id) => id !== monitor.id) : [...prev, monitor.id],
                            )
                          }
                        />
                        {monitor.name}
                      </label>
                    )
                  })}
                </div>
              </fieldset>
            )}

            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? 'Creating…' : 'Create status page'}
            </Button>
          </form>
        </Card>
      )}
    </main>
  )
}
