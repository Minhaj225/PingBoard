import { type FormEvent, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { apiKeyKeys, apiKeysApi, apiKeysQuery } from '@/api/apiKeys'
import { errorMessage } from '@/api/client'
import { orgsQuery } from '@/api/orgs'
import { roleCovers } from '@/api/types'
import { absoluteTime, relativeTime } from '@/components/format'
import { useToast } from '@/features/toast/useToast'
import { Alert, Button, Card, Field, Input, Spinner } from '@/components/ui'

export function ApiKeysPage() {
  const { toast } = useToast()
  const { orgId = '' } = useParams()
  const queryClient = useQueryClient()

  const { data: orgs } = useQuery(orgsQuery)
  const org = orgs?.find((candidate) => candidate.id === orgId)
  const canCreate = org ? roleCovers(org.role, 'admin') : false
  const canRevoke = org ? roleCovers(org.role, 'owner') : false

  const keys = useQuery(apiKeysQuery(orgId))
  const [name, setName] = useState('')
  /** Held in component state only — never persisted, and gone on navigation. */
  const [revealed, setRevealed] = useState<{ name: string; secret: string } | null>(null)
  const [copied, setCopied] = useState(false)

  const refresh = () => queryClient.invalidateQueries({ queryKey: apiKeyKeys.list(orgId) })

  const create = useMutation({
    mutationFn: () => apiKeysApi.create(orgId, name),
    onSuccess: async (result) => {
      setRevealed({ name: result.key.name, secret: result.secret })
      setCopied(false)
      setName('')
      await refresh()
    },
  })

  const revoke = useMutation({
    mutationFn: (keyId: string) => apiKeysApi.revoke(orgId, keyId),
    onSuccess: async () => {
      toast('API key revoked', 'success')
      await refresh()
    },
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
        <h1 className="text-2xl font-semibold tracking-tight text-ink">API keys</h1>
        <p className="mt-1 text-sm text-ink-muted">
          For scripts and CI. A key acts as an admin of this organization and cannot reach any
          other.
        </p>
      </div>

      {revealed && (
        <Card className="border-degraded/40 bg-degraded-soft">
          <h2 className="text-sm font-semibold text-ink">
            Copy “{revealed.name}” now — it will not be shown again
          </h2>
          <p className="mt-1 text-sm text-ink-muted">
            Only a hash is stored on the server, so this value cannot be recovered. Create a
            replacement key if you lose it.
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <code className="min-w-0 flex-1 break-all rounded-lg border border-degraded/40 bg-surface-raised px-3 py-2 font-mono text-xs text-ink">
              {revealed.secret}
            </code>
            <Button
              variant="secondary"
              onClick={() => {
                void navigator.clipboard?.writeText(revealed.secret).then(() => setCopied(true))
              }}
            >
              {copied ? 'Copied' : 'Copy'}
            </Button>
            <Button variant="ghost" onClick={() => setRevealed(null)}>
              Dismiss
            </Button>
          </div>
          <p className="mt-3 text-xs text-ink-muted">
            Use it as an <code className="font-mono">X-API-Key</code> header, for example:
          </p>
          <pre className="mt-1 overflow-x-auto rounded-lg bg-ink px-3 py-2 font-mono text-[11px] text-slate-100">
{`curl -X POST "$API/monitors?org_id=${orgId}" \\
  -H "X-API-Key: <your key>" \\
  -H "Content-Type: application/json" \\
  -d '{"name":"From CI","url":"https://example.com"}'`}
          </pre>
        </Card>
      )}

      {keys.isPending && <Spinner label="Loading API keys…" />}
      {keys.isError && <Alert>{errorMessage(keys.error, 'Could not load API keys')}</Alert>}

      {keys.data?.length === 0 && (
        <Card className="text-center">
          <p className="text-sm text-ink-muted">No API keys yet.</p>
        </Card>
      )}

      {keys.data && keys.data.length > 0 && (
        <Card className="p-0">
          <ul className="divide-y divide-line">
            {keys.data.map((key) => {
              const active = key.revoked_at === null
              return (
                <li key={key.id} className="flex flex-wrap items-center gap-3 px-5 py-4">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <p className="truncate text-sm font-medium text-ink">{key.name}</p>
                      {!active && (
                        <span className="rounded-full bg-surface-sunken px-2 py-0.5 text-xs font-medium text-ink-muted">
                          Revoked
                        </span>
                      )}
                    </div>
                    <p className="mt-0.5 text-xs text-ink-subtle">
                      Created {relativeTime(key.created_at)} ·{' '}
                      {key.last_used_at ? (
                        <span title={absoluteTime(key.last_used_at)}>
                          last used {relativeTime(key.last_used_at)}
                        </span>
                      ) : (
                        'never used'
                      )}
                    </p>
                  </div>
                  {active && canRevoke && (
                    <Button
                      variant="ghost"
                      className="text-down hover:bg-down-soft"
                      disabled={revoke.isPending}
                      onClick={() => {
                        if (
                          window.confirm(
                            `Revoke “${key.name}”? Anything using it will stop working immediately.`,
                          )
                        ) {
                          revoke.mutate(key.id)
                        }
                      }}
                    >
                      Revoke
                    </Button>
                  )}
                </li>
              )
            })}
          </ul>
        </Card>
      )}

      {canCreate && (
        <Card>
          <h2 className="text-sm font-semibold text-ink">Create a key</h2>
          <form onSubmit={handleCreate} className="mt-4 flex flex-wrap items-end gap-3">
            {create.isError && (
              <div className="w-full">
                <Alert>{errorMessage(create.error, 'Could not create the key')}</Alert>
              </div>
            )}
            <div className="min-w-56 flex-1">
              <Field label="Name" hint="Something that says where it will be used.">
                <Input
                  required
                  maxLength={120}
                  placeholder="CI pipeline"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </Field>
            </div>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? 'Creating…' : 'Create key'}
            </Button>
          </form>
        </Card>
      )}
    </main>
  )
}
