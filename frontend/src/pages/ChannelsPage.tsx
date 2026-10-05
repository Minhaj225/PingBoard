import { type FormEvent, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { channelKeys, channelsApi, channelsQuery } from '@/api/channels'
import { errorMessage } from '@/api/client'
import { orgsQuery } from '@/api/orgs'
import { type ChannelTestResult, type ChannelType, roleCovers } from '@/api/types'
import { useToast } from '@/features/toast/useToast'
import { Alert, Button, Card, Field, Input, Select, Spinner } from '@/components/ui'

interface TypeSpec {
  label: string
  /** The single config key this channel type stores. */
  field: string
  placeholder: string
}

// A Record rather than an array: every ChannelType is required to have a spec,
// and lookups are total, so there is no "possibly undefined" to handle.
const TYPES: Record<ChannelType, TypeSpec> = {
  slack: {
    label: 'Slack',
    field: 'webhook_url',
    placeholder: 'https://hooks.slack.com/services/…',
  },
  discord: {
    label: 'Discord',
    field: 'webhook_url',
    placeholder: 'https://discord.com/api/webhooks/…',
  },
  email: { label: 'Email', field: 'to', placeholder: 'oncall@example.com' },
}

const TYPE_ORDER: ChannelType[] = ['slack', 'discord', 'email']

export function ChannelsPage() {
  const { toast } = useToast()
  const { orgId = '' } = useParams()
  const queryClient = useQueryClient()

  const { data: orgs } = useQuery(orgsQuery)
  const org = orgs?.find((candidate) => candidate.id === orgId)
  const canEdit = org ? roleCovers(org.role, 'admin') : false

  const channels = useQuery(channelsQuery(orgId))

  const [name, setName] = useState('')
  const [type, setType] = useState<ChannelType>('slack')
  const [value, setValue] = useState('')
  const [testResults, setTestResults] = useState<Record<string, ChannelTestResult>>({})

  const spec = TYPES[type]

  const refresh = () => queryClient.invalidateQueries({ queryKey: channelKeys.list(orgId) })

  const create = useMutation({
    mutationFn: () =>
      channelsApi.create(orgId, { name, type, config: { [spec.field]: value.trim() } }),
    onSuccess: async () => {
      toast('Channel added', 'success')
      setName('')
      setValue('')
      await refresh()
    },
  })

  const test = useMutation({
    mutationFn: (channelId: string) => channelsApi.test(orgId, channelId),
    onSuccess: (result, channelId) => {
      setTestResults((prev) => ({ ...prev, [channelId]: result }))
      toast(
        result.delivered ? 'Test notification delivered' : 'Test delivery failed',
        result.delivered ? 'success' : 'error',
      )
    },
  })

  const remove = useMutation({
    mutationFn: (channelId: string) => channelsApi.remove(orgId, channelId),
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
        <h1 className="text-2xl font-semibold tracking-tight text-ink">
          Notification channels
        </h1>
        <p className="mt-1 text-sm text-ink-muted">
          Where PingBoard tells you about incidents on this organization's monitors.
        </p>
      </div>

      {channels.isPending && <Spinner label="Loading channels…" />}
      {channels.isError && <Alert>{errorMessage(channels.error, 'Could not load channels')}</Alert>}

      {channels.data?.length === 0 && (
        <Card className="text-center">
          <p className="text-sm text-ink-muted">No channels configured.</p>
          <p className="mt-1 text-sm text-ink-subtle">
            Without one, incidents still open — nobody just gets told about them.
          </p>
        </Card>
      )}

      {channels.data && channels.data.length > 0 && (
        <Card className="p-0">
          <ul className="divide-y divide-line">
            {channels.data.map((channel) => {
              const result = testResults[channel.id]
              return (
                <li key={channel.id} className="px-5 py-4">
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="shrink-0 rounded bg-surface-sunken px-2 py-0.5 text-xs font-medium text-ink-muted">
                      {channel.type}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-ink">{channel.name}</p>
                      {/* The server masks secrets; this is only ever a hint. */}
                      <p className="truncate font-mono text-xs text-ink-subtle">
                        {Object.values(channel.config).join(' ')}
                      </p>
                    </div>
                    {canEdit && (
                      <div className="flex shrink-0 gap-2">
                        <Button
                          variant="secondary"
                          disabled={test.isPending}
                          onClick={() => test.mutate(channel.id)}
                        >
                          Send test
                        </Button>
                        <Button
                          variant="ghost"
                          className="text-down hover:bg-down-soft"
                          disabled={remove.isPending}
                          onClick={() => {
                            if (window.confirm(`Delete the “${channel.name}” channel?`)) {
                              remove.mutate(channel.id)
                            }
                          }}
                        >
                          Delete
                        </Button>
                      </div>
                    )}
                  </div>

                  {result && (
                    <div className="mt-3">
                      <Alert kind={result.delivered ? 'success' : 'error'}>
                        {result.delivered
                          ? 'Test notification delivered.'
                          : `Delivery failed: ${result.detail ?? 'unknown error'}`}
                      </Alert>
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        </Card>
      )}

      {canEdit && (
        <Card>
          <h2 className="text-sm font-semibold text-ink">Add a channel</h2>
          <form onSubmit={handleCreate} className="mt-4 space-y-4">
            {create.isError && (
              <Alert>{errorMessage(create.error, 'Could not add the channel')}</Alert>
            )}

            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Name">
                <Input
                  required
                  maxLength={120}
                  placeholder="On-call Slack"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </Field>
              <Field label="Type">
                <Select
                  value={type}
                  onChange={(e) => {
                    setType(e.target.value as ChannelType)
                    setValue('')
                  }}
                >
                  {TYPE_ORDER.map((option) => (
                    <option key={option} value={option}>
                      {TYPES[option].label}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>

            <Field
              label={type === 'email' ? 'Recipient' : 'Webhook URL'}
              hint={
                type === 'email'
                  ? 'In development, email is written to the API log instead of sent.'
                  : 'Treated as a secret — it is masked everywhere after you save it.'
              }
            >
              <Input
                required
                type={type === 'email' ? 'email' : 'url'}
                placeholder={spec.placeholder}
                value={value}
                onChange={(e) => setValue(e.target.value)}
              />
            </Field>

            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? 'Adding…' : 'Add channel'}
            </Button>
          </form>
        </Card>
      )}
    </main>
  )
}
